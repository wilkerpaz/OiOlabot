import asyncio
import logging

from html import escape
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from decouple import config
from emoji import emojize
from pyrogram import Client, Filters
from pyrogram.errors import BadRequest

from util.database import DatabaseHandler
from util.feedhandler import FeedHandler
from util.processing import BatchProcess

LOG = config('LOG')
logging.basicConfig(level=LOG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger('apscheduler').setLevel(logging.WARNING)
logging.getLogger('OiOlaBot').setLevel(logging.WARNING)

My_Bot = config('MyBot')
Token = config('TOKEN')

db = DatabaseHandler(0)
app = Client(session_name=My_Bot, bot_token=Token)


def loop_parse():
    if not app.is_connected and scheduler.get_job('feed'):
        scheduler.remove_job('feed')
    else:
        BatchProcess(database=db, bot=app)


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


def _check(client, update, override_lock=None):
    chat_id = update.chat.id
    chat_type_id = str(update.chat.type) + ':' + str(update.chat.id)

    if chat_id > 0:
        text = 'Please add me to a group first!'
        update.reply_text(text=text, quote=False)
        return False

    locked = override_lock if override_lock is not None \
        else bool(db.redis.hget('group:' + chat_type_id, str(chat_id) + '_lock'))

    if locked and int(db.redis.hget('group:' + chat_type_id, str(chat_id) + '_adm')) != update.from_user.id:
        if not bool(db.redis.hget('group:' + chat_type_id, str(chat_id) + '_quiet')):
            text = 'Sorry, only the person who invited me can do that.'
            update.reply_text(text=text, quote=False)
        return False

    return True


# Welcome a user to the chat
def _welcome(client, update, member=None):
    """ Welcomes a user to the chat """
    chat_id = update.chat.id
    chat_type_id = str(update.chat.type) + ':' + str(chat_id)

    logger.info('%s joined to chat %d (%s)' % (escape(member.first_name), chat_id, escape(update.chat.title)))

    # Pull the custom message for this chat from the database
    text_group = db.redis.hget('group:' + chat_type_id, str(chat_id) + '_welcome')
    if text_group == 'False':
        return

    # Use default message if there's no custom one set
    welcome_text = 'Hello $username! Welcome to $title %s' % emojize(':grinning_face:')
    if text_group:
        text = welcome_text + '\n' + text_group
    else:
        text = welcome_text

    # Replace placeholders and send message
    welcome_text = text.replace('$username', member.first_name).replace('$title', update.chat.title)
    update.reply_text(text=welcome_text, quote=False, parse_mode='html')


# Introduce the bot to a chat its been added to
def _introduce(client, update):
    """
    Introduces the bot to a chat its been added to and saves the user id of the
    user who invited us.
    """
    chat_id = update.chat.id
    chat_title = update.chat.title
    chat_name = '@' + update.chat.username

    chat_type_id = str(update.chat.type) + ':' + str(chat_id)
    invited = update.from_user.id

    logger.info('Invited by %s to chat %d (%s)'
                % (invited, chat_id, update.chat.title))

    db.redis.hmset('group:' + str(chat_type_id), {str(chat_id): str(chat_id),
                                                  str(chat_id) + '_adm': str(invited),
                                                  str(chat_id) + '_lock': 'True',
                                                  str(chat_id) + '_name': chat_name,
                                                  str(chat_id) + '_title': str(chat_title)})

    text = 'Hello %s! I will now greet anyone who joins this chat with a' \
           ' nice message %s \nCheck the /help command for more info!' \
           % (update.chat.title,
              emojize(':grinning_face:'))
    update.reply_text(text=text, quote=False, parse_mode='html')

    if client.get_me().username == 'LiturgiaDiaria_bot':
        user_name = '@' + update.chat.username if update.chat.username else \
            '@' + update.from_user.username if update.from_user.username else update.from_user.first_name
        url = 'http://feeds.feedburner.com/evangelhoddia/dia'
        db.set_url_to_group(chat_id=invited, user_id=chat_id, user_name=user_name, url=url)


@app.on_message(Filters.regex(r'^/(start|help)($|@\w+)'))
def start(client, update):
    chat_id = update.chat.id
    invited = update.from_user.id

    if client.get_me().username == 'LiturgiaDiaria_bot':
        # print(client.get_me().username)
        user_name = '@' + update.chat.username if update.chat.username else \
            '@' + update.from_user.username if update.from_user.username else update.from_user.first_name
        url = 'http://feeds.feedburner.com/evangelhoddia/dia'
        # print(invited, chat_id, user_name, url)
        db.set_url_to_group(chat_id=invited, user_id=chat_id, user_name=user_name, url=url)

    update.reply_text(text=help_text, quote=False)


@app.on_message(Filters.new_chat_members)
def new_chat_members(client, update):
    for member in update.new_chat_members:
        # Bot was added to a group chat

        if member.first_name == client.get_me().first_name:
            return _introduce(client, update)
        # Another user joined the chat
        else:
            return _welcome(client, update, member)


@app.on_message(Filters.left_chat_member)
def left_chat_member(client, update):
    """ Sends goodbye message when a user left the chat """
    first_name = update.left_chat_member.first_name
    if first_name == client.get_me().first_name:
        return
    chat_id = update.chat.id
    chat_type_id = str(update.chat.type) + ':' + str(chat_id)

    logger.info('%s left chat %d (%s)'
                % (escape(update.left_chat_member.first_name),
                   chat_id,
                   escape(update.chat.title)))

    # Pull the custom message for this chat from the database
    text_group = db.redis.hget('group:' + chat_type_id, str(chat_id) + '_bye')

    # Goodbye was disabled
    if text_group == 'False':
        return

    # Use default message if there's no custom one set
    if text_group is None:
        text_group = 'Goodbye, $username!'

    # Replace placeholders and send message
    chat_title = update.chat.title
    text = text_group.replace('$username', first_name).replace('$title', chat_title)
    update.reply_text(text=text, quote=False, parse_mode='html')


# Set custom message
@app.on_message(Filters.regex(r'^/_welcome(?:\s|$|@\w+\s+)(?:(?P<text>.+))?'))
def set_welcome(client, update):
    """ Sets custom welcome message """
    chat_id = update.chat.id
    chat_type_id = str(update.chat.type) + ':' + str(chat_id)
    set_text = update.matches[0]['text']

    # Check admin privilege and group context
    if _check(client, update):
        # Only continue if there's a message
        if not set_text:
            text = 'You need to send a message, too! For example:\n' \
                   '<code>/welcome Hello $username, welcome to $title!</code>'
            client.send_message(chat_id, text, parse_mode='html')
            return

        # Put message into database
        db.redis.hset('group:' + chat_type_id, str(chat_id) + '_welcome', set_text)
        update.reply_text(text='Got it!', quote=False)


# Set custom message
@app.on_message(Filters.regex(r'^/goodbye(?:\s|$|@\w+\s+)(?:(?P<text>.+))?'))
def set_goodbye(client, update):
    """ Enables and sets custom goodbye message """
    chat_id = update.chat.id
    chat_type_id = str(update.chat.type) + ':' + str(chat_id)
    set_text = update.matches[0]['text']

    # Check admin privilege and group context
    if _check(client, update):
        # Only continue if there's a message
        if not set_text:
            text = 'You need to send a message, too! For example:\n' \
                   '<code>/goodbye Goodbye, $username!</code'
            update.reply_text(text=text, quote=False, parse_mode='html')
            return

        # Put message into database
        db.redis.hset('group:' + chat_type_id, str(chat_id) + '_goodbye', set_text)
        update.reply_text(text='Got it!', quote=False)


@app.on_message(Filters.regex(r'^/(disable_welcome|disable_goodbye|lock|unlock|quiet|unquiet)($|@\w+)'))
def command_control(client, update):
    """ Disables the goodbye message """
    chat_id = update.chat.id
    chat_type_id = str(update.chat.type) + ':' + str(chat_id)
    command = update.matches[0][0][1:].split('@', 1)[0]

    # Check admin privilege and group context
    if _check(client, update):
        # Disable goodbye message
        if command == 'disable_welcome':
            commit = db.redis.hset('group:' + chat_type_id, str(chat_id) + '_welcome', 'False')
        elif command == 'disable_goodbye':
            commit = db.redis.hset('group:' + chat_type_id, str(chat_id) + '_goodbye', 'False')
        elif command == 'lock':
            commit = db.redis.hset('group:' + chat_type_id, str(chat_id) + '_lock', 'True')
        elif command == 'unlock':
            commit = db.redis.hset('group:' + chat_type_id, str(chat_id) + '_lock', 'False')
        elif command == 'quiet':
            commit = db.redis.hset('group:' + chat_type_id, str(chat_id) + '_quiet', 'True')
        elif command == 'unquiet':
            commit = db.redis.hset('group:' + chat_type_id, str(chat_id) + '_quiet', 'False')
        else:
            commit = 1
        if commit == 0:
            update.reply_text(text='Got it!', quote=False)


def get_id_db(client, update):
    """
    Removes an rss subscription from user
    """
    args = update.matches[0]['text'].split(' ')
    chat_id = update.chat.id
    # Check admin privilege and group context
    if chat_id < 0:
        if not _check(client, update):
            return

    message = "To remove a subscriptions from your list please use " \
              "/remove <entryname>. To see all your subscriptions along or " \
              "/remove @username <entryname>. To see all your subscriptions along " \
              "with their entry names use /listurl !"

    if len(args) > 2:
        update.reply_text(text=message, quote=False)
        return

    url = args[0] if len(args) == 1 else args[1]
    user_name = args[0] if len(args) == 2 else update.chat.first_name
    group_id_db = db.get_user_id(chat_id, url, user_name)
    return {'key': group_id_db['key'], 'user_id_db': group_id_db['user_id'], 'user_name_db': user_name, 'url': url,
            'message': message} if group_id_db else None


@app.on_message(Filters.regex(r'^/me(?:\s|$|@\w+\s+)(?:(?P<text>.+))?'))
def get_user(client, update):
    command_filter_regex = 'me'
    user_id = update.from_user.id
    first_name = update.from_user.first_name
    command = str(update.matches[0][0][1:].split('@', 1)[0]).strip()
    args = update.matches[0]['text'] if update.matches else None

    if args:
        args = args.split(' ')
    user_input = args[0] if args else None

    get_chat = None
    if user_input:
        try:
            get_chat = client.get_chat(user_input)
        except BadRequest as e:
            text = "Sorry, " + first_name + "! I already have that url with stored in your subscriptions."
            update.reply_text(text=text, parse_mode='html')
            # print(user_input, e)
            return None

    get_chat = get_chat if get_chat else client.get_chat(user_id)
    user = {}
    user.update({'id': str(get_chat.id)}) if get_chat.id else None
    user.update({'first_name': get_chat.first_name}) if get_chat.first_name else None
    user.update({'last_name': get_chat.last_name}) if get_chat.last_name else None
    user.update({'username': get_chat.username}) if get_chat.username else None
    user.update({'description': get_chat.description}) if get_chat.description else None

    if user:
        text = ''
        for k, v in user.items():
            text = text + k + ': ' + v + '\n'
        if text != '' and command == command_filter_regex:
            update.reply_text(text=text, parse_mode='html')
        return user
    return None


def get_id(client, update):
    user = get_user(client, update)
    if user:
        username = user['username'] if '@' + user['username'] else user['first_name']
        use_id = user['id']
        return {'user_id': use_id, 'user_name': str(username)}
    else:
        return None


@app.on_message(Filters.regex(r'^/addurl(?:\s|$|@\w+\s+)(?:(?P<text>.+))?'))
def add_url(client, update):
    """
    Adds a rss subscription to user
    """
    args = update.matches[0]['text'].split(' ')
    from_user = update.from_user
    chat_id = update.chat.id
    first_name = update.chat.first_name

    # Check admin privilege and group context
    if chat_id < 0:
        if not _check(client, update):
            return

    message = "Sorry! I could not add the entry! " \
              "Please use the the command passing the following arguments:\n\n " \
              "/addurl <url> or \n /addurl <username> <url> \n\n Here is a short example: \n\n " \
              "/addurl http://www.feedforall.com/sample.xml ExampleEntry \n\n" \
              "/addurl @username http://www.feedforall.com/sample.xml ExampleEntry"

    if len(args) > 2 or not args:
        update.reply_text(text=message, quote=False)
        return

    url = args[0] if len(args) == 1 else args[1]
    group = args[0] if len(args) == 2 else None
    user_id = get_id(client, update) if group else \
        {'user_id': chat_id, 'user_name': first_name}
    if len(args) == 2 and user_id is None:
        return
    arg_url = FeedHandler.format_url_string(string=url)

    # Check if argument matches url format
    if not FeedHandler.is_parsable(url=arg_url):
        message = "Sorry! It seems like '" + \
                  str(arg_url) + "' doesn't provide an RSS news feed.. Have you tried another URL from that provider?"
        update.reply_text(text=message, quote=False)
        return

    # Check if entry does not exists
    entries = db.exist_url_to_group(chat_id, user_id['user_id'], url)

    if entries:
        result = None
    else:
        result = db.set_url_to_group(
            chat_id=str(chat_id), user_id=str(user_id['user_id']), user_name=str(user_id['user_name']), url=url)
    if result:
        message = "I successfully added " + arg_url + " to your subscriptions!"
    else:
        message = "Sorry, " + from_user.first_name + \
                  "! I already have that url with stored in your subscriptions."

    update.reply_text(text=message, quote=False)


@app.on_message(Filters.regex(r'^/(listurl)(\s|$|@\w+)'))
def list_url(client, update):
    """
    Displays a list of all user subscriptions
    """
    chat_id = update.chat.id

    # Check admin privilege and group context
    if chat_id < 0:
        if not _check(client, update):
            return

    message = "Here is a list of all subscriptions I stored for you!"
    update.reply_text(text=message, quote=False)

    urls = db.get_group_urls(chat_id=chat_id)
    for url in urls:
        url = (url['chat_name'] + ' ' if int(url['chat_id']) < 0 else '') + url['url']
        text = '<code>/removeurl ' + url + '</code>'
        update.reply_text(text=text, quote=False, parse_mode='html')


def all_url(client, update):
    """
    Displays a list of all user subscriptions
    """
    chat_id = update.chat.id

    # Check admin privilege and group context
    if chat_id < 0:
        if not _check(client, update):
            return

    message = "Here is a list of all subscriptions I stored for you!"
    update.reply_text(message)

    urls = db.get_all_urls()
    for url in urls:
        last_update = db.get_update_url(url)
        text = 'last_update: ' + last_update['last_update'] + '\n\n' \
               + 'last_url: <code>' + last_update['last_url'] + '</code>\n\n' \
               + 'url: <code>' + last_update['url'] + '</code>'

        update.reply_text(text=text, quote=False, parse_mode='html')


@app.on_message(Filters.regex(r'^/removeurl(?:\s|$|@\w+\s+)(?:(?P<text>.+))?'))
def remove_url(client, update):
    """
    Removes an rss subscription from user
    """
    args = update.matches[0]['text'].split(' ')

    # args = context.args
    user_db = get_id_db(client, update)
    if not user_db:
        update.reply_text(text='This url not exist', quote=False)
        return
    user_id = user_db['user_id_db']  # if int(user_db['user_id_db']) < 0 else None
    # user_name = user_db['user_name_db']
    url = user_db['url']
    key = user_db['key']

    if len(args) == 2 and user_id is None:
        update.reply_text(text=user_db['message'], quote=False)
        return

    result = True if db.redis.delete(key) == 1 else False

    if result:
        message = "I removed " + url + " from your subscriptions!"
    else:
        message = "I can not find an entry with label " + \
                  url + " in your subscriptions! Please check your subscriptions using " \
                        "/list and use the delete command again!"
    update.reply_text(text=message, quote=False)
    if len(db.get_urls(url)) == 0:
        key_url = db.find_keys('url:*' + url + '*')
        for key in key_url:
            db.redis.delete(key)


@app.on_message(Filters.regex(r'^/getkey(?:\s|$|@\w+\s+)(?:(?P<text>.+))?'))
def get_key(client, update):
    args = update.matches[0]['text'].split(' ')
    if len(args) == 1:
        keys = db.find_keys('*' + args[0] + '*')
        for k in keys:
            text = '<code>/removekey ' + str(k) + '</code>'
            update.reply_text(text=str(text), quote=False, parse_mode='html')


@app.on_message(Filters.regex(r'^/removekey(?:\s|$|@\w+\s+)(?:(?P<text>.+))?'))
def remove_key(client, update):
    args = update.matches[0]['text'].split(' ')
    text = 'I removed '
    if len(args) == 1:
        if db.redis.delete(args[0]) == 1:
            update.reply_text(text=str(text + args[0]), quote=False, parse_mode='html')


@app.on_message(Filters.regex(r'^/(owner)(\s|$|@\w+)'))
def owner(client, update):
    """
    Introduces the bot to a chat its been added to and saves the user id of the
    user who invited us.
    """
    chat_id = update.chat.id
    chat_title = update.chat.title
    chat_name = '@' + update.chat.username

    chat_type_id = str(update.chat.type) + ':' + str(chat_id)
    invited = update.from_user.id

    logger.info('Invited by %s to chat %d (%s)' % (invited, chat_id, update.chat.title))

    db.redis.hmset('group:' + str(chat_type_id), {str(chat_id): str(chat_id),
                                                  str(chat_id) + '_adm': str(invited),
                                                  str(chat_id) + '_lock': 'True',
                                                  str(chat_id) + '_name': chat_name,
                                                  str(chat_id) + '_title': str(chat_title)})
    update.reply_text(text='Got it!', quote=False)


@app.on_message(Filters.regex(r'^/(stop)(\s|$|@\w+)'))
def stop(client, update):
    """
    Stops the bot from working
    """
    chat_id = update.chat.id

    # Check admin privilege and group context
    if chat_id < 0:
        if not _check(client, update):
            return

    text = "Oh.. Okay, I will not send you any more news updates! " \
           "If you change your mind and you want to receive messages " \
           "from me again use /start command again!"
    update.reply_text(text=text, quote=False)


@app.on_message(Filters.regex(r'^/(\w+)'))
def other_command(client, update):
    chat_id = update.chat.id
    if chat_id > 0:
        text = "Sorry, I don't answer this command"
        update.reply_text(text=text, quote=False)


@app.on_message(Filters.text and Filters.group)
def message_text_group(client, update):
    return


@app.on_message()
def all_update(client, update):
    pass
    #print(update)


if __name__ == '__main__':
    app.start()
    loop_parse()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(loop_parse, 'interval', seconds=45, id='feed', replace_existing=True, max_instances=10)
    scheduler.start()
    print('Press Ctrl+{0} to exit'.format('C'))

    # Execution will block here until Ctrl+C is pressed.
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.remove_job('feed')
        app.stop()
