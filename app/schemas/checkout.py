from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.schemas.member import MemberOut

CheckoutStatusLiteral = Literal["checked_out", "returned", "overdue", "lost", "cancelled"]


class CheckoutCreate(BaseModel):
    book_id: str = Field(alias="bookId")
    member_id: Optional[str] = Field(default=None, alias="memberId")
    due_at: Optional[datetime | date] = Field(default=None, alias="dueAt")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class CheckoutUpdate(BaseModel):
    action: Literal["return", "extend", "cancel", "mark_lost"]
    days: Optional[int] = Field(default=None, alias="days")
    new_due_at: Optional[datetime | date] = Field(default=None, alias="newDueAt")
    notes: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    @field_validator("days")
    @classmethod
    def validate_days(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value <= 0:
            raise ValueError("days must be a positive integer")
        return value

    @model_validator(mode="after")
    def validate_extend_payload(self) -> "CheckoutUpdate":
        if self.action != "extend":
            if self.days is not None or self.new_due_at is not None:
                raise ValueError("days or newDueAt can only be provided for extend action")
            return self

        provided = sum(value is not None for value in (self.days, self.new_due_at))
        if provided != 1:
            raise ValueError("extend action requires exactly one of days or newDueAt")
        return self


class BookLite(BaseModel):
    id: str
    title: str
    author: str
    cover_image_url: Optional[str] = Field(default=None, alias="coverImageUrl")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
    )


class CheckoutOut(BaseModel):
    id: str
    book_id: str = Field(alias="bookId")
    member_id: str = Field(alias="memberId")
    status: CheckoutStatusLiteral
    checked_out_at: datetime = Field(alias="checkedOutAt")
    due_at: datetime = Field(alias="dueAt")
    returned_at: Optional[datetime] = Field(default=None, alias="returnedAt")
    notes: Optional[str] = None
    created_at: datetime = Field(alias="createdAt")
    updated_at: Optional[datetime] = Field(default=None, alias="updatedAt")
    book: Optional[BookLite] = None
    member: Optional[MemberOut] = None

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
    )
