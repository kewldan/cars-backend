from datetime import datetime, timezone
from typing import Literal, Annotated

from beanie import Document, Indexed
from pydantic import Field


class User(Document):
    email: Annotated[str, Indexed(unique=True)]
    name: str | None = None
    locale: Literal["ru", "en", "ka"] = "ru"
    currency: Literal["USD", "RUB"] = "USD"
    palette: Literal["electric", "sunset", "azure", "tbilisi"] = "electric"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
