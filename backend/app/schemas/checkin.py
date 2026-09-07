from __future__ import annotations

from pydantic import BaseModel


class CheckinRequest(BaseModel):
    ticket_code: str | None = None
    participant_id: int | None = None


class CheckinStatsResponse(BaseModel):
    total_confirmados: int
    total_checkin: int
    faltam_entrar: int
    percentual: float
