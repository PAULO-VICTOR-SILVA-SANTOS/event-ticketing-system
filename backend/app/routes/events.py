from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.admin_user import AdminUser
from app.models.event import Event
from app.models.participant import Participant, PaymentStatus
from app.schemas.event import EventResponse, EventUpdate
from app.services import storage_service

router = APIRouter(prefix="/events", tags=["events"])

ALLOWED_BANNER_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_BANNER_BYTES = 5 * 1024 * 1024


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


@router.post("/{event_id}/banner", response_model=EventResponse)
async def upload_banner(
    event_id: int,
    file: UploadFile = File(...),
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

    if file.content_type not in ALLOWED_BANNER_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de imagem invalido. Use JPEG, PNG ou WEBP.",
        )

    data = await file.read()
    if len(data) > MAX_BANNER_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Imagem maior que 5MB.",
        )

    try:
        public_url, storage_path = storage_service.upload_event_banner(
            event_id, file.content_type, data
        )
    except storage_service.StorageNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Nao foi possivel enviar a imagem agora. Tente novamente.",
        ) from error

    # Swap in the new banner first (so a slow/failed delete below never
    # blocks or rolls back a successful upload), then clean up the file it
    # replaced -- best-effort, see storage_service.delete_event_banner.
    old_storage_path = event.banner_storage_path
    event.banner_url = public_url
    event.banner_storage_path = storage_path
    db.commit()
    db.refresh(event)

    if old_storage_path and old_storage_path != storage_path:
        storage_service.delete_event_banner(old_storage_path)

    return event
