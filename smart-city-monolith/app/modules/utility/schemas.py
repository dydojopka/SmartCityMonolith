from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

IssueStatus = Literal["NEW", "IN_PROGRESS", "RESOLVED", "REJECTED"]


class IssueCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=5000)
    category: str = Field(min_length=2, max_length=50)
    address: str = Field(min_length=3, max_length=300)

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value):
        return value.strip().upper() if isinstance(value, str) else value


class IssueStatusUpdate(BaseModel):
    status: IssueStatus


class IssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    description: str
    category: str
    address: str
    status: IssueStatus
    created_at: datetime
    updated_at: datetime
