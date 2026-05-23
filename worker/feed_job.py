import logging

from util.database.base import BaseDatabase

logger = logging.getLogger(__name__)


class FeedJob:
    """Background job to distribute RSS feeds to subscribers."""

    def __init__(self, db: BaseDatabase, bot_token: str):
        """Initialize with database and bot token."""
        self.db = db
        self.bot_token = bot_token

    async def run(self) -> None:
        """Execute the feed distribution job."""
        logger.info(f"FeedJob starting for token {self.bot_token[:10]}...")
        pass
