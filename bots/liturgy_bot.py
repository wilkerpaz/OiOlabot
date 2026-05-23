import logging

from bots.base import BaseBot
from factories.base import BotFactory
from mixins.welcome import WelcomeMixin
from mixins.feed import FeedMixin
from mixins.liturgy import LiturgyMixin

logger = logging.getLogger(__name__)


class LiturgyBot(WelcomeMixin, FeedMixin, LiturgyMixin, BaseBot):
    """Liturgy bot: daily readings, homily, saint of the day."""

    def register_handlers(self) -> None:
        """Register all handlers for the liturgy bot."""
        self._register_welcome_handlers()
        self._register_feed_handlers()
        self._register_liturgy_handlers()
        self._register_admin_handlers()

    def _register_admin_handlers(self) -> None:
        """Register admin-only commands."""
        pass
