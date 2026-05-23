import logging
from util.database.base import BaseDatabase
from util.datehandler import DateHandler

logger = logging.getLogger(__name__)


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
        names = await self._find("user_url*")
        active_names = []
        for name in names:
            disable_status = await self.redis.hget(name, "disable")
            if disable_status != "True":
                active_names.append(name)

        # Extract URLs from key names (format: user_url:user_id:chat_id:^url^)
        urls = set()
        for name in active_names:
            # Extract URL from between ^ delimiters
            if "^" in name:
                url = name.split("^")[1]
                urls.add(url)
        return sorted(list(urls))

    async def get_urls_deactivated(self) -> list[str]:
        """Retrieve all deactivated RSS feed URLs."""
        names = await self._find("user_url*")
        deactivated_names = []
        for name in names:
            disable_status = await self.redis.hget(name, "disable")
            if disable_status == "True":
                deactivated_names.append(name)

        # Extract URLs from key names
        urls = set()
        for name in deactivated_names:
            if "^" in name:
                url = name.split("^")[1]
                urls.add(url)
        return sorted(list(urls))

    async def activate_all_urls(self) -> bool:
        """Activate all RSS feeds at once using pipeline."""
        names = await self._find("user_url*")
        if not names:
            return True

        async with self.redis.pipeline() as pipe:
            for name in names:
                pipe.hset(name, mapping={"disable": "False"})
            await pipe.execute()
        return True

    async def list_admins(self) -> list[str]:
        """Retrieve list of admin user IDs."""
        return await self.redis.lrange("admins", 0, -1)

    async def backup(self) -> bool:
        """Trigger a Redis backup if conditions are met."""
        now = DateHandler.get_datetime_now()

        last_backup_str = await self.redis.hget("backup", "last_backup")
        if not last_backup_str:
            # First backup
            await self.redis.hset("backup", mapping={"last_backup": str(now)})
            await self.redis.save()
            logger.info("Initial backup completed")
            return True

        last_backup = DateHandler.parse_datetime(last_backup_str)
        last_backup_date = DateHandler.date(last_backup)
        current_date = DateHandler.date(now)

        # Backup only once per day
        if current_date > last_backup_date:
            await self.redis.hset("backup", mapping={"last_backup": str(now)})
            await self.redis.save()
            logger.info("Daily backup completed")
            return True

        logger.debug(f"Backup already performed today ({current_date})")
        return False
