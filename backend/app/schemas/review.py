from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReviewWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rating: int = Field(strict=True, ge=1, le=5)
    comment: str = Field(default="", max_length=2000)

    @field_validator("comment", mode="before")
    @classmethod
    def normalize_comment(cls, value):
        return "" if value is None else value.strip() if isinstance(value, str) else value


class ReviewRead(BaseModel):
    id: int
    product_id: int
    author_name: str
    rating: int
    comment: str
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class ReviewPage(BaseModel):
    items: list[ReviewRead]
    total: int
    average_rating: float | None
    limit: int
    offset: int
