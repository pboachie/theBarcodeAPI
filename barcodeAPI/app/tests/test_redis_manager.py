import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime
import pytz
from app.models import User

@pytest.mark.asyncio
async def test_sync_db_to_redis_successful(redis_manager, mock_db):
    # Mock Usage data
    mock_usage = Mock(
        user_id="1",
        user_identifier="test_user",
        ip_address="127.0.0.1",
        requests_today=10,
        remaining_requests=90,
        last_request=datetime.now(pytz.utc),
        last_reset=datetime.now(pytz.utc),
        tier="authenticated"
    )

    # Mock DB query results
    mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_usage]

    # Mock Redis pipeline
    mock_pipeline = AsyncMock()
    redis_manager.redis.pipeline.return_value.__aenter__.return_value = mock_pipeline
    mock_pipeline.execute = AsyncMock()

    # Execute sync
    await redis_manager.sync_db_to_redis(mock_db)

    # Verify Redis operations
    mock_pipeline.hmset.assert_called_once()
    mock_pipeline.execute.assert_called_once()

@pytest.mark.asyncio
async def test_sync_db_to_redis_empty_data(redis_manager, mock_db):
    # Mock empty DB results
    mock_db.execute.return_value.scalars.return_value.all.return_value = []

    # Mock Redis pipeline
    mock_pipeline = AsyncMock()
    redis_manager.redis.pipeline.return_value.__aenter__.return_value = mock_pipeline
    mock_pipeline.execute = AsyncMock()

    # Execute sync
    await redis_manager.sync_db_to_redis(mock_db)

    # Verify no Redis operations occurred
    mock_pipeline.hmset.assert_not_called()
    mock_pipeline.execute.assert_called_once()

@pytest.mark.asyncio
async def test_sync_all_username_mappings(redis_manager, mock_db):
    # Mock User data
    mock_user = Mock(
        id="1",
        username="test_user",
        tier="authenticated",
        api_key=None
    )

    # Mock DB query results
    mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_user]

    # Mock Redis pipeline
    mock_pipeline = AsyncMock()
    redis_manager.redis.pipeline.return_value.__aenter__.return_value = mock_pipeline
    mock_pipeline.execute = AsyncMock()

    # Execute sync
    await redis_manager.sync_all_username_mappings(mock_db)

    # Verify Redis operations
    mock_pipeline.hmset.assert_called_once()
    mock_pipeline.execute.assert_called_once()

@pytest.mark.asyncio
async def test_sync_db_to_redis_error_handling(redis_manager, mock_db):
    # Mock DB error
    mock_db.execute.side_effect = Exception("Database error")

    # Execute sync and check error handling
    with pytest.raises(Exception) as exc_info:
        await redis_manager.sync_db_to_redis(mock_db)

    assert str(exc_info.value) == "Database error"

@pytest.mark.asyncio
async def test_token_management_operations(redis_manager):
    # Test adding token
    mock_pipeline = AsyncMock()
    redis_manager.redis.pipeline.return_value.__aenter__.return_value = mock_pipeline
    mock_pipeline.execute.return_value = [1]  # Successful operation

    result = await redis_manager.token_management(1, "add", "test_token", 3600)
    assert result is True

    # Test getting token
    redis_manager.redis.hget.return_value = b"test_token"
    result = await redis_manager.token_management(1, "get")
    assert result == "test_token"

    # Test removing token
    redis_manager.redis.hdel.return_value = 1
    result = await redis_manager.token_management(1, "remove")
    assert result is True

    # Test checking token
    redis_manager.redis.hget.return_value = b"test_token"
    result = await redis_manager.token_management(1, "check", "test_token")
    assert result is True

@pytest.mark.asyncio
async def test_cleanup_redis_keys(redis_manager):
    # Mock Redis key operations
    redis_manager.redis.keys.side_effect = [
        ["ip:127.0.0.1", "ip:192.168.1.1"],  # IP keys
        ["user_data:1", "user_data:2"]  # User data keys
    ]
    redis_manager.redis.type.side_effect = [b'string', b'hash', b'string', b'hash']

    # Mock Redis pipeline
    mock_pipeline = AsyncMock()
    redis_manager.redis.pipeline.return_value.__aenter__.return_value = mock_pipeline
    mock_pipeline.execute = AsyncMock()

    # Execute cleanup
    await redis_manager.cleanup_redis_keys()

    # Verify Redis operations
    assert redis_manager.redis.type.call_count == 4
    mock_pipeline.delete.assert_called()

