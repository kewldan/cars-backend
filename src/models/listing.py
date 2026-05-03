from datetime import datetime
from typing import Literal

import pymongo
from beanie import Document
from pydantic import BaseModel

PriceRating = Literal["great", "good", "fair", "high", "overpriced"]
Currency = Literal["USD"]

PRICE_RATING_RANK: dict[PriceRating, int] = {
    "great": 0,
    "good": 1,
    "fair": 2,
    "high": 3,
    "overpriced": 4,
}


class TgChannelEmbed(BaseModel):
    id: str
    name: str
    subs: int


class Listing(Document):
    id_code: str
    url: str
    make: str
    model: str
    year: int
    fuel: str
    engine: float
    power: int
    mileage: int
    transmission: str
    drive: str
    body: str
    color: str
    city: str

    price: int
    currency: Currency = "USD"
    price_rating: PriceRating
    price_rating_rank: int = 2
    fair_price: int

    vin: str = ""
    vin_checked: bool = False
    customs_cleared: bool = False
    sold: bool = False
    has_photos: bool = True
    photos: list[str] = []

    channel: TgChannelEmbed
    posted_at: datetime

    summary: str = ""
    features: list[str] = []
    seller: str = ""
    description: str = ""
    bargain: bool = False

    location: dict | None = None

    class Settings:
        indexes = [
            "id_code",
            "make",
            "model",
            "year",
            "fuel",
            "power",
            "mileage",
            "transmission",
            "drive",
            "body",
            "city",
            "price",
            [("posted_at", pymongo.DESCENDING)],
            [("year", pymongo.DESCENDING)],
            [("price_rating_rank", pymongo.ASCENDING), ("posted_at", pymongo.DESCENDING)],
            [("make", pymongo.ASCENDING), ("model", pymongo.ASCENDING)],
            [("location", pymongo.GEOSPHERE)],
            pymongo.IndexModel(
                [
                    ("make", pymongo.TEXT),
                    ("model", pymongo.TEXT),
                    ("city", pymongo.TEXT),
                    ("id_code", pymongo.TEXT),
                ],
                weights={"make": 5, "model": 5, "id_code": 10, "city": 1},
                default_language="none",
                name="listing_text_idx",
            ),
            pymongo.IndexModel([("id_code", pymongo.ASCENDING)], unique=True, name="id_code_unique"),
        ]
