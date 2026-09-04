from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/public")
def get_public_config() -> dict:
    return {"mp_public_key": settings.MP_PUBLIC_KEY}
