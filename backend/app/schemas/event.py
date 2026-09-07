from __future__ import annotations

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class EventBase(BaseModel):
    name: str
    description: str | None = None
    date: dt.date
    time: dt.time
    location: str
    banner_url: str | None = None
    max_capacity: int
    ticket_price: Decimal
    pix_key: str | None = None
    show_remaining_slots: bool = True


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    date: dt.date | None = None
    time: dt.time | None = None
    location: str | None = None
    banner_url: str | None = None
    max_capacity: int | None = None
    ticket_price: Decimal | None = None
    pix_key: str | None = None
    show_remaining_slots: bool | None = None


class EventResponse(EventBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: dt.datetime
    registered_count: int = 0
    remaining_slots: int = 0
