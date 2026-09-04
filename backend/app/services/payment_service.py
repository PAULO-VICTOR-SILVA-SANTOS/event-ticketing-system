from __future__ import annotations

from decimal import Decimal
from typing import Any

import mercadopago

from app.core.config import settings

_sdk: mercadopago.SDK | None = None


def _get_sdk() -> mercadopago.SDK:
    global _sdk
    if _sdk is None:
        if not settings.MP_ACCESS_TOKEN:
            raise RuntimeError("MP_ACCESS_TOKEN nao configurado")
        _sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
    return _sdk


def create_pix_payment(
    participant_id: int,
    amount: Decimal,
    participant_name: str,
    participant_email: str,
    event_name: str,
) -> dict[str, Any]:
    first_name, _, last_name = participant_name.partition(" ")
    payment_data = {
        "transaction_amount": float(amount),
        "description": f"Ingresso - {event_name}",
        "payment_method_id": "pix",
        "payer": {
            "email": participant_email,
            "first_name": first_name or participant_name,
            "last_name": last_name or first_name or participant_name,
        },
        "external_reference": str(participant_id),
    }

    result = _get_sdk().payment().create(payment_data)
    response = result["response"]
    if result["status"] not in (200, 201):
        raise RuntimeError(f"Falha ao criar pagamento PIX: {response}")

    transaction_data = response.get("point_of_interaction", {}).get("transaction_data", {})
    return {
        "payment_id": response["id"],
        "qr_code": transaction_data.get("qr_code"),
        "qr_code_base64": transaction_data.get("qr_code_base64"),
        "ticket_url": transaction_data.get("ticket_url"),
        "status": response["status"],
    }


def create_card_payment(
    participant_id: int,
    amount: Decimal,
    token: str,
    installments: int,
    participant_email: str,
    event_name: str,
) -> dict[str, Any]:
    payment_data = {
        "transaction_amount": float(amount),
        "token": token,
        "description": f"Ingresso - {event_name}",
        "installments": installments,
        "payer": {"email": participant_email},
        "external_reference": str(participant_id),
    }

    result = _get_sdk().payment().create(payment_data)
    response = result["response"]
    if result["status"] not in (200, 201):
        raise RuntimeError(f"Falha ao processar pagamento com cartao: {response}")

    return {"payment_id": response["id"], "status": response["status"]}


def get_payment_status(payment_id: str) -> dict[str, Any]:
    result = _get_sdk().payment().get(payment_id)
    response = result["response"]
    if result["status"] != 200:
        raise RuntimeError(f"Falha ao consultar pagamento: {response}")

    return {"payment_id": response["id"], "status": response["status"]}


def cancel_payment(payment_id: str) -> dict[str, Any]:
    result = _get_sdk().payment().update(payment_id, {"status": "cancelled"})
    response = result["response"]
    if result["status"] not in (200, 201):
        raise RuntimeError(f"Falha ao cancelar pagamento: {response}")

    return {"payment_id": response["id"], "status": response["status"]}
