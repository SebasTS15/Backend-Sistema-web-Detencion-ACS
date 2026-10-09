from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    usuario_id: int | None = None
    paciente_id: str | None = None
    signals: list[list[float]] = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    normalize: bool = True
    guardar_resultado: bool = True
    guardar_historial: bool = True


class PredictResponse(BaseModel):
    prediccion: bool
    probabilidad: float
    clase: str
    threshold: float
    modelo: str
    preprocessing: dict[str, Any]
    resultado_id: int | None = None
    historial_id: int | None = None


class ResultadoResponse(BaseModel):
    id: int
    usuario_id: int | None = None
    paciente_id: str | None = None
    prediccion: bool
    probabilidad: float
    clase: str
    modelo: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class HistorialResponse(BaseModel):
    id: int
    usuario_id: int | None = None
    endpoint: str
    request: dict[str, Any] = Field(default_factory=dict)
    response: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    database: str
    model_loaded: bool


class ErrorDetailItem(BaseModel):
    loc: list[Any]
    msg: str
    type: str


class ValidationErrorResponse(BaseModel):
    detail: list[ErrorDetailItem]
    code: str = "validation_error"


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None

