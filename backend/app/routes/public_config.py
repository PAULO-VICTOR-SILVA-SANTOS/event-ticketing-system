from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.security import get_current_user
from app.models.admin_user import AdminUser

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/public")
def get_public_config() -> dict:
    return {"mp_public_key": settings.MP_PUBLIC_KEY}


@router.get("/status")
def get_config_status(current_admin: AdminUser = Depends(get_current_user)) -> dict:
    return {
        "mercadopago_access_token_configured": bool(settings.MP_ACCESS_TOKEN),
        "mercadopago_public_key_configured": bool(settings.MP_PUBLIC_KEY),
        "resend_configured": bool(settings.RESEND_API_KEY),
    }
