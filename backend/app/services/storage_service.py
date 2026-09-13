from __future__ import annotations

import mimetypes
import uuid

import httpx

from app.core.config import settings


class StorageNotConfiguredError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY)


def _headers() -> dict[str, str]:
    return {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY or "",
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
    }


def upload_event_banner(
    event_id: int, content_type: str, data: bytes
) -> tuple[str, str]:
    """Uploads banner bytes to Supabase Storage.

    Returns (public_url, storage_path). storage_path is what
    delete_event_banner needs later to remove this exact object.
    """
    if not is_configured():
        raise StorageNotConfiguredError(
            "Upload de imagem nao configurado no servidor "
            "(SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY ausentes)"
        )

    ext = mimetypes.guess_extension(content_type) or ""
    if ext == ".jpe":
        ext = ".jpg"
    storage_path = f"events/{event_id}/banner-{uuid.uuid4().hex}{ext}"

    base_url = (settings.SUPABASE_URL or "").rstrip("/")
    bucket = settings.SUPABASE_STORAGE_BUCKET
    upload_url = f"{base_url}/storage/v1/object/{bucket}/{storage_path}"

    response = httpx.post(
        upload_url,
        headers={**_headers(), "Content-Type": content_type, "x-upsert": "true"},
        content=data,
        timeout=30.0,
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"Falha ao enviar imagem para o Supabase Storage: "
            f"{response.status_code} {response.text}"
        )

    public_url = f"{base_url}/storage/v1/object/public/{bucket}/{storage_path}"
    return public_url, storage_path


def delete_event_banner(storage_path: str) -> None:
    """Best-effort cleanup of a previously uploaded banner.

    Never raises -- called right after a new banner already replaced this
    one, so a failure here (network blip, already-gone object) shouldn't
    surface as an error for an upload that otherwise succeeded.
    """
    if not is_configured() or not storage_path:
        return
    base_url = (settings.SUPABASE_URL or "").rstrip("/")
    bucket = settings.SUPABASE_STORAGE_BUCKET
    delete_url = f"{base_url}/storage/v1/object/{bucket}/{storage_path}"
    try:
        httpx.delete(delete_url, headers=_headers(), timeout=15.0)
    except httpx.HTTPError:
        pass