@pytest.mark.asyncio
async def test_get_metrics(redis_manager):
    # Mock Redis info
    redis_manager.redis.info.return_value = {
        "connected_clients": 1,
        "used_memory_human": "1M",
        "total_connections_received": 100,
        "total_commands_processed": 1000
    }

    # Mock connection pool
    redis_manager.redis.connection_pool.max_connections = 10
    redis_manager.redis.connection_pool._in_use_connections = set([1])
    redis_manager.redis.connection_pool._available_connections = set([2, 3])

    # Get metrics
    metrics = await redis_manager.get_metrics()

    # Verify metrics structure
    assert "redis" in metrics
    assert "connection_pool" in metrics
    assert "batch_processors" in metrics
    assert metrics["redis"]["connected_clients"] == 1
async def test_sync_redis_to_db_successful(redis_manager, mock_db):
    # Mock Redis data
    mock_user_data = [
        ['user_data', '1',
         ['username', 'test_user'],
         ['tier', 'authenticated'],
         ['ip_address', '127.0.0.1'],
         ['requests_today', '10'],
         ['remaining_requests', '90'],
         ['last_request', datetime.now(pytz.utc).isoformat()]
        ]
    ]
    redis_manager.redis.eval.return_value = mock_user_data

    # Mock DB query results
    mock_db.execute.return_value.scalars.return_value.all.side_effect = [[], []]

    # Execute sync
    await redis_manager.sync_redis_to_db(mock_db)

    # Verify Redis calls
    redis_manager.redis.eval.assert_called_once()

    # Verify DB operations
    assert mock_db.add_all.called
    assert mock_db.commit.called
    mock_db.close.assert_called_once()

@pytest.mark.asyncio
async def test_sync_redis_to_db_empty_data(redis_manager, mock_db):
    # Mock empty Redis data
    redis_manager.redis.eval.return_value = []

    # Execute sync
    await redis_manager.sync_redis_to_db(mock_db)

    # Verify no DB operations occurred
    mock_db.add_all.assert_not_called()
    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()

@pytest.mark.asyncio
async def test_sync_redis_to_db_error_handling(redis_manager, mock_db):
    # Mock Redis error
    redis_manager.redis.eval.side_effect = Exception("Redis error")

    # Execute sync and check error handling
    with pytest.raises(Exception) as exc_info:
        await redis_manager.sync_redis_to_db(mock_db)

    assert str(exc_info.value) == "Redis error"
    mock_db.close.assert_called_once()

@pytest.mark.asyncio
async def test_sync_redis_to_db_update_existing(redis_manager, mock_db):
    # Mock Redis data
    current_time = datetime.now(pytz.utc)
    mock_user_data = [
        ['user_data', '1',
         ['username', 'existing_user'],
         ['tier', 'authenticated'],
         ['ip_address', '127.0.0.1'],
         ['requests_today', '10'],
         ['remaining_requests', '90'],
         ['last_request', current_time.isoformat()]
        ]
    ]
    redis_manager.redis.eval.return_value = mock_user_data

    # Mock existing user in DB
    existing_user = User(
        id='1',
        username='existing_user',
        tier='free',
        requests_today=5,
        remaining_requests=95,
        last_request=current_time
    )

    # Mock DB query results
    mock_db.execute.return_value.scalars.return_value.all.side_effect = [
        [existing_user],  # Users query
        []  # Usages query
    ]

    # Execute sync
    await redis_manager.sync_redis_to_db(mock_db)

    # Verify user was updated
    assert mock_db.add.called
    mock_db.commit.assert_called_once()

@pytest.mark.asyncio
async def test_sync_redis_to_db_data_conversion(redis_manager, mock_db):
    # Mock Redis data with various data types
    current_time = datetime.now(pytz.utc)
    mock_user_data = [
        ['user_data', '1',
         ['username', 'test_user'],
         ['tier', 'authenticated'],
         ['requests_today', 'invalid'],  # Invalid integer
         ['remaining_requests', '90'],
         ['last_request', 'invalid_date'],  # Invalid date
         ['ip_address', '127.0.0.1']
        ]
    ]
    redis_manager.redis.eval.return_value = mock_user_data

    # Mock empty DB results
    mock_db.execute.return_value.scalars.return_value.all.side_effect = [[], []]

    # Execute sync
    await redis_manager.sync_redis_to_db(mock_db)

    # Verify sync completed without errors
    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()

@pytest.mark.asyncio
async def test_sync_redis_to_db_ip_keys(redis_manager, mock_db):
    # Mock Redis data with IP-based keys
    mock_user_data = [
        ['ip', '127.0.0.1',
         ['requests_today', '5'],
         ['remaining_requests', '95']
        ]
    ]
    redis_manager.redis.eval.return_value = mock_user_data

    # Execute sync
    await redis_manager.sync_redis_to_db(mock_db)

    # Verify IP-based keys were skipped
    mock_db.add_all.assert_not_called()
    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()

def test_redis_manager_initialization(mock_redis):
    manager = RedisManager(mock_redis)
    assert manager.redis == mock_redis
    assert manager.increment_usage_sha is None
    assert isinstance(manager.ip_cache, dict)