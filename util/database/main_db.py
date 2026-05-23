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

    async def add_url_subscription(
        self, chat_id: int, url: str, user_id: int, chat_name: str
    ) -> bool:
        """Subscribe a chat to an RSS feed."""
        # Ensure the URL is registered
        if not await self.exists(f"url:^{url}^"):
            await self.redis.hset(f"url:^{url}^", mapping={
                "last_update": "2000-01-01 00:00:00+00:00",
                "last_url": "",
            })

        # Check if subscription already exists
        key = f"user_url:{user_id}:chat_id:{chat_id}:^{url}^"
        if await self.exists(key):
            return False

        # Create subscription
        mapping = {
            "chat_id": str(chat_id),
            "chat_name": chat_name,
            "user_id": str(user_id),
            "disable": "False",
        }
        result = await self.redis.hset(key, mapping=mapping)
        return result is not None

    async def remove_url_for_chat(self, chat_id: int, url: str) -> bool:
        """Remove a URL subscription for a chat."""
        names = await self._find(f"user_url:*chat_id:{chat_id}*{url}*")
        if not names:
            return False

        deleted_count = 0
        for name in names:
            deleted = await self.redis.delete(name)
            if deleted:
                deleted_count += 1

        return deleted_count > 0

    async def get_chat_urls(self, chat_id: int) -> list[str]:
        """Get all active RSS feed URLs for a chat."""
        names = await self._find(f"user_url:*chat_id:{chat_id}*")
        urls = set()

        for name in names:
            disable_status = await self.redis.hget(name, "disable")
            if disable_status != "True" and "^" in name:
                url = name.split("^")[1]
                urls.add(url)

        return sorted(list(urls))

    async def get_chats_for_url(self, url: str) -> list[dict]:
        """Get all chats subscribed to a specific URL with their info."""
        names = await self._find(f"user_url:*:^{url}^")
        chats = []
        seen_chat_ids = set()

        for name in names:
            disable_status = await self.redis.hget(name, "disable")
            if disable_status != "True":
                chat_data = await self.redis.hgetall(name)
                chat_id = int(chat_data.get("chat_id", 0))
                # Avoid duplicates (a URL might have multiple user subscriptions per chat)
                if chat_id not in seen_chat_ids:
                    chats.append({
                        "chat_id": chat_id,
                        "chat_name": chat_data.get("chat_name", ""),
                    })
                    seen_chat_ids.add(chat_id)

        return chats

    async def update_url_metadata(self, url: str, last_update: str, last_url: str) -> bool:
        """Update URL metadata (last_update, last_url)."""
        key = f"url:^{url}^"
        result = await self.redis.hset(
            key,
            mapping={"last_update": last_update, "last_url": last_url}
        )
        return result is not None

    async def get_url_metadata(self, url: str) -> dict | None:
        """Get URL metadata."""
        key = f"url:^{url}^"
        if not await self.exists(key):
            return None
        return await self.redis.hgetall(key)

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
