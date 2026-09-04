from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.admin_user import AdminUser
from app.models.event import Event
from app.models.participant import Participant, PaymentStatus
from app.schemas.participant import ParticipantCreate, ParticipantResponse

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


@router.patch("/{participant_id}/checkin", response_model=ParticipantResponse)
def checkin_participant(
    participant_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_user),
) -> Participant:
    participant = _get_scoped_participant(participant_id, current_admin, db)
    if participant.checkin_done:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Check-in ja realizado"
        )

    participant.checkin_done = True
    participant.checkin_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
    db.refresh(participant)
    return participant
