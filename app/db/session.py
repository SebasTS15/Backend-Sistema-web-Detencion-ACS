from collections.abc import Generator
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

logger.info(
    f"Creando Motor SQLAlchemy para BD '{settings.db_name}' en host '{settings.db_host}:{settings.db_port}'"
)
engine = create_engine(
    settings.get_database_url(),
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

