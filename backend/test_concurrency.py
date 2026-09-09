"""Teste de concorrencia local (SQLite descartavel) para o evento de 21/11.

Sobe uma instancia isolada do backend (uvicorn, porta livre escolhida em
tempo de execucao) contra um arquivo SQLite descartavel (nao toca no banco
de dev nem em producao/Railway), cria um evento de teste com capacidade
baixa e dispara requisicoes concorrentes contra:

  1. POST /api/v1/participants/  -> checa overselling (vagas vendidas acima
     da capacidade configurada).
  2. PATCH /api/v1/participants/{id}/payment -> checa se dois "webhooks"
     duplicados marcando o mesmo participante como pago deixam o registro
     em estado inconsistente.

Uso (a partir da raiz do projeto, usa o Python do venv do backend):
    backend/venv/Scripts/python.exe backend/test_concurrency.py
    backend/venv/Scripts/python.exe backend/test_concurrency.py --capacity 5 --requests 12

O arquivo de banco de teste e o log do servidor sao apagados/fechados ao
final (a nao ser que --keep-db seja passado, util para inspecionar o estado
depois de uma corrida com resultado inesperado).
"""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)
sys.path.insert(0, str(SCRIPT_DIR))

TEST_SECRET_KEY = "concurrency-test-secret-do-not-use-in-prod"
TEST_DB_PATH = SCRIPT_DIR / "test_concurrency.db"
TEST_LOG_PATH = SCRIPT_DIR / "test_concurrency_server.log"

# DATABASE_URL/SECRET_KEY precisam estar no ambiente ANTES de qualquer import
# de app.* (pydantic-settings le o .env/ambiente na hora do import de
# app.core.config). As demais chaves opcionais sao zeradas para o processo
# do servidor de teste nao herdar segredos do .env local por acidente
# (env_ignore_empty=True faz "" ser tratado como "nao configurado").
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["SECRET_KEY"] = TEST_SECRET_KEY
for _key in ("MP_ACCESS_TOKEN", "MP_PUBLIC_KEY", "MP_WEBHOOK_SECRET", "RESEND_API_KEY", "PORTARIA_SECRET_KEY"):
    os.environ[_key] = ""

