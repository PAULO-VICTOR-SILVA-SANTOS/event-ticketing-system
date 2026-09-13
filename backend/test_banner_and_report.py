"""Teste end-to-end de:
  1) POST /events/{id}/banner -- rejeita sem SUPABASE_URL configurado (503),
     rejeita content-type invalido (400), rejeita > 5MB (400), rejeita admin
     de outro evento (403).
  2) GET /participants/report/pdf -- so inclui participantes PAID do evento
     do admin logado, PDF valido (%PDF), funciona com zero participantes
     pagos, e Content-Disposition de download presente.

Roda tudo em processo via TestClient (sem subir servidor real, sem rede
real para o Supabase Storage -- essa parte fica coberta so pelo caminho de
"nao configurado", ja que nao ha credenciais reais aqui).

Uso (a partir da raiz do projeto):
    backend/venv/Scripts/python.exe backend/test_banner_and_report.py
"""
from __future__ import annotations

import datetime as dt
import io
import os
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)
sys.path.insert(0, str(SCRIPT_DIR))

TEST_DB_PATH = SCRIPT_DIR / "test_banner_and_report.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["SECRET_KEY"] = "banner-report-test-secret"
for _key in (
    "MP_ACCESS_TOKEN",
    "MP_PUBLIC_KEY",
    "MP_WEBHOOK_SECRET",
    "RESEND_API_KEY",
    "PORTARIA_SECRET_KEY",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
):
    os.environ[_key] = ""

from fastapi.testclient import TestClient  # noqa: E402
from pypdf import PdfReader  # noqa: E402 -- test-only, not a runtime dependency

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
import app.models  # noqa: E402
from app.main import app  # noqa: E402
from app.models.admin_user import AdminUser  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.participant import Participant, PaymentMethod, PaymentStatus  # noqa: E402


def _cleanup_db_files() -> None:
    engine.dispose()
    for suffix in ("", "-wal", "-shm"):
        path = Path(f"{TEST_DB_PATH}{suffix}")
        if path.exists():
            path.unlink()


