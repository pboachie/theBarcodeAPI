from redis.asyncio import Redis, ConnectionPool
from app.config import settings
from app.redis_manager import RedisManager
import logging

logger = logging.getLogger(__name__)

redis_pool = ConnectionPool.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
    max_connections=500,
    health_check_interval=30,
    socket_timeout=5,
    db=1
)

redis = Redis(connection_pool=redis_pool)

redis_manager = RedisManager(redis)

async def get_redis_manager() -> RedisManager:
    return redis_manager

async def initialize_redis_manager():
    """Initialize Redis manager and batch processors"""
    logger.info("Initializing Redis manager...")
    try:
        await redis_manager.start()
        logger.info("Redis manager initialization complete")

        for priority, processor in redis_manager.batch_processor.processors.items():
            if not processor.running:
                logger.error(f"{priority} batch processor not running")
            else:
                logger.info(f"{priority} batch processor running")
    except Exception as e:
        logger.error(f"Failed to initialize Redis manager: {e}", exc_info=True)
        raise


async def close_redis_connection():
    await redis.close()
    await redis_pool.disconnect()
    logger.info("Redis connection closed")
