from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.admin_user import AdminUser
from app.models.event import Event
from app.models.expense import Expense
from app.models.participant import Participant, PaymentStatus

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardResponse(BaseModel):
    total_registered: int
    total_paid: int
    total_pending: int
    total_collected: Decimal
    total_expenses: Decimal
    remaining_to_collect: Decimal
    value_per_person: Decimal
    remaining_slots: int


@router.get("/", response_model=DashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_user),
) -> DashboardResponse:
    event = db.get(Event, current_admin.event_id)

    total_registered = (
        db.query(func.count(Participant.id))
        .filter(Participant.event_id == current_admin.event_id)
        .scalar()
        or 0
    )
    total_paid = (
        db.query(func.count(Participant.id))
        .filter(
            Participant.event_id == current_admin.event_id,
            Participant.payment_status == PaymentStatus.PAID,
        )
        .scalar()
        or 0
    )
    total_pending = (
        db.query(func.count(Participant.id))
        .filter(
            Participant.event_id == current_admin.event_id,
            Participant.payment_status == PaymentStatus.PENDING,
        )
        .scalar()
        or 0
    )

    ticket_price = event.ticket_price if event else Decimal("0")
    total_collected = ticket_price * total_paid

    total_expenses_raw = (
        db.query(func.coalesce(func.sum(Expense.value), 0))
        .filter(Expense.event_id == current_admin.event_id)
        .scalar()
        or 0
    )
    total_expenses = Decimal(str(total_expenses_raw))

    remaining_to_collect = max(total_expenses - total_collected, Decimal("0"))
    remaining_slots = max((event.max_capacity - total_registered), 0) if event else 0

    return DashboardResponse(
        total_registered=total_registered,
        total_paid=total_paid,
        total_pending=total_pending,
        total_collected=total_collected,
        total_expenses=total_expenses,
        remaining_to_collect=remaining_to_collect,
        value_per_person=ticket_price,
        remaining_slots=remaining_slots,
    )
