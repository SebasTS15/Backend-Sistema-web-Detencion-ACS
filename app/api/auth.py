from datetime import timedelta
import logging

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.repositories import get_usuario_by_username
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class AuthRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/token", response_model=TokenResponse)
def login_for_access_token(
    credentials: AuthRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    logger.info(f"Intento de autenticación para usuario: '{credentials.username}'")

    usuario = get_usuario_by_username(db, credentials.username)
    if usuario is None:
        logger.warning(f"Usuario '{credentials.username}' no encontrado en la BD.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    password_valid = bcrypt.checkpw(
        credentials.password.encode("utf-8"),
        usuario["password_hash"].encode("utf-8"),
    )
    if not password_valid:
        logger.warning(f"Password inválido para el usuario: '{credentials.username}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()
    access_token_expires = timedelta(minutes=settings.jwt_access_token_expires_minutes)
    access_token = create_access_token(
        subject=str(usuario["id"]),
        expires_delta=access_token_expires,
    )
    logger.info(f"Token JWT generado exitosamente para usuario: '{credentials.username}'")
    return TokenResponse(access_token=access_token)
