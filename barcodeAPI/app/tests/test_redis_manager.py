import pytest
from unittest.mock import AsyncMock, Mock
from datetime import datetime
import pytz
from app.models import User
from app.redis_manager import RedisManager

@pytest.fixture
def mock_redis():
    return AsyncMock()

@pytest.fixture
def mock_db():
    return AsyncMock()

@pytest.fixture
def redis_manager(mock_redis):
    return RedisManager(mock_redis)

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
    mock_result = Mock()
    mock_result.scalars = Mock()
    mock_result.scalars.return_value.all.return_value = [mock_usage]
    mock_db.execute= Mock(return_value=mock_result)

    # Mock Redis pipeline
    mock_pipeline= Mock()
    mock_pipeline.execute= Mock()
    redis_manager.redis.pipeline.return_value= Mock()
    redis_manager.redis.pipeline.return_value.__aenter__= Mock(return_value=mock_pipeline)
    redis_manager.redis.pipeline.return_value.__aexit__= Mock(return_value=None)

    # Execute sync
    await redis_manager.sync_db_to_redis(mock_db)

    # Verify Redis operations
    await mock_pipeline.hset.assert_called_once()
    await mock_pipeline.execute.assert_called_once()
@pytest.mark.asyncio
async def test_sync_db_to_redis_empty_data(redis_manager, mock_db):
    # Mock empty DB results
    mock_db.execute.return_value.scalars.return_value.all.return_value = []

    # Mock Redis pipeline
    mock_pipeline= Mock()
    redis_manager.redis.pipeline.return_value.__aenter__.return_value = mock_pipeline
    mock_pipeline.execute= Mock()

    # Execute sync
    await redis_manager.sync_db_to_redis(mock_db)

    # Verify no Redis operations occurred
    mock_pipeline.hmset.assert_not_called()
    mock_pipeline.execute.assert_called_once()

@pytest.mark.asyncio
async def test_sync_all_username_mappings(redis_manager, mock_db):
    # Mock User data
    mock_user = Mock(
        tier="authenticated",
        api_key=None
    )
    # Mock DB query results
    mock_results= Mock()
    mock_results.scalars= Mock()
    mock_results.scalars.return_value= Mock()
    mock_results.scalars.return_value.all= Mock(return_value=[mock_user])
    mock_db.execute= Mock(return_value=mock_results)
    mock_results.scalars.return_value.all.return_value = [mock_user]
    mock_db.execute.return_value = mock_results
    # Mock Redis pipeline
    mock_pipeline= Mock()
    redis_manager.redis.pipeline.return_value.__aenter__.return_value = mock_pipeline
    mock_pipeline.execute= Mock()

    # Execute sync
    await redis_manager.sync_all_username_mappings(mock_db)

    # Verify Redis operations
    mock_pipeline.hmset.assert_called_once()
    mock_pipeline.execute.assert_called_once()

@pytest.mark.asyncio
async def test_sync_db_to_redis_error_handling(redis_manager, mock_db):
    # Mock DB error
    mock_db.execute= Mock(side_effect=Exception("Database error"))

    # Execute sync and check error handling
    with pytest.raises(Exception) as exc_info:
        await redis_manager.sync_db_to_redis(mock_db)

    assert str(exc_info.value) == "Database error"

@pytest.mark.asyncio
async def test_token_management_operations(redis_manager):
    # Test adding token
    mock_pipeline= Mock()
    redis_manager.redis.pipeline.return_value.__aenter__.return_value = mock_pipeline
    redis_manager.redis.pipeline.return_value.__aexit__= Mock(return_value=None)
    mock_pipeline.hset= Mock()
    mock_pipeline.expire= Mock()
    mock_pipeline.execute= Mock(return_value=[1, 1])  # Both operations successful

    result = await redis_manager.token_management(1, "add", "test_token", 3600)
    assert result is True

    # Test getting token
    redis_manager.redis.hget= Mock(return_value=b"test_token")
    result = await redis_manager.token_management(1, "get")
    assert result == "test_token"

    # Test removing token
    redis_manager.redis.hdel= Mock(return_value=1)
    result = await redis_manager.token_management(1, "remove")
    assert result is True

    # Test checking token
    redis_manager.redis.hget= Mock(return_value=b"test_token")
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
    mock_pipeline= AsyncMock()
    redis_manager.redis.pipeline.return_value.__aenter__.return_value = mock_pipeline
    mock_pipeline.execute= AsyncMock()

    # Mock Redis info
    redis_manager.redis.info= AsyncMock(return_value={"connected_clients": 1})

    # Execute cleanup
    await redis_manager.cleanup_redis_keys()

    # Verify Redis operations
    assert redis_manager.redis.type.call_count == 4
    mock_pipeline.delete.assert_called()
    mock_info = {
        "connected_clients": 1,
        "used_memory_human": "1M",
        "total_connections_received": 100,
        "total_commands_processed": 1000
    }
    redis_manager.redis.info= AsyncMock(return_value=mock_info)
    redis_manager.redis.type= AsyncMock(side_effect=[b'string', b'hash', b'string', b'hash'])

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

@pytest.mark.asyncio
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

    redis_manager.redis.eval = AsyncMock(return_value=mock_user_data)

    # Mock DB query results
    mock_result= AsyncMock()
    mock_result.scalars = AsyncMock()
    mock_result.scalars.return_value = AsyncMock()
    mock_result.scalars.return_value.all = AsyncMock(return_value=[])
    mock_db.execute= AsyncMock(return_value=mock_result)

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
        requests_today=0,
        remaining_requests=100,
        last_request=current_time,
        ip_address='192.186.1.1'
    )

    # Mock DB query results
    mock_results= AsyncMock()
    mock_results.scalars= AsyncMock()
    mock_results.scalars.return_value= AsyncMock()
    mock_results.scalars.return_value.all= AsyncMock(side_effect=[[existing_user], []])
    mock_db.execute= AsyncMock(return_value=mock_results)

    # Mock DB query results
    mock_db.execute.return_value.scalars.return_value.all.side_effect = [
        [existing_user],  # Users query
        []  # Usages query
    ]

    mock_results= AsyncMock()
    mock_results.scalars.return_value.all.side_effect = [
        [existing_user],  # Users query
        []  # Usages query
    ]
    mock_db.execute.return_value = mock_results

    # Execute sync
    await redis_manager.sync_redis_to_db(mock_db)

    # Verify DB operations
    assert mock_db.add.called
    mock_db.commit.assert_called_once()

@pytest.mark.asyncio
async def test_sync_redis_to_db_data_conversion(redis_manager, mock_db):
    # Mock Redis data with various data types
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