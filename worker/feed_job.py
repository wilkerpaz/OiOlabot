import logging
import httpx
from datetime import datetime, timezone

from util.database.base import BaseDatabase
from util.feedhandler import FeedHandler
from util.datehandler import DateHandler

logger = logging.getLogger(__name__)


class FeedJob:
    """Background job to distribute RSS feeds to subscribers."""

    def __init__(self, db: BaseDatabase, bot_token: str):
        """Initialize with database and bot token."""
        self.db = db
        self.bot_token = bot_token
        self.api_url = f"https://api.telegram.org/bot{bot_token}"

    async def run(self) -> None:
        """Execute the feed distribution job."""
        logger.info(f"FeedJob starting for token {self.bot_token[:10]}...")
        try:
            urls = await self.db.get_urls_activated()
            if not urls:
                logger.debug("No active URLs to process")
                return

            async with httpx.AsyncClient(timeout=30) as client:
                for url in urls:
                    await self._process_url(client, url)

            logger.info("FeedJob completed successfully")
        except Exception as e:
            logger.error(f"FeedJob error: {e}", exc_info=True)

    async def _process_url(self, client: httpx.AsyncClient, url: str) -> None:
        """Process a single feed URL."""
        try:
            # Get URL metadata
            metadata = await self.db.get_url_metadata(url)
            last_update_str = metadata.get("last_update") if metadata else None

            # Parse the feed
            entries = await FeedHandler.parse_feed(url, entries=4)
            if not entries:
                logger.debug(f"No entries found for {url}")
                return

            # Get subscribed chats
            chats = await self.db.get_chats_for_url(url)
            if not chats:
                logger.debug(f"No subscribed chats for {url}")
                return

            # Send to each chat
            for chat in chats:
                await self._send_entries_to_chat(client, chat["chat_id"], entries)

            # Update metadata
            now = DateHandler.get_datetime_now()
            await self.db.update_url_metadata(url, str(now), str(entries[0]) if entries else "")
            logger.info(f"Processed {url} for {len(chats)} chat(s)")

        except Exception as e:
            logger.error(f"Error processing URL {url}: {e}")

    async def _send_entries_to_chat(
        self, client: httpx.AsyncClient, chat_id: int, entries: list
    ) -> None:
        """Send feed entries to a chat."""
        try:
            for entry in entries:
                text = self._format_entry(entry)
                if not text:
                    continue

                payload = {
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                }

                response = await client.post(
                    f"{self.api_url}/sendMessage",
                    json=payload,
                )

                if response.status_code != 200:
                    logger.warning(
                        f"Failed to send to {chat_id}: {response.status_code} - {response.text}"
                    )
        except Exception as e:
            logger.error(f"Error sending entries to {chat_id}: {e}")

    def _format_entry(self, entry: dict) -> str:
        """Format a feed entry as HTML message."""
        try:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            summary = entry.get("summary", entry.get("description", "")).strip()

            if not title:
                return ""

            text = f"<b>{title}</b>\n"
            if summary:
                # Truncate summary to 300 chars
                summary = summary[:300].replace("<", "&lt;").replace(">", "&gt;")
                text += f"{summary}\n"
            if link:
                text += f'<a href="{link}">Leia mais</a>'

            return text.strip()
        except Exception as e:
            logger.error(f"Error formatting entry: {e}")
            return ""
