import logging
import httpx
import re
from datetime import datetime, timezone
from html import unescape

from util.database.base import BaseDatabase
from util.feedhandler import FeedHandler
from util.datehandler import DateHandler
from worker.error_handler import ErrorHandler

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
        """Process a single feed URL with date/URL validation (v1 logic)."""
        try:
            # Get URL metadata (last update and last URL)
            metadata = await self.db.get_url_metadata(url)
            last_update_str = metadata.get("last_update") if metadata else None
            last_url = metadata.get("last_url") if metadata else None

            # Parse the feed (get 4 latest entries)
            entries = await FeedHandler.parse_feed(url, entries=4)
            if not entries:
                logger.debug(f"No entries found for {url}")
                return

            # Reverse to process from oldest to newest (ascending date order)
            entries = list(reversed(entries))

            # Get subscribed chats
            chats = await self.db.get_chats_for_url(url)
            if not chats:
                logger.debug(f"No subscribed chats for {url}")
                return

            # Parse last_update for comparison
            last_update = None
            if last_update_str:
                try:
                    last_update = DateHandler.parse_datetime(last_update_str)
                except Exception as e:
                    logger.warning(f"Could not parse last_update {last_update_str}: {e}")

            # Process each entry (oldest to newest)
            for entry in entries:
                entry_url = entry.get("link", "").strip()

                # Extract and parse entry date
                entry_date = self._get_entry_datetime(entry)
                if not entry_date:
                    logger.debug(f"Skipping entry with missing/invalid date")
                    continue

                if not entry_url:
                    logger.debug(f"Skipping entry with missing URL")
                    continue

                # Validate: skip if date <= last_update
                if last_update and entry_date <= last_update:
                    logger.debug(f"Entry date {entry_date} <= last_update {last_update}, skipping")
                    continue

                # Validate: skip if URL same as last_url
                if last_url and entry_url == last_url:
                    logger.debug(f"Entry URL same as last_url, skipping")
                    continue

                # Send this entry to all chats
                success_count = 0
                for chat in chats:
                    if await self._send_entry_to_chat(client, chat["chat_id"], entry):
                        success_count += 1

                # Update metadata if at least one send succeeded
                if success_count > 0:
                    await self.db.update_url_metadata(url, str(entry_date), entry_url)
                    logger.info(f"Sent entry {entry_url} to {success_count} chat(s), updated metadata")
                else:
                    logger.warning(f"Failed to send entry {entry_url} to any chat")

        except Exception as e:
            logger.error(f"Error processing URL {url}: {e}")

    async def _send_entry_to_chat(
        self, client: httpx.AsyncClient, chat_id: int, entry: dict
    ) -> bool:
        """Send a single feed entry to a chat. Return True if succeeded."""
        try:
            text = await self._format_entry(entry, client, chat_id)
            if not text:
                return False

            payload = {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": False,
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
                await self.db.deactivate_url_for_chat(chat_id)
                return False
            elif strategy == "transient":
                ErrorHandler.log_error(chat_id, error_details, strategy)
                return False
            else:
                ErrorHandler.log_error(chat_id, error_details, strategy)
                return False

        except Exception as e:
            logger.error(f"Error sending entry to {chat_id}: {e}")
            return False

    async def _format_entry(self, entry: dict, client: httpx.AsyncClient, chat_id: int) -> str:
        """Format a feed entry: title + link + group link (plain text, no HTML)."""
        try:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()

            if not title or not link:
                return ""

            # Clean HTML tags from title
            title = self._clean_html(title)

            # Simple format: Title\nLink\n\ngroup_link
            text = f"{title}\n{link}"

            # Add group/channel link footer
            group_link = await self._get_chat_link(client, chat_id)
            if group_link:
                text += f"\n\n{group_link}"

            return text.strip()
        except Exception as e:
            logger.error(f"Error formatting entry: {e}")
            return ""

    async def _get_chat_link(self, client: httpx.AsyncClient, chat_id: int) -> str:
        """Get chat username or construct link (matching v1 logic)."""
        try:
            # Call Telegram getChat API to get chat info
            response = await client.get(f"{self.api_url}/getChat?chat_id={chat_id}")
            if response.status_code == 200:
                data = response.json().get("result", {})
                chat_type = data.get("type")
                username = data.get("username")

                # If it's a group/supergroup/channel with username, return t.me/username
                if username and chat_type != "private":
                    return f"t.me/{username}"
        except Exception as e:
            logger.debug(f"Could not get chat info for {chat_id}: {e}")

        return ""

    def _get_entry_datetime(self, entry: dict):
        """Extract and parse entry date to datetime object (v1 logic)."""
        try:
            # Try published field first
            if "published" in entry and entry["published"]:
                return DateHandler.parse_datetime(entry["published"])

            # Try updated field
            if "updated" in entry and entry["updated"]:
                return DateHandler.parse_datetime(entry["updated"])

            return None
        except Exception as e:
            logger.debug(f"Error extracting entry date: {e}")
            return None

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags and decode HTML entities."""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Decode HTML entities
        text = unescape(text)
        # Clean multiple spaces
        text = ' '.join(text.split())
        return text.strip()
