import asyncio
import feedparser
from feedparser import exceptions
import re
import logging

from util.datehandler import DateHandler

logger = logging.getLogger(__name__)


class FeedHandler:

    @staticmethod
    async def parse_feed(url: str, entries: int = 4, modified=None):
        """
        Asynchronously parse a feed URL. Uses asyncio.to_thread to avoid
        blocking the event loop with feedparser (which is sync).

        Returns a list containing the most recent entries (up to `entries`).
        """
        return await asyncio.to_thread(
            FeedHandler._parse_feed_sync, url, entries, modified
        )

    @staticmethod
    def _parse_feed_sync(url: str, entries: int = 4, modified=None):
        """Synchronous implementation of feed parsing."""
        try:
            if 1 <= entries <= 10:
                feeds = feedparser.parse(url, modified=modified).entries[:entries]
                if url == 'http://feeds.feedburner.com/evangelhoddia/dia':
                    for f in feeds:
                        f['published'] = f['id'][:10] + ' ' + '06:00:00'
                        f['link'] = f['link'] + f['id'][:10]
                        f['daily_liturgy'] = f['summary']
                    feeds.reverse()
                    return feeds
                else:
                    feed = feeds[:entries]
                    feed.reverse()
                    return feed
            else:
                feed = feedparser.parse(url, modified=modified).entries[:4]
                feed.reverse()
                return feed
        except Exception as e:
            logger.error(f"Error parsing feed {url}: {e}")
            return []

    @staticmethod
    def format_url_string(string: str) -> str:
        """
        Format a URL string to ensure it has http(s):// prefix.
        """
        url_pattern = re.compile(r"(http(s?)):\/\/.*")
        if not url_pattern.match(string):
            string = "http://" + string
        return string

    @staticmethod
    async def is_parsable(url: str) -> bool:
        """
        Asynchronously check if a URL provides a valid RSS feed.
        Returns True if the feed has entries, False otherwise.
        """
        return await asyncio.to_thread(FeedHandler._is_parsable_sync, url)

    @staticmethod
    def _is_parsable_sync(url: str) -> bool:
        """Synchronous implementation of feed validation."""
        url_pattern = re.compile(r"((http(s?))):\/\/.*")
        if not url_pattern.match(url):
            return False

        try:
            feed = feedparser.parse(url)

            if not feed.entries:
                return False

            for post in feed.entries:
                if hasattr(post, "published") or hasattr(post, 'summary'):
                    return True
            return True
        except Exception as e:
            logger.error(f"Error validating feed {url}: {e}")
            return False
