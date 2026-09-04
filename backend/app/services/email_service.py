from __future__ import annotations

import base64
import datetime as dt
import io
import json
import logging
import uuid

import qrcode
import resend

from app.core.config import settings
from app.models.event import Event
from app.models.participant import Participant

logger = logging.getLogger(__name__)

FROM_EMAIL = "Ingressos <ingressos@resend.dev>"


def _resend_ready() -> bool:
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY nao configurado; e-mail nao sera enviado")
        return False

    resend.api_key = settings.RESEND_API_KEY
    return True


def _send_email(to: str, subject: str, html: str) -> None:
    if not _resend_ready():
        return

    try:
        resend.Emails.send({"from": FROM_EMAIL, "to": to, "subject": subject, "html": html})
    except Exception:
        logger.exception("Falha ao enviar e-mail via Resend para %s", to)


def send_registration_email(
    participant_name: str,
    participant_email: str,
    event_name: str,
    event_date: dt.date | str,
    event_location: str,
) -> None:
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; color: #1a1a1a;">
      <h1 style="font-size: 20px;">Inscricao confirmada!</h1>
      <p>Ola, {participant_name}!</p>
      <p>Sua inscricao para <strong>{event_name}</strong> foi recebida com sucesso.</p>
      <ul style="padding-left: 18px; color: #444;">
        <li><strong>Data:</strong> {event_date}</li>
        <li><strong>Local:</strong> {event_location}</li>
      </ul>
      <p style="color: #666; font-size: 14px;">
        Assim que o pagamento for confirmado, enviaremos o seu ingresso com o QR Code de acesso.
      </p>
    </div>
    """
    _send_email(participant_email, f"Inscricao confirmada - {event_name}", html)


def _generate_ticket_qr_code_base64(payload: dict) -> str:
    qr = qrcode.QRCode(border=2)
    qr.add_data(json.dumps(payload))
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def send_ticket_email(participant: Participant, event: Event) -> None:
    if not participant.ticket_code:
        participant.ticket_code = str(uuid.uuid4())

    qr_code_base64 = _generate_ticket_qr_code_base64(
        {
            "participant_id": participant.id,
            "event_id": participant.event_id,
            "ticket_code": participant.ticket_code,
        }
    )

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto;
                border: 1px solid #e5e5e5; border-radius: 12px; overflow: hidden;">
      <div style="background: #111827; color: #fff; padding: 24px; text-align: center;">
        <h1 style="margin: 0; font-size: 22px;">{event.name}</h1>
      </div>
      <div style="padding: 24px;">
        <p>Ola, {participant.name}! Seu pagamento foi confirmado e o seu ingresso esta pronto.</p>
        <table style="width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px;">
          <tr>
            <td style="padding: 4px 0; color: #666;">Data</td>
            <td style="padding: 4px 0; text-align: right;"><strong>{event.date}</strong></td>
          </tr>
          <tr>
            <td style="padding: 4px 0; color: #666;">Horario</td>
            <td style="padding: 4px 0; text-align: right;"><strong>{event.time}</strong></td>
          </tr>
          <tr>
            <td style="padding: 4px 0; color: #666;">Local</td>
            <td style="padding: 4px 0; text-align: right;"><strong>{event.location}</strong></td>
          </tr>
        </table>
        <div style="text-align: center; margin: 24px 0;">
          <img src="data:image/png;base64,{qr_code_base64}" alt="QR Code do ingresso"
               style="width: 220px; height: 220px;" />
          <p style="color: #999; font-size: 12px; margin-top: 8px;">
            Codigo: {participant.ticket_code}
          </p>
        </div>
        <p style="color: #666; font-size: 13px;">
          Apresente este QR Code na entrada do evento.
        </p>
      </div>
    </div>
    """
    _send_email(participant.email, f"Seu ingresso - {event.name}", html)


def send_reminder_email(
    participant_name: str,
    participant_email: str,
    event_name: str,
    event_date: dt.date | str,
    event_location: str,
) -> None:
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; color: #1a1a1a;">
      <h1 style="font-size: 20px;">O evento esta chegando!</h1>
      <p>Ola, {participant_name}!</p>
      <p><strong>{event_name}</strong> acontece em menos de 48 horas.</p>
      <ul style="padding-left: 18px; color: #444;">
        <li><strong>Data:</strong> {event_date}</li>
        <li><strong>Local:</strong> {event_location}</li>
      </ul>
      <p style="color: #666; font-size: 14px;">Nao esqueca de levar o QR Code do seu ingresso!</p>
    </div>
    """
    _send_email(participant_email, f"Lembrete: {event_name} e em breve", html)