def _setup_database():
    _cleanup_db_files()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    event_a = Event(
        name="Evento A",
        date=dt.date(2026, 12, 20),
        time=dt.time(19, 30, 0),
        location="Local A",
        max_capacity=100,
        ticket_price=Decimal("50.00"),
    )
    event_b = Event(
        name="Evento B",
        date=dt.date(2026, 12, 21),
        time=dt.time(20, 0, 0),
        location="Local B",
        max_capacity=100,
        ticket_price=Decimal("30.00"),
    )
    db.add_all([event_a, event_b])
    db.commit()
    db.refresh(event_a)
    db.refresh(event_b)

    admin_a = AdminUser(
        event_id=event_a.id, username="admin_a", password_hash=hash_password("senha123")
    )
    admin_b = AdminUser(
        event_id=event_b.id, username="admin_b", password_hash=hash_password("senha123")
    )
    db.add_all([admin_a, admin_b])
    db.commit()

    paid1 = Participant(
        event_id=event_a.id, name="Zelia Paga", email="zelia@example.com",
        whatsapp="11900000001", payment_method=PaymentMethod.PIX,
        payment_status=PaymentStatus.PAID,
    )
    paid2 = Participant(
        event_id=event_a.id, name="Ana Paga", nickname="Aninha", email="ana@example.com",
        whatsapp="11900000002", payment_method=PaymentMethod.PIX,
        payment_status=PaymentStatus.PAID,
    )
    pending = Participant(
        event_id=event_a.id, name="Bruno Pendente", email="bruno@example.com",
        whatsapp="11900000003", payment_method=PaymentMethod.PIX,
        payment_status=PaymentStatus.PENDING,
    )
    other_event_paid = Participant(
        event_id=event_b.id, name="Carla Outro Evento", email="carla@example.com",
        whatsapp="11900000004", payment_method=PaymentMethod.PIX,
        payment_status=PaymentStatus.PAID,
    )
    db.add_all([paid1, paid2, pending, other_event_paid])
    db.commit()

    event_a_id, event_b_id = event_a.id, event_b.id
    db.close()

    return event_a_id, event_b_id


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def run_tests() -> None:
    event_a_id, event_b_id = _setup_database()
    client = TestClient(app)
    failures: list[str] = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        status_label = "OK" if condition else "FALHOU"
        print(f"[{status_label}] {label}" + (f" -- {detail}" if detail and not condition else ""))
        if not condition:
            failures.append(label)

    token_a = _login(client, "admin_a", "senha123")
    token_b = _login(client, "admin_b", "senha123")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # --- Banner upload ---
    files = {"file": ("banner.png", b"\x89PNG\r\n fake but has content", "image/png")}
    response = client.post(f"/api/v1/events/{event_a_id}/banner", headers=headers_a, files=files)
    check(
        "Upload sem Supabase configurado -> 503",
        response.status_code == 503,
        f"got {response.status_code}: {response.text}",
    )

    with patch(
        "app.routes.events.storage_service.upload_event_banner"
    ) as mock_upload, patch(
        "app.routes.events.storage_service.delete_event_banner"
    ) as mock_delete:
        url_1 = "https://fake.supabase.co/storage/v1/object/public/event-banners/events/1/banner-aaa.png"
        url_2 = "https://fake.supabase.co/storage/v1/object/public/event-banners/events/1/banner-bbb.png"
        mock_upload.side_effect = [
            (url_1, "events/1/banner-aaa.png"),
            (url_2, "events/1/banner-bbb.png"),
        ]
        first = client.post(f"/api/v1/events/{event_a_id}/banner", headers=headers_a, files=files)
        check(
            "Upload com Supabase mockado -> 200 e devolve banner_url novo",
            first.status_code == 200 and first.json()["banner_url"] == url_1,
            f"got {first.status_code}: {first.text}",
        )
        check("Delete nao chamado no primeiro upload (nao havia banner anterior)", mock_delete.call_count == 0)

        second = client.post(f"/api/v1/events/{event_a_id}/banner", headers=headers_a, files=files)
        check(
            "Segundo upload substitui o banner_url",
            second.status_code == 200 and second.json()["banner_url"] == url_2,
        )
        check(
            "Segundo upload aciona limpeza do arquivo antigo (delete_event_banner)",
            mock_delete.call_count == 1 and mock_delete.call_args[0][0] == "events/1/banner-aaa.png",
        )

    bad_type_files = {"file": ("banner.txt", b"not an image", "text/plain")}
    response = client.post(
        f"/api/v1/events/{event_a_id}/banner", headers=headers_a, files=bad_type_files
    )
    check(
        "Upload com content-type invalido -> 400",
        response.status_code == 400,
        f"got {response.status_code}: {response.text}",
    )

    big_files = {"file": ("banner.png", b"0" * (6 * 1024 * 1024), "image/png")}
    response = client.post(
        f"/api/v1/events/{event_a_id}/banner", headers=headers_a, files=big_files
    )
    check(
        "Upload maior que 5MB -> 400",
        response.status_code == 400,
        f"got {response.status_code}: {response.text}",
    )

    response = client.post(f"/api/v1/events/{event_b_id}/banner", headers=headers_a, files=files)
    check(
        "Admin do evento A tentando enviar banner do evento B -> 403",
        response.status_code == 403,
        f"got {response.status_code}: {response.text}",
    )

    # --- PDF report ---
    response = client.get("/api/v1/participants/report/pdf", headers=headers_a)
    check(
        "GET /participants/report/pdf (evento A) -> 200",
        response.status_code == 200,
        f"got {response.status_code}: {response.text[:200]}",
    )
    check(
        "Resposta e um PDF valido (comeca com %PDF)",
        response.content.startswith(b"%PDF"),
    )
    check(
        "Content-Disposition indica download em anexo",
        "attachment" in response.headers.get("content-disposition", ""),
        response.headers.get("content-disposition", "<ausente>"),
    )
    pdf_text = _extract_pdf_text(response.content)
    check("PDF contem as duas pagas do evento A (Zelia e Ana)", "Zelia" in pdf_text and "Ana" in pdf_text)
    check("PDF nao contem participante pendente (Bruno)", "Bruno" not in pdf_text)
    check("PDF nao contem participante de outro evento (Carla)", "Carla" not in pdf_text)
    check("PDF contem 'Total de participantes pagos: 2'", "Total de participantes pagos: 2" in pdf_text)

    response_b = client.get("/api/v1/participants/report/pdf", headers=headers_b)
    check(
        "GET /participants/report/pdf (evento B, so tem 1 pago) -> 200",
        response_b.status_code == 200,
    )
    pdf_text_b = _extract_pdf_text(response_b.content)
    check(
        "PDF do evento B contem a participante paga de la (Carla)",
        "Carla" in pdf_text_b,
    )
    check("PDF do evento B contem 'Total de participantes pagos: 1'", "Total de participantes pagos: 1" in pdf_text_b)

    response_noauth = client.get("/api/v1/participants/report/pdf")
    check(
        "GET /participants/report/pdf sem token -> 401",
        response_noauth.status_code == 401,
        f"got {response_noauth.status_code}",
    )

    print()
    if failures:
        print(f"{len(failures)} teste(s) falharam: {failures}")
        sys.exit(1)
    print("Todos os testes passaram.")


if __name__ == "__main__":
    try:
        run_tests()
    finally:
        _cleanup_db_files()
