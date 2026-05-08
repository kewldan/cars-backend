from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from deps import Filters, Pagination
from models.listing import Listing
from schemas.common import CamelModel
from schemas.listing import ListingOut, ListingPage, SortKey
from services.filters import build_query
from services.sorting import resolve_sort

router = APIRouter()

CACHE_HEADER = "public, max-age=30, stale-while-revalidate=120"

BY_IDS_LIMIT = 24


class ListingsByIdsOut(CamelModel):
    items: list[ListingOut]


@router.get("", response_model=ListingPage, response_model_by_alias=True)
async def list_listings(
    response: Response,
    filters: Filters,
    pagination: Pagination,
    sort: SortKey = "newest",
) -> ListingPage:
    page, page_size = pagination
    where = build_query(filters)
    skip = (page - 1) * page_size

    sort_spec = resolve_sort(sort)
    cursor = Listing.find(where, sort=sort_spec).skip(skip).limit(page_size)
    docs = await cursor.to_list()
    total = await Listing.find(where).count()

    response.headers["Cache-Control"] = CACHE_HEADER
    return ListingPage(
        items=[ListingOut.from_doc(d) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/by-ids", response_model=ListingsByIdsOut, response_model_by_alias=True)
async def listings_by_ids(
    response: Response,
    id: Annotated[list[str], Query()] = [],
) -> ListingsByIdsOut:
    seen: set[str] = set()
    ids: list[str] = []
    for raw in id:
        if raw and raw not in seen:
            seen.add(raw)
            ids.append(raw)
        if len(ids) >= BY_IDS_LIMIT:
            break

    if not ids:
        response.headers["Cache-Control"] = CACHE_HEADER
        return ListingsByIdsOut(items=[])

    docs = await Listing.find({"id_code": {"$in": ids}}).to_list()
    by_code = {d.id_code: d for d in docs}
    items = [ListingOut.from_doc(by_code[i]) for i in ids if i in by_code]

    response.headers["Cache-Control"] = CACHE_HEADER
    return ListingsByIdsOut(items=items)


@router.get("/{listing_id}", response_model=ListingOut, response_model_by_alias=True)
async def get_listing(listing_id: str, response: Response) -> ListingOut:
    doc = await Listing.find_one(Listing.id_code == listing_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    response.headers["Cache-Control"] = CACHE_HEADER
    return ListingOut.from_doc(doc)


@router.get(
    "/{listing_id}/similar",
    response_model=list[ListingOut],
    response_model_by_alias=True,
)
async def similar_listings(
    listing_id: str,
    response: Response,
    limit: int = Query(4, ge=1, le=24),
) -> list[ListingOut]:
    base = await Listing.find_one(Listing.id_code == listing_id)
    if not base:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")

    where = {
        "id_code": {"$ne": base.id_code},
        "$or": [{"make": base.make}, {"body": base.body}],
    }
    docs = await Listing.find(where, sort=[("posted_at", -1)]).limit(limit).to_list()
    response.headers["Cache-Control"] = CACHE_HEADER
    return [ListingOut.from_doc(d) for d in docs]
