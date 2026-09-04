from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.models.participant import Participant, PaymentStatus


class CheckinError(Exception):
    def __init__(
        self, status_code: int, reason: str, checkin_at: dt.datetime | None = None
    ) -> None:
        super().__init__(reason)
        self.status_code = status_code
        self.reason = reason
        self.checkin_at = checkin_at


def find_participant_by_ticket_code(
    ticket_code: str, db: Session, *, event_id: int | None = None
) -> Participant:
    participant = db.query(Participant).filter(Participant.ticket_code == ticket_code).first()
    if participant is None or (event_id is not None and participant.event_id != event_id):
        raise CheckinError(404, "invalid_ticket")
    return participant


def perform_checkin(participant: Participant, db: Session) -> Participant:
    if participant.payment_status != PaymentStatus.PAID:
        raise CheckinError(400, "payment_pending")

    if participant.checkin_done:
        raise CheckinError(400, "already_checked_in", checkin_at=participant.checkin_at)

    participant.checkin_done = True
    participant.checkin_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
    db.refresh(participant)
    return participant
