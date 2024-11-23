# app/database.py

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool
from app.config import settings
import logging
import gc

logger = logging.getLogger(__name__)

DATABASE_URL = settings.DATABASE_URL
ASYNC_DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')

# Synchronous engine for Alembic
sync_engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Asynchronous engine for the application
engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_size=20,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600,  # 1 hour
    pool_pre_ping=True,
    poolclass=AsyncAdaptedQueuePool,
    echo=False  # Set to True for SQL query logging
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def close_db_connection():
    await engine.dispose()
    logger.debug("Database connections closed")
    gc.collect()