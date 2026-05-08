from datetime import datetime
from typing import Annotated

from beanie import Document, Indexed
from pydantic import BaseModel, Field


class SavedSearchFilters(BaseModel):
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
    makes: list[str] = []
    models: list[str] = []
    fuels: list[str] = []
    trans: list[str] = []
    drives: list[str] = []
    bodies: list[str] = []
    cities: list[str] = []
    colors: list[str] = []
    channel: str | None = None
    vin_only: bool = False
    price_only: bool = False
    bargain: bool = False
    customs_cleared: bool = False


class SavedSearch(Document):
    user_id: Annotated[str, Indexed()]
    name: str
    filters: SavedSearchFilters
    search: str = ""
    sort: str | None = None
    notify: bool = True
    last_match_at: datetime | None = None
    fresh_count: int = 0
    total_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
