from util.scrapers.base import BaseScraper


class HomiliaScraper(BaseScraper):
    """Scraper for daily homilies from homilia.cancaonova.com."""

    async def fetch(self) -> str | None:
        """Fetch today's homily text and audio."""
        pass

    def _fallback(self) -> str:
        """Fallback message when homily scraping fails."""
        return "Não consegui recuperar a homilia do dia. Por favor, tente novamente."
