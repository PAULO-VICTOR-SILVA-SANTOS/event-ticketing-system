from __future__ import annotations

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.event import Event
from app.models.participant import Participant, PaymentStatus
from app.schemas.payment import (
    CardPaymentRequest,
    CardPaymentResponse,
    PaymentStatusResponse,
    PixPaymentRequest,
    PixPaymentResponse,
)
from app.services import payment_service
from app.services.email_service import send_ticket_email

router = APIRouter(prefix="/payments", tags=["payments"])
logger = logging.getLogger(__name__)


def _get_participant_for_event(
    participant_id: int, event_id: int, db: Session
) -> Participant:
    participant = db.get(Participant, participant_id)
    if participant is None or participant.event_id != event_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Participante nao encontrado"
        )
    return participant


def _get_event(event_id: int, db: Session) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Evento nao encontrado"
        )
    return event


@router.post("/pix", response_model=PixPaymentResponse, status_code=status.HTTP_201_CREATED)
def create_pix(payload: PixPaymentRequest, db: Session = Depends(get_db)) -> PixPaymentResponse:
    participant = _get_participant_for_event(payload.participant_id, payload.event_id, db)
    event = _get_event(payload.event_id, db)

    result = payment_service.create_pix_payment(
        participant_id=participant.id,
        amount=event.ticket_price,
        participant_name=participant.name,
        participant_email=participant.email,
        event_name=event.name,
    )

    participant.mp_payment_id = str(result["payment_id"])
    db.commit()

    return PixPaymentResponse(
        payment_id=str(result["payment_id"]),
        qr_code=result["qr_code"],
        qr_code_base64=result["qr_code_base64"],
        ticket_url=result["ticket_url"],
        status=result["status"],
    )


@router.post("/card", response_model=CardPaymentResponse, status_code=status.HTTP_201_CREATED)
def create_card(
    payload: CardPaymentRequest, db: Session = Depends(get_db)
) -> CardPaymentResponse:
    participant = _get_participant_for_event(payload.participant_id, payload.event_id, db)
    event = _get_event(payload.event_id, db)

    result = payment_service.create_card_payment(
        participant_id=participant.id,
        amount=event.ticket_price,
        token=payload.token,
        installments=payload.installments,
        participant_email=participant.email,
        event_name=event.name,
    )

    participant.mp_payment_id = str(result["payment_id"])
    if result["status"] == "approved":
        participant.payment_status = PaymentStatus.PAID
    db.commit()

    return CardPaymentResponse(payment_id=str(result["payment_id"]), status=result["status"])


def _extract_payment_id(request: Request, body: bytes) -> str | None:
    data_id = request.query_params.get("data.id") or request.query_params.get("id")
    if data_id:
        return data_id

    if not body:
        return None

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None

    data = payload.get("data") or {}
    payment_id = data.get("id") or payload.get("id")
    return str(payment_id) if payment_id is not None else None


def _verify_webhook_signature(request: Request) -> None:
    if not settings.MP_WEBHOOK_SECRET:
        return

    signature_header = request.headers.get("x-signature")
    request_id = request.headers.get("x-request-id")
    data_id = request.query_params.get("data.id") or request.query_params.get("id")

    if not signature_header or not data_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Assinatura de webhook invalida"
        )

    parts = dict(item.split("=", 1) for item in signature_header.split(",") if "=" in item)
    ts = parts.get("ts")
    received_hash = parts.get("v1")
    if not ts or not received_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Assinatura de webhook invalida"
        )

    manifest = f"id:{data_id.lower()};request-id:{request_id or ''};ts:{ts};"
    expected_hash = hmac.new(
        settings.MP_WEBHOOK_SECRET.encode(), manifest.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Assinatura de webhook invalida"
        )


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def payment_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    body = await request.body()
    _verify_webhook_signature(request)

    payment_id = _extract_payment_id(request, body)
    if payment_id is None:
        return {"status": "ignored"}

    try:
        result = payment_service.get_payment_status(payment_id)
    except RuntimeError:
        logger.exception("Falha ao consultar pagamento %s no webhook", payment_id)
        return {"status": "error"}

    if result["status"] != "approved":
        return {"status": "received"}

    participant = (
        db.query(Participant).filter(Participant.mp_payment_id == str(payment_id)).first()
    )
    if participant is None:
        return {"status": "participant_not_found"}

    if participant.payment_status != PaymentStatus.PAID:
        participant.payment_status = PaymentStatus.PAID
        db.commit()
        db.refresh(participant)

        event = db.get(Event, participant.event_id)
        if event is not None:
            send_ticket_email(participant, event)
            db.commit()

    return {"status": "processed"}


@router.get("/status/{payment_id}", response_model=PaymentStatusResponse)
def get_payment_status(payment_id: str) -> PaymentStatusResponse:
    result = payment_service.get_payment_status(payment_id)
    return PaymentStatusResponse(payment_id=str(result["payment_id"]), status=result["status"])
