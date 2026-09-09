"""Teste sequencial (sem concorrencia) do fluxo de "retomar inscricao pendente".

Cobre o comportamento novo de POST /participants/ quando ja existe um
cadastro ativo (mesmo evento, mesmo e-mail OU whatsapp):

  1. PENDENTE dentro do TTL (20min): a segunda tentativa, com uma forma de
     pagamento diferente, NAO deve criar uma segunda linha -- deve devolver
     HTTP 200 (nao 201), reused=true, o MESMO id do cadastro original, e o
     payment_method deve ter sido atualizado para o recem-escolhido. Uma
     terceira tentativa com a MESMA forma de pagamento tambem deve reusar
     (reused=true) e nao alterar o payment_method.
  2. Confirma no banco que so existe UMA linha para aquele e-mail/whatsapp
     depois dessas tentativas (nao duplicou).
  3. PAGO: depois de marcar o cadastro como PAID (via PATCH admin), uma nova
     tentativa de cadastro com o mesmo e-mail/whatsapp continua BLOQUEADA
     com HTTP 400 -- este comportamento nao muda.

Uso (a partir da raiz do projeto, usa o Python do venv do backend):
    backend/venv/Scripts/python.exe backend/test_pending_resume.py
"""
from __future__ import annotations

import datetime as dt
import os
import socket
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)
sys.path.insert(0, str(SCRIPT_DIR))

TEST_SECRET_KEY = "pending-resume-test-secret"
TEST_DB_PATH = SCRIPT_DIR / "test_pending_resume.db"
TEST_LOG_PATH = SCRIPT_DIR / "test_pending_resume_server.log"

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["SECRET_KEY"] = TEST_SECRET_KEY
for _key in ("MP_ACCESS_TOKEN", "MP_PUBLIC_KEY", "MP_WEBHOOK_SECRET", "RESEND_API_KEY", "PORTARIA_SECRET_KEY"):
    os.environ[_key] = ""

