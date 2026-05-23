import logging
from abc import ABC, abstractmethod

import httpx

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class for web scrapers with fallback handling."""

    @staticmethod
    def make_client(**kwargs) -> httpx.AsyncClient:
        """Create an httpx client with sensible defaults for scraping."""
        defaults = {
            "follow_redirects": True,
            "timeout": 30.0,
            "headers": {"User-Agent": "Mozilla/5.0 (compatible; OiaLabot/1.0)"},
        }
        defaults.update(kwargs)
        return httpx.AsyncClient(**defaults)

    @abstractmethod
    async def fetch(self) -> str | None:
        """
        Fetch content from the source.

        Should return the content as a string, or None if fetch failed.
        """
        pass

    async def safe_fetch(self) -> str:
        """
        Safely fetch content with fallback.

        Catches any exception and returns a fallback message.
        """
        try:
            result = await self.fetch()
            return result if result else self._fallback()
        except Exception as e:
            logger.error(f"Error in {self.__class__.__name__}.fetch(): {e}")
            return self._fallback()

    def _fallback(self) -> str:
        """Return a fallback message when scraping fails."""
        return ""
