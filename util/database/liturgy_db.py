import logging
from util.database.base import BaseDatabase
from util.datehandler import DateHandler

logger = logging.getLogger(__name__)


class LiturgyDatabase(BaseDatabase):
    """Database handler for the liturgy bot (daily subscriptions, audio cache)."""

    async def add_daily_liturgy_subscription(
        self, chat_id: int, chat_name: str, user_id: int
    ) -> bool:
        """Subscribe a user to daily liturgy."""
        key = f"daily_liturgy:user_id:{user_id}:chat_id:{chat_id}"
        mapping = {
            "chat_id": str(chat_id),
            "chat_name": chat_name,
            "user_id": str(user_id),
            "disable": "False",
            "last_send": str(DateHandler.get_datetime_now()),
        }
        result = await self.redis.hset(key, mapping=mapping)
        return result is not None

    async def remove_daily_liturgy_subscription(self, chat_id: int) -> bool:
        """Unsubscribe a user from daily liturgy."""
        names = await self._find(f"daily_liturgy:*chat_id:{chat_id}*")
        if not names:
            return False

        deleted_count = 0
        for name in names:
            deleted = await self.redis.delete(name)
            if deleted:
                deleted_count += 1

        return deleted_count > 0

    async def get_active_subscriptions(self) -> list[int]:
        """Retrieve all active subscriber chat IDs."""
        names = await self._find("daily_liturgy:*")
        chat_ids = set()

        for name in names:
            disable_status = await self.redis.hget(name, "disable")
            if disable_status != "True":
                # Extract chat_id from key name (format: daily_liturgy:user_id:...:chat_id:xyz)
                parts = name.split(":")
                for i, part in enumerate(parts):
                    if part == "chat_id" and i + 1 < len(parts):
                        chat_ids.add(int(parts[i + 1]))
                        break

        return sorted(list(chat_ids))

    async def get_deactivated_subscriptions(self) -> list[int]:
        """Retrieve all deactivated subscriber chat IDs."""
        names = await self._find("daily_liturgy:*")
        chat_ids = set()

        for name in names:
            disable_status = await self.redis.hget(name, "disable")
            if disable_status == "True":
                # Extract chat_id from key name
                parts = name.split(":")
                for i, part in enumerate(parts):
                    if part == "chat_id" and i + 1 < len(parts):
                        chat_ids.add(int(parts[i + 1]))
                        break

        return sorted(list(chat_ids))

    async def activate_all_subscriptions(self) -> bool:
        """Activate all liturgy subscriptions using pipeline."""
        names = await self._find("daily_liturgy:*")
        if not names:
            return True

        async with self.redis.pipeline() as pipe:
            for name in names:
                pipe.hset(name, mapping={"disable": "False"})
            await pipe.execute()
        return True

    async def set_last_send(self, chat_id: int) -> bool:
        """Update last_send timestamp for a subscription."""
        names = await self._find(f"daily_liturgy:*chat_id:{chat_id}*")
        if not names:
            return False

        now = str(DateHandler.get_datetime_now())
        updated_count = 0
        for name in names:
            result = await self.redis.hset(name, mapping={"last_send": now})
            if result is not None:
                updated_count += 1

        return updated_count > 0

    async def cache_audio_file_id(self, date: str, file_id: str) -> bool:
        """Cache Telegram audio file_id for reuse."""
        result = await self.redis.hset("audio_liturgy", mapping={date: file_id})
        return result is not None

    async def get_cached_audio_file_id(self, date: str) -> str | None:
        """Retrieve cached audio file_id."""
        return await self.redis.hget("audio_liturgy", date)

    async def list_admins(self) -> list[str]:
        """Retrieve list of admin user IDs for liturgy bot."""
        return await self.redis.lrange("admins", 0, -1)
