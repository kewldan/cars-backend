from datetime import datetime

import pymongo
from beanie import Document
from pydantic import Field


class Favorite(Document):
    user_id: str
    listing_id: str
    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        indexes = [
            pymongo.IndexModel(
                [("user_id", pymongo.ASCENDING), ("listing_id", pymongo.ASCENDING)],
                unique=True,
            ),
        ]
