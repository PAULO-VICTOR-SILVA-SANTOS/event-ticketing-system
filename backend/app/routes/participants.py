from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.admin_user import AdminUser
from app.models.event import Event
from app.models.participant import Participant, PaymentStatus
from app.schemas.checkin import CheckinRequest
from app.schemas.participant import ParticipantCreate, ParticipantResponse
from app.services.checkin_service import (
    CheckinError,
    find_participant_by_ticket_code,
    perform_checkin,
)
from app.services.email_service import send_registration_email

router = APIRouter(prefix="/participants", tags=["participants"])


def _get_scoped_participant(
    participant_id: int, current_admin: AdminUser, db: Session
) -> Participant:
    participant = db.get(Participant, participant_id)
    if participant is None or participant.event_id != current_admin.event_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Participante nao encontrado"
        )
    return participant


@router.post("/", response_model=ParticipantResponse, status_code=status.HTTP_201_CREATED)
def create_participant(
    payload: ParticipantCreate, event_id: int, db: Session = Depends(get_db)
) -> Participant:
    event = db.get(Event, event_id)
    if event is None or not event.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento nao encontrado ou inativo",
        )

    active_registrations = (
        db.query(Participant)
        .filter(
            Participant.event_id == event_id,
            Participant.payment_status != PaymentStatus.EXPIRED,
        )
        .count()
    )
    if active_registrations >= event.max_capacity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Evento sem vagas disponiveis"
        )

    participant = Participant(event_id=event_id, **payload.model_dump())
    db.add(participant)
    db.commit()
    db.refresh(participant)

    send_registration_email(
        participant_name=participant.name,
        participant_email=participant.email,
        event_name=event.name,
        event_date=event.date,
        event_location=event.location,
    )

    return participant


@router.get("/", response_model=list[ParticipantResponse])
def list_participants(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_user),
) -> list[Participant]:
    return (
        db.query(Participant)
        .filter(Participant.event_id == current_admin.event_id)
        .order_by(Participant.created_at.desc())
        .all()
    )


@router.patch("/{participant_id}/payment", response_model=ParticipantResponse)
def confirm_payment(
    participant_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_user),
) -> Participant:
    participant = _get_scoped_participant(participant_id, current_admin, db)
    participant.payment_status = PaymentStatus.PAID
    db.commit()
    db.refresh(participant)
    return participant


@router.patch("/checkin", response_model=None)
def checkin_by_ticket(
    payload: CheckinRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_user),
) -> dict | JSONResponse:
    try:
        participant = find_participant_by_ticket_code(
            payload.ticket_code, db, event_id=current_admin.event_id
        )
        perform_checkin(participant, db)
    except CheckinError as error:
        content: dict = {"ok": False, "reason": error.reason}
        if error.checkin_at is not None:
            content["checkin_at"] = error.checkin_at.isoformat()
        return JSONResponse(status_code=error.status_code, content=content)

    return {
        "ok": True,
        "name": participant.name,
        "checkin_at": participant.checkin_at.isoformat(),
    }
