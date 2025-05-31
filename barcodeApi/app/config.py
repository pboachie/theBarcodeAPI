# app/config.py
import os

from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from app.schemas import BatchPriority
from sqlalchemy import engine_from_config, pool
from alembic.config import Config
from alembic import context
from typing import List, ClassVar

class Settings(BaseSettings):
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "thebarcodeapi")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    MASTER_API_KEY: str = os.getenv("MASTER_API_KEY", "")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/barcodeapi")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost")
    API_VERSION: str = os.getenv("APP_VERSION", "0.0.0-config-default")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_DIRECTORY: str = os.getenv("LOG_DIRECTORY", "logs")
    ROOT_PATH: str = os.getenv("ROOT_PATH", "/api/v1")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    SERVER_URL: str = os.getenv("SERVER_URL", "https://www.thebarcodeapi.com")
    RATE_LIMIT_WINDOW: ClassVar[int] = 60  # Window duration in seconds
    RATE_LIMIT_LIMIT: ClassVar[int] = 100  # Maximum number of requests within the window
    ALLOWED_HOSTS: ClassVar[List[str]] = [
        "thebarcodeapi.com",
        "*.thebarcodeapi.com"
    ]

    class Config:
        env_file = ".env"
        extra = "allow"

    @property
    def SYNC_DATABASE_URL(self) -> str:
        """Return a synchronous database URL for Alembic migrations"""
        if self.DATABASE_URL.startswith('postgresql+asyncpg'):
            return self.DATABASE_URL.replace('postgresql+asyncpg', 'postgresql')
        return self.DATABASE_URL

    class RateLimit:
        unauthenticated: int = 5000

        class Tier:
            unauthenticated: int = 5000
            basic: int = 10000
            standard: int = 15000
            premium: int = 50000

        @staticmethod
        def get_limit(tier: str) -> int:
            return getattr(Settings.RateLimit.Tier, tier, Settings.RateLimit.unauthenticated)


settings = Settings()

class OperationConfig:
    def __init__(self, priority: BatchPriority, max_batch_size: int):
        self.priority = priority
        self.max_batch_size = max_batch_size

def run_migrations_online() -> None:
    alembic_config = Config()
    configuration = alembic_config.get_section(alembic_config.config_ini_section)
    if configuration is None:
        raise ValueError("Alembic configuration section not found")
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    from app.database import Base
    target_metadata = Base.metadata

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()
