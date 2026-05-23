from abc import ABC, abstractmethod

from pyrogram import Client

from util.database.base import BaseDatabase


class BotFactory(ABC):
    """Abstract factory for creating a coherent family of bot components."""

    @abstractmethod
    def create_client(self) -> Client:
        """Create and return a configured Pyrogram Client."""
        pass

    @abstractmethod
    def create_database(self) -> BaseDatabase:
        """Create and return a configured database handler."""
        pass
