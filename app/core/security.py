from datetime import datetime, timedelta
import logging
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


class TokenPayload(BaseModel):
    sub: str
    exp: int


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.jwt_access_token_expires_minutes))
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
    }
    logger.debug(f"Creando token JWT para subject='{subject}', expira en '{expire}'")
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> TokenPayload:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        logger.debug(f"Token JWT verificado correctamente para subject='{payload.get('sub')}'")
        return TokenPayload(**payload)
    except JWTError as exc:
        logger.warning(f"Fallo en verificación de token JWT: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict[str, str]:
    token_data = decode_access_token(token)
    return {"username": token_data.sub}

