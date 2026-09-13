from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.admin_user import AdminUser
from app.models.event import Event
from app.models.participant import (
    PENDING_REGISTRATION_TTL,
    Participant,
    PaymentMethod,
    PaymentStatus,
)
from app.schemas.checkin import CheckinRequest
from app.schemas.participant import (
    DuplicateCheckResponse,
    DuplicateParticipantInfo,
    ParticipantCreate,
    ParticipantResponse,
)
from app.services.checkin_service import (
    CheckinError,
    find_participant_by_ticket_code,
    perform_checkin,
)
from app.services.email_service import send_registration_email

router = APIRouter(prefix="/participants", tags=["participants"])


def _active_registration_condition(event_id: int, stale_cutoff: dt.datetime):
    # "Active" = counts as a real registration right now: PAID always does;
    # PENDING only within PENDING_REGISTRATION_TTL of creation (past that
    # it's an abandoned checkout, see the constant's docstring). Shared by
    # the capacity count and the duplicate check below so both agree on
    # what counts as "this person already has a spot".
    return and_(
        Participant.event_id == event_id,
        or_(
            Participant.payment_status == PaymentStatus.PAID,
            and_(
                Participant.payment_status == PaymentStatus.PENDING,
                Participant.created_at >= stale_cutoff,
            ),
        ),
    )


def _get_scoped_participant(
    participant_id: int, current_admin: AdminUser, db: Session
) -> Participant:
    participant = db.get(Participant, participant_id)
    if participant is None or participant.event_id != current_admin.event_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Participante nao encontrado"
        )
    return participant


@router.get("/check-duplicate", response_model=DuplicateCheckResponse)
def check_duplicate(
    event_id: int,
    email: str | None = None,
    whatsapp: str | None = None,
    db: Session = Depends(get_db),
) -> DuplicateCheckResponse:
    if not email and not whatsapp:
        return DuplicateCheckResponse(duplicate=False)

    conditions = []
    if email:
        conditions.append(Participant.email == email)
    if whatsapp:
        conditions.append(Participant.whatsapp == whatsapp)

    participant = (
        db.query(Participant)
        .filter(Participant.event_id == event_id, or_(*conditions))
        .first()
    )
    if participant is None:
        return DuplicateCheckResponse(duplicate=False)

    return DuplicateCheckResponse(
        duplicate=True,
        participant=DuplicateParticipantInfo(
            name=participant.name,
            payment_status=participant.payment_status,
            payment_method=participant.payment_method,
        ),
    )


@router.post("/", response_model=ParticipantResponse, status_code=status.HTTP_201_CREATED)
def create_participant(
    payload: ParticipantCreate, event_id: int, response: Response, db: Session = Depends(get_db)
) -> Participant:
    # Cartao temporariamente desativado (pendente de validacao completa) --
    # so Pix aceito. Remover este bloco para reativar cartao.
    if payload.payment_method == PaymentMethod.CARD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pagamento com cartao indisponivel no momento. Use Pix.",
        )

    # Locks the event row for the rest of this transaction so concurrent
    # registrations for the same event serialize instead of racing on the
    # capacity count below (classic check-then-act TOCTOU otherwise -- see
    # the concurrency test in backend/test_concurrency.py).
    event = db.query(Event).filter(Event.id == event_id).with_for_update().first()
    if event is None or not event.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento nao encontrado ou inativo",
        )

    # This is a query-time filter only -- a stale/rejected row's own
    # payment_status still says "pending" until the scheduled job in
    # services/expiration_service.py gets to it.
    stale_cutoff = dt.datetime.now(dt.timezone.utc) - PENDING_REGISTRATION_TTL

    # Real duplicate guard: reusing the event-row lock above means only one
    # registration for this event runs this check at a time, so two
    # concurrent submissions for the same person can't both slip past it.
    # GET /participants/check-duplicate (unchanged) is a separate, softer,
    # frontend-facing warning -- this is what actually stops a second row
    # from being created if that warning is ignored or skipped.
    duplicate = (
        db.query(Participant)
        .filter(
            _active_registration_condition(event_id, stale_cutoff),
            or_(
                Participant.email == payload.email,
                Participant.whatsapp == payload.whatsapp,
            ),
        )
        .first()
    )
    if duplicate is not None:
        if duplicate.payment_status == PaymentStatus.PAID:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ja existe um cadastro pago com esse e-mail ou WhatsApp para este evento",
            )

        # PENDING within the TTL: this is the same person mid-checkout, not a
        # new registration attempt (e.g. tried Pix, wants to switch to Card).
        # Resume that row -- letting the payment method change -- instead of
        # rejecting it, so they aren't blocked from finishing their own
        # in-progress signup.
        if duplicate.payment_method != payload.payment_method:
            duplicate.payment_method = payload.payment_method
            db.commit()
            db.refresh(duplicate)

        response.status_code = status.HTTP_200_OK
        duplicate.reused = True
        return duplicate

    active_registrations = (
        db.query(Participant).filter(_active_registration_condition(event_id, stale_cutoff)).count()
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
    status_value: PaymentStatus = Query(PaymentStatus.PAID, alias="status"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_user),
) -> Participant:
    participant = _get_scoped_participant(participant_id, current_admin, db)
    participant.payment_status = status_value
    db.commit()
    db.refresh(participant)
    return participant


@router.delete("/{participant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_participant(
    participant_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_user),
) -> None:
    participant = _get_scoped_participant(participant_id, current_admin, db)
    db.delete(participant)
    db.commit()


@router.patch("/checkin", response_model=None)
def checkin_by_ticket(
    payload: CheckinRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_user),
) -> dict | JSONResponse:
    try:
        if payload.participant_id is not None:
            participant = db.get(Participant, payload.participant_id)
            if participant is None or participant.event_id != current_admin.event_id:
                raise CheckinError(404, "not_found")
        elif payload.ticket_code:
            participant = find_participant_by_ticket_code(
                payload.ticket_code, db, event_id=current_admin.event_id
            )
        else:
            raise CheckinError(400, "missing_identifier")
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
