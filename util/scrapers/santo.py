from util.scrapers.base import BaseScraper


class SantoScraper(BaseScraper):
    """Scraper for saint of the day from santo.cancaonova.com."""

    async def fetch(self) -> str | None:
        """Fetch today's saint information."""
        pass

    def _fallback(self) -> str:
        """Fallback message when saint scraping fails."""
        return "Não consegui recuperar o santo do dia. Por favor, tente novamente."
