"""Teste sequencial (sem concorrencia) de regras de negocio de vagas/duplicata.

Cobre 3 comportamentos, contra um backend local isolado (SQLite descartavel,
nao toca no banco de dev nem em producao/Railway):

  1. Evento com capacidade EXATA de 3: 3 cadastros sequenciais devem passar,
     o 4o deve ser rejeitado com uma mensagem clara.
  2. Os 3 cadastros acima nunca tem o pagamento confirmado (a API nao tem
     "confirmar no cadastro" -- isso e um PATCH admin separado) -- ou seja,
     o mesmo teste acima ja responde "vaga pendente conta pro limite?"
     diretamente: se o 4o e bloqueado com 0 pagamentos PAID, pendente conta.
  3. GET /participants/check-duplicate: mesmo email + whatsapp diferente, e
     whatsapp igual + email diferente, devem ambos disparar duplicate=true
     (confirma que a checagem e OR, nao AND); um par totalmente diferente
     deve dar duplicate=false (controle negativo).
  4. TTL de inscricao pendente (PENDING_REGISTRATION_TTL, 20 min): um
     pendente "velho" (created_at simulado como > 20 min atras) nao deve
     mais contar para a capacidade -- registra 1 pendente velho + 3 novos
     num evento de capacidade 3 e confirma que os 3 novos passam (o velho
     foi ignorado) mas um 5o e rejeitado. Depois roda o job de expiracao
     (services/expiration_service.py) direto e confirma que o registro
     velho vira EXPIRED de fato no banco.

Uso (a partir da raiz do projeto, usa o Python do venv do backend):
    backend/venv/Scripts/python.exe backend/test_capacity_duplicate.py
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

TEST_SECRET_KEY = "capacity-duplicate-test-secret"
TEST_DB_PATH = SCRIPT_DIR / "test_capacity_duplicate.db"
TEST_LOG_PATH = SCRIPT_DIR / "test_capacity_duplicate_server.log"

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["SECRET_KEY"] = TEST_SECRET_KEY
for _key in ("MP_ACCESS_TOKEN", "MP_PUBLIC_KEY", "MP_WEBHOOK_SECRET", "RESEND_API_KEY", "PORTARIA_SECRET_KEY"):
    os.environ[_key] = ""

import httpx  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
import app.models  # noqa: E402  (registra as tabelas em Base.metadata)
from app.models.event import Event  # noqa: E402
from app.models.participant import (  # noqa: E402
    PENDING_REGISTRATION_TTL,
    Participant,
    PaymentMethod,
    PaymentStatus,
)
from app.services.expiration_service import expire_stale_pending_participants  # noqa: E402


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _setup_database() -> tuple[int, int, int, int]:
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        capacity_event = Event(
            name="[TESTE] Capacidade exata",
            date=dt.date(2026, 11, 21),
            time=dt.time(20, 0, 0),
            location="Local de teste",
            max_capacity=3,
            ticket_price=Decimal("150.00"),
            is_active=True,
        )
        duplicate_event = Event(
            name="[TESTE] Deteccao de duplicata",
            date=dt.date(2026, 11, 21),
            time=dt.time(20, 0, 0),
            location="Local de teste",
            max_capacity=50,
            ticket_price=Decimal("150.00"),
            is_active=True,
        )
        ttl_event = Event(
            name="[TESTE] TTL de pendente",
            date=dt.date(2026, 11, 21),
            time=dt.time(20, 0, 0),
            location="Local de teste",
            max_capacity=3,
            ticket_price=Decimal("150.00"),
            is_active=True,
        )
        db.add_all([capacity_event, duplicate_event, ttl_event])
        db.commit()
        db.refresh(capacity_event)
        db.refresh(duplicate_event)
        db.refresh(ttl_event)

        # Simula um checkout abandonado: pendente criado ha mais que o TTL,
        # inserido direto no banco (created_at nao e aceito no payload da
        # API -- e sempre "agora" via server_default).
        stale_created_at = dt.datetime.now(dt.timezone.utc) - PENDING_REGISTRATION_TTL - dt.timedelta(minutes=5)
        stale_participant = Participant(
            event_id=ttl_event.id,
            name="Pendente Abandonado",
            email="pendente.velho@example.com",
            whatsapp="5583966000000",
            payment_method=PaymentMethod.PIX,
            payment_status=PaymentStatus.PENDING,
            created_at=stale_created_at,
        )
        db.add(stale_participant)
        db.commit()
        db.refresh(stale_participant)

        return capacity_event.id, duplicate_event.id, ttl_event.id, stale_participant.id
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


def _register(client: httpx.Client, api: str, event_id: int, idx: int) -> httpx.Response:
    payload = {
        "name": f"Participante {idx}",
        "email": f"cap.teste.{idx}@example.com",
        "whatsapp": f"5583988{idx:06d}",
        "payment_method": "pix",
    }
    return client.post(f"{api}/participants/", params={"event_id": event_id}, json=payload)


def run_tests(
    base_url: str,
    capacity_event_id: int,
    duplicate_event_id: int,
    ttl_event_id: int,
    stale_participant_id: int,
) -> dict:
    api = f"{base_url}/api/v1"
    report: dict = {}

    # ---- Testes 1 e 2: capacidade exata de 3, cadastros sequenciais nunca pagos ----
    with httpx.Client(timeout=10.0) as client:
        first_three = [_register(client, api, capacity_event_id, i) for i in range(1, 4)]
        fourth = _register(client, api, capacity_event_id, 4)

    payment_statuses = [r.json()["payment_status"] for r in first_three if r.status_code == 201]

    report["capacity_and_pending"] = {
        "first_three_status_codes": [r.status_code for r in first_three],
        "first_three_payment_status": payment_statuses,
        "fourth_status_code": fourth.status_code,
        "fourth_body": fourth.json() if fourth.headers.get("content-type", "").startswith("application/json") else fourth.text,
        "all_three_accepted": all(r.status_code == 201 for r in first_three),
        "all_three_remained_pending": all(s == "pending" for s in payment_statuses),
        "fourth_rejected": fourth.status_code == 400,
        "pending_counts_toward_capacity": fourth.status_code == 400 and all(s == "pending" for s in payment_statuses),
    }

    # ---- Teste 3: deteccao de duplicata (OR, nao AND) ----
    with httpx.Client(timeout=10.0) as client:
        base_email = "duplicata.teste@example.com"
        base_whatsapp = "5583977000001"

        original = client.post(
            f"{api}/participants/",
            params={"event_id": duplicate_event_id},
            json={
                "name": "Original",
                "email": base_email,
                "whatsapp": base_whatsapp,
                "payment_method": "pix",
            },
        )

        same_email_diff_whatsapp = client.get(
            f"{api}/participants/check-duplicate",
            params={"event_id": duplicate_event_id, "email": base_email, "whatsapp": "5583977999999"},
        )
        same_whatsapp_diff_email = client.get(
            f"{api}/participants/check-duplicate",
            params={"event_id": duplicate_event_id, "email": "outro.email@example.com", "whatsapp": base_whatsapp},
        )
        neither_matches = client.get(
            f"{api}/participants/check-duplicate",
            params={"event_id": duplicate_event_id, "email": "totalmente.diferente@example.com", "whatsapp": "5583900000000"},
        )

    report["duplicate_detection"] = {
        "original_registration_status": original.status_code,
        "same_email_diff_whatsapp": same_email_diff_whatsapp.json(),
        "same_whatsapp_diff_email": same_whatsapp_diff_email.json(),
        "neither_matches_control": neither_matches.json(),
        "email_match_alone_triggers_duplicate": same_email_diff_whatsapp.json().get("duplicate") is True,
        "whatsapp_match_alone_triggers_duplicate": same_whatsapp_diff_email.json().get("duplicate") is True,
        "is_or_not_and": (
            same_email_diff_whatsapp.json().get("duplicate") is True
            and same_whatsapp_diff_email.json().get("duplicate") is True
        ),
        "negative_control_correct": neither_matches.json().get("duplicate") is False,
    }

    # ---- Teste 4a: pendente "velho" (> TTL) nao conta pra capacidade ----
    # ttl_event ja tem 1 pendente com created_at simulado como TTL+5min
    # atras (inserido direto no banco em _setup_database, ANTES do servidor
    # subir). Se ele estiver sendo ignorado corretamente pela query de
    # capacidade, 3 cadastros novos ainda cabem (o velho nao ocupa nenhuma
    # das 3 vagas) e so o 4o novo estoura a capacidade. Nota: o app real
    # tambem roda o scheduler (services/expiration_service.py) no startup,
    # entao esse pendente pode ja ter sido marcado EXPIRED automaticamente
    # antes desse teste rodar -- tanto faz para esta asserção, ja que a
    # query de capacidade ignora tanto "pending vencido" quanto "expired".
    with httpx.Client(timeout=10.0) as client:
        three_fresh = [_register(client, api, ttl_event_id, 100 + i) for i in range(1, 4)]
        fourth_fresh = _register(client, api, ttl_event_id, 104)

    report["ttl_exemption"] = {
        "three_fresh_status_codes": [r.status_code for r in three_fresh],
        "three_fresh_all_accepted": all(r.status_code == 201 for r in three_fresh),
        "fourth_fresh_status_code": fourth_fresh.status_code,
        "fourth_fresh_rejected": fourth_fresh.status_code == 400,
        "stale_pending_ignored_by_capacity_check": (
            all(r.status_code == 201 for r in three_fresh) and fourth_fresh.status_code == 400
        ),
    }

    # ---- Teste 4b: o job de expiracao realmente marca o registro no banco ----
    # Insere um SEGUNDO pendente velho agora (depois que o servidor ja
    # subiu e ja rodou seu primeiro ciclo automatico do scheduler -- o
    # proximo ciclo automatico so acontece em 5min, entao nao ha corrida
    # com esta chamada manual) e chama o servico diretamente para confirmar
    # que ele vira EXPIRED de fato, nao so fica mascarado na contagem.
    db = SessionLocal()
    try:
        stale_created_at = (
            dt.datetime.now(dt.timezone.utc) - PENDING_REGISTRATION_TTL - dt.timedelta(minutes=5)
        )
        job_test_participant = Participant(
            event_id=ttl_event_id,
            name="Pendente Para Job",
            email="pendente.job@example.com",
            whatsapp="5583955000000",
            payment_method=PaymentMethod.PIX,
            payment_status=PaymentStatus.PENDING,
            created_at=stale_created_at,
        )
        db.add(job_test_participant)
        db.commit()
        db.refresh(job_test_participant)
        job_test_participant_id = job_test_participant.id

        status_before_job = job_test_participant.payment_status.value
        expired_count = expire_stale_pending_participants(db)
        db.expire_all()
        status_after_job = db.get(Participant, job_test_participant_id).payment_status.value
    finally:
        db.close()

    report["expiration_job"] = {
        "status_before_job": status_before_job,
        "expire_job_flipped_count": expired_count,
        "status_after_job": status_after_job,
        "job_correctly_expired_stale_row": (
            status_before_job == "pending" and expired_count >= 1 and status_after_job == "expired"
        ),
    }

    return report


def _print_report(report: dict) -> None:
    import json

    t12 = report["capacity_and_pending"]
    t3 = report["duplicate_detection"]
    t4a = report["ttl_exemption"]
    t4b = report["expiration_job"]

    print("\n" + "=" * 70)
    print("RELATORIO - CAPACIDADE EXATA / VAGA PENDENTE / DUPLICATA")
    print("=" * 70)

    print("\n[1+2] Evento com capacidade=3, 3 cadastros sequenciais (nunca pagos)")
    print(f"    Status HTTP dos 3 primeiros: {t12['first_three_status_codes']}")
    print(f"    payment_status dos 3: {t12['first_three_payment_status']}")
    print(f"    4o cadastro -> HTTP {t12['fourth_status_code']}: {t12['fourth_body']}")
    print(f"    3 aceitos: {t12['all_three_accepted']} | todos ficaram 'pending': {t12['all_three_remained_pending']}")
    print(f"    4o rejeitado: {t12['fourth_rejected']}")
    veredito = (
        "vaga PENDENTE CONTA para o limite (bloqueia o 4o mesmo com 0 pagos)"
        if t12["pending_counts_toward_capacity"]
        else "vaga pendente NAO bloqueou o 4o (inesperado dado o codigo atual)"
    )
    print(f"    >>> {veredito}")

    print("\n[3] GET /participants/check-duplicate (email OU whatsapp)")
    print(f"    Mesmo email, whatsapp diferente -> {t3['same_email_diff_whatsapp']}")
    print(f"    Mesmo whatsapp, email diferente -> {t3['same_whatsapp_diff_email']}")
    print(f"    Nenhum dos dois bate (controle) -> {t3['neither_matches_control']}")
    veredito3 = "confirmado: e OR (qualquer um dos dois campos sozinho ja dispara)" if t3["is_or_not_and"] else "FALHOU: nao se comportou como OR"
    print(f"    >>> {veredito3}")
    if not t3["negative_control_correct"]:
        print("    >>> ATENCAO: controle negativo tambem deu duplicate=true (falso positivo)")

    print("\n[4a] TTL de pendente (20min): 1 pendente velho + 3 novos em evento cap=3")
    print(f"    3 novos -> HTTP {t4a['three_fresh_status_codes']}")
    print(f"    4o novo -> HTTP {t4a['fourth_fresh_status_code']}")
    veredito4a = (
        "confirmado: pendente vencido (>20min) foi IGNORADO na contagem de vagas"
        if t4a["stale_pending_ignored_by_capacity_check"]
        else "FALHOU: pendente vencido ainda esta ocupando vaga"
    )
    print(f"    >>> {veredito4a}")

    print("\n[4b] Job de expiracao marca o pendente vencido como EXPIRED no banco")
    print(f"    status antes: {t4b['status_before_job']} | qtd expirada pelo job: {t4b['expire_job_flipped_count']} | status depois: {t4b['status_after_job']}")
    veredito4b = (
        "confirmado: job flipou o registro para 'expired'"
        if t4b["job_correctly_expired_stale_row"]
        else "FALHOU: registro nao foi expirado corretamente"
    )
    print(f"    >>> {veredito4b}")

    print("\n" + "-" * 70)
    print("JSON bruto:")
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    print("=" * 70)


def main() -> None:
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    print("Preparando banco de teste isolado (3 eventos: capacidade=3, capacidade=50 e TTL)...")
    capacity_event_id, duplicate_event_id, ttl_event_id, stale_participant_id = _setup_database()

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
        report = run_tests(
            base_url, capacity_event_id, duplicate_event_id, ttl_event_id, stale_participant_id
        )
        _print_report(report)
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
