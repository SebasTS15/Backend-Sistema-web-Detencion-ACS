import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.repositories import (
    check_database,
    get_usuario,
    insert_historial_consulta,
    insert_resultado,
    list_historial_by_usuario,
    list_resultados_by_usuario,
)
from app.db.session import get_db
from app.ml.file_parser import parse_signal_file
from app.ml.service import get_model_service
from app.schemas import ErrorResponse, HealthResponse, PredictResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    logger.info("Comprobando salud del sistema en /health...")
    database_status = "ok"
    try:
        check_database(db)
    except SQLAlchemyError as exc:
        logger.error(f"Error verificando la base de datos: {exc}")
        database_status = "error"

    model_loaded = True
    try:
        get_model_service()
    except Exception as exc:
        logger.error(f"Error verificando disponibilidad del modelo: {exc}")
        model_loaded = False

    logger.info(f"Salud comprobada: BD='{database_status}', modelo_cargado={model_loaded}")
    return HealthResponse(status="ok", database=database_status, model_loaded=model_loaded)


@router.post(
    "/predict",
    response_model=PredictResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def predict(
    archivo: UploadFile = File(...),
    usuario_id: int | None = Form(None),
    paciente_id: str | None = Form(None),
    metadata: str | None = Form(None),
    normalize: bool = Form(True),
    guardar_resultado: bool = Form(True),
    guardar_historial: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: dict[str, str] = Depends(get_current_user),
) -> PredictResponse:
    logger.info(
        f"Petición de predicción recibida por user_id={current_user.get('user_id')}: "
        f"archivo='{archivo.filename}', usuario_id={usuario_id}, paciente_id='{paciente_id}', "
        f"normalize={normalize}, guardar_resultado={guardar_resultado}, guardar_historial={guardar_historial}"
    )

    if usuario_id is not None and get_usuario(db, usuario_id) is None:
        logger.warning(f"Rechazando predicción: usuario_id={usuario_id} no existe en la base de datos.")
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    try:
        logger.info(f"Iniciando parseo de señales del archivo: '{archivo.filename}'")
        signals, file_metadata = parse_signal_file(archivo)

        if metadata:
            try:
                metadata_dict = json.loads(metadata)
                if not isinstance(metadata_dict, dict):
                    raise ValueError("metadata debe ser un objeto JSON.")
            except ValueError as exc:
                logger.warning(f"JSON inválido en parámetro metadata: {exc}")
                raise ValueError("metadata debe ser un JSON válido.") from exc
        else:
            metadata_dict = {}

        logger.info("Ejecutando inferencia con el modelo ResNet...")
        prediction = get_model_service().predict(signals, normalize=normalize)
    except ValueError as exc:
        logger.warning(f"Error de validación al procesar la predicción: {exc}")
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Error no controlado al ejecutar el modelo ML: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error ejecutando el modelo: {exc}") from exc

    response_data: dict[str, Any] = {**prediction, "resultado_id": None, "historial_id": None}

    try:
        if guardar_resultado:
            logger.info("Guardando registro de resultado en BD...")
            response_data["resultado_id"] = insert_resultado(
                db,
                usuario_id=usuario_id,
                paciente_id=paciente_id,
                prediccion=prediction["prediccion"],
                probabilidad=prediction["probabilidad"],
                clase=prediction["clase"],
                modelo=prediction["modelo"],
                metadata={**metadata_dict, **file_metadata, "preprocessing": prediction["preprocessing"]},
            )

        if guardar_historial:
            logger.info("Guardando registro de consulta en el historial de BD...")
            response_data["historial_id"] = insert_historial_consulta(
                db,
                usuario_id=usuario_id,
                endpoint="/api/v1/predict",
                request={
                    "usuario_id": usuario_id,
                    "paciente_id": paciente_id,
                    "metadata": metadata_dict,
                    "normalize": normalize,
                    "guardar_resultado": guardar_resultado,
                    "guardar_historial": guardar_historial,
                    "file_name": archivo.filename,
                },
                response=response_data,
            )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(f"Error al guardar resultado o historial en PostgreSQL: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error guardando en PostgreSQL: {exc}") from exc

    logger.info(
        f"Proceso de predicción completado exitosamente. "
        f"resultado_id={response_data['resultado_id']}, historial_id={response_data['historial_id']}"
    )
    return PredictResponse(**response_data)


@router.get(
    "/usuarios/{usuario_id}",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    current_user: dict[str, str] = Depends(get_current_user),
) -> dict[str, Any]:
    logger.info(f"Usuario user_id={current_user.get('user_id')} solicita info de usuario ID={usuario_id}")
    data = get_usuario(db, usuario_id)
    if data is None:
        logger.warning(f"Usuario ID={usuario_id} no encontrado.")
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return data


@router.get(
    "/usuarios/{usuario_id}/resultados",
    responses={401: {"model": ErrorResponse}},
)
def resultados_usuario(
    usuario_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: dict[str, str] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    logger.info(f"Usuario user_id={current_user.get('user_id')} consulta resultados de usuario ID={usuario_id} (limit={limit})")
    return list_resultados_by_usuario(db, usuario_id, limit=limit)


@router.get(
    "/usuarios/{usuario_id}/historial",
    responses={401: {"model": ErrorResponse}},
)
def historial_usuario(
    usuario_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: dict[str, str] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    logger.info(f"Usuario user_id={current_user.get('user_id')} consulta historial de usuario ID={usuario_id} (limit={limit})")
    return list_historial_by_usuario(db, usuario_id, limit=limit)

