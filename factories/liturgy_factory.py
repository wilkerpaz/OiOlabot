from decouple import config
from pyrogram import Client

from factories.base import BotFactory
from util.database.liturgy_db import LiturgyDatabase
from util.database.base import BaseDatabase


class LiturgyBotFactory(BotFactory):
    """Factory for the liturgy bot (daily readings + homily + saint)."""

    def create_client(self) -> Client:
        """Create the liturgy bot client."""
        api_id = config("API_ID")
        api_hash = config("API_HASH")
        bot_token = config("DEV_TOKEN_LD")
        bot_name = config("BOT_NAME_LD")

        return Client(
            name=bot_name,
            api_id=api_id,
            api_hash=api_hash,
            bot_token=bot_token,
        )

    def create_database(self) -> BaseDatabase:
        """Create the liturgy bot database handler."""
        db_number = int(config("DB_LD", default="1"))
        return LiturgyDatabase(db_number)
