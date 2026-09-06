"""Cria um usuario admin para um evento via linha de comando.

Uso (a partir da raiz do projeto):
    py backend/create_admin.py --username admin --password suasenha --event-id 1
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)
sys.path.insert(0, str(SCRIPT_DIR))

from app.core.database import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.admin_user import AdminUser  # noqa: E402
from app.models.event import Event  # noqa: E402


def create_admin(username: str, password: str, event_id: int) -> None:
    db = SessionLocal()
    try:
        event = db.get(Event, event_id)
        if event is None:
            print(f"Erro: evento com id {event_id} nao existe.")
            raise SystemExit(1)

        existing = db.query(AdminUser).filter(AdminUser.username == username).first()
        if existing is not None:
            print(f"Erro: usuario '{username}' ja esta em uso.")
            raise SystemExit(1)

        admin = AdminUser(
            event_id=event_id,
            username=username,
            password_hash=hash_password(password),
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        print(
            f"Admin '{admin.username}' criado com sucesso "
            f"(id={admin.id}, event_id={admin.event_id})."
        )
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cria um usuario admin para um evento existente."
    )
    parser.add_argument("--username", required=True, help="Nome de usuario do admin")
    parser.add_argument("--password", required=True, help="Senha do admin")
    parser.add_argument(
        "--event-id", type=int, required=True, dest="event_id", help="ID do evento"
    )
    args = parser.parse_args()

    create_admin(args.username, args.password, args.event_id)


if __name__ == "__main__":
    main()
