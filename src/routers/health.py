from fastapi import APIRouter

import db

router = APIRouter()


@router.get("")
async def health() -> dict[str, bool]:
    return {"ok": True, "db": await db.ping()}
