from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.admin_user import AdminUser
from app.models.event import Event
from app.models.participant import Participant, PaymentStatus
from app.schemas.event import EventResponse, EventUpdate

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/{event_id}", response_model=EventResponse)
def get_event(event_id: int, db: Session = Depends(get_db)) -> EventResponse:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Evento nao encontrado"
        )

    registered_count = (
        db.query(Participant)
        .filter(
            Participant.event_id == event_id,
            Participant.payment_status != PaymentStatus.EXPIRED,
        )
        .count()
    )

    return EventResponse.model_validate(event).model_copy(
        update={
            "registered_count": registered_count,
            "remaining_slots": max(event.max_capacity - registered_count, 0),
        }
    )


@router.put("/{event_id}", response_model=EventResponse)
def update_event(
    event_id: int,
    payload: EventUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_user),
) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Evento nao encontrado"
        )
    if current_admin.event_id != event_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissao para editar este evento",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, field, value)

    db.commit()
    db.refresh(event)
    return event