import httpx  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
import app.models  # noqa: E402  (registra as tabelas em Base.metadata)
from app.core.security import hash_password  # noqa: E402
from app.models.admin_user import AdminUser  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.participant import Participant, PaymentStatus  # noqa: E402


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _setup_database() -> tuple[int, str, str]:
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        event = Event(
            name="[TESTE] Retomar pendente",
            date=dt.date(2026, 11, 21),
            time=dt.time(20, 0, 0),
            location="Local de teste",
            max_capacity=50,
            ticket_price=Decimal("150.00"),
            is_active=True,
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        admin_username = "admin_resume_test"
        admin_password = "senha-teste-123"
        admin = AdminUser(
            username=admin_username,
            password_hash=hash_password(admin_password),
            event_id=event.id,
        )
        db.add(admin)
        db.commit()

        return event.id, admin_username, admin_password
    finally:
        db.close()


def _wait_for_server(base_url: str, proc: subprocess.Popen, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"Servidor de teste encerrou prematuramente (exit code {proc.returncode}). "
                f"Veja {TEST_LOG_PATH}"
            )
        try:
            resp = httpx.get(f"{base_url}/health", timeout=1.0)
            if resp.status_code == 200:
                return
        except httpx.HTTPError as error:
            last_error = error
        time.sleep(0.3)
    raise RuntimeError(f"Servidor de teste nao respondeu a tempo. Ultimo erro: {last_error}")


def _cleanup_db_files() -> None:
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


def run_tests(base_url: str, event_id: int, admin_username: str, admin_password: str) -> dict:
    api = f"{base_url}/api/v1"
    report: dict = {}

    email = "retomar.teste@example.com"
    whatsapp = "5583999000001"

    with httpx.Client(timeout=10.0) as client:
        # ---- 1a tentativa: cadastro novo com Pix ----
        first = client.post(
            f"{api}/participants/",
            params={"event_id": event_id},
            json={
                "name": "Retomar Teste",
                "email": email,
                "whatsapp": whatsapp,
                "payment_method": "pix",
            },
        )
        first_body = first.json()

        # ---- 2a tentativa: mesmo e-mail, agora com Cartao (ainda pendente, dentro do TTL) ----
        second = client.post(
            f"{api}/participants/",
            params={"event_id": event_id},
            json={
                "name": "Retomar Teste",
                "email": email,
                "whatsapp": whatsapp,
                "payment_method": "card",
            },
        )
        second_body = second.json()

        # ---- 3a tentativa: mesmo e-mail, mesma forma de pagamento (card de novo) ----
        third = client.post(
            f"{api}/participants/",
            params={"event_id": event_id},
            json={
                "name": "Retomar Teste",
                "email": email,
                "whatsapp": whatsapp,
                "payment_method": "card",
            },
        )
        third_body = third.json()

    report["pending_resume"] = {
        "first_status_code": first.status_code,
        "first_reused": first_body.get("reused"),
        "first_payment_method": first_body.get("payment_method"),
        "second_status_code": second.status_code,
        "second_reused": second_body.get("reused"),
        "second_payment_method": second_body.get("payment_method"),
        "same_id_second": second_body.get("id") == first_body.get("id"),
        "third_status_code": third.status_code,
        "third_reused": third_body.get("reused"),
        "third_payment_method": third_body.get("payment_method"),
        "same_id_third": third_body.get("id") == first_body.get("id"),
        "first_created_new": first.status_code == 201 and first_body.get("reused") is False,
        "second_resumed_and_switched_method": (
            second.status_code == 200
            and second_body.get("reused") is True
            and second_body.get("payment_method") == "card"
        ),
        "third_resumed_same_method": (
            third.status_code == 200
            and third_body.get("reused") is True
            and third_body.get("payment_method") == "card"
        ),
    }

    # ---- Confirma que so existe UMA linha no banco para esse e-mail/whatsapp ----
    db = SessionLocal()
    try:
        rows = (
            db.query(Participant)
            .filter(Participant.event_id == event_id, Participant.email == email)
            .all()
        )
        row_count = len(rows)
        participant_id = rows[0].id if rows else None
        db_payment_method = rows[0].payment_method.value if rows else None
    finally:
        db.close()

    report["no_duplicate_row"] = {
        "row_count": row_count,
        "expected_1": row_count == 1,
        "db_payment_method_is_card": db_payment_method == "card",
    }

    # ---- Marca o cadastro como PAID via PATCH admin, depois confirma bloqueio ----
    with httpx.Client(timeout=10.0) as client:
        login = client.post(
            f"{api}/auth/login",
            json={"username": admin_username, "password": admin_password},
        )
        token = login.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        confirm_payment = client.patch(
            f"{api}/participants/{participant_id}/payment",
            params={"status": "paid"},
            headers=headers,
        )

        blocked_attempt = client.post(
            f"{api}/participants/",
            params={"event_id": event_id},
            json={
                "name": "Retomar Teste",
                "email": email,
                "whatsapp": whatsapp,
                "payment_method": "pix",
            },
        )
        blocked_body = (
            blocked_attempt.json()
            if blocked_attempt.headers.get("content-type", "").startswith("application/json")
            else blocked_attempt.text
        )

    report["paid_still_blocked"] = {
        "login_ok": login.status_code == 200,
        "confirm_payment_status_code": confirm_payment.status_code,
        "blocked_attempt_status_code": blocked_attempt.status_code,
        "blocked_attempt_body": blocked_body,
        "correctly_blocked": blocked_attempt.status_code == 400,
    }

    return report


def _print_report(report: dict) -> None:
    import json

    t1 = report["pending_resume"]
    t2 = report["no_duplicate_row"]
    t3 = report["paid_still_blocked"]

    print("\n" + "=" * 70)
    print("RELATORIO - RETOMAR CADASTRO PENDENTE (troca de forma de pagamento)")
    print("=" * 70)

    print("\n[1] 1a tentativa (Pix, cadastro novo)")
    print(f"    HTTP {t1['first_status_code']} | reused={t1['first_reused']} | payment_method={t1['first_payment_method']}")
    print("[1] 2a tentativa (mesmo e-mail, troca para Cartao)")
    print(f"    HTTP {t1['second_status_code']} | reused={t1['second_reused']} | payment_method={t1['second_payment_method']} | mesmo id: {t1['same_id_second']}")
    print("[1] 3a tentativa (mesmo e-mail, Cartao de novo)")
    print(f"    HTTP {t1['third_status_code']} | reused={t1['third_reused']} | payment_method={t1['third_payment_method']} | mesmo id: {t1['same_id_third']}")
    veredito1 = (
        "confirmado: pendente foi retomado (200 + reused=true) e o metodo de pagamento mudou"
        if t1["first_created_new"] and t1["second_resumed_and_switched_method"] and t1["third_resumed_same_method"]
        else "FALHOU: comportamento de retomada nao veio como esperado"
    )
    print(f"    >>> {veredito1}")

    print("\n[2] Linhas no banco para esse e-mail apos as 3 tentativas")
    print(f"    quantidade: {t2['row_count']} (esperado 1) | payment_method no banco: card? {t2['db_payment_method_is_card']}")
    veredito2 = "confirmado: nao duplicou" if t2["expected_1"] else "FALHOU: criou linha duplicada"
    print(f"    >>> {veredito2}")

    print("\n[3] Apos marcar como PAID, nova tentativa com mesmo e-mail")
    print(f"    login admin ok: {t3['login_ok']} | PATCH pagamento -> HTTP {t3['confirm_payment_status_code']}")
    print(f"    nova tentativa -> HTTP {t3['blocked_attempt_status_code']}: {t3['blocked_attempt_body']}")
    veredito3 = "confirmado: pago continua bloqueando (sem mudanca)" if t3["correctly_blocked"] else "FALHOU: pago nao bloqueou mais"
    print(f"    >>> {veredito3}")

    print("\n" + "-" * 70)
    print("JSON bruto:")
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    print("=" * 70)


def main() -> None:
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    print("Preparando banco de teste isolado (1 evento + 1 admin)...")
    event_id, admin_username, admin_password = _setup_database()

    print(f"Subindo backend de teste em {base_url} ...")
    log_file = open(TEST_LOG_PATH, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=SCRIPT_DIR,
        env=os.environ.copy(),
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    try:
        _wait_for_server(base_url, proc)
        print("Backend de teste no ar. Rodando cenarios sequenciais...")
        report = run_tests(base_url, event_id, admin_username, admin_password)
        _print_report(report)

        all_ok = (
            report["pending_resume"]["first_created_new"]
            and report["pending_resume"]["second_resumed_and_switched_method"]
            and report["pending_resume"]["third_resumed_same_method"]
            and report["no_duplicate_row"]["expected_1"]
            and report["paid_still_blocked"]["correctly_blocked"]
        )
        if not all_ok:
            sys.exit(1)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        log_file.close()
        engine.dispose()
        _cleanup_db_files()
        if TEST_LOG_PATH.exists():
            try:
                TEST_LOG_PATH.unlink()
            except PermissionError:
                pass


if __name__ == "__main__":
    main()
