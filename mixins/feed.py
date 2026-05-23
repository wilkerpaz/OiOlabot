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
        """Add a new RSS feed subscription (can be used in group or DM with group name)."""
        chat_id = message.chat.id
        user_id = message.from_user.id
        is_dm = chat_id > 0

        # Parse arguments
        text = message.text.split(None, 1)[1] if len(message.text.split(None, 1)) > 1 else ""
        args = text.strip().split() if text else []

        # Validate arguments
        if len(args) == 0 or len(args) > 2:
            help_text = (
                "❌ Argumentos inválidos.\n\n"
                "**Em um grupo:**\n"
                "`/addurl <url>`\n\n"
                "**Em DM:**\n"
                "`/addurl <url>` — Adiciona ao grupo padrão\n"
                "`/addurl @grupo <url>` — Adiciona ao grupo especificado"
            )
            await message.reply(help_text)
            return

        # Extract chat_id and url based on context
        target_chat_id = chat_id
        target_chat_name = message.chat.username or message.chat.title or str(chat_id)

        if len(args) == 2:
            # `/addurl @grupo url`
            if not is_dm:
                await message.reply("❌ Use `/addurl <url>` em um grupo. Para outro grupo, use DM.")
                return

            group_name = args[0]
            url = FeedHandler.format_url_string(args[1])

            # Try to find the group by name
            try:
                # Search for the group in user's subscriptions
                found = False
                # For now, assume the group name is the username
                if group_name.startswith("@"):
                    group_name = group_name[1:]

                # This is a simplified approach - in real implementation, would need a mapping
                # For now, we'll require the user to be in the group or have access
                await message.reply(f"⚠️ Funcionalidade de buscar grupo '{group_name}' em implementação.\nUse `/addurl <url>` no grupo desejado.")
                return
            except Exception as e:
                logger.error(f"Error finding group: {e}")
                await message.reply(f"❌ Não consegui encontrar o grupo '@{group_name}'.")
                return
        else:
            # `/addurl url` (in group or DM default)
            url = FeedHandler.format_url_string(args[0])

        # Validate feed
        is_valid = await FeedHandler.is_parsable(url)
        if not is_valid:
            await message.reply(f"❌ Não consegui validar o feed: `{url}`")
            return

        # Add subscription
        try:
            result = await self.db.add_url_subscription(
                chat_id=target_chat_id,
                url=url,
                user_id=user_id,
                chat_name=target_chat_name,
            )
            if result:
                await message.reply(f"✅ Feed adicionado: `{url}`")
            else:
                await message.reply(f"⚠️ Este feed já está cadastrado.")
        except Exception as e:
            logger.error(f"Error adding feed: {e}")
            await message.reply(f"❌ Erro ao adicionar feed.")

    async def list_feed_urls(self, client, message):
        """List all active RSS subscriptions for current chat."""
        chat_id = message.chat.id

        try:
            urls = await self.db.get_chat_urls(chat_id)
            if not urls:
                await message.reply("Nenhum feed cadastrado neste chat.")
                return

            text = "📰 **Feeds ativos:**\n\n"
            for i, url in enumerate(urls, 1):
                text += f"{i}. `{url}`\n"

            await message.reply(text)
        except Exception as e:
            logger.error(f"Error listing feeds: {e}")
            await message.reply("❌ Erro ao listar feeds.")

    async def remove_feed_url(self, client, message):
        """Remove an RSS feed subscription."""
        chat_id = message.chat.id
        is_dm = chat_id > 0

        # Parse arguments
        text = message.text.split(None, 1)[1] if len(message.text.split(None, 1)) > 1 else ""
        args = text.strip().split() if text else []

        # Validate arguments
        if len(args) == 0 or len(args) > 2:
            help_text = (
                "❌ Argumentos inválidos.\n\n"
                "**Em um grupo:**\n"
                "`/removeurl <url>`\n\n"
                "**Em DM:**\n"
                "`/removeurl <url>` — Remove do grupo padrão\n"
                "`/removeurl @grupo <url>` — Remove do grupo especificado"
            )
            await message.reply(help_text)
            return

        # Extract target chat and url
        target_chat_id = chat_id

        if len(args) == 2:
            # `/removeurl @grupo url`
            if not is_dm:
                await message.reply("❌ Use `/removeurl <url>` em um grupo. Para outro grupo, use DM.")
                return

            group_name = args[0]
            url = args[1]

            # Similar to add_feed_url - simplified for now
            await message.reply(f"⚠️ Funcionalidade de buscar grupo '{group_name}' em implementação.\nUse `/removeurl <url>` no grupo desejado.")
            return
        else:
            # `/removeurl url`
            url = args[0]

        try:
            result = await self.db.remove_url_for_chat(target_chat_id, url)
            if result:
                await message.reply(f"✅ Feed removido: `{url}`")
            else:
                await message.reply(f"⚠️ Feed não encontrado neste chat.")
        except Exception as e:
            logger.error(f"Error removing feed: {e}")
            await message.reply("❌ Erro ao remover feed.")
