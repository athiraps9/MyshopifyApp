from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InteractionIn(BaseModel):
    channel: Literal["phone", "email", "in_person", "chat", "other"]
    summary: str = Field(min_length=1, max_length=2000)
    created_by: str | None = Field(default=None, max_length=100)


class InteractionOut(InteractionIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class FollowUpIn(BaseModel):
    shopify_customer_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    due_date: date
    assigned_to: str | None = Field(default=None, max_length=100)


class FollowUpOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    crm_customer_id: int
    title: str
    due_date: date
    status: str
    assigned_to: str | None
    created_at: datetime


class CRMCustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    shopify_customer_id: int
    display_name: str | None
    internal_notes: str | None
    last_synced_at: datetime | None
    created_at: datetime
