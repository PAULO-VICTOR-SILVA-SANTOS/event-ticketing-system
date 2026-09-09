from __future__ import annotations

import datetime as dt
import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.event import Event


class PaymentMethod(str, enum.Enum):
    PIX = "pix"
    CARD = "card"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    EXPIRED = "expired"


# How long a PENDING registration (checkout started, never paid) is allowed
# to hold a capacity slot. Past this, routes/participants.py's capacity
# count treats it as if it weren't there (abandoned-checkout protection --
# someone opening the Pix QR and never paying shouldn't be able to lock a
# seat forever), and services/expiration_service.py's scheduled job flips
# it to EXPIRED in the database so the data reflects reality, not just the
# capacity query. Single source of truth for both -- keep them in sync.
PENDING_REGISTRATION_TTL = dt.timedelta(minutes=20)


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(100))
    cpf: Mapped[str | None] = mapped_column(String(14))
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    whatsapp: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method"), nullable=False
    )
    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"),
        default=PaymentStatus.PENDING,
        nullable=False,
    )
    mp_payment_id: Mapped[str | None] = mapped_column(String(100))
    ticket_code: Mapped[str | None] = mapped_column(String(36), unique=True)
    checkin_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    checkin_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    event: Mapped["Event"] = relationship(back_populates="participants")
