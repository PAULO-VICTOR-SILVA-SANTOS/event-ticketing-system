from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy.orm import Session

from app.models.participant import PENDING_REGISTRATION_TTL, Participant, PaymentStatus

logger = logging.getLogger(__name__)


def expire_stale_pending_participants(db: Session) -> int:
    """Flip PENDING participants past PENDING_REGISTRATION_TTL to EXPIRED.

    routes/participants.py's capacity check already ignores these at query
    time (so a stale pending never blocks a new registration), but the row
    itself still says "pending" until this runs -- meant to be called
    periodically (see core/scheduler.py) so the stored data reflects reality
    (admin participant list, dashboard counts, exports) instead of only
    being correct at the one call site that happens to filter by TTL too.
    """
    stale_cutoff = dt.datetime.now(dt.timezone.utc) - PENDING_REGISTRATION_TTL
    stale_participants = (
        db.query(Participant)
        .filter(
            Participant.payment_status == PaymentStatus.PENDING,
            Participant.created_at < stale_cutoff,
        )
        .all()
    )
    for participant in stale_participants:
        participant.payment_status = PaymentStatus.EXPIRED
    if stale_participants:
        db.commit()
        logger.info("Expirou %d inscricao(oes) pendente(s) alem do TTL", len(stale_participants))
    return len(stale_participants)
