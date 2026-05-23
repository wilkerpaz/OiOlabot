import asyncio
import logging
from abc import ABC, abstractmethod

from pyrogram import Client

from factories.base import BotFactory
from util.database.base import BaseDatabase

logger = logging.getLogger(__name__)


class BaseBot(ABC):
    """Base class for all bots with lifecycle and handler management."""

    def __init__(self, factory: BotFactory):
        """Initialize bot with factory-created components."""
        self.client: Client = factory.create_client()
        self.db: BaseDatabase = factory.create_database()

        self._register_lifecycle()
        self.register_handlers()
        logger.info(f"{self.__class__.__name__} initialized")

    def _register_lifecycle(self) -> None:
        """Register startup and shutdown handlers."""

        @self.client.on_start()
        async def _on_start(_: Client) -> None:
            logger.info(f"{self.__class__.__name__} started")

        @self.client.on_stop()
        async def _on_stop(_: Client) -> None:
            await self.db.close()
            logger.info(f"{self.__class__.__name__} stopped")

    @abstractmethod
    def register_handlers(self) -> None:
        """Register message and event handlers. Implemented by subclasses."""
        pass

    def run(self) -> None:
        """Start the bot and keep it running."""
        self.client.run()
