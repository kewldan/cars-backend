from typing import Any

from models.saved_search import SavedSearchFilters
from schemas.listing import ListingFilters


def _range(low: int | float | None, high: int | float | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if low is not None:
        out["$gte"] = low
    if high is not None:
        out["$lte"] = high
    return out


def build_query(f: ListingFilters | SavedSearchFilters) -> dict[str, Any]:
    where: dict[str, Any] = {}

    q = getattr(f, "q", None)
    if q:
        where["$text"] = {"$search": q}

    price = _range(f.price_from, f.price_to)
    if price:
        where["price"] = price
    year = _range(f.year_from, f.year_to)
    if year:
        where["year"] = year
    mileage = _range(f.mileage_from, f.mileage_to)
    if mileage:
        where["mileage"] = mileage
    engine = _range(f.engine_from, f.engine_to)
    if engine:
        where["engine"] = engine
    power = _range(f.power_from, f.power_to)
    if power:
        where["power"] = power

    multi = [
        ("make", f.makes),
        ("model", f.models),
        ("fuel", f.fuels),
        ("transmission", f.trans),
        ("drive", f.drives),
        ("body", f.bodies),
        ("city", f.cities),
        ("color", f.colors),
    ]
    for field, vals in multi:
        if vals:
            where[field] = {"$in": list(vals)}

    if f.channel:
        where["channel.id"] = f.channel
    if f.vin_only:
        where["vin_checked"] = True
    if f.price_only:
        existing = where.get("price")
        if isinstance(existing, dict):
            existing["$gt"] = max(existing.get("$gt", 0), 0)
        else:
            where["price"] = {"$gt": 0}
    if getattr(f, "bargain", False):
        where["bargain"] = True
    if getattr(f, "customs_cleared", False):
        where["customs_cleared"] = True

    return where


def filters_to_saved(f: ListingFilters) -> SavedSearchFilters:
    """Translate request filters into the persistable saved-search shape (drops free-text q)."""
    return SavedSearchFilters(
        price_from=f.price_from,
        price_to=f.price_to,
        year_from=f.year_from,
        year_to=f.year_to,
        mileage_from=f.mileage_from,
        mileage_to=f.mileage_to,
        engine_from=f.engine_from,
        engine_to=f.engine_to,
        power_from=f.power_from,
        power_to=f.power_to,
        makes=list(f.makes),
        models=list(f.models),
        fuels=list(f.fuels),
        trans=list(f.trans),
        drives=list(f.drives),
        bodies=list(f.bodies),
        cities=list(f.cities),
        colors=list(f.colors),
        channel=f.channel,
        vin_only=f.vin_only,
        price_only=f.price_only,
        bargain=f.bargain,
        customs_cleared=f.customs_cleared,
    )


def describe_filters(f: SavedSearchFilters) -> str:
    parts: list[str] = []
    if f.makes:
        parts.append(" ".join(f.makes))
    if f.models:
        parts.append(" ".join(f.models))
    if f.year_from and f.year_to:
        parts.append(f"{f.year_from}–{f.year_to}")
    elif f.year_from:
        parts.append(f"{f.year_from}+")
    elif f.year_to:
        parts.append(f"до {f.year_to}")
    if f.price_to and f.price_from:
        parts.append(f"{f.price_from:,}–{f.price_to:,}$".replace(",", " "))
    elif f.price_to:
        parts.append(f"до {f.price_to:,}$".replace(",", " "))
    elif f.price_from:
        parts.append(f"от {f.price_from:,}$".replace(",", " "))
    if f.cities:
        parts.append(", ".join(f.cities))
    if f.bodies:
        parts.append(", ".join(f.bodies))
    if f.fuels:
        parts.append(", ".join(f.fuels))
    if f.vin_only:
        parts.append("VIN ✓")
    return " · ".join(parts) if parts else "Все объявления"
