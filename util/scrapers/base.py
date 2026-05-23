import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class for web scrapers with fallback handling."""

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
