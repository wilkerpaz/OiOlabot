import logging

from pyrogram.types import ReplyKeyboardRemove
from bots.base import BaseBot
from factories.base import BotFactory
from mixins.welcome import WelcomeMixin
from mixins.feed import FeedMixin
from mixins.admin_main import AdminMainMixin

logger = logging.getLogger(__name__)


class MainBot(WelcomeMixin, FeedMixin, AdminMainMixin, BaseBot):
    """Main bot: welcome messages and RSS feed management."""

    def register_handlers(self) -> None:
        """Register all handlers for the main bot."""
        self._register_welcome_handlers()
        self._register_feed_handlers()
        self._register_help_handler()
        self._register_admin_handlers()  # From AdminMainMixin

    def _register_help_handler(self) -> None:
        """Register help command handler."""
        from pyrogram import filters
        from pyrogram.handlers import MessageHandler

        self.client.add_handler(
            MessageHandler(self._on_help, filters.command("help"))
        )

    async def _on_help(self, client, message):
        """Send help text with available commands."""
        help_text = (
            "**OiOlabot — Comandos Disponíveis**\n\n"
            "**Gerais:**\n"
            "/start — Ativa o bot neste grupo\n"
            "/stop — Desativa o bot\n"
            "/me — Informações do chat\n"
            "/help — Mostra este menu\n\n"
            "**Boas-vindas e Despedidas:**\n"
            "/welcome <mensagem> — Define mensagem de boas-vindas\n"
            "/goodbye <mensagem> — Define mensagem de despedida\n"
            "/disable_welcome — Desativa mensagens de boas-vindas\n"
            "/disable_goodbye — Desativa mensagens de despedida\n\n"
            "**Configurações:**\n"
            "/lock — Apenas admin pode alterar configurações\n"
            "/unlock — Todos podem alterar configurações\n"
            "/quiet — Desativa mensagens de erro\n"
            "/unquiet — Ativa mensagens de erro\n\n"
            "**Feeds RSS:**\n"
            "/addurl <url> — Adiciona um feed RSS\n"
            "/listurl — Lista todos os feeds cadastrados\n"
            "/removeurl <url> — Remove um feed RSS"
        )
        await message.reply(help_text, reply_markup=ReplyKeyboardRemove())
