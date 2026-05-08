import pymongo

SORT_SPECS: dict[str, list[tuple[str, int]]] = {
    "newest": [("posted_at", pymongo.DESCENDING)],
    "cheap": [("price", pymongo.ASCENDING)],
    "expensive": [("price", pymongo.DESCENDING)],
    "mileage_asc": [("mileage", pymongo.ASCENDING)],
    "year_desc": [("year", pymongo.DESCENDING)],
    "year_asc": [("year", pymongo.ASCENDING)],
    "best_deal": [
        ("price_rating_rank", pymongo.ASCENDING),
        ("posted_at", pymongo.DESCENDING),
    ],
    "bargain": [
        ("bargain", pymongo.DESCENDING),
        ("posted_at", pymongo.DESCENDING),
    ],
}

DEFAULT_SORT = "newest"


def resolve_sort(key: str | None) -> list[tuple[str, int]]:
    return SORT_SPECS.get(key or DEFAULT_SORT, SORT_SPECS[DEFAULT_SORT])
