from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.participant import PaymentMethod, PaymentStatus


class ParticipantCreate(BaseModel):
    name: str
    nickname: str | None = None
    cpf: str | None = None
    email: EmailStr
    whatsapp: str
    payment_method: PaymentMethod


class ParticipantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    name: str
    nickname: str | None = None
    cpf: str | None = None
    email: EmailStr
    whatsapp: str
    payment_method: PaymentMethod
    payment_status: PaymentStatus
    mp_payment_id: str | None = None
    ticket_code: str | None = None
    checkin_done: bool
    checkin_at: dt.datetime | None = None
    created_at: dt.datetime
