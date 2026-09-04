from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.participant import Participant, PaymentStatus
from app.schemas.checkin import CheckinRequest, CheckinStatsResponse
from app.services.checkin_service import (
    CheckinError,
    find_participant_by_ticket_code,
    perform_checkin,
)

router = APIRouter(prefix="/checkin", tags=["checkin"])


def verify_portaria_key(x_portaria_key: str = Header(..., alias="X-Portaria-Key")) -> None:
    if not settings.PORTARIA_SECRET_KEY or x_portaria_key != settings.PORTARIA_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Chave da portaria invalida"
        )


@router.post("", response_model=None, dependencies=[Depends(verify_portaria_key)])
def checkin_at_gate(payload: CheckinRequest, db: Session = Depends(get_db)) -> dict | JSONResponse:
    try:
        participant = find_participant_by_ticket_code(payload.ticket_code, db)
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


@router.get(
    "/stats",
    response_model=CheckinStatsResponse,
    dependencies=[Depends(verify_portaria_key)],
)
def checkin_stats(db: Session = Depends(get_db)) -> CheckinStatsResponse:
    total_confirmados = (
        db.query(Participant).filter(Participant.payment_status == PaymentStatus.PAID).count()
    )
    total_checkin = db.query(Participant).filter(Participant.checkin_done.is_(True)).count()
    faltam_entrar = total_confirmados - total_checkin
    percentual = round((total_checkin / total_confirmados * 100), 2) if total_confirmados else 0.0

    return CheckinStatsResponse(
        total_confirmados=total_confirmados,
        total_checkin=total_checkin,
        faltam_entrar=faltam_entrar,
        percentual=percentual,
    )
