import logging

from util.database.base import BaseDatabase
from util.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class LiturgyJob:
    """Background job to send daily liturgy to subscribers."""

    def __init__(
        self, db: BaseDatabase, bot_token: str, scrapers: list
    ):
        """Initialize with database, bot token, and scrapers."""
        self.db = db
        self.bot_token = bot_token
        self.scrapers = scrapers

    async def run(self) -> None:
        """Execute the daily liturgy job."""
        logger.info(f"LiturgyJob running for token {self.bot_token[:10]}...")
        pass
