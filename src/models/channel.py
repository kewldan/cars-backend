from typing import Annotated

from beanie import Document, Indexed


class TgChannel(Document):
    channel_id: Annotated[int, Indexed(unique=True)]
    name: str
    subs: int = 0
