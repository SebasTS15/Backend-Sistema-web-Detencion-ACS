from pathlib import Path
import logging
import sys

base_log_dir = Path(__file__).resolve().parent.parent.parent / "logs"
base_log_dir.mkdir(exist_ok=True, parents=True)


def setup_logging(log_level: int = logging.INFO) -> None:
    """Configura el sistema de logging global para la aplicación."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    handlers = [
        logging.FileHandler(base_log_dir / "app.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]

    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=handlers,
        force=True,
    )

    # Silenciar o ajustar logs ruidosos de librerías de terceros
    logging.getLogger("paramiko").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

    init_logger = logging.getLogger("app.core.logging")
    init_logger.info(f"Sistema de logging inicializado. Archivo de log en: {base_log_dir / 'app.log'}")


logger = logging.getLogger("app")