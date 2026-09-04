from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.admin_user import AdminUser
from app.schemas.auth import AdminUserCreate, LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    admin = (
        db.query(AdminUser).filter(AdminUser.username == payload.username).first()
    )
    if admin is None or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario ou senha invalidos",
        )

    token = create_access_token({"sub": str(admin.id), "event_id": admin.event_id})
    return TokenResponse(access_token=token)


@router.post("/admin", status_code=status.HTTP_201_CREATED)
def create_admin(
    payload: AdminUserCreate,
    event_id: int,
    x_setup_key: str = Header(..., alias="X-Setup-Key"),
    db: Session = Depends(get_db),
) -> dict:
    if x_setup_key != settings.SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chave de configuracao invalida",
        )

    existing = (
        db.query(AdminUser).filter(AdminUser.username == payload.username).first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome de usuario ja esta em uso",
        )

    admin = AdminUser(
        event_id=event_id,
        username=payload.username,
        password_hash=hash_password(payload.password),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    return {"id": admin.id, "username": admin.username, "event_id": admin.event_id}
