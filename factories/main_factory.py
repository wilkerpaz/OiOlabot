from decouple import config
from pyrogram import Client

from factories.base import BotFactory
from util.database.main_db import MainDatabase
from util.database.base import BaseDatabase


class MainBotFactory(BotFactory):
    """Factory for the main bot (welcome + RSS)."""

    def create_client(self) -> Client:
        """Create the main bot client."""
        api_id = config("API_ID")
        api_hash = config("API_HASH")
        bot_token = config("DEV_TOKEN")
        bot_name = config("BOT_NAME")

        return Client(
            name=bot_name,
            api_id=api_id,
            api_hash=api_hash,
            bot_token=bot_token,
        )

    def create_database(self) -> BaseDatabase:
        """Create the main bot database handler."""
        db_number = int(config("DB", default="0"))
        return MainDatabase(db_number)
