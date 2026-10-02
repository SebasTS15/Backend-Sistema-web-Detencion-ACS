import logging
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.schemas import ErrorResponse, ValidationErrorResponse

# Inicializar sistema de logs
setup_logging()
logger = logging.getLogger(__name__)

settings = get_settings()
cors_origins = settings.cors_origin_list

logger.info(f"Cargando aplicación: '{settings.app_name}' en entorno '{settings.app_env}'")

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials="*" not in cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"--> [HTTP IN] {request.method} {request.url.path} - Client: {client_ip}")

    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        logger.info(
            f"<-- [HTTP OUT] {request.method} {request.url.path} - "
            f"Status: {response.status_code} - Tiempo: {process_time:.2f}ms"
        )
        return response
    except Exception as exc:
        process_time = (time.time() - start_time) * 1000
        logger.error(
            f"<-- [HTTP ERR] {request.method} {request.url.path} - "
            f"Excepción no capturada: {exc} - Tiempo: {process_time:.2f}ms",
            exc_info=True,
        )
        raise exc


app.include_router(auth_router)
app.include_router(router)


@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger.warning(
        f"HTTPException [{exc.status_code}] en {request.method} {request.url.path}: {exc.detail}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(detail=exc.detail, code="http_error").model_dump(),
    )


@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]}
        for err in exc.errors()
    ]
    logger.warning(
        f"ValidationError [422] en {request.method} {request.url.path}: {errors}"
    )
    return JSONResponse(
        status_code=422,
        content=ValidationErrorResponse(detail=errors).model_dump(),
    )


@app.get("/")
def root() -> dict[str, str]:
    logger.info("Endpoint raíz '/' accedido")
    return {
        "message": "Backend FastAPI para deteccion de apnea central",
        "docs": "/docs",
        "health": "/api/v1/health",
    }

