"""Teste de concorrencia para o webhook do Mercado Pago (POST /payments/webhook).

Confirma que dois webhooks duplicados chegando ao MESMO TEMPO para o mesmo
pagamento (Mercado Pago reenvia webhooks em caso de timeout/retry, e nada
impede dois deliveries quase simultaneos) nao disparam o e-mail do ingresso
duas vezes nem deixam o participante em estado inconsistente.

Roda tudo em processo (nao sobe um servidor real): a API real do Mercado
Pago (`payment_service.get_payment_status`) e o envio real de e-mail
(`send_ticket_email`, usado dentro de app.routes.payments) sao substituidos
por stubs, entao nao precisa de MP_ACCESS_TOKEN/RESEND_API_KEY reais e nao
faz nenhuma chamada de rede externa.

Concorrencia real (nao apenas asyncio.gather no mesmo loop): cada requisicao
roda em um TestClient proprio, cada um com seu proprio portal/event loop em
background (padrao do starlette.testclient), disparados em duas threads
simultaneas via ThreadPoolExecutor. Isso reproduz o cenario mais realista e
mais dificil: dois workers/processos diferentes recebendo o mesmo webhook ao
mesmo tempo (o que uma unica instancia asyncio single-threaded nao consegue
simular, porque o handler async so cede o controle em pontos de await).

Usa um SQLite descartavel separado (nao toca no banco de dev nem em
producao/Railway).

Uso (a partir da raiz do projeto, usa o Python do venv do backend):
    backend/venv/Scripts/python.exe backend/test_webhook_duplicate.py
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)
sys.path.insert(0, str(SCRIPT_DIR))

TEST_DB_PATH = SCRIPT_DIR / "test_webhook_duplicate.db"

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["SECRET_KEY"] = "webhook-duplicate-test-secret"
for _key in ("MP_ACCESS_TOKEN", "MP_PUBLIC_KEY", "MP_WEBHOOK_SECRET", "RESEND_API_KEY", "PORTARIA_SECRET_KEY"):
    os.environ[_key] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
import app.models  # noqa: E402  (registra as tabelas em Base.metadata)
from app.main import app  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.participant import Participant, PaymentMethod, PaymentStatus  # noqa: E402
import app.routes.payments as payments_route  # noqa: E402
from app.services import payment_service  # noqa: E402


PAYMENT_ID = "mp-test-payment-123"


def _cleanup_db_files() -> None:
    import time

    paths = [TEST_DB_PATH] + [Path(str(TEST_DB_PATH) + suffix) for suffix in ("-shm", "-wal", "-journal")]
    for attempt in range(5):
        remaining = [p for p in paths if p.exists()]
        if not remaining:
            return
        for p in remaining:
            try:
                p.unlink()
            except PermissionError:
                pass
        if attempt < 4:
            time.sleep(0.5)


def _setup_database() -> int:
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        import datetime as dt
        from decimal import Decimal

        event = Event(
            name="[TESTE] Webhook duplicado",
            date=dt.date(2026, 11, 21),
            time=dt.time(20, 0, 0),
            location="Local de teste",
            max_capacity=100,
            ticket_price=Decimal("150.00"),
            is_active=True,
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        participant = Participant(
            event_id=event.id,
            name="Participante Duplicado",
            email="webhook.duplicado@example.com",
            whatsapp="5583999999999",
            payment_method=PaymentMethod.PIX,
            payment_status=PaymentStatus.PENDING,
            mp_payment_id=PAYMENT_ID,
        )
        db.add(participant)
        db.commit()
        db.refresh(participant)
        return participant.id
    finally:
        db.close()


def _query_participant(participant_id: int) -> Participant:
    db = SessionLocal()
    try:
        return db.get(Participant, participant_id)
    finally:
        db.close()


def main() -> None:
    print("Preparando banco de teste isolado e participante PENDING...")
    participant_id = _setup_database()

    sent_emails: list[tuple[int, str]] = []

    def fake_get_payment_status(payment_id: str) -> dict:
        return {"payment_id": payment_id, "status": "approved"}

    def fake_send_ticket_email(participant: Participant, event: Event) -> None:
        # Sem chamada de rede real -- so registra que teria enviado.
        sent_emails.append((participant.id, participant.email))

    def _post_webhook(_: int):
        client = TestClient(app)
        return client.post("/api/v1/payments/webhook", params={"data.id": PAYMENT_ID})

    print("Disparando 2 webhooks duplicados simultaneos (threads + event loops separados)...")
    with patch.object(payment_service, "get_payment_status", side_effect=fake_get_payment_status), \
         patch.object(payments_route, "send_ticket_email", side_effect=fake_send_ticket_email):
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(_post_webhook, range(2)))

    final_participant = _query_participant(participant_id)

    engine.dispose()
    _cleanup_db_files()

    statuses = [r.status_code for r in responses]
    bodies = [r.json() for r in responses]
    emails_sent = len(sent_emails)
    consistent = (
        all(code == 200 for code in statuses)
        and emails_sent == 1
        and final_participant.payment_status == PaymentStatus.PAID
    )

    print("\n" + "=" * 70)
    print("RELATORIO - WEBHOOK DUPLICADO (POST /payments/webhook)")
    print("=" * 70)
    print(f"Status HTTP das 2 respostas: {statuses}")
    print(f"Corpo das respostas: {bodies}")
    print(f"E-mails de ingresso enviados: {emails_sent} (esperado: 1)")
    print(f"payment_status final do participante: {final_participant.payment_status.value}")
    veredito = "OK: sem duplicacao de e-mail, estado consistente" if consistent else "FALHOU: comportamento inconsistente"
    print(f">>> {veredito}")
    print("=" * 70)


if __name__ == "__main__":
    main()
