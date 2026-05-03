from .common import CamelModel
from .listing import TgChannelOut


class FacetsRange(CamelModel):
    min: float
    max: float


class FacetsRanges(CamelModel):
    price: FacetsRange
    year: FacetsRange
    mileage: FacetsRange
    engine: FacetsRange
    power: FacetsRange


class FacetsOut(CamelModel):
    makes: dict[str, list[str]]
    fuels: list[str]
    transmissions: list[str]
    drives: list[str]
    bodies: list[str]
    cities: list[str]
    colors: list[str]
    channels: list[TgChannelOut]
    ranges: FacetsRanges
