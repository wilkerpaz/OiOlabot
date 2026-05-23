"""Entry point for the liturgy bot (daily readings + homily + saint)."""

import logging
from decouple import config

from factories.liturgy_factory import LiturgyBotFactory
from bots.liturgy_bot import LiturgyBot

logging.basicConfig(
    level=config("LOG", default="INFO"),
    format="%(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def main():
    """Run the liturgy bot."""
    logger.info("Starting LiturgyBot...")
    bot = LiturgyBot(LiturgyBotFactory())
    bot.run()


if __name__ == "__main__":
    main()
