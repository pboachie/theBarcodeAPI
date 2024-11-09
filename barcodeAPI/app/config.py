# app/config.py
import os
from app.schemas import BatchPriority
from pydantic_settings import BaseSettings
from sqlalchemy import engine_from_config, pool
from alembic.config import Config
from alembic import context

class Settings(BaseSettings):
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    MASTER_API_KEY: str = os.getenv("MASTER_API_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    REDIS_URL: str = os.getenv("REDIS_URL")
    API_VERSION: str = os.getenv("API_VERSION")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    @property
    def SYNC_DATABASE_URL(self) -> str:
        """Return a synchronous database URL for Alembic migrations"""
        if self.DATABASE_URL.startswith('postgresql+asyncpg'):
            return self.DATABASE_URL.replace('postgresql+asyncpg', 'postgresql')
        return self.DATABASE_URL

    class Config:
        env_file = ".env"
        extra = "allow"

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
    configuration["sqlalchemy.url"] = settings.SYNC_DATABASE_URL
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
