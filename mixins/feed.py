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
        """List RSS subscriptions: direct with bot (if DM) or grouped by chat."""
        chat_id = message.chat.id
        user_id = message.from_user.id
        is_dm = chat_id > 0

        try:
            if is_dm:
                # DM: show all URLs grouped by chat/group
                await self._list_feeds_by_chat(user_id, message)
            else:
                # Group: show only URLs for this group
                urls = await self.db.get_chat_urls(chat_id)
                if not urls:
                    await message.reply("Nenhum feed cadastrado neste grupo.")
                    return

                text = "📰 **Feeds ativos neste grupo:**\n\n"
                for i, url in enumerate(urls, 1):
                    text += f"{i}. `{url}`\n"

                await message.reply(text)
        except Exception as e:
            logger.error(f"Error listing feeds: {e}")
            await message.reply("❌ Erro ao listar feeds.")

    async def _list_feeds_by_chat(self, user_id: int, message) -> None:
        """List all feeds grouped by chat (for DM usage)."""
        try:
            # Get all subscription keys for this user
            names = await self.db._find(f"user_url:{user_id}:chat_id:*")
            if not names:
                await message.reply("Você não possui feeds cadastrados.")
                return

            # Group by chat_id and extract chat_name from subscription data
            chats_feeds = {}
            for name in names:
                # Extract URL and chat_id from key name
                # Format: user_url:{user_id}:chat_id:{chat_id}:^{url}^
                if "^" in name:
                    url = name.split("^")[1]
                    # Extract chat_id from key
                    parts = name.split(":")
                    try:
                        chat_id_idx = parts.index("chat_id")
                        chat_id = int(parts[chat_id_idx + 1])
                    except (ValueError, IndexError):
                        continue

                    # Check if active
                    disable_status = await self.db.redis.hget(name, "disable")
                    if disable_status != "True":
                        # Get chat_name from subscription data
                        chat_name = await self.db.redis.hget(name, "chat_name")
                        if chat_name:
                            chat_name = chat_name.decode() if isinstance(chat_name, bytes) else chat_name
                        else:
                            chat_name = f"Chat {chat_id}"

                        if chat_id not in chats_feeds:
                            chats_feeds[chat_id] = {"name": chat_name, "urls": []}
                        chats_feeds[chat_id]["urls"].append(url)

            if not chats_feeds:
                await message.reply("Você não possui feeds ativos cadastrados.")
                return

            # Build message with feeds grouped by chat
            messages = []
            current_text = "📰 **Seus Feeds:**\n\n"
            max_length = 3500

            for chat_id in sorted(chats_feeds.keys()):
                chat_info = chats_feeds[chat_id]
                chat_title = chat_info["name"]

                # Add chat header
                chat_header = f"**{chat_title}**:\n"

                # Add all URLs for this chat
                urls_text = ""
                for url in chat_info["urls"]:
                    urls_text += f"  • `{url}`\n"

                section_text = chat_header + urls_text + "\n"

                # Check if adding this section would exceed limit
                if len(current_text) + len(section_text) > max_length:
                    if current_text.strip() and current_text != "📰 **Seus Feeds:**\n\n":
                        messages.append(current_text.strip())
                    current_text = "📰 **Seus Feeds (cont.):**\n\n" + section_text
                else:
                    current_text += section_text

            # Add remaining text
            if current_text.strip() and current_text != "📰 **Seus Feeds:**\n\n":
                messages.append(current_text.strip())

            if not messages:
                await message.reply("Você não possui feeds ativos cadastrados.")
                return

            # Send all messages
            for msg in messages:
                if len(msg) > 4096:
                    logger.warning(f"Message exceeds 4096 chars ({len(msg)}), truncating")
                    msg = msg[:4000] + "..."
                await message.reply(msg)

        except Exception as e:
            logger.error(f"Error listing feeds by chat: {e}", exc_info=True)
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
