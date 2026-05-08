import time

from fastapi import APIRouter, Response

from models.channel import TgChannel
from models.listing import Listing
from schemas.facets import FacetsOut, FacetsRange, FacetsRanges
from schemas.listing import TgChannelOut

router = APIRouter()

_TTL_SECONDS = 300
_cache: dict[str, tuple[float, FacetsOut]] = {}


async def _load_facets() -> FacetsOut:
    pipeline = [
        {
            "$facet": {
                "makes": [{"$group": {"_id": {"make": "$make", "model": "$model"}}}],
                "fuels": [{"$group": {"_id": "$fuel"}}],
                "transmissions": [{"$group": {"_id": "$transmission"}}],
                "drives": [{"$group": {"_id": "$drive"}}],
                "bodies": [{"$group": {"_id": "$body"}}],
                "cities": [{"$group": {"_id": "$city"}}],
                "colors": [{"$group": {"_id": "$color"}}],
                "ranges": [
                    {
                        "$group": {
                            "_id": None,
                            "price_min": {"$min": "$price"},
                            "price_max": {"$max": "$price"},
                            "year_min": {"$min": "$year"},
                            "year_max": {"$max": "$year"},
                            "mileage_min": {"$min": "$mileage"},
                            "mileage_max": {"$max": "$mileage"},
                            "engine_min": {"$min": "$engine"},
                            "engine_max": {"$max": "$engine"},
                            "power_min": {"$min": "$power"},
                            "power_max": {"$max": "$power"},
                        }
                    }
                ],
            }
        }
    ]

    raw_list = await Listing.aggregate(pipeline).to_list()
    raw = raw_list[0] if raw_list else {}

    makes_map: dict[str, list[str]] = {}
    for entry in raw.get("makes", []):
        d = entry.get("_id") or {}
        mk = d.get("make")
        md = d.get("model")
        if not mk:
            continue
        bucket = makes_map.setdefault(mk, [])
        if md and md not in bucket:
            bucket.append(md)
    for mk in makes_map:
        makes_map[mk].sort()

    def _scalars(key: str) -> list[str]:
        vals = [e["_id"] for e in raw.get(key, []) if e.get("_id")]
        return sorted({str(v) for v in vals})

    r = (raw.get("ranges") or [{}])[0]
    ranges = FacetsRanges(
        price=FacetsRange(min=r.get("price_min") or 0, max=r.get("price_max") or 0),
        year=FacetsRange(min=r.get("year_min") or 0, max=r.get("year_max") or 0),
        mileage=FacetsRange(
            min=r.get("mileage_min") or 0, max=r.get("mileage_max") or 0
        ),
        engine=FacetsRange(
            min=r.get("engine_min") or 0.0, max=r.get("engine_max") or 0.0
        ),
        power=FacetsRange(min=r.get("power_min") or 0, max=r.get("power_max") or 0),
    )

    channels_docs = await TgChannel.find_all().to_list()
    channels = [
        TgChannelOut(id=str(c.channel_id), name=c.name, subs=c.subs)
        for c in channels_docs
    ]
    channels.sort(key=lambda c: c.name.lower())

    return FacetsOut(
        makes=dict(sorted(makes_map.items())),
        fuels=_scalars("fuels"),
        transmissions=_scalars("transmissions"),
        drives=_scalars("drives"),
        bodies=_scalars("bodies"),
        cities=_scalars("cities"),
        colors=_scalars("colors"),
        channels=channels,
        ranges=ranges,
    )


@router.get("", response_model=FacetsOut, response_model_by_alias=True)
async def get_facets(response: Response) -> FacetsOut:
    now = time.monotonic()
    cached = _cache.get("v1")
    if cached and now - cached[0] < _TTL_SECONDS:
        result = cached[1]
    else:
        result = await _load_facets()
        _cache["v1"] = (now, result)
    response.headers["Cache-Control"] = (
        "public, max-age=300, stale-while-revalidate=600"
    )
    return result
