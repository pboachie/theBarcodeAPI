import os
import pytest
from app.config import Settings, run_migrations_online
from dotenv import load_dotenv
from app.schemas import BatchPriority
from app.config import OperationConfig
from unittest.mock import patch, MagicMock
from alembic import context
from sqlalchemy import pool
from app.database import Base

load_dotenv()

# barcodeApi/app/tests/test_config.py

@pytest.fixture
def set_env_vars(monkeypatch):
    monkeypatch.setenv("PROJECT_NAME", "test_project")
    monkeypatch.setenv("SECRET_KEY", "test_secret")
    monkeypatch.setenv("MASTER_API_KEY", "test_master_api_key")
    monkeypatch.setenv("ALGORITHM", "HS512")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test_user:test_password@localhost:5432/test_db")
    monkeypatch.setenv("REDIS_URL", "redis://test_redis")
    monkeypatch.setenv("API_VERSION", "0.2.0")
    monkeypatch.setenv("ENVIRONMENT", "testing")
    monkeypatch.setenv("LOG_DIRECTORY", "test_logs")
    monkeypatch.setenv("ROOT_PATH", "/api/v2")
    monkeypatch.setenv("DB_PASSWORD", "test_db_password")
    monkeypatch.setenv("SERVER_URL", "https://test.thebarcodeapi.com")

@pytest.mark.usefixtures("set_env_vars")
def test_settings():
    settings = Settings()
    assert settings.PROJECT_NAME == "test_project"
    assert settings.SECRET_KEY == "test_secret"
    assert settings.MASTER_API_KEY == "test_master_api_key"
    assert settings.ALGORITHM == "HS512"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 60
    assert settings.DATABASE_URL == "postgresql://test_user:test_password@localhost:5432/test_db"
    assert settings.REDIS_URL == "redis://test_redis"
    assert settings.API_VERSION == "0.2.0"
    assert settings.ENVIRONMENT == "testing"
    assert settings.LOG_DIRECTORY == "test_logs"
    assert settings.ROOT_PATH == "/api/v2"
    assert settings.DB_PASSWORD == "test_db_password"
    assert settings.SERVER_URL == "https://test.thebarcodeapi.com"

def test_sync_database_url():
    settings = Settings(DATABASE_URL="postgresql+asyncpg://test_user:test_password@localhost:5432/test_db")
    assert settings.SYNC_DATABASE_URL == "postgresql://test_user:test_password@localhost:5432/test_db"

def test_sync_database_url_no_change():
    settings = Settings(DATABASE_URL="postgresql://test_user:test_password@localhost:5432/test_db")
    assert settings.SYNC_DATABASE_URL == "postgresql://test_user:test_password@localhost:5432/test_db"

def test_rate_limit():
    assert Settings.RateLimit.get_limit("unauthenticated") == 5000
    assert Settings.RateLimit.get_limit("basic") == 10000
    assert Settings.RateLimit.get_limit("standard") == 15000
    assert Settings.RateLimit.get_limit("premium") == 50000
    assert Settings.RateLimit.get_limit("nonexistent") == 5000

def test_operation_config():
    priority = BatchPriority.HIGH
    max_batch_size = 100
    operation_config = OperationConfig(priority=priority, max_batch_size=max_batch_size)

    assert operation_config.priority == priority
    assert operation_config.max_batch_size == max_batch_size

def test_operation_config_default():
    priority = BatchPriority.LOW
    max_batch_size = 50
    operation_config = OperationConfig(priority=priority, max_batch_size=max_batch_size)
    assert operation_config.priority == priority

def test_run_migrations_online():
    with patch("app.config.Config") as mock_config, \
            patch("app.config.engine_from_config") as mock_engine_from_config, \
            patch("app.config.context") as mock_context, \
            patch("app.database.Base.metadata") as mock_metadata:

        mock_alembic_config = MagicMock()
        mock_config.return_value = mock_alembic_config
        mock_alembic_config.get_section.return_value = {"sqlalchemy.url": "postgresql://test_user:test_password@localhost:5432/test_db"}

        mock_engine = MagicMock()
        mock_engine_from_config.return_value = mock_engine
        mock_connection = mock_engine.connect.return_value.__enter__.return_value

        run_migrations_online()

        mock_config.assert_called_once()
        mock_alembic_config.get_section.assert_called_once_with(mock_alembic_config.config_ini_section)
        mock_engine_from_config.assert_called_once_with(
            {"sqlalchemy.url": "postgresql://test_user:test_password@localhost:5432/test_db"},
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
        mock_engine.connect.assert_called_once()
        mock_context.configure.assert_called_once_with(connection=mock_connection, target_metadata=mock_metadata)
        mock_context.begin_transaction.assert_called_once()
        mock_context.run_migrations.assert_called_once()
