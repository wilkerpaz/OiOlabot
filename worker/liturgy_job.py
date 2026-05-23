import logging
import httpx

from util.database.base import BaseDatabase
from util.scrapers.base import BaseScraper
from util.scrapers.liturgia import LiturgiaScraper
from util.scrapers.audio import AudioScraper
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
        """Execute the daily liturgy job with date/time validation (v1 logic)."""
        logger.info(f"LiturgyJob running for token {self.bot_token[:10]}...")
        try:
            # Get today's date and time
            now = DateHandler.get_datetime_now()
            today = DateHandler.date(now)
            today_str = str(today)

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

            # Send liturgy text to all subscribed chats with date/time validation
            async with httpx.AsyncClient(timeout=30) as client:
                success_count = 0
                for chat_id in chat_ids:
                    if await self._send_to_chat(client, chat_id, text, now):
                        success_count += 1

            logger.info(f"Sent daily liturgy to {success_count}/{len(chat_ids)} chat(s)")

            # Fetch and send audio after liturgy text (only if text was sent to at least one chat)
            if success_count > 0:
                await self._send_audio_to_all(chat_ids, today_str)

        except Exception as e:
            logger.error(f"LiturgyJob error: {e}", exc_info=True)

    async def _send_to_chat(
        self, client: httpx.AsyncClient, chat_id: int, text: str, send_time
    ) -> bool:
        """Send liturgy text to a chat with date validation. Return True if successful."""
        try:
            # Get chat's last send date/time
            last_send_str = await self.db.get_last_send(chat_id)
            last_send = None
            if last_send_str:
                try:
                    last_send = DateHandler.parse_datetime(last_send_str)
                except Exception as e:
                    logger.warning(f"Could not parse last_send {last_send_str} for {chat_id}: {e}")

            # Validate: skip if send_time <= last_send (already sent today)
            if last_send and send_time <= last_send:
                logger.debug(f"Chat {chat_id}: already received today ({last_send}), skipping")
                return False

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
                # Update last send time only on success
                await self.db.set_last_send(chat_id, str(send_time))
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

    async def _send_audio_to_all(self, chat_ids: list, today_str: str) -> None:
        """Fetch and send audio to all subscribed chats."""
        try:
            # Check if audio is already cached
            cached_file_id = await self.db.get_cached_audio_file_id(today_str)
            audio_data = None

            if not cached_file_id:
                # Fetch audio if not cached
                audio_scraper = AudioScraper(today_str)
                audio_data = await audio_scraper.fetch()
                if not audio_data:
                    logger.warning("No audio content fetched")
                    return

            # Send audio to all subscribed chats
            async with httpx.AsyncClient(timeout=30) as client:
                success_count = 0
                for chat_id in chat_ids:
                    if cached_file_id:
                        if await self._send_audio(client, chat_id, cached_file_id):
                            success_count += 1
                    else:
                        file_id = await self._send_audio_file(client, chat_id, audio_data.get("path_audio"))
                        if file_id:
                            if success_count == 0:
                                await self.db.cache_audio_file_id(today_str, file_id)
                            success_count += 1

            logger.info(f"Sent audio to {success_count} chat(s)")

        except Exception as e:
            logger.error(f"Error sending audio: {e}")

    async def _send_audio(self, client: httpx.AsyncClient, chat_id: int, file_id: str) -> bool:
        """Send audio via cached file_id. Return True if successful."""
        try:
            payload = {
                "chat_id": chat_id,
                "audio": file_id,
            }
            response = await client.post(f"{self.api_url}/sendAudio", json=payload)

            strategy, error_details = ErrorHandler.classify_response(response)
            if strategy == "permanent":
                ErrorHandler.log_error(chat_id, error_details, strategy)
                await self.db.deactivate_subscription(chat_id)
                return False
            elif strategy != "success":
                ErrorHandler.log_error(chat_id, error_details, strategy)
                return False

            return True
        except Exception as e:
            logger.error(f"Error sending audio to {chat_id}: {e}")
            return False

    async def _send_audio_file(self, client: httpx.AsyncClient, chat_id: int, file_path: str) -> str | None:
        """Send audio file and return file_id. Returns None if failed or on permanent error."""
        try:
            with open(file_path, "rb") as audio_file:
                files = {"audio": audio_file}
                data = {"chat_id": chat_id}
                response = await client.post(f"{self.api_url}/sendAudio", files=files, data=data)

                strategy, error_details = ErrorHandler.classify_response(response)
                if strategy == "permanent":
                    ErrorHandler.log_error(chat_id, error_details, strategy)
                    await self.db.deactivate_subscription(chat_id)
                    return None
                elif strategy != "success":
                    ErrorHandler.log_error(chat_id, error_details, strategy)
                    return None

                try:
                    result = response.json()
                    if result.get("ok") and "result" in result:
                        message = result["result"]
                        if "audio" in message:
                            return message["audio"].get("file_id")
                except Exception as e:
                    logger.error(f"Error parsing response for {chat_id}: {e}")
                return None
        except Exception as e:
            logger.error(f"Error sending audio file to {chat_id}: {e}")
            return None
