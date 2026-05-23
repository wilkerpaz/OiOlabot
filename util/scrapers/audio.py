import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup

from util.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class AudioScraper(BaseScraper):
    """Scraper for daily liturgy audio from Canção Nova."""

    def __init__(self, date_str: str = "today"):
        """Initialize audio scraper with target date."""
        self.date_str = date_str

    async def fetch(self) -> dict | None:
        """
        Fetch audio MP3 for the target date.

        Returns:
            Dict with 'date' and 'path_audio', or None if failed
        """
        try:
            tmp_path = Path(f"/tmp/{self.date_str}.mp3")
            if tmp_path.exists():
                logger.debug(f"Audio already cached at {tmp_path}")
                return {
                    "date": self.date_str,
                    "path_audio": str(tmp_path),
                }

            # Use a single client for all requests
            async with self.make_client() as client:
                # Step 1: Get the page and find iframe
                response = await client.get("https://homilia.cancaonova.com/pb/")
                response.raise_for_status()
                html = response.text

                soup = BeautifulSoup(html, "html.parser")

                # Look for the audio iframe inside embeds-audio div (more robust)
                audio_div = soup.find("div", class_="embeds-audio")
                if not audio_div:
                    logger.warning("No embeds-audio div found on homilia page")
                    return None

                iframe = audio_div.find("iframe")
                if not iframe:
                    logger.warning("No iframe found inside embeds-audio div")
                    return None

                iframe_src = iframe.get("src", "")
                if not iframe_src:
                    logger.warning("Iframe has no src attribute")
                    return None

                # Step 2: Extract audio_id from iframe URL
                audio_id_match = re.search(r'[?&]id=([^&]+)', iframe_src)
                if not audio_id_match:
                    logger.warning(f"Could not extract audio_id from iframe src: {iframe_src}")
                    return None

                audio_id = audio_id_match.group(1)
                logger.debug(f"Extracted audio_id: {audio_id}")

                # Step 3: Fetch player HTML to get MP3 URL
                player_url = f"https://apps.cancaonova.com/embeds/EmbedsMedia/get_player/{audio_id}"
                response = await client.get(player_url)
                response.raise_for_status()
                player_html = response.text

                # Step 4: Extract MP3 URL from <source src="...">
                player_soup = BeautifulSoup(player_html, "html.parser")
                source = player_soup.find("source")
                if not source:
                    logger.warning("No <source> tag found in player HTML")
                    return None

                mp3_url = source.get("src", "")
                if not mp3_url:
                    logger.warning("Source tag has no src attribute")
                    return None

                logger.debug(f"Found MP3 URL: {mp3_url}")

                # Step 5: Download MP3
                response = await client.get(mp3_url)
                response.raise_for_status()
                mp3_content = response.content

                # Save to /tmp
                tmp_path.write_bytes(mp3_content)
                logger.info(f"Audio saved to {tmp_path}")

                return {
                    "date": self.date_str,
                    "path_audio": str(tmp_path),
                }

        except Exception as e:
            logger.error(f"Error fetching audio: {e}")
            return None
