import logging
from datetime import datetime, timedelta

from pyrogram import filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler

from util.datehandler import DateHandler
from util.calendar import create_calendar, process_calendar_selection
from util.scrapers.liturgia import LiturgiaScraper
from util.scrapers.santo import SantoScraper

logger = logging.getLogger(__name__)


class LiturgyMixin:
    """Mixin for daily liturgy handlers."""

    def _register_liturgy_handlers(self) -> None:
        """Register liturgy-specific handlers."""
        self.client.add_handler(
            MessageHandler(self._on_help, filters.command("help"))
        )
        self.client.add_handler(
            MessageHandler(self.today_liturgy, filters.command("hoje"))
        )
        self.client.add_handler(
            MessageHandler(self.yesterday_liturgy, filters.command("ontem"))
        )
        self.client.add_handler(
            MessageHandler(self.tomorrow_liturgy, filters.command("amanha"))
        )
        self.client.add_handler(
            MessageHandler(self.sunday_liturgy, filters.command("dominical"))
        )
        self.client.add_handler(
            MessageHandler(self.saint_of_day, filters.command("santododia"))
        )
        self.client.add_handler(
            MessageHandler(self.show_calendar, filters.command("calendario"))
        )
        self.client.add_handler(
            CallbackQueryHandler(self.handle_calendar_selection)
        )
        self.client.add_handler(
            MessageHandler(self.start_daily_delivery, filters.command("start"))
        )
        self.client.add_handler(
            MessageHandler(self.stop_daily_delivery, filters.command("stop"))
        )

    async def today_liturgy(self, client, message):
        """Send today's liturgy."""
        now = DateHandler.get_datetime_now()
        target_date = DateHandler.date(now)
        await self._send_liturgy(message, target_date)

    async def yesterday_liturgy(self, client, message):
        """Send yesterday's liturgy."""
        now = DateHandler.get_datetime_now()
        target_date = DateHandler.date(now) - timedelta(days=1)
        await self._send_liturgy(message, target_date)

    async def tomorrow_liturgy(self, client, message):
        """Send tomorrow's liturgy."""
        now = DateHandler.get_datetime_now()
        target_date = DateHandler.date(now) + timedelta(days=1)
        await self._send_liturgy(message, target_date)

    async def sunday_liturgy(self, client, message):
        """Send Sunday's liturgy."""
        now = DateHandler.get_datetime_now()
        current_date = DateHandler.date(now)
        days_until_sunday = (6 - current_date.weekday()) % 7
        if days_until_sunday == 0:
            days_until_sunday = 7
        sunday_date = current_date + timedelta(days=days_until_sunday)
        await self._send_liturgy(message, sunday_date)

    async def saint_of_day(self, client, message):
        """Send saint of the day."""
        scraper = SantoScraper()
        text = await scraper.safe_fetch()
        try:
            await message.reply(text)
        except Exception as e:
            logger.error(f"Error sending saint: {e}")

    async def show_calendar(self, client, message):
        """Show date selection calendar."""
        keyboard = create_calendar()
        try:
            await message.reply("Escolha uma data:", reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Error showing calendar: {e}")

    async def handle_calendar_selection(self, client, callback_query):
        """Handle calendar date selection."""
        ret_data = process_calendar_selection(client, callback_query)
        is_selected, selected_date = ret_data

        if is_selected and selected_date:
            await self._send_liturgy(callback_query, selected_date.date())

    async def _send_liturgy(self, update, target_date):
        """Helper to send liturgy for a specific date."""
        scraper = LiturgiaScraper(target_date)
        text = await scraper.safe_fetch()

        try:
            if hasattr(update, 'reply'):  # MessageHandler
                await update.reply(text)
            elif hasattr(update, 'edit_message_text'):  # CallbackQueryHandler
                await update.edit_message_text(text)
        except Exception as e:
            logger.error(f"Error sending liturgy: {e}")

    async def start_daily_delivery(self, client, message):
        """Enable daily liturgy delivery."""
        chat_id = message.chat.id
        user_id = message.from_user.id
        chat_name = message.chat.username or message.chat.title

        try:
            await self.db.add_daily_liturgy_subscription(chat_id, chat_name, user_id)
            await message.reply("✅ Você receberá a liturgia diária às 7h!")
        except Exception as e:
            logger.error(f"Error subscribing to daily liturgy: {e}")
            await message.reply("Erro ao ativar entrega diária.")

    async def stop_daily_delivery(self, client, message):
        """Disable daily liturgy delivery."""
        chat_id = message.chat.id

        try:
            await self.db.remove_daily_liturgy_subscription(chat_id)
            await message.reply("✅ Entrega diária desativada.")
        except Exception as e:
            logger.error(f"Error unsubscribing from daily liturgy: {e}")
            await message.reply("Erro ao desativar entrega diária.")

    async def _on_help(self, client, message):
        """Send help message with available commands."""
        help_text = (
            "**Comandos Disponíveis (Liturgia)**\n\n"
            "/hoje — Leitura de hoje\n"
            "/ontem — Leitura de ontem\n"
            "/amanha — Leitura de amanhã\n"
            "/dominical — Leitura de domingo\n"
            "/santododia — Santo do dia\n"
            "/calendario — Escolher data\n"
            "/start — Receber liturgia diariamente às 7h\n"
            "/stop — Parar entrega diária\n"
            "/addurl — Adicionar feed RSS\n"
            "/listurl — Listar feeds\n"
            "/removeurl — Remover feed\n"
            "/welcome — Mensagem de boas-vindas\n"
            "/goodbye — Mensagem de despedida\n"
        )
        try:
            await message.reply(help_text)
        except Exception as e:
            logger.error(f"Error sending help: {e}")
