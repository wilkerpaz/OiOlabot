import logging
import httpx

from pyrogram import filters
from pyrogram.handlers import MessageHandler

from util.datehandler import DateHandler
from util.scrapers.liturgia import LiturgiaScraper
from util.scrapers.audio import AudioScraper
from worker.error_handler import ErrorHandler

logger = logging.getLogger(__name__)


class AdminLiturgyMixin:
    """Mixin for admin-only commands in the liturgy bot."""

    def _register_admin_handlers(self) -> None:
        """Register admin-only command handlers."""
        self.client.add_handler(
            MessageHandler(self._on_admin, filters.command("admin"))
        )
        self.client.add_handler(
            MessageHandler(self._on_senddailyliturgy, filters.command("senddailyliturgy"))
        )
        self.client.add_handler(
            MessageHandler(self._on_sendaudioliturgy, filters.command("sendaudioliturgy"))
        )
        self.client.add_handler(
            MessageHandler(self._on_activateallliturgy, filters.command("activateallliturgy"))
        )
        self.client.add_handler(
            MessageHandler(self._on_deactivated, filters.command("deactivated"))
        )
        self.client.add_handler(
            MessageHandler(self._on_activated, filters.command("activated"))
        )
        self.client.add_handler(
            MessageHandler(self._on_userinfoliturgy, filters.command("userinfoliturgy"))
        )
        self.client.add_handler(
            MessageHandler(self._on_userliturgydeactivated, filters.command("userliturgydeactivated"))
        )

    async def _on_admin(self, client, message):
        """Send admin commands list."""
        admin_text = (
            "**Comandos de Admin (Liturgia)**\n\n"
            "/senddailyliturgy — Envia liturgia do dia para todos\n"
            "/sendaudioliturgy — Envia áudio da homilia para todos\n"
            "/activateallliturgy — Ativa todas as assinaturas\n"
            "/deactivated — Lista usuários desativados\n"
            "/activated — Lista usuários ativados\n"
            "/userinfoliturgy — Detalhes de cada assinatura\n"
            "/userliturgydeactivated — Lista chaves desativadas\n"
        )
        await message.reply(admin_text)

    async def _on_senddailyliturgy(self, client, message):
        """Send daily liturgy to all active subscribers manually."""
        try:
            await message.reply("⏳ Enviando liturgia do dia para todos...")

            now = DateHandler.get_datetime_now()
            today = DateHandler.date(now)

            scraper = LiturgiaScraper(today)
            text = await scraper.fetch()

            if not text:
                await message.reply("Erro ao buscar liturgia do dia.")
                return

            chat_ids = await self.db.get_active_subscriptions()
            if not chat_ids:
                await message.reply("Nenhuma assinatura ativa.")
                return

            async with httpx.AsyncClient(timeout=30) as http_client:
                sent_count = 0
                for chat_id in chat_ids:
                    try:
                        await self._send_message(http_client, chat_id, text)
                        await self.db.set_last_send(chat_id)
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Error sending to {chat_id}: {e}")

            await message.reply(f"✅ Liturgia enviada para {sent_count} chat(s).")
        except Exception as e:
            logger.error(f"Error in _on_senddailyliturgy: {e}")
            await message.reply("Erro ao enviar liturgia.")

    async def _on_sendaudioliturgy(self, client, message):
        """Send daily audio to all active subscribers manually."""
        try:
            await message.reply("⏳ Enviando áudio da homilia para todos...")

            now = DateHandler.get_datetime_now()
            today = DateHandler.date(now)
            today_str = str(today)

            cached_file_id = await self.db.get_cached_audio_file_id(today_str)
            audio_data = None

            if not cached_file_id:
                scraper = AudioScraper(today_str)
                audio_data = await scraper.fetch()
                if not audio_data:
                    await message.reply("Erro ao buscar áudio da homilia.")
                    return

            chat_ids = await self.db.get_active_subscriptions()
            if not chat_ids:
                await message.reply("Nenhuma assinatura ativa.")
                return

            async with httpx.AsyncClient(timeout=30) as http_client:
                sent_count = 0
                for chat_id in chat_ids:
                    if cached_file_id:
                        if await self._send_audio(http_client, chat_id, cached_file_id):
                            sent_count += 1
                    else:
                        file_id = await self._send_audio_file(http_client, chat_id, audio_data.get("path_audio"))
                        if file_id:
                            if sent_count == 0:
                                await self.db.cache_audio_file_id(today_str, file_id)
                            sent_count += 1

            await message.reply(f"✅ Áudio enviado para {sent_count} chat(s).")
        except Exception as e:
            logger.error(f"Error in _on_sendaudioliturgy: {e}")
            await message.reply("Erro ao enviar áudio.")

    async def _on_activateallliturgy(self, client, message):
        """Activate all liturgy subscriptions."""
        try:
            result = await self.db.activate_all_subscriptions()
            if result:
                await message.reply("✅ Todas as assinaturas foram ativadas.")
            else:
                await message.reply("Nenhuma assinatura para ativar.")
        except Exception as e:
            logger.error(f"Error in _on_activateallliturgy: {e}")
            await message.reply("Erro ao ativar assinaturas.")

    async def _on_deactivated(self, client, message):
        """List deactivated subscriptions."""
        try:
            chat_ids = await self.db.get_deactivated_subscriptions()
            count = len(chat_ids)
            await message.reply(f"Existem {count} inativos no momento.")
        except Exception as e:
            logger.error(f"Error in _on_deactivated: {e}")
            await message.reply("Erro ao listar inativos.")

    async def _on_activated(self, client, message):
        """List active subscriptions."""
        try:
            chat_ids = await self.db.get_active_subscriptions()
            count = len(chat_ids)
            await message.reply(f"Existem {count} ativos no momento.")
        except Exception as e:
            logger.error(f"Error in _on_activated: {e}")
            await message.reply("Erro ao listar ativos.")

    async def _on_userinfoliturgy(self, client, message):
        """Send user info for all active subscriptions."""
        try:
            active_ids = await self.db.get_active_subscriptions()
            if not active_ids:
                await message.reply("Nenhuma assinatura ativa.")
                return

            text = "**Usuários Ativos (Liturgia):**\n\n"
            for chat_id in active_ids[:50]:
                text += f"Chat ID: `{chat_id}`\n"

            await message.reply(text)
        except Exception as e:
            logger.error(f"Error in _on_userinfoliturgy: {e}")
            await message.reply("Erro ao listar usuários.")

    async def _on_userliturgydeactivated(self, client, message):
        """Send deactivated subscription keys."""
        try:
            deactivated_ids = await self.db.get_deactivated_subscriptions()
            if not deactivated_ids:
                await message.reply("Nenhuma assinatura desativada.")
                return

            text = "**Assinaturas Desativadas:**\n\n"
            for chat_id in deactivated_ids[:50]:
                text += f"`/removekey liturgy:{chat_id}`\n"

            await message.reply(text)
        except Exception as e:
            logger.error(f"Error in _on_userliturgydeactivated: {e}")
            await message.reply("Erro ao listar desativadas.")

    async def _send_message(self, client: httpx.AsyncClient, chat_id: int, text: str) -> bool:
        """Send a text message via Telegram Bot API. Return True if successful."""
        from decouple import config
        api_token = config("DEV_TOKEN_LD")
        api_url = f"https://api.telegram.org/bot{api_token}"

        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        response = await client.post(f"{api_url}/sendMessage", json=payload)

        strategy, error_details = ErrorHandler.classify_response(response)
        if strategy == "permanent":
            ErrorHandler.log_error(chat_id, error_details, strategy)
            await self.db.deactivate_subscription(chat_id)
        elif strategy != "success":
            ErrorHandler.log_error(chat_id, error_details, strategy)

        return strategy == "success"

    async def _send_audio(self, client: httpx.AsyncClient, chat_id: int, file_id: str) -> bool:
        """Send audio via cached file_id. Return True if successful."""
        from decouple import config
        api_token = config("DEV_TOKEN_LD")
        api_url = f"https://api.telegram.org/bot{api_token}"

        payload = {
            "chat_id": chat_id,
            "audio": file_id,
        }
        response = await client.post(f"{api_url}/sendAudio", json=payload)

        strategy, error_details = ErrorHandler.classify_response(response)
        if strategy == "permanent":
            ErrorHandler.log_error(chat_id, error_details, strategy)
            await self.db.deactivate_subscription(chat_id)
        elif strategy != "success":
            ErrorHandler.log_error(chat_id, error_details, strategy)

        return strategy == "success"

    async def _send_audio_file(self, client: httpx.AsyncClient, chat_id: int, file_path: str) -> str | None:
        """Send audio file and return file_id. Returns None if failed or on permanent error."""
        from decouple import config
        api_token = config("DEV_TOKEN_LD")
        api_url = f"https://api.telegram.org/bot{api_token}"

        with open(file_path, "rb") as audio_file:
            files = {"audio": audio_file}
            data = {"chat_id": chat_id}
            response = await client.post(f"{api_url}/sendAudio", files=files, data=data)

            strategy, error_details = ErrorHandler.classify_response(response)
            if strategy == "permanent":
                ErrorHandler.log_error(chat_id, error_details, strategy)
                await self.db.deactivate_subscription(chat_id)
                return None
            elif strategy != "success":
                ErrorHandler.log_error(chat_id, error_details, strategy)
                return None

            try:
                result = response.json()
                if result.get("ok") and "result" in result:
                    message = result["result"]
                    if "audio" in message:
                        return message["audio"].get("file_id")
            except Exception as e:
                logger.error(f"Error parsing response for {chat_id}: {e}")
            return None
