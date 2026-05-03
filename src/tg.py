from pathlib import Path

from pyrogram import Client

from settings import settings


def make_client() -> Client:
    workdir = Path(settings.TG_SESSION_DIR)
    workdir.mkdir(parents=True, exist_ok=True)
    return Client(
        name=settings.TG_SESSION_NAME,
        api_id=settings.TG_API_ID,
        api_hash=settings.TG_API_HASH,
        workdir=str(workdir),
    )
