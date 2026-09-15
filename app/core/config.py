from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Backend Tesis Apnea"
    app_env: str = "development"

    model_path: Path
    model_threshold: float = Field(default=0.3, ge=0.0, le=1.0)

    # La conexión se compone desde variables separadas.
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "DB_Sistema_Deteccion_ACS"
    db_user: str = "postgres"
    db_password: str
    db_sslmode: str = "require"

    cors_origins: str = "*"

    jwt_secret_key: str = Field(
        description="Clave secreta para firmar los JWT.",
    )

    jwt_algorithm: str = "HS256"
    jwt_access_token_expires_minutes: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_database_url(self) -> str:
        """Retorna la URL de conexión a la base de datos."""
        return (
            "postgresql+psycopg://"
            f"{quote_plus(self.db_user)}:{quote_plus(self.db_password)}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?sslmode={quote_plus(self.db_sslmode)}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
