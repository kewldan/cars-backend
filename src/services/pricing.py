from models.listing import PRICE_RATING_RANK, PriceRating


def rate(price: int, fair: int) -> tuple[PriceRating, int]:
    if fair <= 0:
        return ("fair", PRICE_RATING_RANK["fair"])
    delta = (price - fair) / fair
    if delta < -0.12:
        return ("great", PRICE_RATING_RANK["great"])
    if delta < -0.04:
        return ("good", PRICE_RATING_RANK["good"])
    if delta < 0.06:
        return ("fair", PRICE_RATING_RANK["fair"])
    if delta < 0.15:
        return ("high", PRICE_RATING_RANK["high"])
    return ("overpriced", PRICE_RATING_RANK["overpriced"])
