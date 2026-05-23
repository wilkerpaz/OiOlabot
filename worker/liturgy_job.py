import logging
import httpx

from util.database.base import BaseDatabase
from util.scrapers.base import BaseScraper
from util.scrapers.liturgia import LiturgiaScraper
from util.datehandler import DateHandler
from worker.error_handler import ErrorHandler

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
        self.api_url = f"https://api.telegram.org/bot{bot_token}"

    async def run(self) -> None:
        """Execute the daily liturgy job."""
        logger.info(f"LiturgyJob running for token {self.bot_token[:10]}...")
        try:
            # Get today's date
            now = DateHandler.get_datetime_now()
            today = DateHandler.date(now)

            # Fetch today's liturgy
            scraper = LiturgiaScraper(today)
            text = await scraper.safe_fetch()

            if not text:
                logger.warning("No liturgy content fetched")
                return

            # Get all active subscriptions
            chat_ids = await self.db.get_active_subscriptions()
            if not chat_ids:
                logger.debug("No active subscriptions")
                return

            # Send to all subscribed chats
            async with httpx.AsyncClient(timeout=30) as client:
                success_count = 0
                for chat_id in chat_ids:
                    if await self._send_to_chat(client, chat_id, text):
                        await self.db.set_last_send(chat_id)
                        success_count += 1

            logger.info(f"Sent daily liturgy to {len(chat_ids)} chat(s) ({success_count} succeeded)")

        except Exception as e:
            logger.error(f"LiturgyJob error: {e}", exc_info=True)

    async def _send_to_chat(
        self, client: httpx.AsyncClient, chat_id: int, text: str
    ) -> bool:
        """Send liturgy text to a chat. Return True if successful."""
        try:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
            }

            response = await client.post(
                f"{self.api_url}/sendMessage",
                json=payload,
            )

            strategy, error_details = ErrorHandler.classify_response(response)

            if strategy == "success":
                return True
            elif strategy == "permanent":
                ErrorHandler.log_error(chat_id, error_details, strategy)
                await self.db.deactivate_subscription(chat_id)
                return False
            else:
                ErrorHandler.log_error(chat_id, error_details, strategy)
                return False

        except Exception as e:
            logger.error(f"Error sending to {chat_id}: {e}")
            return False
