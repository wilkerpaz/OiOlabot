import logging

from bots.base import BaseBot
from factories.base import BotFactory
from mixins.welcome import WelcomeMixin
from mixins.feed import FeedMixin

logger = logging.getLogger(__name__)


class MainBot(WelcomeMixin, FeedMixin, BaseBot):
    """Main bot: welcome messages and RSS feed management."""

    def register_handlers(self) -> None:
        """Register all handlers for the main bot."""
        self._register_welcome_handlers()
        self._register_feed_handlers()
        self._register_admin_handlers()

    def _register_admin_handlers(self) -> None:
        """Register admin-only commands."""
        pass
