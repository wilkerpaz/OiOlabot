import logging

from pyrogram import filters
from pyrogram.handlers import MessageHandler

logger = logging.getLogger(__name__)


class WelcomeMixin:
    """Mixin for welcome/goodbye message handlers."""

    def _register_welcome_handlers(self) -> None:
        """Register welcome/goodbye/permissions handlers."""
        self.client.add_handler(
            MessageHandler(self._on_new_chat_members, filters.new_chat_members)
        )
        self.client.add_handler(
            MessageHandler(self._on_left_chat_member, filters.left_chat_member)
        )
        self.client.add_handler(
            MessageHandler(self.set_welcome, filters.command("welcome") & filters.group)
        )
        self.client.add_handler(
            MessageHandler(self.set_goodbye, filters.command("goodbye") & filters.group)
        )
        self.client.add_handler(
            MessageHandler(self.disable_welcome, filters.command("disable_welcome") & filters.group)
        )
        self.client.add_handler(
            MessageHandler(self.disable_goodbye, filters.command("disable_goodbye") & filters.group)
        )
        self.client.add_handler(
            MessageHandler(self.lock_settings, filters.command("lock") & filters.group)
        )
        self.client.add_handler(
            MessageHandler(self.unlock_settings, filters.command("unlock") & filters.group)
        )
        self.client.add_handler(
            MessageHandler(self.quiet_mode, filters.command("quiet") & filters.group)
        )
        self.client.add_handler(
            MessageHandler(self.unquiet_mode, filters.command("unquiet") & filters.group)
        )

    async def _on_new_chat_members(self, client, message):
        """Handle new members joining - send welcome message if configured."""
        chat_id = message.chat.id
        config = await self.db.get_group_config(chat_id)
        if not config:
            return

        welcome_msg = config.get("chat_welcome", "False")
        if welcome_msg == "False":
            return

        text = f"Bem-vindo ao {message.chat.title}!\n\n{welcome_msg}"
        try:
            await message.reply(text)
        except Exception as e:
            logger.error(f"Error sending welcome message: {e}")

    async def _on_left_chat_member(self, client, message):
        """Handle members leaving - send goodbye message if configured."""
        chat_id = message.chat.id
        config = await self.db.get_group_config(chat_id)
        if not config:
            return

        goodbye_msg = config.get("chat_goodbye", "False")
        if goodbye_msg == "False":
            return

        text = f"Até logo!\n\n{goodbye_msg}"
        try:
            await message.reply(text)
        except Exception as e:
            logger.error(f"Error sending goodbye message: {e}")

    async def set_welcome(self, client, message):
        """Set welcome message."""
        chat_id = message.chat.id
        user_id = message.from_user.id

        config = await self.db.get_group_config(chat_id)
        if not config:
            await message.reply("O bot não está registrado neste grupo.")
            return

        # Check permissions
        if not await self._check_permissions(chat_id, user_id, config):
            await message.reply("Você não tem permissão para alterar as configurações.")
            return

        # Extract message text after command
        args = message.command
        if len(args) < 2:
            await message.reply("Use: /welcome <mensagem>")
            return

        welcome_text = " ".join(args[1:])
        config["chat_welcome"] = welcome_text
        await self.db.set_group_config(chat_id, config)
        await message.reply("Mensagem de boas-vindas atualizada!")

    async def set_goodbye(self, client, message):
        """Set goodbye message."""
        chat_id = message.chat.id
        user_id = message.from_user.id

        config = await self.db.get_group_config(chat_id)
        if not config:
            await message.reply("O bot não está registrado neste grupo.")
            return

        if not await self._check_permissions(chat_id, user_id, config):
            await message.reply("Você não tem permissão para alterar as configurações.")
            return

        args = message.command
        if len(args) < 2:
            await message.reply("Use: /goodbye <mensagem>")
            return

        goodbye_text = " ".join(args[1:])
        config["chat_goodbye"] = goodbye_text
        await self.db.set_group_config(chat_id, config)
        await message.reply("Mensagem de despedida atualizada!")

    async def disable_welcome(self, client, message):
        """Disable welcome messages."""
        chat_id = message.chat.id
        user_id = message.from_user.id

        config = await self.db.get_group_config(chat_id)
        if not config:
            await message.reply("O bot não está registrado neste grupo.")
            return

        if not await self._check_permissions(chat_id, user_id, config):
            await message.reply("Você não tem permissão para alterar as configurações.")
            return

        config["chat_welcome"] = "False"
        await self.db.set_group_config(chat_id, config)
        await message.reply("Mensagens de boas-vindas desativadas.")

    async def disable_goodbye(self, client, message):
        """Disable goodbye messages."""
        chat_id = message.chat.id
        user_id = message.from_user.id

        config = await self.db.get_group_config(chat_id)
        if not config:
            await message.reply("O bot não está registrado neste grupo.")
            return

        if not await self._check_permissions(chat_id, user_id, config):
            await message.reply("Você não tem permissão para alterar as configurações.")
            return

        config["chat_goodbye"] = "False"
        await self.db.set_group_config(chat_id, config)
        await message.reply("Mensagens de despedida desativadas.")

    async def lock_settings(self, client, message):
        """Lock settings to admin only."""
        chat_id = message.chat.id
        user_id = message.from_user.id

        config = await self.db.get_group_config(chat_id)
        if not config:
            await message.reply("O bot não está registrado neste grupo.")
            return

        if not await self._check_permissions(chat_id, user_id, config):
            await message.reply("Você não tem permissão para alterar as configurações.")
            return

        config["chat_lock"] = "True"
        await self.db.set_group_config(chat_id, config)
        await message.reply("Configurações bloqueadas. Só admins podem alterá-las.")

    async def unlock_settings(self, client, message):
        """Allow all users to change settings."""
        chat_id = message.chat.id
        user_id = message.from_user.id

        config = await self.db.get_group_config(chat_id)
        if not config:
            await message.reply("O bot não está registrado neste grupo.")
            return

        if not await self._check_permissions(chat_id, user_id, config):
            await message.reply("Você não tem permissão para alterar as configurações.")
            return

        config["chat_lock"] = "False"
        await self.db.set_group_config(chat_id, config)
        await message.reply("Configurações desbloqueadas. Qualquer um pode alterá-las.")

    async def quiet_mode(self, client, message):
        """Enable quiet mode (suppress error messages)."""
        chat_id = message.chat.id
        user_id = message.from_user.id

        config = await self.db.get_group_config(chat_id)
        if not config:
            await message.reply("O bot não está registrado neste grupo.")
            return

        if not await self._check_permissions(chat_id, user_id, config):
            await message.reply("Você não tem permissão para alterar as configurações.")
            return

        config["chat_quiet"] = "True"
        await self.db.set_group_config(chat_id, config)

    async def unquiet_mode(self, client, message):
        """Disable quiet mode."""
        chat_id = message.chat.id
        user_id = message.from_user.id

        config = await self.db.get_group_config(chat_id)
        if not config:
            await message.reply("O bot não está registrado neste grupo.")
            return

        if not await self._check_permissions(chat_id, user_id, config):
            await message.reply("Você não tem permissão para alterar as configurações.")
            return

        config["chat_quiet"] = "False"
        await self.db.set_group_config(chat_id, config)

    async def _check_permissions(self, chat_id: int, user_id: int, config: dict) -> bool:
        """Check if user can modify group settings."""
        # Admin check
        chat_adm = config.get("chat_adm")
        if str(user_id) == str(chat_adm):
            return True

        # Lock check
        is_locked = config.get("chat_lock") == "True"
        return not is_locked
