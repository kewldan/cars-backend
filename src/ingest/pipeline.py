import logging
import re
from datetime import datetime, timezone

from pyrogram import Client
from pyrogram.types import Message

import db
from models.channel import TgChannel
from models.listing import Listing, TgChannelEmbed
from models.processed_post import ProcessedPost
from services.pricing import rate
from tg import make_client

from .parsers import ParsedCar, Parser
from .photos import download_post_photos

log = logging.getLogger(__name__)

VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")


def _peer(bare_id: int) -> int:
    """Channel IDs without the -100 prefix → the chat_id pyrogram expects."""
    return int(f"-100{bare_id}")


async def _fetch_posts(client: Client, bare_id: int, limit: int) -> list[Message]:
    posts: list[Message] = []
    async for msg in client.get_chat_history(_peer(bare_id), limit=limit):
        if msg.text or msg.caption:
            posts.append(msg)
    return posts


async def _ensure_channel(client: Client, bare_id: int) -> TgChannelEmbed:
    chat = await client.get_chat(_peer(bare_id))
    title = getattr(chat, "title", None) or str(bare_id)
    subs = getattr(chat, "members_count", 0) or 0

    existing = await TgChannel.find_one(TgChannel.channel_id == bare_id)
    if existing:
        if existing.name != title or existing.subs != subs:
            existing.name = title
            existing.subs = subs
            await existing.save()
    else:
        await TgChannel(channel_id=bare_id, name=title, subs=subs).insert()

    return TgChannelEmbed(id=str(bare_id), name=title, subs=subs)


async def _build_listing(
    msg: Message,
    car: ParsedCar,
    channel: TgChannelEmbed,
    client: Client,
) -> Listing:
    posted_at = msg.date or datetime.now(timezone.utc)
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)

    fair_price = car.price
    rating, rank = rate(car.price, fair_price)

    id_code = f"tg-{channel.id}-{msg.id}"
    photos = await download_post_photos(client, msg, id_code)

    vin = (car.vin or "").upper().strip()
    vin_checked = bool(VIN_RE.match(vin))
    if vin and not vin_checked:
        log.warning("listing %s: invalid VIN %r — discarded", id_code, vin)
        vin = ""

    return Listing(
        id_code=id_code,
        url=f"https://t.me/c/{channel.id}/{msg.id}",
        make=car.make or "Unknown",
        model=car.model or "Unknown",
        year=car.year or 0,
        vin=vin,
        vin_checked=vin_checked,
        fuel=car.fuel,
        engine=car.engine,
        power=car.power,
        mileage=car.mileage,
        transmission=car.transmission,
        drive=car.drive,
        body=car.body,
        color=car.color,
        city=car.city or "Тбилиси",
        price=car.price,
        currency="USD",
        price_rating=rating,
        price_rating_rank=rank,
        fair_price=fair_price,
        sold=car.sold,
        has_photos=bool(photos),
        photos=photos,
        channel=channel,
        posted_at=posted_at,
        summary=car.summary,
        description=car.description,
        features=car.features,
    )


def _apply_update(listing: Listing, car: ParsedCar) -> None:
    """Merge a re-parsed result onto an existing listing (for reply updates).
    Only overwrites fields the LLM populated; preserves photos, posted_at, channel."""
    if car.price:
        listing.price = car.price
        fair = car.price
        rating, rank = rate(car.price, fair)
        listing.price_rating = rating
        listing.price_rating_rank = rank
        listing.fair_price = fair
    listing.sold = bool(car.sold or listing.sold)
    if car.mileage:
        listing.mileage = car.mileage
    if car.summary:
        listing.summary = car.summary
    if car.description:
        listing.description = car.description
    if car.features:
        listing.features = car.features


async def _record_processed(channel_id: int, message_id: int, reason: str) -> None:
    try:
        await ProcessedPost(
            channel_id=channel_id, message_id=message_id, reason=reason,
        ).insert()
    except Exception:
        log.debug("processed_post upsert collision for %s/%s", channel_id, message_id)


async def ingest_channel(
    parser: Parser,
    channel_id: int,
    limit: int = 100,
    dry_run: bool = False,
) -> int:
    await db.connect()
    async with make_client() as client:
        channel = await _ensure_channel(client, channel_id)
        posts = await _fetch_posts(client, channel_id, limit)
        log.info("fetched %d post(s) from %s", len(posts), channel.name)

        skip_msg_ids: set[int] = {
            p.message_id
            for p in await ProcessedPost.find(ProcessedPost.channel_id == channel_id).to_list()
        }
        log.info("processed-post cache: %d entries for channel %s", len(skip_msg_ids), channel_id)

        seen_groups: set[str] = set()
        n = 0
        for msg in posts:
            if msg.id in skip_msg_ids:
                log.info("post %s previously processed, skipped", msg.id)
                continue
            if msg.media_group_id:
                key = str(msg.media_group_id)
                if key in seen_groups:
                    continue
                seen_groups.add(key)

            reply = getattr(msg, "reply_to_message", None)
            reply_text = ""
            if reply is not None:
                reply_text = (getattr(reply, "text", None) or getattr(reply, "caption", None) or "")
            is_update = bool(reply is not None and reply_text)

            if is_update:
                target_msg = reply
                text_for_llm = (
                    "=== ORIGINAL POST ===\n"
                    f"{reply_text}\n\n"
                    "=== UPDATE (newer reply) ===\n"
                    f"{msg.text or msg.caption or ''}"
                )
            else:
                target_msg = msg
                text_for_llm = msg.text or msg.caption or ""

            target_id_code = f"tg-{channel.id}-{target_msg.id}"
            existing = await Listing.find_one(Listing.id_code == target_id_code)
            if existing and not is_update:
                log.info("post %s already in DB, skipped", target_id_code)
                skip_msg_ids.add(msg.id)
                continue

            try:
                car = await parser.parse(text_for_llm)
            except Exception:
                log.exception("parse failed for post %s", msg.id)
                continue

            if car is None:
                log.info("post %s: not a listing, marked & skipped", msg.id)
                if not dry_run:
                    await _record_processed(channel_id, msg.id, "not_listing")
                skip_msg_ids.add(msg.id)
                continue

            if existing:
                if dry_run:
                    log.info(
                        "DRY-RUN UPDATE %s: $%d → $%d, sold=%s",
                        existing.id_code, existing.price, car.price, car.sold,
                    )
                else:
                    _apply_update(existing, car)
                    await existing.save()
                    log.info(
                        "updated %s via reply %s: $%d sold=%s",
                        existing.id_code, msg.id, existing.price, existing.sold,
                    )
                    await _record_processed(
                        channel_id, msg.id, f"reply_update_for:{existing.id_code}",
                    )
                skip_msg_ids.add(msg.id)
                n += 1
                continue

            listing = await _build_listing(target_msg, car, channel, client)
            if dry_run:
                log.info(
                    "DRY-RUN %s: %s %s %s @ $%d (%s) sold=%s — %d photo(s)",
                    listing.id_code, listing.make, listing.model, listing.year,
                    listing.price, listing.city, listing.sold, len(listing.photos),
                )
                n += 1
                continue

            await listing.insert()
            log.info(
                "inserted %s: %s %s %s @ $%d sold=%s — %d photo(s)",
                listing.id_code, listing.make, listing.model, listing.year,
                listing.price, listing.sold, len(listing.photos),
            )
            if is_update:
                await _record_processed(
                    channel_id, msg.id, f"reply_update_for:{listing.id_code}",
                )
                skip_msg_ids.add(msg.id)
            n += 1
        return n
