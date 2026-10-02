"""
Script para insertar el usuario inicial en la base de datos.

Uso:
    cd Backend-Sistema-web-Detencion-ACS
    python -m db.seed

Requiere que las variables de entorno de conexión a la BD estén configuradas
(vía .env o variables de entorno del sistema).
"""

import bcrypt
from sqlalchemy import text

from app.db.session import SessionLocal

DEFAULT_USERNAME = "Administrador"
DEFAULT_PASSWORD = "Admin12"
DEFAULT_NOMBRE = "Administrador"
DEFAULT_EMAIL = "admin@apneacare.com"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def seed_usuario():
    db = SessionLocal()
    try:
        existing = db.execute(
            text("SELECT id FROM public.usuarios WHERE username = :username"),
            {"username": DEFAULT_USERNAME},
        ).first()

        if existing:
            print(f"El usuario '{DEFAULT_USERNAME}' ya existe (id={existing[0]}). No se inserta duplicado.")
            return

        password_hash = hash_password(DEFAULT_PASSWORD)

        db.execute(
            text(
                """
                INSERT INTO public.usuarios (username, password_hash, nombre, email, activo)
                VALUES (:username, :password_hash, :nombre, :email, TRUE)
                """
            ),
            {
                "username": DEFAULT_USERNAME,
                "password_hash": password_hash,
                "nombre": DEFAULT_NOMBRE,
                "email": DEFAULT_EMAIL,
            },
        )
        db.commit()
        print(f"Usuario '{DEFAULT_USERNAME}' insertado exitosamente en la BD.")
    except Exception as exc:
        db.rollback()
        print(f"Error al insertar usuario: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_usuario()
