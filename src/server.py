import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import db
from routers import (
    facets,
    favorites,
    health,
    listings,
    map as map_router,
    saved_searches,
)
from settings import settings

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await db.connect()
    log.info("MongoDB connected: db=%s", settings.MONGO_DB)
    yield
    await db.close()


app = FastAPI(
    title="GeorgianCars API",
    version="1",
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Cache-Control"],
)

_images_dir = Path("data/images")
_images_dir.mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=str(_images_dir)), name="images")

app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(listings.router, prefix="/listings", tags=["listings"])
app.include_router(facets.router, prefix="/facets", tags=["facets"])
app.include_router(favorites.router, prefix="/favorites", tags=["favorites"])
app.include_router(saved_searches.router, prefix="/saved-searches", tags=["saved"])
app.include_router(map_router.router, prefix="/map", tags=["map"])
