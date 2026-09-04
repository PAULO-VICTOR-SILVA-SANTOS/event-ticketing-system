from __future__ import annotations

import logging

from app.core.config import settings
from app.models.event import Event
from app.models.participant import Participant

logger = logging.getLogger(__name__)


def send_ticket_email(participant: Participant, event: Event) -> None:
    if not settings.RESEND_API_KEY:
        logger.info(
            "RESEND_API_KEY nao configurado; pulando envio de ingresso para %s",
            participant.email,
        )
        return

    # TODO: integrar com a API do Resend quando o envio de e-mails for implementado.
    logger.info("Ingresso confirmado para %s (evento %s)", participant.email, event.name)
