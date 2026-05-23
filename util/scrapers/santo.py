import logging
import httpx
from bs4 import BeautifulSoup

from util.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class SantoScraper(BaseScraper):
    """Scraper for saint of the day from santo.cancaonova.com."""

    async def fetch(self) -> str | None:
        """Fetch today's saint information."""
        try:
            async with self.make_client(timeout=10.0) as client:
                response = await client.get("https://santo.cancaonova.com/")
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "lxml")

                # Extract saint name
                title_elem = soup.find("h1", {"class": "entry-title"})
                if not title_elem or not title_elem.findChild("span"):
                    logger.warning("Saint name not found")
                    return None
                saint_name = title_elem.findChild("span").text

                # Extract saint description
                content_elem = soup.find("div", {"class": "entry-content content-santo"})
                if not content_elem:
                    logger.warning("Saint content not found")
                    return None

                paragraphs = content_elem.findChildren("p")
                descriptions = [p.text for p in paragraphs]
                saint_text = "\n".join(descriptions)

                # Format the saint information
                formatted = f"Santo do dia: {saint_name}\n\n{saint_text}\n\n{saint_name}, rogai por nós."
                return formatted

        except httpx.RequestError as e:
            logger.error(f"HTTP error fetching saint: {e}")
            return None
        except Exception as e:
            logger.error(f"Error scraping saint: {e}")
            return None

    def _fallback(self) -> str:
        """Fallback message when saint scraping fails."""
        return "Não consegui recuperar o santo do dia. Por favor, tente novamente."
