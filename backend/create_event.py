"""Cria o evento (id=1) de producao via linha de comando.

Uso (a partir da raiz do projeto, com DATABASE_URL apontando para o banco correto):
    py backend/create_event.py
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from decimal import Decimal
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)
sys.path.insert(0, str(SCRIPT_DIR))

from app.core.database import SessionLocal  # noqa: E402
from app.models.event import Event  # noqa: E402


def create_event() -> None:
    db = SessionLocal()
    try:
        existing = db.get(Event, 1)
        if existing is not None:
            print(f"Erro: evento com id 1 ja existe ({existing.name!r}).")
            raise SystemExit(1)

        event = Event(
            id=1,
            name="Confraternização Enfermeiras Unimed-JP",
            description="Confraternização do setor de enfermagem do Hospital Unimed João Pessoa",
            date=dt.date(2026, 11, 21),
            time=dt.time(20, 0, 0),
            location="A definir",
            banner_url=None,
            max_capacity=70,
            ticket_price=Decimal("150.00"),
            pix_key=None,
            is_active=True,
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        print(f"Evento '{event.name}' criado com sucesso (id={event.id}).")
    finally:
        db.close()


if __name__ == "__main__":
    create_event()
