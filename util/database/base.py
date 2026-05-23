import logging
from decouple import config
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class BaseDatabase:
    """Base database handler for async Redis operations."""

    def __init__(self, db: int):
        """Initialize Redis connection parameters."""
        # Try REDIS_PASSWORD first (v2 format), fall back to REDIS (v1 format)
        password = config("REDIS_PASSWORD", default=None)
        if not password:
            password = config("REDIS", default=None)

        self.redis = Redis(
            host=config("REDIS_HOST", default="localhost"),
            port=int(config("REDIS_PORT", default=6379)),
            password=password,
            decode_responses=True,
            db=db,
        )

    async def _find(self, pattern: str) -> list[str]:
        """
        Find all keys matching a pattern using SCAN.

        Safe in production — never blocks the server.
        """
        return sorted({key async for key in self.redis.scan_iter(match=pattern)})

    async def exists(self, name: str) -> bool:
        """Check if a key exists."""
        return bool(await self.redis.exists(name))

    async def close(self) -> None:
        """Close the Redis connection."""
        await self.redis.aclose()
        logger.info("Redis connection closed")
