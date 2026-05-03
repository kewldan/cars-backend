from datetime import datetime, timezone

import pymongo
from beanie import Document
from pydantic import Field


class ProcessedPost(Document):
    """Records a Telegram post the parser has already classified but did not
    turn into a fresh listing. Two reasons populate it:

    - "not_listing"          — Qwen declared the post is not a car-for-sale ad.
    - "reply_update_for:..." — the post was a reply that updated an older
                                listing (its content was merged into that
                                listing instead of producing a new one).

    Future ingest runs skip messages whose IDs are in this collection so we
    don't re-ask the LLM about the same post."""

    channel_id: int
    message_id: int
    reason: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        indexes = [
            pymongo.IndexModel(
                [("channel_id", pymongo.ASCENDING), ("message_id", pymongo.ASCENDING)],
                unique=True,
                name="processed_post_uniq",
            ),
        ]
