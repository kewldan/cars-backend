from datetime import datetime, timezone

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Response, status

from deps import DeviceId
from models.listing import Listing
from models.saved_search import SavedSearch
from schemas.listing import ListingOut
from schemas.saved_search import (
    SavedSearchIn,
    SavedSearchOut,
    SavedSearchRunOut,
    SavedSearchUpdate,
)
from services.filters import build_query, describe_filters
from services.sorting import resolve_sort

router = APIRouter()


def _saved_where(doc: SavedSearch) -> dict:
    where = build_query(doc.filters)
    if doc.search:
        where["$text"] = {"$search": doc.search}
    return where


def _parse_object_id(raw: str) -> PydanticObjectId:
    try:
        return PydanticObjectId(raw)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Saved search not found"
        ) from exc


async def _owned(saved_id: str, device_id: str) -> SavedSearch:
    oid = _parse_object_id(saved_id)
    doc = await SavedSearch.get(oid)
    if not doc or doc.user_id != device_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Saved search not found")
    return doc


@router.get("")
async def list_saved(device_id: DeviceId) -> dict:
    docs = await SavedSearch.find(
        SavedSearch.user_id == device_id, sort=[("created_at", -1)]
    ).to_list()
    items = [
        SavedSearchOut.from_doc(d, describe_filters(d.filters)).model_dump(
            by_alias=True
        )
        for d in docs
    ]
    return {"items": items}


@router.post(
    "",
    response_model=SavedSearchOut,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_saved(payload: SavedSearchIn, device_id: DeviceId) -> SavedSearchOut:
    doc = SavedSearch(
        user_id=device_id,
        name=payload.name,
        filters=payload.filters,
        search=payload.search,
        sort=payload.sort,
        notify=payload.notify,
        total_count=0,
        fresh_count=0,
    )
    total = await Listing.find(_saved_where(doc)).count()
    doc.total_count = total
    doc.last_match_at = datetime.now(timezone.utc) if total else None
    await doc.insert()
    return SavedSearchOut.from_doc(doc, describe_filters(doc.filters))


@router.patch(
    "/{saved_id}", response_model=SavedSearchOut, response_model_by_alias=True
)
async def update_saved(
    saved_id: str, payload: SavedSearchUpdate, device_id: DeviceId
) -> SavedSearchOut:
    doc = await _owned(saved_id, device_id)
    update = payload.model_dump(exclude_unset=True)
    for k, v in update.items():
        setattr(doc, k, v)
    if "filters" in update or "search" in update:
        doc.total_count = await Listing.find(_saved_where(doc)).count()
    await doc.save()
    return SavedSearchOut.from_doc(doc, describe_filters(doc.filters))


@router.delete("/{saved_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved(saved_id: str, device_id: DeviceId) -> Response:
    doc = await _owned(saved_id, device_id)
    await doc.delete()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{saved_id}/run", response_model=SavedSearchRunOut, response_model_by_alias=True
)
async def run_saved(saved_id: str, device_id: DeviceId) -> SavedSearchRunOut:
    doc = await _owned(saved_id, device_id)
    where = _saved_where(doc)

    last_at = doc.last_match_at
    fresh_count = 0
    if last_at:
        fresh_where = {**where, "posted_at": {"$gt": last_at}}
        fresh_count = await Listing.find(fresh_where).count()

    sort_spec = resolve_sort(doc.sort)
    items_docs = await Listing.find(where, sort=sort_spec).limit(24).to_list()
    total = await Listing.find(where).count()

    doc.total_count = total
    doc.fresh_count = fresh_count
    doc.last_match_at = datetime.now(timezone.utc)
    await doc.save()

    return SavedSearchRunOut(
        items=[ListingOut.from_doc(d) for d in items_docs],
        total=total,
        fresh_count=fresh_count,
    )
