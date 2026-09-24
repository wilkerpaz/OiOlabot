import logging
import os
from datetime import datetime

from decouple import config
from pyrogram import filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Document

from util.datehandler import DateHandler
from util.feed_health import DEFAULT_STALE_DAYS, build_feed_errors_report

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
            MessageHandler(self._on_activated, filters.command("activated"))
        )
        self.client.add_handler(
            MessageHandler(self._on_deactivated, filters.command("deactivated"))
        )
        self.client.add_handler(
            MessageHandler(self._on_userinfo, filters.command("userinfo"))
        )
        self.client.add_handler(
            MessageHandler(self._on_getkey, filters.command("getkey"))
        )
        self.client.add_handler(
            MessageHandler(self._on_removekey, filters.command("removekey"))
        )
        self.client.add_handler(
            MessageHandler(self._on_feederrors, filters.command("feederrors"))
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
            logger.error(f"Error in _on_owner: {e}", exc_info=True)
            await message.reply("Erro ao definir proprietário.")

    async def _check_admin(self, user_id: int) -> bool:
        """Check if user is an admin."""
        return await self.db.is_admin(user_id)

    async def _on_feederrors(self, client, message):
        """List feeds with fetch errors or no new post in N days (admin only).

        Usage: /feederrors [dias] — default 60 days.
        """
        if not await self._check_admin(message.from_user.id):
            await message.reply("❌ Você não é administrador.")
            return

        args = message.command[1:]
        stale_days = DEFAULT_STALE_DAYS
        if args:
            if not args[0].isdigit() or int(args[0]) < 1:
                await message.reply(
                    f"Uso: /feederrors [dias]\nPadrão: {DEFAULT_STALE_DAYS} dias sem posts novos."
                )
                return
            stale_days = int(args[0])

        try:
            for text in await build_feed_errors_report(self.db, stale_days):
                await message.reply(text)
        except Exception as e:
            logger.error(f"Error in _on_feederrors: {e}", exc_info=True)
            await message.reply(f"❌ Erro ao verificar feeds: {type(e).__name__}")

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
            "/activated — Mostra número de feeds ativos\n"
            "/deactivated — Mostra número de feeds inativos\n"
            "/deactivatedurl — Lista feeds desativados\n"
            "/activateallurl — Ativa todos os feeds\n"
            "/feederrors [dias] — Feeds com erro ou sem posts há mais de N dias (padrão 60)\n\n"
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
            logger.error(f"Error in _on_addadmin: {e}", exc_info=True)
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
            logger.error(f"Error in _on_removeadmin: {e}", exc_info=True)
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
            logger.error(f"Error in _on_listadmin: {e}", exc_info=True)
            await message.reply("❌ Erro ao listar administradores.")

    async def _on_backup(self, client, message):
        """Create and send Redis backup file (admin only)."""
        if not await self._check_admin(message.from_user.id):
            await message.reply("❌ Você não é administrador.")
            return

        try:
            await message.reply("⏳ Criando backup do banco de dados...")

            # Trigger Redis backup
            result = await self.db.backup()
            if not result:
                logger.info("Backup already done today, attempting to send existing file")

            # Get Redis backup path from .env
            redis_path = config("PATH_REDIS", default="/var/lib/redis/dump.rdb")
            logger.info(f"Attempting backup path from .env: {redis_path}")

            # Try primary path
            if not os.path.exists(redis_path):
                logger.warning(f"Path not found: {redis_path}")
                # Try alternative paths
                alternative_paths = [
                    "/var/lib/redis/dump.rdb",
                    "/data/dump.rdb",
                    os.path.expanduser("~/.redis/dump.rdb"),
                ]
                for alt_path in alternative_paths:
                    if os.path.exists(alt_path):
                        redis_path = alt_path
                        logger.info(f"Found backup at alternative path: {redis_path}")
                        break

            if not os.path.exists(redis_path):
                logger.error(f"Backup file not found at any path. Tried: {redis_path}")
                await message.reply(
                    f"❌ Arquivo de backup não encontrado.\n\n"
                    f"**Configuração esperada:**\n"
                    f"`PATH_REDIS={redis_path}`\n\n"
                    f"**Verifique:**\n"
                    f"1. O arquivo existe em `{redis_path}`?\n"
                    f"2. A variável `PATH_REDIS` está no `.env`?\n"
                    f"3. O Redis está rodando?"
                )
                return

            # Verify file size and readability
            file_size = os.path.getsize(redis_path)
            if file_size == 0:
                logger.error(f"Backup file is empty: {redis_path}")
                await message.reply("❌ Arquivo de backup está vazio. Redis pode não estar rodando.")
                return

            file_size_mb = file_size / (1024 * 1024)
            logger.info(f"Backup file ready at {redis_path}: {file_size_mb:.2f} MB")

            # Send backup file
            caption = f"Backup Redis 💾\n📦 Tamanho: {file_size_mb:.2f} MB\n📁 Path: {redis_path}\n⏰ {DateHandler.get_datetime_now().strftime('%Y-%m-%d %H:%M:%S')}"
            await message.reply_document(
                document=redis_path,
                caption=caption,
                file_name=f"redis_dump_{DateHandler.get_datetime_now().strftime('%Y%m%d_%H%M%S')}.rdb"
            )
            logger.info(f"Backup sent successfully: {file_size_mb:.2f} MB")
            await message.reply("✅ Backup concluído e arquivo enviado.")

        except Exception as e:
            logger.error(f"Error in _on_backup: {e}", exc_info=True)
            await message.reply(f"❌ Erro ao fazer backup: {type(e).__name__}: {str(e)}")

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
                text += f"{url}\n`/getkey *^{url}^`\n\n"

            await message.reply(text)
        except Exception as e:
            logger.error(f"Error in _on_deactivatedurl: {e}", exc_info=True)
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
            logger.error(f"Error in _on_activateallurl: {e}", exc_info=True)
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
            max_length = 3500  # Conservative limit (Telegram max is 4096, but account for overhead)
            page_num = 1

            for url in urls:
                metadata = await self.db.get_url_metadata(url)
                if metadata:
                    last_update = metadata.get("last_update", "N/A")
                    last_url = metadata.get("last_url", "N/A")
                    entry_text = f"🔗 {url}\n  Última atualização: {last_update}\n  Último artigo: {last_url}\n\n"

                    # If adding this entry would exceed limit, save current message and start new one
                    if len(current_text) + len(entry_text) > max_length:
                        if current_text.strip():
                            messages.append(current_text.strip())
                        page_num += 1
                        current_text = f"**Feeds Ativos (página {page_num}):**\n\n{entry_text}"
                    else:
                        current_text += entry_text

            # Add remaining text
            if current_text.strip() and current_text != "**Feeds Ativos:**\n\n":
                messages.append(current_text.strip())

            if not messages:
                await message.reply("Nenhum feed com metadados encontrado.")
                return

            # Send all messages
            for msg in messages:
                if len(msg) > 4096:
                    logger.warning(f"Message exceeds 4096 chars ({len(msg)}), truncating")
                    msg = msg[:4000] + "..."
                await message.reply(msg)

        except Exception as e:
            logger.error(f"Error in _on_allurl: {e}", exc_info=True)
            await message.reply(f"❌ Erro ao listar feeds: {type(e).__name__}")

    async def _on_deactivated(self, client, message):
        """List deactivated URLs (admin only)."""
        if not await self._check_admin(message.from_user.id):
            await message.reply("❌ Você não é administrador.")
            return

        try:
            urls = await self.db.get_urls_deactivated()
            count = len(urls)
            await message.reply(f"Existem {count} feed(s) inativo(s) no momento.")
        except Exception as e:
            logger.error(f"Error in _on_deactivated: {e}", exc_info=True)
            await message.reply("Erro ao listar inativos.")

    async def _on_activated(self, client, message):
        """List active URLs (admin only)."""
        if not await self._check_admin(message.from_user.id):
            await message.reply("❌ Você não é administrador.")
            return

        try:
            urls = await self.db.get_urls_activated()
            count = len(urls)
            await message.reply(f"Existem {count} feed(s) ativo(s) no momento.")
        except Exception as e:
            logger.error(f"Error in _on_activated: {e}", exc_info=True)
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
            logger.error(f"Error in _on_userinfo: {e}", exc_info=True)
            await message.reply("Erro ao listar chats.")

    async def _on_getkey(self, client, message):
        """Search Redis keys by pattern, suggesting /removekey for each (admin only)."""
        if not await self._check_admin(message.from_user.id):
            await message.reply("❌ Você não é administrador.")
            return

        try:
            args = message.text.split(None, 1)
            if len(args) < 2:
                await message.reply("❌ Uso: `/getkey <padrão>` (ex: `/getkey user_url:*`)")
                return

            pattern = args[1].strip()
            keys = await self.db._find(pattern)
            if not keys:
                await message.reply(f"Nenhuma chave encontrada para: `{pattern}`")
                return

            messages = []
            current_text = f"**Chaves encontradas ({len(keys)}):**\n\n"
            max_length = 3500

            for key in keys:
                entry = f"`/removekey {key}`\n"
                if len(current_text) + len(entry) > max_length:
                    messages.append(current_text.strip())
                    current_text = entry
                else:
                    current_text += entry

            if current_text.strip():
                messages.append(current_text.strip())

            for msg in messages:
                await message.reply(msg)
        except Exception as e:
            logger.error(f"Error in _on_getkey: {e}", exc_info=True)
            await message.reply("❌ Erro ao buscar chaves.")

    async def _on_removekey(self, client, message):
        """Delete an exact Redis key (admin only)."""
        if not await self._check_admin(message.from_user.id):
            await message.reply("❌ Você não é administrador.")
            return

        try:
            args = message.text.split(None, 1)
            if len(args) < 2:
                await message.reply("❌ Uso: `/removekey <chave_exata>` (use `/getkey <padrão>` para encontrar a chave)")
                return

            key = args[1].strip()
            deleted = await self.db.redis.delete(key)
            if deleted:
                await message.reply(f"✅ Chave removida: `{key}`")
            else:
                await message.reply(f"⚠️ Chave não encontrada: `{key}`")
        except Exception as e:
            logger.error(f"Error in _on_removekey: {e}", exc_info=True)
            await message.reply("❌ Erro ao remover chave.")
