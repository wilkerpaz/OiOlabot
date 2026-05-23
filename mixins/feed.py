import logging

from pyrogram import filters
from pyrogram.handlers import MessageHandler

from util.feedhandler import FeedHandler

logger = logging.getLogger(__name__)


class FeedMixin:
    """Mixin for RSS feed subscription handlers."""

    def _register_feed_handlers(self) -> None:
        """Register RSS feed handlers."""
        self.client.add_handler(
            MessageHandler(self.add_feed_url, filters.command("addurl"))
        )
        self.client.add_handler(
            MessageHandler(self.list_feed_urls, filters.command("listurl"))
        )
        self.client.add_handler(
            MessageHandler(self.remove_feed_url, filters.command("removeurl"))
        )

    async def add_feed_url(self, client, message):
        """Add a new RSS feed subscription."""
        chat_id = message.chat.id
        user_id = message.from_user.id

        # Extract URL from command
        args = message.command
        if len(args) < 2:
            await message.reply("Use: /addurl <url>")
            return

        url = FeedHandler.format_url_string(args[1])

        # Validate feed
        is_valid = await FeedHandler.is_parsable(url)
        if not is_valid:
            await message.reply(f"Não consegui validar o feed: {url}")
            return

        # Add subscription
        try:
            result = await self.db.add_url_subscription(
                chat_id=chat_id,
                url=url,
                user_id=user_id,
                chat_name=message.chat.username or message.chat.title,
            )
            if result:
                await message.reply(f"✅ Feed adicionado: {url}")
            else:
                await message.reply(f"Este feed já está cadastrado.")
        except Exception as e:
            logger.error(f"Error adding feed: {e}")
            await message.reply(f"Erro ao adicionar feed.")

    async def list_feed_urls(self, client, message):
        """List all active RSS subscriptions."""
        chat_id = message.chat.id

        try:
            urls = await self.db.get_chat_urls(chat_id)
            if not urls:
                await message.reply("Nenhum feed cadastrado.")
                return

            text = "📰 **Feeds ativos:**\n\n"
            for i, url in enumerate(urls, 1):
                text += f"{i}. {url}\n"

            await message.reply(text)
        except Exception as e:
            logger.error(f"Error listing feeds: {e}")
            await message.reply("Erro ao listar feeds.")

    async def remove_feed_url(self, client, message):
        """Remove an RSS feed subscription."""
        chat_id = message.chat.id

        # Extract URL from command
        args = message.command
        if len(args) < 2:
            await message.reply("Use: /removeurl <url>")
            return

        url = args[1]

        try:
            result = await self.db.remove_url_for_chat(chat_id, url)
            if result:
                await message.reply(f"✅ Feed removido: {url}")
            else:
                await message.reply(f"Feed não encontrado.")
        except Exception as e:
            logger.error(f"Error removing feed: {e}")
            await message.reply("Erro ao remover feed.")
