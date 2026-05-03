from fastapi import APIRouter, HTTPException, Response, status

from deps import DeviceId
from models.favorite import Favorite
from models.listing import Listing
from schemas.listing import ListingOut

router = APIRouter()


@router.get("", response_model=dict, response_model_by_alias=True)
async def list_favorites(device_id: DeviceId) -> dict:
    favs = await Favorite.find(Favorite.user_id == device_id).to_list()
    if not favs:
        return {"items": []}
    listing_ids = [f.listing_id for f in favs]
    docs = await Listing.find({"id_code": {"$in": listing_ids}}).to_list()
    by_id = {d.id_code: d for d in docs}
    ordered = [by_id[i] for i in listing_ids if i in by_id]
    return {"items": [ListingOut.from_doc(d).model_dump(by_alias=True) for d in ordered]}


@router.get("/ids")
async def favorite_ids(device_id: DeviceId) -> dict[str, list[str]]:
    favs = await Favorite.find(Favorite.user_id == device_id).to_list()
    return {"ids": [f.listing_id for f in favs]}


@router.post("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_favorite(listing_id: str, device_id: DeviceId) -> Response:
    listing = await Listing.find_one(Listing.id_code == listing_id)
    if not listing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    existing = await Favorite.find_one(
        Favorite.user_id == device_id, Favorite.listing_id == listing_id
    )
    if not existing:
        await Favorite(user_id=device_id, listing_id=listing_id).insert()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(listing_id: str, device_id: DeviceId) -> Response:
    fav = await Favorite.find_one(
        Favorite.user_id == device_id, Favorite.listing_id == listing_id
    )
    if fav:
        await fav.delete()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
