import logging

from pyrogram import filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler

logger = logging.getLogger(__name__)


class LiturgyMixin:
    """Mixin for daily liturgy handlers."""

    def _register_liturgy_handlers(self) -> None:
        """Register liturgy-specific handlers."""
        self.client.add_handler(
            MessageHandler(self.today_liturgy, filters.command("hoje"))
        )
        self.client.add_handler(
            MessageHandler(self.yesterday_liturgy, filters.command("ontem"))
        )
        self.client.add_handler(
            MessageHandler(self.tomorrow_liturgy, filters.command("amanha"))
        )
        self.client.add_handler(
            MessageHandler(self.sunday_liturgy, filters.command("dominical"))
        )
        self.client.add_handler(
            MessageHandler(self.saint_of_day, filters.command("santododia"))
        )
        self.client.add_handler(
            MessageHandler(self.show_calendar, filters.command("calendario"))
        )
        self.client.add_handler(
            CallbackQueryHandler(self.handle_calendar_selection)
        )

    async def today_liturgy(self, client, message):
        """Send today's liturgy."""
        pass

    async def yesterday_liturgy(self, client, message):
        """Send yesterday's liturgy."""
        pass

    async def tomorrow_liturgy(self, client, message):
        """Send tomorrow's liturgy."""
        pass

    async def sunday_liturgy(self, client, message):
        """Send Sunday's liturgy."""
        pass

    async def saint_of_day(self, client, message):
        """Send saint of the day."""
        pass

    async def show_calendar(self, client, message):
        """Show date selection calendar."""
        pass

    async def handle_calendar_selection(self, client, callback_query):
        """Handle calendar date selection."""
        pass

    async def start_daily_delivery(self, client, message):
        """Enable daily liturgy delivery."""
        pass

    async def stop_daily_delivery(self, client, message):
        """Disable daily liturgy delivery."""
        pass
