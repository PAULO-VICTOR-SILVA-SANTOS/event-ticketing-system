from __future__ import annotations

from pydantic import BaseModel


class PixPaymentRequest(BaseModel):
    participant_id: int
    event_id: int


class PixPaymentResponse(BaseModel):
    payment_id: str
    qr_code: str | None = None
    qr_code_base64: str | None = None
    ticket_url: str | None = None
    status: str


class CardPaymentRequest(BaseModel):
    participant_id: int
    event_id: int
    token: str
    installments: int = 1


class CardPaymentResponse(BaseModel):
    payment_id: str
    status: str


class PaymentStatusResponse(BaseModel):
    payment_id: str
    status: str
