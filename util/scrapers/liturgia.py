import logging
import re
from datetime import date

import httpx
from bs4 import BeautifulSoup

from util.scrapers.base import BaseScraper
from util.datehandler import DateHandler

logger = logging.getLogger(__name__)


class LiturgiaScraper(BaseScraper):
    """Scraper for daily scripture readings from liturgia.cancaonova.com."""

    def __init__(self, target_date: date | None = None):
        """Initialize with optional target date. Defaults to today."""
        if target_date is None:
            target_date = DateHandler.date(DateHandler.get_datetime_now())
        self.target_date = target_date
        self.dia = str(target_date.day)
        self.mes = str(target_date.month)
        self.ano = str(target_date.year)
        # Format date in Portuguese: "sexta-feira, 23 de maio de 2026"
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
        """Fetch today's scripture reading."""
        try:
            async with self.make_client(timeout=10.0) as client:
                # Step 1: Get the URL for this specific date
                payload = {
                    "action": "widget-ajax",
                    "sMes": self.mes,
                    "sAno": self.ano,
                    "title": "",
                    "type": "liturgia",
                    "ajax": "true",
                }
                response = await client.post(
                    "https://liturgia.cancaonova.com/wp-admin/admin-ajax.php",
                    data=payload,
                )
                response.raise_for_status()

                # Parse calendar to find the URL for this date
                soup = BeautifulSoup(response.text, "lxml")
                table = soup.find("table", {"id": "wp-calendar"})
                if not table:
                    logger.warning(f"Calendar table not found for {self.target_date}")
                    return None

                table_body = table.find("tbody")
                if not table_body:
                    logger.warning(f"Calendar body not found for {self.target_date}")
                    return None

                # Extract links for each day of the month
                day_links = {}
                for row in table_body.find_all("tr"):
                    for cell in row.find_all("td"):
                        day_text = cell.text.strip()
                        if day_text:
                            link_tag = cell.find("a")
                            day_links[day_text] = link_tag["href"] if link_tag else None

                # Check if this day has a reading
                liturgy_url = day_links.get(self.dia)
                if not liturgy_url:
                    logger.warning(
                        f"No reading available for {self.target_date}"
                    )
                    return None

                # Step 2: Fetch the actual reading from the URL
                reading_response = await client.get(liturgy_url)
                reading_response.raise_for_status()

                reading_soup = BeautifulSoup(reading_response.text, "lxml")

                # Extract title
                title_meta = reading_soup.find("meta", {"property": "og:title"})
                if not title_meta:
                    logger.warning(f"Title not found in {liturgy_url}")
                    return None
                day_title = title_meta["content"].split(" | ")[0]

                # Extract readings (divs with id matching liturgia-\d pattern)
                readings_divs = reading_soup.find_all("div", {"id": re.compile(r"liturgia-\d")})
                if not readings_divs:
                    logger.warning(f"Readings not found in {liturgy_url}")
                    return None

                # Format readings
                result = []
                for reading_div in readings_divs:
                    reading_text = reading_div.text.strip()

                    # Add spacing after first line
                    lines = reading_text.split("\n")
                    if lines:
                        first_line = lines[0]
                        reading_text = reading_text.replace(
                            first_line, f"{first_line}\n", 1
                        )

                    # Add spacing around "Glória a vós, Senhor"
                    reading_text = reading_text.replace(
                        "\n— Glória a vós, Senhor.\n",
                        "\n— Glória a vós, Senhor.\n\n",
                    )

                    # Prepend date and title
                    formatted = f"{self.formatted_date}\n{day_title}\n{reading_text}"
                    result.append(formatted)

                return "\n\n".join(result) if result else None

        except httpx.RequestError as e:
            logger.error(f"HTTP error fetching liturgy: {e}")
            return None
        except Exception as e:
            logger.error(f"Error scraping liturgy: {e}")
            return None

    def _fallback(self) -> str:
        """Fallback message when liturgy scraping fails."""
        return "Não consegui recuperar a leitura do dia. Por favor, tente novamente."
