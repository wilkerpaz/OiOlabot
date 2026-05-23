import logging
import httpx
from bs4 import BeautifulSoup
from datetime import date

from util.scrapers.base import BaseScraper
from util.datehandler import DateHandler

logger = logging.getLogger(__name__)


class HomiliaScraper(BaseScraper):
    """Scraper for daily homilies from homilia.cancaonova.com."""

    def __init__(self, target_date: date | None = None):
        """Initialize with optional target date. Defaults to today."""
        if target_date is None:
            target_date = DateHandler.date(DateHandler.get_datetime_now())
        self.target_date = target_date
        # Format date as "quinta-feira, 23 de maio de 2026" for display
        self.formatted_date = self._format_portuguese_date(target_date)

    def _format_portuguese_date(self, dt: date) -> str:
        """Format date in Portuguese style."""
        days_pt = ["segunda-feira", "terça-feira", "quarta-feira",
                   "quinta-feira", "sexta-feira", "sábado", "domingo"]
        months_pt = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
                     "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

        day_name = days_pt[dt.weekday()]
        month_name = months_pt[dt.month - 1]
        return f"{day_name}, {dt.day} de {month_name} de {dt.year}"

    async def fetch(self) -> str | None:
        """Fetch today's homily text."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Fetch the homily page
                response = await client.get("https://homilia.cancaonova.com/pb/")
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "lxml")

                # Extract title
                title_elem = soup.find("h1", {"class": "entry-title"})
                if not title_elem or not title_elem.findChild("span"):
                    logger.warning("Homily title not found")
                    return None
                title = title_elem.findChild("span").text

                # Extract homily text
                content_elem = soup.find("div", {"class": "entry-content content-homilia"})
                if not content_elem:
                    logger.warning("Homily content not found")
                    return None
                text = content_elem.text.split("\t\t")[0].strip()

                # Format the homily
                formatted = f"{self.formatted_date}\n{title}.\n\nReflexão do dia.\n{text}"
                return formatted

        except httpx.RequestError as e:
            logger.error(f"HTTP error fetching homily: {e}")
            return None
        except Exception as e:
            logger.error(f"Error scraping homily: {e}")
            return None

    def _fallback(self) -> str:
        """Fallback message when homily scraping fails."""
        return "Não consegui recuperar a homilia do dia. Por favor, tente novamente."
