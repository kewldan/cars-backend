from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from models.listing import Currency, Listing, PriceRating

from .common import CamelModel


class TgChannelOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    name: str
    subs: int


class ListingOut(CamelModel):
    id: str
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
    fair_price: int
    vin: str = ""
    vin_checked: bool
    customs_cleared: bool
    sold: bool = False
    has_photos: bool
    photos: list[str]
    channel: TgChannelOut
    posted_days: int
    posted_hours: int
    summary: str = ""
    features: list[str] = []
    seller: str = ""
    description: str = ""
    bargain: bool = False

    @classmethod
    def from_doc(cls, doc: Listing, *, now: datetime | None = None) -> "ListingOut":
        n = now or datetime.now(timezone.utc)
        posted = doc.posted_at
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
        delta = n - posted
        days = delta.days
        hours = (delta.seconds // 3600)
        return cls(
            id=doc.id_code,
            make=doc.make,
            model=doc.model,
            year=doc.year,
            fuel=doc.fuel,
            engine=doc.engine,
            power=doc.power,
            mileage=doc.mileage,
            transmission=doc.transmission,
            drive=doc.drive,
            body=doc.body,
            color=doc.color,
            city=doc.city,
            price=doc.price,
            currency=doc.currency,
            price_rating=doc.price_rating,
            fair_price=doc.fair_price,
            vin=doc.vin,
            vin_checked=doc.vin_checked,
            sold=doc.sold,
            customs_cleared=doc.customs_cleared,
            has_photos=doc.has_photos,
            photos=doc.photos,
            channel=TgChannelOut(id=doc.channel.id, name=doc.channel.name, subs=doc.channel.subs),
            posted_days=days,
            posted_hours=hours,
            summary=doc.summary,
            features=doc.features,
            seller=doc.seller,
            description=doc.description,
            bargain=doc.bargain,
        )


class ListingPage(CamelModel):
    items: list[ListingOut]
    total: int
    page: int
    page_size: int


SortKey = Literal[
    "newest",
    "best_deal",
    "cheap",
    "expensive",
    "mileage_asc",
    "year_desc",
    "year_asc",
]


class ListingFilters(BaseModel):
    """Query filter container; all fields optional."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    q: str | None = None
    price_from: int | None = None
    price_to: int | None = None
    year_from: int | None = None
    year_to: int | None = None
    mileage_from: int | None = None
    mileage_to: int | None = None
    engine_from: float | None = None
    engine_to: float | None = None
    power_from: int | None = None
    power_to: int | None = None
    makes: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)
    fuels: list[str] = Field(default_factory=list)
    trans: list[str] = Field(default_factory=list)
    drives: list[str] = Field(default_factory=list)
    bodies: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    colors: list[str] = Field(default_factory=list)
    channel: str | None = None
    vin_only: bool = False
    price_only: bool = False
