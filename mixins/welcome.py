import logging

from pyrogram import filters
from pyrogram.handlers import MessageHandler

logger = logging.getLogger(__name__)


class WelcomeMixin:
    """Mixin for welcome/goodbye message handlers."""

    def _register_welcome_handlers(self) -> None:
        """Register welcome/goodbye/permissions handlers."""
        self.client.add_handler(
            MessageHandler(self._on_new_chat_members, filters.new_chat_members)
        )
        self.client.add_handler(
            MessageHandler(self._on_left_chat_member, filters.left_chat_member)
        )

    async def _on_new_chat_members(self, client, message):
        """Handle new members joining."""
        pass

    async def _on_left_chat_member(self, client, message):
        """Handle members leaving."""
        pass

    async def set_welcome(self, client, message):
        """Set welcome message."""
        pass

    async def set_goodbye(self, client, message):
        """Set goodbye message."""
        pass

    async def disable_welcome(self, client, message):
        """Disable welcome messages."""
        pass

    async def disable_goodbye(self, client, message):
        """Disable goodbye messages."""
        pass

    async def lock_settings(self, client, message):
        """Lock settings to admin only."""
        pass

    async def unlock_settings(self, client, message):
        """Allow all users to change settings."""
        pass

    async def quiet_mode(self, client, message):
        """Enable quiet mode (suppress error messages)."""
        pass

    async def unquiet_mode(self, client, message):
        """Disable quiet mode."""
        pass
