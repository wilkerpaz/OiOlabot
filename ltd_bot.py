import logging

from datetime import datetime, timedelta
from html import escape

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from babel.dates import format_date
from decouple import config
from pyrogram import Client, filters, emoji
from pyrogram.errors import RPCError
from pyrogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

import util.homiliadodia
from util import calendar
from util.database_daily_liturgy import DatabaseHandler
from util.datehandler import DateHandler
from util.feedhandler import FeedHandler
from util.liturgiadiaria import BuscarLiturgia

LOG = config('LOG')
logging.basicConfig(level=LOG, format='%(name)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

DB = config('DB_LD')
BOT_NAME = config('BOT_NAME_LD')
API_TOKEN = config('DEV_TOKEN_LD')  # Tokens do Bot de Desenvolvimento

bot = Client(session_name=BOT_NAME, bot_token=API_TOKEN)
db = DatabaseHandler(DB)

buttons = [
    [
        KeyboardButton(text='/ontem'),
        KeyboardButton(text='/hoje'),
        KeyboardButton(text='/amanha'),
    ],
    [
        KeyboardButton(text='/dominical'),
        KeyboardButton(text='/calendario'),
        KeyboardButton(text='/help'),
    ],
]
keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

help_text = 'Welcomes everyone that enters a group chat that this bot is a ' \
            'part of. By default, only the person who invited the bot into ' \
            'the group is able to change settings.\nCommands:\n\n' \
            '/welcome - Set welcome message\n' \
            '/goodbye - Set goodbye message\n' \
            '/disable_welcome - Disable the goodbye message\n' \
            '/disable_goodbye - Disable the goodbye message\n' \
            '/lock - Only the person who invited the bot can change messages\n' \
            '/unlock - Everyone can change messages\n' \
            '/quiet - Disable "Sorry, only the person who..." ' \
            '& help messages\n' \
            '/unquiet - Enable "Sorry, only the person who..." ' \
            '& help messages\n\n' \
            '/msg <msg> - To send message\n' \
            'You can use _$username_ and _$title_ as placeholders when setting' \
            ' messages. [HTML formatting]' \
            '(https://core.telegram.org/bots/api#formatting-options) ' \
            'is also supported.\n\n' \
            "Controls\n " \
            "/start - Activates the bot. If you have subscribed to RSS feeds, you will receive news from now on\n " \
            "/stop - Deactivates the bot. You won't receive any messages from the bot until you activate the bot again \
            using the start comand\n"

help_text_feed = "RSS Management\n" \
                 "/addurl <url> - Adds a util subscription to your list. or\n" \
                 "/addurl @chanel <url> - Add url in Your chanel to receve feed. or\n" \
                 "/addurl @group <url> - Add url in Your group to receve feed.\n" \
                 "/listurl - Shows all your subscriptions as a list.\n" \
                 "/remove <url> - Removes an exisiting subscription from your list.\n" \
                 "/remove @chanel <url> - Removes url in Your chanel.\n" \
                 "/remove @group <url> - Removes url in Your group.\n" \
                 "Other\n" \
                 "/help - Shows the help menu  :)"

help_text = help_text + help_text_feed


def _check(_, update, override_lock=None):
    """
    Perform some hecks on the update. If checks were successful, returns True,
    else sends an error message to the chat and returns False.
    """
    chat_id = update.chat.id
    user_id = update.from_user.id

    if chat_id > 0:
        text = 'Please add me to a group first!'
        update.reply_text(text=text)
        return False

    locked = override_lock if override_lock is not None \
        else bool(db.get_value_name_key('group:' + str(chat_id), 'chat_lock'))

    if locked and int(db.get_value_name_key('group:' + str(chat_id), 'chat_adm')) != user_id:
        if not bool(db.get_value_name_key('group:' + str(chat_id), 'chat_quiet')):
            text = 'Sorry, only the person who invited me can do that.'
            update.reply_text(chat_id=chat_id, text=text)
        return False

    return True


# Welcome a user to the chat
def _welcome(update, member=None):
    """ Welcomes a user to the chat """
    chat_id = update.chat.id
    chat_title = update.chat.title
    first_name = member.first_name
    logger.info(f'{escape(first_name)} joined to chat {chat_id} ({escape(chat_title)})')

    # Pull the custom message for this chat from the database
    text_group = db.get_value_name_key('group:' + str(chat_id), 'chat_welcome')
    if not text_group:
        return

    # Use default message if there's no custom one set
    welcome_text = f'Hello $username! Welcome to $title {emoji.GRINNING_FACE}'
    if text_group:
        text = welcome_text + '\n' + text_group

    # Replace placeholders and send message
    else:
        text = welcome_text

    # Replace placeholders and send message
    text = text.replace('$username', first_name).replace('$title', chat_title)
    update.reply_text(text=text, quote=False, parse_mode='html')


# Introduce the context to a chat its been added to
def _introduce(client, update):
    """
    Introduces the bot to a chat its been added to and saves the user id of the
    user who invited us.
    """
    me = client.get_me()
    if me.username == '@' + BOT_NAME:
        start(client, update)

    chat_title = update.chat.title
    chat_id = update.chat.id
    first_name = update.from_user.first_name
    chat_name = '@' + update.chat.username if update.chat.username else '@' + update.from_user.username \
        if update.from_user.username else chat_title if chat_title else update.from_user.first_name
    user_id = update.from_user.id

    logger.info(f'Invited by {user_id} to chat {chat_id} ({escape(chat_title)})')

    db.update_group(chat_id=chat_id, chat_name=chat_name, chat_title=chat_title, user_id=user_id)

    text = f'Hello {escape(first_name)}! I will now greet anyone who joins this chat ({chat_title}) with a' \
           f' nice message {emoji.GRINNING_FACE} \n\ncheck the /help command for more info!'
    update.reply_text(text=text, quote=False, parse_mode='html')


@bot.on_message(filters.regex(r'^/(start|help)($|@\w+)'))
async def start(client, update):
    chat_id = update.chat.id
    chat_name = '@' + update.chat.username if update.chat.username else '@' + update.from_user.username \
        if update.from_user.username else update.from_user.first_name
    chat_title = update.chat.title or update.from_user.first_name
    user_id = update.from_user.id
    text = 'Vou te enviar a liturgia todos os dias\n\n' \
           'Você também pode usar uma das opções abaixo para buscar a leitura do dia desejado\n\n' \
           '/ontem - liturgia do dia anterior\n' \
           '/hoje - liturgia do dia\n' \
           '/amanha - liturgia do dia seguinte\n' \
           '/dominical - liturgia dominical\n' \
           '/calendario - escolher um dia específico\n' \
           '/help - exibe esta mensagem.'

    db.set_user_daily_liturgy(chat_id=chat_id, chat_name=chat_name, user_id=user_id)
    await update.delete()
    await update.reply_text(text=text, quote=False, parse_mode='html', reply_markup=keyboard)
    logger.info(f'Invited by {user_id} to chat {chat_id} ({escape(chat_title)})')

    date = DateHandler.get_datetime_now()
    date_full = format_date(date.date(), format='full', locale='pt_br')
    await client.send_chat_action(chat_id, "typing")
    readings = BuscarLiturgia(dia=date.day, mes=date.month, ano=date.year).obter_url()
    if readings:
        await send_daily_liturgy(chat_id, readings)
    await client.send_chat_action(chat_id, "typing")

    audio_telegram = db.get_value_name_key('audio_liturgy', date_full)
    if audio_telegram:
        homily = util.homiliadodia.HomiliadoDia().obter_homilia()
        if homily:
            await send_daily_liturgy(chat_id, homily)
        await client.send_chat_action(chat_id, "upload_audio")
        if audio_telegram:
            await send_daily_liturgy_audio(chat_id, audio_telegram, date_full)


@bot.on_message(filters.regex(r'^/(stop)($|@\w+)'))
def stop(_, update):
    chat_id = update.chat.id
    chat_title = update.chat.title or update.from_user.first_name
    text = 'ok. Você pode digitar /start para iniciar novamente o recebimento das leituras diárias'

    db.del_chat_id_daily_liturgy(chat_id=chat_id)
    update.delete()
    update.reply_text(text=text, quote=False, parse_mode='html', reply_markup=ReplyKeyboardRemove())
    logger.info(f'left chat {chat_id} ({escape(chat_title)})')


@bot.on_message(filters.regex(r'^/(ontem|hoje|amanha|dominical|calendario)(?:\s|$|@\w+\s+)(?:(?P<text>.+))?'))
def check_button(client, update):
    # audio = None
    chat_id = update.chat.id
    chat_name = '@' + update.chat.username if update.chat.username else '@' + update.from_user.username \
        if update.from_user.username else update.from_user.first_name
    user_id = update.from_user.id

    if chat_id < 0:
        if not _check(client, update):
            return

    db.set_user_daily_liturgy(chat_id=chat_id, chat_name=chat_name, user_id=user_id)

    try:
        client.send_chat_action(chat_id, "typing")
        command = update.text
        # update.delete()
        readings = None

        if command == '/ontem':
            date = datetime.now() + timedelta(days=-1)
            readings = BuscarLiturgia(dia=date.day, mes=date.month, ano=date.year).obter_url()
        elif command == '/hoje':
            date = datetime.now()
            readings = BuscarLiturgia(dia=date.day, mes=date.month, ano=date.year).obter_url()
            # audio = util.homiliadodia.HomiliadoDia().obter_arquivo_audio()
        elif command == '/amanha':
            date = datetime.now() + timedelta(days=1)
            readings = BuscarLiturgia(dia=date.day, mes=date.month, ano=date.year).obter_url()
        elif command == '/dominical':
            weekday = 6 - datetime.now().weekday()
            date = datetime.now() + timedelta(days=weekday)
            readings = BuscarLiturgia(dia=date.day, mes=date.month, ano=date.year).obter_url()
        else:
            text = "Please select a date:"
            calendar_keyboard = calendar.create_calendar()
            client.send_message(chat_id, text, disable_web_page_preview=True, reply_markup=calendar_keyboard)

        chat = update.chat
        chat_username = chat.username if (chat.username and chat.type != 'private') else None
        if readings:
            for message in readings:
                text = message + '\n\nt.me/' + (chat_username or BOT_NAME)
                client.send_message(chat_id, text, disable_web_page_preview=True, reply_markup=keyboard)
        # if audio:
        #     path_audio = '/tmp/homilia_do_dia.aac'
        #     date_caption = datetime.now().strftime("%d_%m_%Y") + '\n\nt.me/' + (chat_username or BOT_NAME)
        #     caption = "homilia_do_dia_%s" % date_caption
        #     bot.send_audio(chat_id, audio=path_audio, caption=caption)
    except RPCError:
        pass


@bot.on_callback_query()
def inline_handler(client, update):
    chat_id = update.from_user.id
    selected, date = calendar.process_calendar_selection(client, update)
    try:
        if selected:
            client.send_chat_action(chat_id, "typing")
            update.message.delete()
            readings = BuscarLiturgia(dia=date.day, mes=date.month, ano=date.year).obter_url()
            if readings:
                chat = update.message.chat
                chat_username = chat.username if (chat.username and chat.type != 'private') else None

                for message in readings:
                    text = message + '\n\nt.me/' + (chat_username or BOT_NAME)
                    client.send_message(chat_id, text, disable_web_page_preview=True, reply_markup=keyboard)
            else:
                text = 'No momento estamos sem liturgia cadastrada para esta data.'
                client.send_message(chat_id, text, disable_web_page_preview=True, reply_markup=keyboard)

    except RPCError:
        pass


@bot.on_message(filters.new_chat_members)
def new_chat_members(client, update):
    me = client.get_me()
    for member in update.new_chat_members:
        if member.id == me.id:
            return _introduce(client, update)
        else:
            return _welcome(update, member)


@bot.on_message(filters.left_chat_member)
def left_chat_member(client, update):
    me = client.get_me()
    member = update.left_chat_member
    if member.id == me.id:
        print(f'O bot foi removido do chat {update.chat.title}')
        return
    else:
        return goodbye(update)


# Welcome a user to the chat
def goodbye(update):
    """ Sends goodbye message when a user left the chat """
    chat_id = update.chat.id
    chat_title = update.chat.title
    first_name = update.left_chat_member.first_name

    logger.info(f'{escape(first_name)} left chat {chat_id} ({escape(chat_title)})')

    # Pull the custom message for this chat from the database
    text = db.get_value_name_key('group:' + str(chat_id), 'chat_goodbye')

    # Goodbye was disabled
    if text == 'False':
        return

    # Use default message if there's no custom one set
    if text is None:
        text = 'Goodbye, $username!'

    # Replace placeholders and send message
    text = text.replace('$username', first_name).replace('$title', chat_title)
    update.reply_text(text=text, quote=False, parse_mode='html')


@bot.on_message(filters.regex(r'^/welcome(?:\s|$|@\w+\s+)(?:(?P<text>.+))?'))
def set_welcome(client, update):
    """ Sets custom welcome message """
    chat_id = update.chat.id
    args = update.matches[0]['text']

    # _check admin privilege and group context
    if not _check(client, update):
        return

    # Split message into words and remove mentions of the bot
    # set_text = r' '.join(args)

    # Only continue if there's a message
    if not args:
        text = 'You need to send a message, too! For example:\n' \
               f'<code>/welcome Hello $username! Welcome to $title {emoji.GRINNING_FACE}</code>'
        update.reply_text(text=text, quote=False, parse_mode='html')
        return

    # Put message into database
    db.set_name_key('group:' + str(chat_id), {'chat_welcome': args})
    text = 'Got it!'
    update.reply_text(text=text, quote=False, parse_mode='html')


@bot.on_message(filters.regex(r'^/goodbye(?:\s|$|@\w+\s+)(?:(?P<text>.+))?'))
def set_goodbye(client, update):
    """ Enables and sets custom goodbye message """
    chat_id = update.chat.id
    args = update.matches[0]['text']

    # _check admin privilege and group context
    if not _check(client, update):
        return

    # Only continue if there's a message
    if not args:
        text = 'You need to send a message, too! For example:\n' \
               '<code>/goodbye Goodbye, $username!</code>'
        update.reply_text(text=text, quote=False, parse_mode='html')
        return

    # Put message into database
    db.set_name_key('group:' + str(chat_id), {'chat_goodbye': args})
    text = 'Got it!'
    update.reply_text(text=text, quote=False, parse_mode='html')


@bot.on_message(filters.regex(r'^/(disable_welcome)($|@\w+)'))
def disable_welcome(client, update):
    """ Disables the goodbye message """
    command_control(client, update, 'disable_welcome')


@bot.on_message(filters.regex(r'^/(disable_goodbye)($|@\w+)'))
def disable_goodbye(client, update):
    """ Disables the goodbye message """
    command_control(client, update, 'disable_goodbye')


@bot.on_message(filters.regex(r'^/(lock)($|@\w+)'))
def lock(client, update):
    """ Locks the chat, so only the invitee can change settings """
    command_control(client, update, 'lock')


@bot.on_message(filters.regex(r'^/(unlock)($|@\w+)'))
def unlock(client, update):
    """ Unlocks the chat, so everyone can change settings """
    command_control(client, update, 'unlock')


@bot.on_message(filters.regex(r'^/(quiet)($|@\w+)'))
def quiet(client, update):
    """ Quiets the chat, so no error messages will be sent """
    command_control(client, update, 'quiet')


@bot.on_message(filters.regex(r'^/(unquiet)($|@\w+)'))
def unquiet(client, update):
    """ Unquiets the chat """
    command_control(client, update, 'unquiet')


def command_control(client, update, command):
    """ Disables the goodbye message """
    chat_id = update.chat.id

    # _check admin privilege and group context
    if _check(client, update):
        if command == 'disable_welcome':
            commit = db.set_name_key('group:' + str(chat_id), {'chat_welcome': 'False'})
        elif command == 'disable_goodbye':
            commit = db.set_name_key('group:' + str(chat_id), {'chat_goodbye': 'False'})
        elif command == 'lock':
            commit = db.set_name_key('group:' + str(chat_id), {'chat_lock': 'True'})
        elif command == 'unlock':
            commit = db.set_name_key('group:' + str(chat_id), {'chat_lock': 'False'})
        elif command == 'quiet':
            commit = db.set_name_key('group:' + str(chat_id), {'chat_quiet': 'True'})
        elif command == 'unquiet':
            commit = db.set_name_key('group:' + str(chat_id), {'chat_quiet': 'False'})
        else:
            commit = False
        if commit:
            text = 'Got it!'
            update.reply_text(text=text, quote=False, parse_mode='html')


def get_chat_by_username(client, update, user_name=None):
    try:
        if user_name:
            user_name = user_name if user_name[0] == '@' or is_integer(user_name) else '@' + str(user_name)
        chat_id = update.chat.id if not user_name else user_name
        get_chat = client.get_chat(chat_id=chat_id)
    except RPCError as _:

        if user_name:
            text = f'I cant resolved username {user_name}'
            update.reply_text(text=text, quote=False, parse_mode='html')
        logger.error(f"{_}")
        return False

    user = {}
    if get_chat:
        user.update({'id': str(get_chat.id) if get_chat.id else None})
        user.update({'type': str(get_chat.type)}) if get_chat.type else None
        user.update({'title': get_chat.title}) if get_chat.title else None
        user.update({'username': '@' + get_chat.username}) if get_chat.username else None
        user.update({'first_name': get_chat.first_name if get_chat.first_name else None})
        user.update({'last_name': get_chat.last_name if get_chat.last_name else None})
        user.update({'description': get_chat.description if get_chat.description else None})
    return user


@bot.on_message(filters.regex(r'^/me(?:\s|$|@\w+\s+)(?:(?P<text>.+))?'))
def get_user_info(client, update):
    command = str(update.matches[0][0][1:].split('@', 1)[0]).strip().split(' ')[0]
    args = update.matches[0]['text'] if update.matches else None

    if args:
        get_chat = get_chat_by_username(client, update, user_name=args) or None

    else:
        get_chat = get_chat_by_username(client, update)

    if get_chat:
        get_chat['id'] = f"<code>{get_chat['id']} </code>"
        text = '\n'.join(f'{k}: {v}' for k, v in get_chat.items())

        if text and command == 'me':
            update.reply_text(text=text, quote=False, parse_mode='html')


def feed_url(update, url, **chat_info):
    arg_url = FeedHandler.format_url_string(string=url)

    # _check if argument matches url format
    if not FeedHandler.is_parsable(url=arg_url):
        text = "Sorry! It seems like '" + \
               str(arg_url) + "' doesn't provide an RSS news feed.. Have you tried another URL from that provider?"
        update.reply_text(text=text, quote=False, parse_mode='html')
        return
    chat_id = chat_info['chat_id']
    chat_name = chat_info.get('chat_name')
    user_id = update.from_user.id

    result = db.set_url_to_chat(
        chat_id=str(chat_id), chat_name=str(chat_name), url=url, user_id=str(user_id))

    if result:
        text = "I successfully added " + arg_url + " to your subscriptions!"
    else:
        text = "Sorry, " + update.from_user.first_name + \
               "! I already have that url with stored in your subscriptions."
    update.reply_text(text=text, quote=False, parse_mode='html')


@bot.on_message(filters.regex(r'^/addurl(?:\s|$|@\w+\s+)(?:(?P<text>.+))?'))
def add_url(client, update):
    """
    Adds a rss subscription to user
    """
    args = update.matches[0]['text'].strip().split(' ')
    chat_id = update.chat.id
    user_id = update.from_user.id

    # _check admin privilege and group context
    if chat_id < 0:
        if not _check(client, update):
            return

    text = "Sorry! I could not add the entry! " \
           "Please use the the command passing the following arguments:\n\n " \
           "<code>/addurl url</code> or \n <code>/addurl username url</code> \n\n Here is a short example: \n\n " \
           "/addurl http://www.feedforall.com/sample.xml \n\n" \
           "/addurl @username http://www.feedforall.com/sample.xml "

    if len(args) > 2 or not args:
        update.reply_text(text=text, quote=False, parse_mode='html')
        return

    elif len(args) == 2:
        chat_name = args[0].strip()
        url = args[1].strip()
        chat_info = get_chat_by_username(client, update, chat_name)
        text = "I don't have access to chat " + chat_name + '\n' + text
        if chat_info is None:
            update.reply_text(text=text, quote=False, parse_mode='html')
        else:
            chat_info = {'chat_id': chat_info['id'], 'chat_name': chat_info['username']}
            feed_url(update, url, **chat_info)

    else:
        url = args[0]
        user_name = ('@' + update.chat.username) if update.chat.username else None
        chat_title = update.chat.title if update.chat.title else None
        first_name = update.from_user.first_name if update.from_user.first_name else None

        chat_name = user_name or chat_title or first_name
        chat_info = {'chat_id': chat_id, 'chat_name': chat_name, 'user_id': user_id}

        feed_url(update, url, **chat_info)


@bot.on_message(filters.regex(r'^/(listurl)(\s|$|@\w+)'))
def list_url(client, update):
    """
    Displays a list of all user subscriptions
    """
    user_id = update.from_user.id
    chat_id = update.chat.id

    # _check admin privilege and group context
    if chat_id < 0:
        if not _check(client, update):
            return

    text = "Here is a list of all subscriptions I stored for you!"
    client.send_message(chat_id=user_id, text=text, parse_mode='html')

    urls = db.get_chat_urls(user_id=user_id)
    for url in urls:
        url = (str(url['chat_name']) + ' ' if url['chat_name'] and int(url['chat_id']) < 0 else '') + url['url']
        text = '<code>/removeurl ' + url + '</code>'
        client.send_message(chat_id=user_id, text=text, parse_mode='html')


@bot.on_message(filters.regex(r'^/(removeurl)(?:\s|$|@\w+\s+)(?:(?P<text>.+))?'))
def remove_url(client, update):
    """
    Removes an rss subscription from user
    """
    args = update.matches[0]['text'].strip().split(' ')
    chat_id = update.chat.id

    # _check admin privilege and group context
    if chat_id < 0:
        if not _check(client, update):
            return

    text = "Sorry! I could not remove the entry! " \
           "Please use the the command passing the following arguments:\n\n " \
           "<code>/removeurl url</code> or \n <code>/removeurl username url</code> \n\n " \
           "Here is a short example: \n\n " \
           "/removeurl http://www.feedforall.com/sample.xml \n\n" \
           "/removeurl @username http://www.feedforall.com/sample.xml "

    if len(args) > 2 or not args or args == '':
        update.reply_text(text=text, quote=False, parse_mode='html')
        return

    user_id = update.from_user.id
    chat_name = args[0] if len(args) == 2 else None
    chat_id_db = db.get_chat_id_for_chat_name(user_id, chat_name) if chat_name else update.chat.id
    url = args[1] if len(args) == 2 else args[0]

    if chat_id_db is None:
        text = "Don't exist chat " + chat_name + '\n' + text
        update.reply_text(text=text, quote=False, parse_mode='html')
    else:
        exist_url = db.exist_url_to_chat(user_id, chat_id, url)
        if not exist_url:
            chat_name = chat_name or update.from_user.first_name
            text = "Don't exist " + url + " for chat " + chat_name + '\n' + text
            update.reply_text(text=text, quote=False, parse_mode='html')
            result = None
        else:
            result = True if db.del_url_for_chat(chat_id, url) else None

        if result:
            text = "I removed " + url + " from your subscriptions!"
        else:
            text = "I can not find an entry with label " + \
                   url + " in your subscriptions! Please check your subscriptions using " \
                         "/listurl and use the delete command again!"
        update.reply_text(text=text, quote=False, parse_mode='html')

    names_url = db.find_names(url)
    if len(names_url) == 1:
        db.del_names(names_url)


# @bot.on_message(filters.regex(r'^/(stop)(\s|$|@\w+)'))
# def stop(client, update):
#     """
#     Stops the bot from working
#     """
#     chat_id = update.chat.id
#
#     # _check admin privilege and group context
#     if chat_id < 0:
#         if not _check(client, update):
#             return
#
#     text = "Oh.. Okay, I will not send you any more news updates! " \
#            "If you change your mind and you want to receive messages " \
#            "from me again use /start command again!"
#     update.reply_text(text=text, quote=False, parse_mode='html')


'''FUNÇÕES CONTRLE ADM BANCO DE DADOS'''
admin_text = 'Commands:\n\n' \
             '/deactivatedurl - list of all keys for users disable\n' \
             '/activateallurl - Activate all url for users\n' \
             '/activateallliturgy - Activate all user for receive the daily liturgy\n' \
             '/allurl - List info about all url\n' \
             '/getkey - Search all keys for args\n' \
             '/removekey - Remove key in data base\n' \
             '/senddailyliturgy - Send daily liturgy for all users active' \
             '/activated - Send info about the number of users activated' \
             '/deactivated - Send info about the number of users deactivated' \
             '/userinfoliturgy - Send info about users daily liturgy'


@bot.on_message(filters.regex(r'^/(deactivatedurl)(\s|$|@\w+)'))
def list_url_deactivated(_, update):
    """
    Displays a list of all names for users disable
    """
    chat_id = update.chat.id

    # _check admin privilege and group context
    if str(chat_id) not in db.list_admins():
        return

    text = "Here is a list of all name deactivated"
    update.reply_text(text=text, quote=False, parse_mode='html')

    urls = db.get_name_urls_deactivated()
    for url in urls:
        text = '<code>/removekey ' + url + '</code>'
        update.reply_text(text=text, quote=False, parse_mode='html')


@bot.on_message(filters.regex(r'^/(activateallurl)(\s|$|@\w+)'))
def activate_all_urls(_, update):
    """
    Activate all url for users
    """
    chat_id = update.chat.id

    # _check admin privilege and group context
    if str(chat_id) not in db.list_admins():
        return

    db.activated_all_urls()
    text = 'Got it!'
    update.reply_text(text=text, quote=False, parse_mode='html')


@bot.on_message(filters.regex(r'^/(activateallliturgy)(\s|$|@\w+)'))
def activate_all_liturgy(_, update):
    """
    Activate all user for receive the daily liturgy
    """
    chat_id = update.chat.id

    # _check admin privilege and group context
    if str(chat_id) not in db.list_admins():
        return

    db.activated_all_chat_id()
    text = 'Got it!'
    update.reply_text(text=text, quote=False, parse_mode='html')


@bot.on_message(filters.regex(r'^/(allurl)(\s|$|@\w+)'))
def all_url(_, update):
    """
    List info about all url
    """
    chat_id = update.chat.id

    # _check admin privilege and group context
    if str(chat_id) not in db.list_admins():
        return

    text = "Here is a list of all subscriptions I stored for you!"
    update.reply_text(text=text, quote=False, parse_mode='html')

    urls = db.get_urls_activated()
    for url in urls:
        last_update = db.get_update_url(url)
        text = 'last_update: ' + last_update['last_update'] + '\n\n' \
               + 'last_url: <code>' + last_update['last_url'] + '</code>\n\n' \
               + 'url: <code>' + url + '</code>'

        update.reply_text(text=text, quote=False, parse_mode='html')


@bot.on_message(filters.regex(r'^/(getkey)(?:\s|$|@\w+\s+)(?:(?P<text>.+))?'))
def get_key(_, update):
    """
    Search all keys for args
    """
    args = update.matches[0]['text'].strip().split(' ')
    chat_id = update.chat.id

    if str(chat_id) not in db.list_admins():
        return

    if len(args) == 1:
        keys = db.find_names(args[0])
        update.reply_text(text=f'Econtrei {len(keys)} chaves', quote=False, parse_mode='html')
        for k in keys:
            text = str('<code>/removekey ' + str(k) + '</code>')
            update.reply_text(text=text, quote=False, parse_mode='html')


@bot.on_message(filters.regex(r'^/(removekey)(?:\s|$|@\w+\s+)(?:(?P<text>.+))?'))
def remove_key(_, update):
    """
    Remove key in data base
    """
    args = update.matches[0]['text'].strip().split(' ')
    chat_id = update.chat.id

    if str(chat_id) not in db.list_admins():
        return
    text = 'I removed '
    if len(args) == 1:
        key = args[0]
        if db.redis.delete(args[0]) == 1:
            text = text + key
            update.reply_text(text=text, quote=False, parse_mode='html')


@bot.on_message(filters.regex(r'^/(owner)(\s|$|@\w+)'))
def owner(_, update):
    """
    Introduces the bot to a chat its been added to and saves the user id of the
    user who invited us.
    """
    chat_id = update.chat.id
    chat_title = update.chat.title
    chat_name = '@' + update.chat.username
    user_id = update.from_user.id

    db.update_group(chat_id=chat_id, chat_name=chat_name, chat_title=chat_title, user_id=user_id)

    logger.info('Invited by %s to chat %d (%s)' % (user_id, chat_id, update.chat.title))
    text = 'Got it!'
    update.reply_text(text=text, quote=False, parse_mode='html')


def error(_):
    """ Error handling """
    logger.error(f"def error {_}")


@bot.on_message(filters.regex(r'^/(senddailylitugy)(\s|$|@\w+)'))
async def send_daily_liturgy_all_users(_client, update):
    """
    Send daily liturgy for all users active
    """
    chat_id = update.chat.id
    if str(chat_id) not in db.list_admins():
        return
    await daily_liturgy()


async def daily_liturgy():
    date = DateHandler.get_datetime_now()
    date_full = format_date(date.date(), format='full', locale='pt_br')
    readings = BuscarLiturgia(dia=date.day, mes=date.month, ano=date.year).obter_url()
    chat_id_activated = db.get_chat_id_activated()
    if readings:
        for chat_id in chat_id_activated:
            await send_daily_liturgy(chat_id, readings)

    homily = util.homiliadodia.HomiliadoDia().obter_homilia()
    if homily:
        for chat_id in chat_id_activated:
            await send_daily_liturgy(chat_id, homily)

    audio = util.homiliadodia.HomiliadoDia().obter_arquivo_audio()
    if audio:
        send = await send_daily_liturgy_audio(config('CHANNEL_LD'), audio['path_audio'], audio['date'])
        path_audio = send.audio.file_id
        db.del_names(['audio_liturgy'])
        db.set_name_key('audio_liturgy', {date_full: path_audio})
        for chat_id in chat_id_activated:
            await send_daily_liturgy_audio(chat_id, path_audio, audio['date'])


async def send_daily_liturgy(chat_id, readings):
    send_message = False
    try:
        chat = await bot.get_chat(chat_id=str(chat_id))
        chat_username = chat.username if (chat.username and chat.type != 'private') else None
        for message in readings:
            text = message + '\n\nt.me/' + (chat_username or BOT_NAME)
            await bot.send_message(chat_id, text, disable_web_page_preview=True)
            send_message = True
    except RPCError as _:
        errors(chat_id)

    if send_message:
        db.set_last_send_daily_liturgy(chat_id)


async def send_daily_liturgy_audio(chat_id, path_audio, date):
    try:
        chat = await bot.get_chat(chat_id=str(chat_id))
        chat_username = chat.username if (chat.username and chat.type != 'private') else None
        caption = date + '\n\nt.me/' + (chat_username or BOT_NAME)
        send = await bot.send_audio(chat_id, audio=path_audio, caption=caption, file_name=f'{date}.aac', title=date)
        return send
    except RPCError as _:
        errors(chat_id)


@bot.on_message(filters.regex(r'^/(deactivated)(\s|$|@\w+)'))
def users_deactivated(_, update):
    """
    Send info about the number of users deactivated
    """
    number_user = len(db.get_name_chat_id_deactivated())
    text = f'Existem {number_user} inativos no momento.'
    update.reply_text(text=text, quote=False, parse_mode='html')


@bot.on_message(filters.regex(r'^/(activated)(\s|$|@\w+)'))
def users_activated(_, update):
    """
    Send info about the number of users activated
    """
    number_user = len(db.get_chat_id_activated())
    text = f'Existem {number_user} ativos no momento.'
    update.reply_text(text=text, quote=False, parse_mode='html')


@bot.on_message(filters.regex(r'^/(userinfoliturgy)(?:\s|$|@\w+\s+)(?:(?P<text>.+))?'))
def get_user_info(_, update):
    """
    userinfoliturgy - Send info about users daily liturgy
    """
    # command = str(update.matches[0][0][1:].split('@', 1)[0]).strip().split(' ')[0]
    args = update.matches[0]['text'] if update.matches else None

    chat_id = update.chat.id
    if str(chat_id) not in db.list_admins():
        return

    if int(update.chat.id) < 0:
        return

    if args == 'deactivated':
        chat_ids = db.get_chat_id_deactivated()
    else:
        chat_ids = db.get_chat_id_activated()

    for chat_id in chat_ids:
        get_chat = db.get_chat_info_daily_liturgy(chat_id)[0]

        if get_chat:
            text = '\n'.join(f'{k}: <code>{v}</code>' for k, v in get_chat.items())

            if text:
                update.reply_text(text=text, quote=False, parse_mode='html')


def errors(chat_id):
    """ Error handling """
    try:
        db.disable_chat_id_daily_liturgy(chat_id)
        logger.error(f'disable chat_id {chat_id} from chat list daily liturgy')
    except ValueError as _:
        logger.error(f"error ValueError {str(_)}")


def is_integer(n):
    try:
        float(n)
    except ValueError:
        return False
    else:
        return float(n).is_integer()


@bot.on_message(filters.regex(r'^/(admin)(?:\s|$|@\w+\s+)(?:(?P<text>.+))?'))
def admin(_, update):
    """
    Send admin commands
    """
    chat_id = update.chat.id
    if str(chat_id) not in db.list_admins():
        return
    update.reply_text(text=admin_text, quote=False, parse_mode='html')


# Start Bot
if __name__ == "__main__":
    try:
        logger.critical('Press Ctrl+%s to exit' % 'C')
        print('Press Ctrl+{0} to exit'.format('C'))
        scheduler = AsyncIOScheduler()
        last_date = DateHandler.get_datetime_now() + timedelta(days=-1)
        start_date = DateHandler.combine(last_date.date(), DateHandler.time('06:00:00-03:00'))
        scheduler.add_job(daily_liturgy, "interval", days=1, start_date=start_date)
        scheduler.start()
        bot.run()

    except RPCError as _:
        error(_)
        logger.critical(f'{_}')
        print(_)
