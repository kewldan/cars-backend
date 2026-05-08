import logging
from pathlib import Path

from PIL import Image
from pyrogram import Client
from pyrogram.types import Message

log = logging.getLogger(__name__)

IMAGES_DIR = Path("data/images")
WEBP_QUALITY = 82


async def download_post_photos(
    client: Client, msg: Message, listing_id: str
) -> list[str]:
    """Download photos from a Telegram post (or its media group) as webp files
    under data/images/{listing_id}/. Returns the list of /images/... URL paths
    suitable for storing in Listing.photos."""
    sources: list[Message] = []
    if msg.media_group_id:
        try:
            group = await client.get_media_group(msg.chat.id, msg.id)
            sources = [m for m in group if m.photo]
        except Exception:
            log.exception("media group fetch failed for post %s", msg.id)
    if not sources and msg.photo:
        sources = [msg]
    if not sources:
        return []

    out_dir = IMAGES_DIR / listing_id
    out_dir.mkdir(parents=True, exist_ok=True)

    urls: list[str] = []
    for i, source in enumerate(sources):
        out_path = out_dir / f"{i}.webp"
        url = f"/api/images/{listing_id}/{i}.webp"
        if out_path.exists():
            urls.append(url)
            continue
        try:
            buf = await client.download_media(source, in_memory=True)
            if buf is None:
                continue
            buf.seek(0)
            img = Image.open(buf)
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            img.save(out_path, "WEBP", quality=WEBP_QUALITY, method=6)
            urls.append(url)
        except Exception:
            log.exception("photo %d download/convert failed for %s", i, listing_id)
    return urls
