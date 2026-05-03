from datetime import datetime

from pydantic import ConfigDict, Field
from pydantic.alias_generators import to_camel

from models.saved_search import SavedSearch, SavedSearchFilters

from .common import CamelModel
from .listing import ListingOut


class SavedSearchIn(CamelModel):
    name: str
    filters: SavedSearchFilters
    notify: bool = True


class SavedSearchUpdate(CamelModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")

    name: str | None = None
    filters: SavedSearchFilters | None = None
    notify: bool | None = None


class SavedSearchOut(CamelModel):
    id: str
    name: str
    crit: str
    filters: SavedSearchFilters
    notify: bool = True
    total: int = 0
    fresh: int = 0
    last_match_at: datetime | None = None

    @classmethod
    def from_doc(cls, doc: SavedSearch, crit: str) -> "SavedSearchOut":
        return cls(
            id=str(doc.id),
            name=doc.name,
            crit=crit,
            filters=doc.filters,
            notify=doc.notify,
            total=doc.total_count,
            fresh=doc.fresh_count,
            last_match_at=doc.last_match_at,
        )


class SavedSearchRunOut(CamelModel):
    items: list[ListingOut] = Field(default_factory=list)
    total: int
    fresh_count: int
