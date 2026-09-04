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
    max_capacity: int
    ticket_price: Decimal
    pix_key: str | None = None


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    date: dt.date | None = None
    time: dt.time | None = None
    location: str | None = None
    max_capacity: int | None = None
    ticket_price: Decimal | None = None
    pix_key: str | None = None


class EventResponse(EventBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: dt.datetime
