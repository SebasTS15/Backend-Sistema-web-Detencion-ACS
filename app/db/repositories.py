import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def check_database(db: Session) -> bool:
    logger.debug("Ejecutando verificación de salud de la base de datos (SELECT 1)...")
    db.execute(text("SELECT 1"))
    logger.debug("Verificación de base de datos exitosa.")
    return True


def get_usuario(db: Session, usuario_id: int) -> dict[str, Any] | None:
    logger.debug(f"Buscando usuario ID={usuario_id} en la base de datos...")
    row = db.execute(
        text("SELECT * FROM public.usuarios WHERE id = :usuario_id"),
        {"usuario_id": usuario_id},
    ).mappings().first()
    if row:
        logger.debug(f"Usuario ID={usuario_id} encontrado.")
    else:
        logger.debug(f"Usuario ID={usuario_id} no existe en la BD.")
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
    logger.info(
        f"Insertando nuevo resultado en BD: usuario_id={usuario_id}, paciente_id='{paciente_id}', "
        f"prediccion={prediccion}, probabilidad={probabilidad:.4f}, clase='{clase}'"
    )
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
    resultado_id = int(row[0]) if row else None
    logger.info(f"Resultado insertado exitosamente con ID={resultado_id}")
    return resultado_id


def insert_historial_consulta(
    db: Session,
    *,
    usuario_id: int | None,
    endpoint: str,
    request: dict[str, Any],
    response: dict[str, Any],
) -> int | None:
    logger.info(f"Insertando historial de consulta en BD: endpoint='{endpoint}', usuario_id={usuario_id}")
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
    historial_id = int(row[0]) if row else None
    logger.info(f"Historial de consulta insertado exitosamente con ID={historial_id}")
    return historial_id


def list_resultados_by_usuario(db: Session, usuario_id: int, limit: int = 50) -> list[dict[str, Any]]:
    logger.info(f"Consultando resultados en BD para usuario_id={usuario_id} (limit={limit})")
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
    logger.info(f"Obtenidos {len(rows)} resultados para usuario_id={usuario_id}")
    return [dict(row) for row in rows]


def list_historial_by_usuario(db: Session, usuario_id: int, limit: int = 50) -> list[dict[str, Any]]:
    logger.info(f"Consultando historial en BD para usuario_id={usuario_id} (limit={limit})")
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
    logger.info(f"Obtenidos {len(rows)} registros de historial para usuario_id={usuario_id}")
    return [dict(row) for row in rows]

