"""Main entry point for the main bot (welcome + RSS)."""

import logging
from decouple import config

from factories.main_factory import MainBotFactory
from bots.main_bot import MainBot

logging.basicConfig(
    level=config("LOG", default="INFO"),
    format="%(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def main():
    """Run the main bot."""
    logger.info("Starting MainBot...")
    bot = MainBot(MainBotFactory())
    bot.run()


if __name__ == "__main__":
    main()
