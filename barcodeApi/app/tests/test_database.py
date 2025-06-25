import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool
from app.config import settings
from unittest import mock
from sqlalchemy.orm import sessionmaker
from app.database import (
    get_db,
    init_db,
    close_db_connection,
    Base,
    engine,
    AsyncSessionLocal
)


@pytest.fixture
async def mock_engine():
    async_engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=AsyncAdaptedQueuePool
    )
    yield async_engine
    await async_engine.dispose()

@pytest.mark.asyncio
async def test_get_db():
    async for session in get_db():
        assert isinstance(session, AsyncSession)
        assert session.is_active

    # Test exception for get_db
    with mock.patch("app.database.AsyncSessionLocal") as mock_session:
        mock_session.side_effect = Exception("Error")
        with pytest.raises(Exception):
            async for session in get_db():
                pass

def test_base_declarative():
    assert hasattr(Base, 'metadata')
    assert Base.metadata.tables == {}

@pytest.mark.asyncio
async def test_init_db():
    await init_db()
    async with engine.begin() as conn:
        result = await conn.run_sync(Base.metadata.create_all)
        assert result is None  # create_all returns None on success

@pytest.mark.asyncio
async def test_close_db_connection():
    await close_db_connection()
    assert engine.pool is None  # After dispose, pool should be None


@pytest.mark.asyncio
async def test_engine_configuration():
    assert isinstance(engine.pool, AsyncAdaptedQueuePool)

@pytest.mark.asyncio
async def test_session_maker_configuration():
    async with AsyncSessionLocal() as session:
        assert isinstance(session, AsyncSession)
        assert session.autoflush is False