import httpx  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
import app.models  # noqa: E402  (registra as tabelas em Base.metadata)
from app.models.event import Event  # noqa: E402
from app.models.participant import Participant, PaymentStatus  # noqa: E402


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _setup_database(capacity: int) -> int:
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        import datetime as dt
        from decimal import Decimal

        event = Event(
            name="[TESTE] Confraternizacao concorrencia",
            date=dt.date(2026, 11, 21),
            time=dt.time(20, 0, 0),
            location="Local de teste",
            max_capacity=capacity,
            ticket_price=Decimal("150.00"),
            is_active=True,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event.id
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


def _query_participants(event_id: int) -> list[Participant]:
    db = SessionLocal()
    try:
        return (
            db.query(Participant)
            .filter(Participant.event_id == event_id)
            .order_by(Participant.id)
            .all()
        )
    finally:
        db.close()


async def _run_tests(base_url: str, event_id: int, n_requests: int, capacity: int) -> dict:
    import asyncio

    api = f"{base_url}/api/v1"
    report: dict = {}

    # ---- Teste 1: N inscricoes simultaneas contra um evento de capacidade baixa ----
    async with httpx.AsyncClient(timeout=30.0) as client:
        payloads = [
            {
                "name": f"Participante Teste {i}",
                "email": f"teste.concorrencia.{i}@example.com",
                "whatsapp": f"5583999{i:06d}",
                "payment_method": "pix",
            }
            for i in range(n_requests)
        ]

        async def _register(payload: dict):
            try:
                resp = await client.post(
                    f"{api}/participants/", params={"event_id": event_id}, json=payload
                )
                return resp.status_code, resp.text
            except Exception as error:  # noqa: BLE001 - queremos capturar qualquer falha de rede
                return None, repr(error)

        results = await asyncio.gather(*(_register(p) for p in payloads))

    accepted = [r for r in results if r[0] == 201]
    rejected_no_slots = [r for r in results if r[0] == 400]
    unexpected = [r for r in results if r[0] not in (201, 400)]

    db_participants = _query_participants(event_id)
    active_in_db = [p for p in db_participants if p.payment_status != PaymentStatus.EXPIRED]

    report["test1_registration"] = {
        "requests_sent": n_requests,
        "capacity": capacity,
        "accepted_201": len(accepted),
        "rejected_400_sem_vagas": len(rejected_no_slots),
        "unexpected_status": [(code, body[:200]) for code, body in unexpected],
        "rows_in_db": len(db_participants),
        "active_rows_in_db": len(active_in_db),
        "overselling": len(active_in_db) > capacity,
        "http_accepted_matches_db_rows": len(accepted) == len(active_in_db),
    }

    # ---- Teste 2: 2 PATCH /payment simultaneos no MESMO participante ----
    admin_payload = {"username": "teste_concorrencia_admin", "password": "senha-teste-123"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        bootstrap_resp = await client.post(
            f"{api}/auth/admin",
            params={"event_id": event_id},
            json=admin_payload,
            headers={"X-Setup-Key": TEST_SECRET_KEY},
        )
        if bootstrap_resp.status_code != 201:
            report["test2_payment"] = {
                "error": f"falha ao criar admin de teste: {bootstrap_resp.status_code} {bootstrap_resp.text}"
            }
            return report

        login_resp = await client.post(f"{api}/auth/login", json=admin_payload)
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        if not active_in_db:
            report["test2_payment"] = {"error": "nenhum participante disponivel (teste 1 rejeitou tudo)"}
            return report

        target_id = active_in_db[0].id

        async def _confirm_payment():
            try:
                resp = await client.patch(
                    f"{api}/participants/{target_id}/payment", headers=headers
                )
                return resp.status_code, resp.text
            except Exception as error:  # noqa: BLE001
                return None, repr(error)

        payment_results = await asyncio.gather(_confirm_payment(), _confirm_payment())

    db_after = _query_participants(event_id)
    target_after = next(p for p in db_after if p.id == target_id)
    rows_with_target_id = [p for p in db_after if p.id == target_id]

    report["test2_payment"] = {
        "target_participant_id": target_id,
        "responses": [(code, body[:200]) for code, body in payment_results],
        "both_succeeded_200": all(code == 200 for code, _ in payment_results),
        "any_500": any(code == 500 for code, _ in payment_results),
        "final_payment_status": target_after.payment_status.value,
        "duplicated_rows_for_same_id": len(rows_with_target_id) != 1,
        "consistent": (
            all(code == 200 for code, _ in payment_results)
            and target_after.payment_status == PaymentStatus.PAID
            and len(rows_with_target_id) == 1
        ),
    }
    return report


def _print_report(report: dict, n_requests: int, capacity: int) -> None:
    import json

    t1 = report.get("test1_registration", {})
    t2 = report.get("test2_payment", {})

    print("\n" + "=" * 70)
    print("RELATORIO - TESTE DE CONCORRENCIA (SQLite local, isolado)")
    print("=" * 70)

    print(f"\n[1] POST /participants/ - {n_requests} requisicoes simultaneas, capacidade={capacity}")
    if t1:
        print(f"    Aceitas (201):              {t1['accepted_201']}")
        print(f"    Rejeitadas por vagas (400): {t1['rejected_400_sem_vagas']}")
        print(f"    Status inesperado:          {len(t1['unexpected_status'])} {t1['unexpected_status']}")
        print(f"    Linhas no banco:            {t1['rows_in_db']} (ativas: {t1['active_rows_in_db']})")
        print(f"    HTTP aceitas == linhas no banco: {t1['http_accepted_matches_db_rows']}")
        veredito = "FALHOU: OVERSELLING DETECTADO" if t1["overselling"] else "OK: capacidade respeitada"
        print(f"    >>> {veredito}")
    else:
        print("    (sem dados)")

    print("\n[2] PATCH /participants/{id}/payment - 2 requisicoes simultaneas no mesmo participante")
    if "error" in t2:
        print(f"    ERRO: {t2['error']}")
    elif t2:
        print(f"    Participante alvo: {t2['target_participant_id']}")
        print(f"    Respostas: {t2['responses']}")
        print(f"    Ambas 200: {t2['both_succeeded_200']}  |  Algum 500: {t2['any_500']}")
        print(f"    Status final no banco: {t2['final_payment_status']}")
        print(f"    Linhas duplicadas para o mesmo id: {t2['duplicated_rows_for_same_id']}")
        veredito = "OK: estado consistente" if t2["consistent"] else "FALHOU: estado inconsistente"
        print(f"    >>> {veredito}")

    print("\n" + "-" * 70)
    print("JSON bruto:")
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capacity", type=int, default=2, help="max_capacity do evento de teste")
    parser.add_argument(
        "--requests", type=int, default=5, help="numero de inscricoes simultaneas no teste 1"
    )
    parser.add_argument(
        "--keep-db", action="store_true", help="nao apaga o SQLite de teste ao final (debug)"
    )
    args = parser.parse_args()

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    print(f"Preparando banco de teste isolado ({TEST_DB_PATH.name}), capacidade={args.capacity}...")
    event_id = _setup_database(args.capacity)

    print(f"Subindo backend de teste em {base_url} ...")
    log_file = open(TEST_LOG_PATH, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=SCRIPT_DIR,
        env=os.environ.copy(),
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    try:
        _wait_for_server(base_url, proc)
        print("Backend de teste no ar. Disparando requisicoes concorrentes...")

        import asyncio

        report = asyncio.run(_run_tests(base_url, event_id, args.requests, args.capacity))
        _print_report(report, args.requests, args.capacity)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        log_file.close()
        engine.dispose()
        if not args.keep_db:
            _cleanup_db_files()


def _cleanup_db_files() -> None:
    # No Windows o SQLite as vezes mantem o arquivo brevemente travado logo
    # apos o processo filho encerrar; tenta algumas vezes antes de desistir.
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
    still_there = [str(p) for p in paths if p.exists()]
    if still_there:
        print(f"Aviso: nao foi possivel apagar {still_there} (arquivo ainda travado); apague manualmente.")


if __name__ == "__main__":
    main()
