import logging
from datetime import datetime, timezone

from pyrogram import Client
from pyrogram.types import Message

import db
from models.channel import TgChannel
from models.listing import Listing, TgChannelEmbed
from services.pricing import rate
from tg import make_client

from .parsers import ParsedCar, Parser

log = logging.getLogger(__name__)


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


def _build_listing(msg: Message, car: ParsedCar, channel: TgChannelEmbed) -> Listing:
    posted_at = msg.date or datetime.now(timezone.utc)
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)

    fair_price = car.price
    rating, rank = rate(car.price, fair_price)

    photos: list[str] = []
    if msg.photo:
        photos.append(msg.photo.file_id)

    return Listing(
        id_code=f"tg-{channel.id}-{msg.id}",
        url=f"https://t.me/c/{channel.id}/{msg.id}",
        make=car.make or "Unknown",
        model=car.model or "Unknown",
        year=car.year or 0,
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
        has_photos=bool(photos),
        photos=photos,
        channel=channel,
        posted_at=posted_at,
        summary=car.summary,
        description=car.description,
        features=car.features,
    )


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

        n = 0
        for msg in posts:
            text = msg.text or msg.caption or ""
            try:
                car = await parser.parse(text)
            except Exception:
                log.exception("parse failed for post %s", msg.id)
                continue
            if car is None:
                log.info("post %s: not a listing, skipped", msg.id)
                continue

            listing = _build_listing(msg, car, channel)
            if dry_run:
                log.info(
                    "DRY-RUN %s: %s %s %s @ $%d (%s)",
                    listing.id_code, listing.make, listing.model, listing.year,
                    listing.price, listing.city,
                )
                n += 1
                continue

            if await Listing.find_one(Listing.id_code == listing.id_code):
                log.info("post %s already in DB, skipped", listing.id_code)
                continue
            await listing.insert()
            log.info(
                "inserted %s: %s %s %s @ $%d",
                listing.id_code, listing.make, listing.model, listing.year, listing.price,
            )
            n += 1
        return n
