from util.scrapers.base import BaseScraper


class LiturgiaScraper(BaseScraper):
    """Scraper for daily scripture readings from liturgia.cancaonova.com."""

    async def fetch(self) -> str | None:
        """Fetch today's scripture reading."""
        pass

    def _fallback(self) -> str:
        """Fallback message when liturgy scraping fails."""
        return "Não consegui recuperar a leitura do dia. Por favor, tente novamente."
