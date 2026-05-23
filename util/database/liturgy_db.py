from util.database.base import BaseDatabase


class LiturgyDatabase(BaseDatabase):
    """Database handler for the liturgy bot (daily subscriptions, audio cache)."""

    async def add_daily_liturgy_subscription(
        self, chat_id: int, chat_name: str, user_id: int
    ) -> bool:
        """Subscribe a user to daily liturgy."""
        pass

    async def remove_daily_liturgy_subscription(self, chat_id: int) -> bool:
        """Unsubscribe a user from daily liturgy."""
        pass

    async def get_active_subscriptions(self) -> list[int]:
        """Retrieve all active subscriber chat IDs."""
        pass

    async def get_deactivated_subscriptions(self) -> list[int]:
        """Retrieve all deactivated subscriber chat IDs."""
        pass

    async def activate_all_subscriptions(self) -> bool:
        """Activate all liturgy subscriptions."""
        pass

    async def set_last_send(self, chat_id: int) -> bool:
        """Update last_send timestamp for a subscription."""
        pass

    async def cache_audio_file_id(self, date: str, file_id: str) -> bool:
        """Cache Telegram audio file_id for reuse."""
        pass

    async def get_cached_audio_file_id(self, date: str) -> str | None:
        """Retrieve cached audio file_id."""
        pass

    async def list_admins(self) -> list[str]:
        """Retrieve list of admin user IDs for liturgy bot."""
        return await self.redis.lrange("admins", 0, -1)
