from fastapi import APIRouter, HTTPException, Query, Response, status

from models.listing import Listing
from schemas.listing import ListingOut

router = APIRouter()

# Approximate center coordinates for Georgian cities; for ingest pipelines that
# don't supply per-listing geo, this is the user-facing pin location.
CITY_COORDS: dict[str, tuple[float, float]] = {
    "Tbilisi": (41.7151, 44.8271),
    "Batumi": (41.6168, 41.6367),
    "Kutaisi": (42.2679, 42.7180),
    "Rustavi": (41.5495, 44.9930),
    "Gori": (41.9847, 44.1086),
    "Zugdidi": (42.5088, 41.8709),
    "Poti": (42.1500, 41.6712),
    "Telavi": (41.9192, 45.4731),
}

CACHE_HEADER = "public, max-age=30, stale-while-revalidate=120"


@router.get("/cities")
async def cities(response: Response) -> dict:
    pipeline = [{"$group": {"_id": "$city", "count": {"$sum": 1}}}]
    rows = await Listing.aggregate(pipeline).to_list()
    cities_out = []
    total = 0
    for row in rows:
        name = row.get("_id")
        if not name:
            continue
        count = int(row.get("count") or 0)
        total += count
        coords = CITY_COORDS.get(name)
        if not coords:
            continue
        cities_out.append(
            {"name": name, "count": count, "lat": coords[0], "lng": coords[1]}
        )
    cities_out.sort(key=lambda c: -c["count"])
    response.headers["Cache-Control"] = CACHE_HEADER
    return {"cities": cities_out, "total": total}


@router.get("/cities/{name}/listings")
async def city_listings(
    name: str,
    response: Response,
    limit: int = Query(6, ge=1, le=50),
) -> dict:
    if name not in CITY_COORDS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown city")
    docs = (
        await Listing.find(Listing.city == name, sort=[("posted_at", -1)])
        .limit(limit)
        .to_list()
    )
    response.headers["Cache-Control"] = CACHE_HEADER
    return {
        "items": [ListingOut.from_doc(d).model_dump(by_alias=True) for d in docs],
    }
