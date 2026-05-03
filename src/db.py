from beanie import init_beanie
from pymongo import AsyncMongoClient

from settings import settings
from models import Listing, TgChannel, SavedSearch, Favorite, User

client: AsyncMongoClient = AsyncMongoClient(settings.MONGO_URL)
database = client[settings.MONGO_DB]


async def connect() -> None:
    await init_beanie(
        database=database,
        document_models=[Listing, TgChannel, SavedSearch, Favorite, User],
    )


async def ping() -> bool:
    try:
        await database.command("ping")
        return True
    except Exception:
        return False


async def close() -> None:
    await client.close()
