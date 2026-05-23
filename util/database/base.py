import logging
from decouple import config
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class BaseDatabase:
    """Base database handler for async Redis operations."""

    def __init__(self, db: int):
        """Initialize Redis connection parameters."""
        password = config("REDIS", default="")
        self.redis = Redis(
            host="localhost",
            port=6379,
            password=password or None,
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
