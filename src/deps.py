from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query, status

from schemas.listing import ListingFilters


async def get_device_id(
    x_device_id: Annotated[str | None, Header(alias="X-Device-Id")] = None,
) -> str:
    if not x_device_id or len(x_device_id) < 8:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Device-Id header is required",
        )
    return x_device_id


DeviceId = Annotated[str, Depends(get_device_id)]


async def pagination(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, alias="pageSize")] = 24,
) -> tuple[int, int]:
    return page, page_size


Pagination = Annotated[tuple[int, int], Depends(pagination)]


async def listing_filters(
    q: str | None = None,
    priceFrom: int | None = None,
    priceTo: int | None = None,
    yearFrom: int | None = None,
    yearTo: int | None = None,
    mileageFrom: int | None = None,
    mileageTo: int | None = None,
    engineFrom: float | None = None,
    engineTo: float | None = None,
    powerFrom: int | None = None,
    powerTo: int | None = None,
    makes: Annotated[list[str] | None, Query()] = None,
    models: Annotated[list[str] | None, Query()] = None,
    fuels: Annotated[list[str] | None, Query()] = None,
    trans: Annotated[list[str] | None, Query()] = None,
    drives: Annotated[list[str] | None, Query()] = None,
    bodies: Annotated[list[str] | None, Query()] = None,
    cities: Annotated[list[str] | None, Query()] = None,
    colors: Annotated[list[str] | None, Query()] = None,
    channel: str | None = None,
    vinOnly: bool = False,
    priceOnly: bool = False,
    bargain: bool = False,
    customsCleared: bool = False,
) -> ListingFilters:
    return ListingFilters(
        q=q,
        price_from=priceFrom,
        price_to=priceTo,
        year_from=yearFrom,
        year_to=yearTo,
        mileage_from=mileageFrom,
        mileage_to=mileageTo,
        engine_from=engineFrom,
        engine_to=engineTo,
        power_from=powerFrom,
        power_to=powerTo,
        makes=makes or [],
        models=models or [],
        fuels=fuels or [],
        trans=trans or [],
        drives=drives or [],
        bodies=bodies or [],
        cities=cities or [],
        colors=colors or [],
        channel=channel,
        vin_only=vinOnly,
        price_only=priceOnly,
        bargain=bargain,
        customs_cleared=customsCleared,
    )


Filters = Annotated[ListingFilters, Depends(listing_filters)]
