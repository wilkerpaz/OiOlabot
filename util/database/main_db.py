from util.database.base import BaseDatabase


class MainDatabase(BaseDatabase):
    """Database handler for the main bot (groups, RSS subscriptions)."""

    async def get_group_config(self, chat_id: int) -> dict | None:
        """Retrieve configuration for a group."""
        key = f"group:{chat_id}"
        if not await self.exists(key):
            return None
        return await self.redis.hgetall(key)

    async def set_group_config(self, chat_id: int, config: dict) -> bool:
        """Store group configuration."""
        key = f"group:{chat_id}"
        return await self.redis.hset(key, mapping=config) is not None

    async def get_urls_activated(self) -> list[str]:
        """Retrieve all active RSS feed URLs."""
        pass

    async def get_urls_deactivated(self) -> list[str]:
        """Retrieve all deactivated RSS feed URLs."""
        pass

    async def activate_all_urls(self) -> bool:
        """Activate all RSS feeds at once."""
        pass

    async def list_admins(self) -> list[str]:
        """Retrieve list of admin user IDs."""
        return await self.redis.lrange("admins", 0, -1)

    async def backup(self) -> bool:
        """Trigger a Redis backup."""
        pass
