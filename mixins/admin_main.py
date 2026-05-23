import logging
import os
from datetime import datetime

from pyrogram import filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Document

logger = logging.getLogger(__name__)


class AdminMainMixin:
    """Mixin for admin-only commands in the main bot."""

    def _register_admin_handlers(self) -> None:
        """Register admin-only command handlers."""
        self.client.add_handler(
            MessageHandler(self._on_owner, filters.command("owner") & filters.group)
        )
        self.client.add_handler(
            MessageHandler(self._on_admin, filters.command("admin"))
        )
        self.client.add_handler(
            MessageHandler(self._on_addadmin, filters.command("addadmin"))
        )
        self.client.add_handler(
            MessageHandler(self._on_removeadmin, filters.command("removeadmin"))
        )
        self.client.add_handler(
            MessageHandler(self._on_listadmin, filters.command("listadmin"))
        )
        self.client.add_handler(
            MessageHandler(self._on_backup, filters.command("backup"))
        )
        self.client.add_handler(
            MessageHandler(self._on_deactivatedurl, filters.command("deactivatedurl"))
        )
        self.client.add_handler(
            MessageHandler(self._on_activateallurl, filters.command("activateallurl"))
        )
        self.client.add_handler(
            MessageHandler(self._on_allurl, filters.command("allurl"))
        )
        self.client.add_handler(
            MessageHandler(self._on_deactivated, filters.command("deactivated"))
        )
        self.client.add_handler(
            MessageHandler(self._on_activated, filters.command("activated"))
        )
        self.client.add_handler(
            MessageHandler(self._on_userinfo, filters.command("userinfo"))
        )

    async def _on_owner(self, client, message):
        """Set current user as group owner."""
        chat_id = message.chat.id
        user_id = message.from_user.id

        try:
            config = await self.db.get_group_config(chat_id)
            if not config:
                await message.reply("Bot não está registrado neste grupo.")
                return

            config["chat_adm"] = str(user_id)
            await self.db.set_group_config(chat_id, config)
            await message.reply(f"✅ {message.from_user.mention} é agora o proprietário deste grupo.")
        except Exception as e:
            logger.error(f"Error in _on_owner: {e}")
            await message.reply("Erro ao definir proprietário.")

    async def _check_admin(self, user_id: int) -> bool:
        """Check if user is an admin."""
        return await self.db.is_admin(user_id)

    async def _on_admin(self, client, message):
        """Send admin commands list (admin only)."""
        if not await self._check_admin(message.from_user.id):
            await message.reply("❌ Você não é administrador.")
            return

        admin_text = (
            "**Comandos de Admin**\n\n"
            "**Configuração do Grupo:**\n"
            "/owner — Define você como proprietário do grupo\n\n"
            "**Gerenciamento de Feeds:**\n"
            "/allurl — Lista todos os feeds com metadata\n"
            "/deactivatedurl — Lista feeds desativados\n"
            "/activateallurl — Ativa todos os feeds\n\n"
            "**Banco de Dados:**\n"
            "/backup — Faz backup do banco de dados\n"
            "/getkey <padrão> — Busca chaves no Redis\n"
            "/removekey <chave> — Remove chave do Redis\n\n"
            "**Gerenciamento de Admins:**\n"
            "/addadmin <id> — Adiciona um administrador\n"
            "/removeadmin <id> — Remove um administrador\n"
            "/listadmin — Lista todos os administradores\n"
        )
        await message.reply(admin_text)

    async def _on_addadmin(self, client, message):
        """Add a user as admin (admin only)."""
        if not await self._check_admin(message.from_user.id):
            await message.reply("❌ Você não é administrador.")
            return

        try:
            args = message.text.split()
            if len(args) < 2:
                await message.reply("❌ Uso: `/addadmin <user_id>`")
                return

            user_id = int(args[1])
            result = await self.db.add_admin(user_id)
            if result:
                await message.reply(f"✅ Usuário {user_id} adicionado como administrador.")
            else:
                await message.reply(f"⚠️ Usuário {user_id} já é administrador.")
        except ValueError:
            await message.reply("❌ ID inválido. Use um número.")
        except Exception as e:
            logger.error(f"Error in _on_addadmin: {e}")
            await message.reply("❌ Erro ao adicionar administrador.")

    async def _on_removeadmin(self, client, message):
        """Remove a user as admin (admin only)."""
        if not await self._check_admin(message.from_user.id):
            await message.reply("❌ Você não é administrador.")
            return

        try:
            args = message.text.split()
            if len(args) < 2:
                await message.reply("❌ Uso: `/removeadmin <user_id>`")
                return

            user_id = int(args[1])
            result = await self.db.remove_admin(user_id)
            if result:
                await message.reply(f"✅ Usuário {user_id} removido da administração.")
            else:
                await message.reply(f"⚠️ Usuário {user_id} não é administrador.")
        except ValueError:
            await message.reply("❌ ID inválido. Use um número.")
        except Exception as e:
            logger.error(f"Error in _on_removeadmin: {e}")
            await message.reply("❌ Erro ao remover administrador.")

    async def _on_listadmin(self, client, message):
        """List all admins (admin only)."""
        if not await self._check_admin(message.from_user.id):
            await message.reply("❌ Você não é administrador.")
            return

        try:
            admins = await self.db.list_admins()
            if not admins:
                await message.reply("Nenhum administrador cadastrado.")
                return

            text = "**Administradores:**\n\n"
            for admin_id in admins:
                text += f"• {admin_id}\n"

            await message.reply(text)
        except Exception as e:
            logger.error(f"Error in _on_listadmin: {e}")
            await message.reply("❌ Erro ao listar administradores.")

    async def _on_backup(self, client, message):
        """Send Redis backup file (admin only)."""
        if not await self._check_admin(message.from_user.id):
            await message.reply("❌ Você não é administrador.")
            return

        try:
            result = await self.db.backup()
            if not result:
                await message.reply("Backup já foi feito hoje.")
                return

            redis_path = os.getenv("PATH_REDIS", "/var/lib/redis/dump.rdb")
            if not os.path.exists(redis_path):
                await message.reply(f"Arquivo de backup não encontrado em {redis_path}")
                return

            await message.reply_document(
                document=redis_path,
                caption=f"Backup Redis — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        except Exception as e:
            logger.error(f"Error in _on_backup: {e}")
            await message.reply("Erro ao fazer backup.")

    async def _on_deactivatedurl(self, client, message):
        """List deactivated feeds (admin only)."""
        if not await self._check_admin(message.from_user.id):
            await message.reply("❌ Você não é administrador.")
            return

        try:
            urls = await self.db.get_urls_deactivated()
            if not urls:
                await message.reply("Nenhum feed desativado.")
                return

            text = "**Feeds Desativados:**\n\n"
            for url in urls:
                text += f"`/removekey {url}`\n"

            await message.reply(text)
        except Exception as e:
            logger.error(f"Error in _on_deactivatedurl: {e}")
            await message.reply("Erro ao listar feeds desativados.")

    async def _on_activateallurl(self, client, message):
        """Activate all RSS feeds (admin only)."""
        if not await self._check_admin(message.from_user.id):
            await message.reply("❌ Você não é administrador.")
            return

        try:
            result = await self.db.activate_all_urls()
            if result:
                await message.reply("✅ Todos os feeds foram ativados.")
            else:
                await message.reply("Nenhum feed para ativar.")
        except Exception as e:
            logger.error(f"Error in _on_activateallurl: {e}")
            await message.reply("Erro ao ativar feeds.")

    async def _on_allurl(self, client, message):
        """List all active feeds with metadata (admin only)."""
        if not await self._check_admin(message.from_user.id):
            await message.reply("❌ Você não é administrador.")
            return

        try:
            urls = await self.db.get_urls_activated()
            if not urls:
                await message.reply("Nenhum feed ativo.")
                return

            # Build messages, splitting if text exceeds Telegram's 4096 char limit
            messages = []
            current_text = "**Feeds Ativos:**\n\n"
            max_length = 4000  # Leave room for safety margin

            for url in urls:
                metadata = await self.db.get_url_metadata(url)
                if metadata:
                    last_update = metadata.get("last_update", "N/A")
                    last_url = metadata.get("last_url", "N/A")
                    entry_text = f"🔗 {url}\n  Última atualização: {last_update}\n  Último artigo: {last_url}\n\n"

                    # If adding this entry would exceed limit, save current message and start new one
                    if len(current_text) + len(entry_text) > max_length:
                        messages.append(current_text)
                        current_text = f"**Feeds Ativos (cont.):**\n\n{entry_text}"
                    else:
                        current_text += entry_text

            # Add remaining text
            if current_text != "**Feeds Ativos:**\n\n":
                messages.append(current_text)

            # Send all messages
            for msg in messages:
                await message.reply(msg)

        except Exception as e:
            logger.error(f"Error in _on_allurl: {e}")
            await message.reply("Erro ao listar feeds.")

    async def _on_deactivated(self, client, message):
        """List deactivated URLs."""
        try:
            urls = await self.db.get_urls_deactivated()
            count = len(urls)
            await message.reply(f"Existem {count} feed(s) inativo(s) no momento.")
        except Exception as e:
            logger.error(f"Error in _on_deactivated: {e}")
            await message.reply("Erro ao listar inativos.")

    async def _on_activated(self, client, message):
        """List active URLs."""
        try:
            urls = await self.db.get_urls_activated()
            count = len(urls)
            await message.reply(f"Existem {count} feed(s) ativo(s) no momento.")
        except Exception as e:
            logger.error(f"Error in _on_activated: {e}")
            await message.reply("Erro ao listar ativos.")

    async def _on_userinfo(self, client, message):
        """Send subscription info for all active chats."""
        try:
            # Get all unique chat IDs from URL subscriptions
            urls = await self.db.get_urls_activated()
            if not urls:
                await message.reply("Nenhum feed ativo.")
                return

            chat_ids = set()
            for url in urls:
                chats = await self.db.get_chats_for_url(url)
                for chat_info in chats:
                    chat_ids.add(chat_info["chat_id"])

            if not chat_ids:
                await message.reply("Nenhum chat com feeds ativos.")
                return

            text = "**Chats com Feeds Ativos:**\n\n"
            for chat_id in sorted(list(chat_ids))[:50]:
                text += f"Chat ID: `{chat_id}`\n"

            await message.reply(text)
        except Exception as e:
            logger.error(f"Error in _on_userinfo: {e}")
            await message.reply("Erro ao listar chats.")
