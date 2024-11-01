# app/redis.py

from redis.asyncio import Redis, ConnectionPool
from app.config import settings
from app.redis_manager import RedisManager
import logging

logger = logging.getLogger(__name__)

# Configure connection pool with appropriate settings
redis_pool = ConnectionPool.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
    max_connections=500,
    health_check_interval=30,
    socket_timeout=10,
    db=1
)

# Initialize Redis client
redis = Redis(connection_pool=redis_pool)

# Initialize RedisManager with the Redis client
redis_manager = RedisManager(redis)

async def get_redis_manager() -> RedisManager:
    return redis_manager

async def initialize_redis_manager():
    logger.info("Starting Redis manager...")
    await redis_manager.start()
    logger.info("Redis manager started.")

async def close_redis_connection():
    await redis.close()
    await redis_pool.disconnect()
    logger.info("Redis connection closed")
