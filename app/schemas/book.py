from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BookBase(BaseModel):
    title: str
    author: str
    category: Optional[str] = None
    publisher: Optional[str] = None
    description: Optional[str] = None
    cover_image_url: Optional[str] = Field(default=None, alias="coverImageUrl")
    isbn: Optional[str] = None
    language: Optional[str] = None
    page_count: Optional[int] = Field(default=None, alias="pageCount")
    published_at: Optional[date] = Field(default=None, alias="publishedAt")
    tags: Optional[list[str]] = None
    ai_summary: Optional[str] = Field(default=None, alias="aiSummary")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    @field_validator("page_count")
    @classmethod
    def validate_page_count(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value <= 0:
            raise ValueError("pageCount must be a positive integer")
        return value


class BookCreate(BookBase):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class BookUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None
    publisher: Optional[str] = None
    description: Optional[str] = None
    cover_image_url: Optional[str] = Field(default=None, alias="coverImageUrl")
    isbn: Optional[str] = None
    language: Optional[str] = None
    page_count: Optional[int] = Field(default=None, alias="pageCount")
    published_at: Optional[date] = Field(default=None, alias="publishedAt")
    tags: Optional[list[str]] = None
    ai_summary: Optional[str] = Field(default=None, alias="aiSummary")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    @field_validator("page_count")
    @classmethod
    def validate_page_count(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value <= 0:
            raise ValueError("pageCount must be a positive integer")
        return value


class BookOut(BookBase):
    id: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: Optional[datetime] = Field(default=None, alias="updatedAt")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
    )
