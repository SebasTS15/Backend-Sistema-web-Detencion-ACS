import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def check_database(db: Session) -> bool:
    db.execute(text("SELECT 1"))
    return True


def get_usuario(db: Session, usuario_id: int) -> dict[str, Any] | None:
    row = db.execute(
        text("SELECT * FROM public.usuarios WHERE id = :usuario_id"),
        {"usuario_id": usuario_id},
    ).mappings().first()
    return dict(row) if row else None


def insert_resultado(
    db: Session,
    *,
    usuario_id: int | None,
    paciente_id: str | None,
    prediccion: bool,
    probabilidad: float,
    clase: str,
    modelo: str,
    metadata: dict[str, Any],
) -> int | None:
    row = db.execute(
        text(
            """
            INSERT INTO public.resultados
                (usuario_id, paciente_id, prediccion, probabilidad, clase, modelo, metadata, created_at)
            VALUES
                (:usuario_id, :paciente_id, :prediccion, :probabilidad, :clase, :modelo, CAST(:metadata AS jsonb), NOW())
            RETURNING id
            """
        ),
        {
            "usuario_id": usuario_id,
            "paciente_id": paciente_id,
            "prediccion": prediccion,
            "probabilidad": probabilidad,
            "clase": clase,
            "modelo": modelo,
            "metadata": json.dumps(metadata),
        },
    ).first()
    db.commit()
    return int(row[0]) if row else None


def insert_historial_consulta(
    db: Session,
    *,
    usuario_id: int | None,
    endpoint: str,
    request: dict[str, Any],
    response: dict[str, Any],
) -> int | None:
    row = db.execute(
        text(
            """
            INSERT INTO public.historial_consultas
                (usuario_id, endpoint, request, response, created_at)
            VALUES
                (:usuario_id, :endpoint, CAST(:request AS jsonb), CAST(:response AS jsonb), NOW())
            RETURNING id
            """
        ),
        {
            "usuario_id": usuario_id,
            "endpoint": endpoint,
            "request": json.dumps(request),
            "response": json.dumps(response),
        },
    ).first()
    db.commit()
    return int(row[0]) if row else None


def list_resultados_by_usuario(db: Session, usuario_id: int, limit: int = 50) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT *
            FROM public.resultados
            WHERE usuario_id = :usuario_id
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"usuario_id": usuario_id, "limit": limit},
    ).mappings().all()
    return [dict(row) for row in rows]


def list_historial_by_usuario(db: Session, usuario_id: int, limit: int = 50) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT *
            FROM public.historial_consultas
            WHERE usuario_id = :usuario_id
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"usuario_id": usuario_id, "limit": limit},
    ).mappings().all()
    return [dict(row) for row in rows]
