# app/config.py
import os
from app.schemas import BatchPriority
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    MASTER_API_KEY: str = os.getenv("MASTER_API_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    REDIS_URL: str = os.getenv("REDIS_URL")
    API_VERSION: str = os.getenv("API_VERSION")

    @property
    def SYNC_DATABASE_URL(self) -> str:
        """Return a synchronous database URL for Alembic migrations"""
        if self.DATABASE_URL.startswith('postgresql+asyncpg'):
            return self.DATABASE_URL.replace('postgresql+asyncpg', 'postgresql')
        return self.DATABASE_URL

    class Config:
        env_file = ".env"

    class RateLimit:
        unauthenticated: int = 10000

        class Tier:
            unauthenticated: int = 10000
            basic: int = 50000
            standard: int = 150000
            premium: int = 500000

settings = Settings()

class OperationConfig:
    def __init__(self, priority: BatchPriority, max_batch_size: int):
        self.priority = priority
        self.max_batch_size = max_batch_size
