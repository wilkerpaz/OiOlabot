import logging
from datetime import timedelta
from multiprocessing.dummy import Pool as ThreadPool

import telebot
from decouple import config

from util.database_daily_liturgy import DatabaseHandler
from util.datehandler import DateHandler
from util.feedhandler import FeedHandler
from util.liturgiadiaria import BuscarLiturgia

LOG = config('LOG')
DB = config('DB_LD')
BOT_NAME = config('BOT_NAME_LD')
API_TOKEN = config('DEV_TOKEN_LD')  # Tokens do Bot de Desenvolvimento

THREADS = config('THREADS')

logging.basicConfig(level='INFO', format='%(name)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

bot = telebot.TeleBot(API_TOKEN, skip_pending=True)
bot.stop_polling()
db = DatabaseHandler(DB)


def daily_liturgy():
    datetime = DateHandler.datetime
    date = datetime.now()
    readings = BuscarLiturgia(dia=date.day, mes=date.month, ano=date.year).obter_url()
    if readings:
        for chat_id in db.get_chat_id_activated():
            send_message = False
            try:
                chat_info = db.get_chat_info_daily_liturgy(chat_id)[0]
                chat = bot.get_chat(chat_id=str(chat_id))
                chat_username = chat.username if (chat.username and chat.type != 'private') else None
                last_send = DateHandler.parse_datetime(str(chat_info['last_send']))
                hour = datetime.strptime('08:00', '%H:%M').hour
                if date.date() > last_send.date() and date.hour > hour:
                    for message in readings:
                        text = message + '\n\nt.me/' + (chat_username or BOT_NAME)
                        bot.send_message(chat_id, text, disable_web_page_preview=True)
                        send_message = True
            except telebot.apihelper.ApiException as _:
                errors(chat_id)

            if send_message:
                db.set_last_send_daily_liturgy(chat_id)


def parse_parallel():
    time_started = DateHandler.datetime.now()
    urls = db.get_urls_activated()
    threads = 2
    pool = ThreadPool(threads)
    pool.map(update_feed, urls)
    pool.close()

    time_ended = DateHandler.datetime.now()
    duration = time_ended - time_started
    logger.info(f"Finished updating! Parsed {str(len(urls))} rss feeds in {str(duration)}! {BOT_NAME}")
    daily_liturgy()
    return True


def update_feed(url):
    try:
        get_url_info = db.get_update_url(url)
        last_url = get_url_info['last_url']
        date_last_url = DateHandler.parse_datetime(get_url_info['last_update'])
        feed = FeedHandler.parse_feed(url, 4, date_last_url + timedelta(days=-1))
        for post in feed:
            if not hasattr(post, "published") and not hasattr(post, "daily_liturgy"):
                logger.warning('not published' + url)
                continue
            date_published = DateHandler.parse_datetime(post.published)

            if hasattr(post, "daily_liturgy"):
                if date_published > date_last_url and post.link != last_url \
                        and post.daily_liturgy != '':
                    message = post.title + '\n' + post.daily_liturgy
                    result = send_newest_messages(message=message, url=url, disable_page_preview=True)
                    if post == feed[-1] and result:
                        update_url(url=url, last_update=date_published, last_url=post.link)
            elif date_published > date_last_url and post.link != last_url:
                message = post.title + '\n' + post.link
                result = send_newest_messages(message=message, url=url)
                if result:
                    update_url(url=url, last_update=date_published, last_url=post.link)
            else:
                pass
    except TypeError as _:
        logger.error(f"TypeError {url} {str(_)}")


def update_url(url, last_update, last_url):
    db.update_url(url=url, last_update=last_update, last_url=last_url)


def send_newest_messages(message, url, disable_page_preview=None):
    names_url = db.get_name_urls_activated(url)
    is_update_url = False
    for name in names_url:
        chat_id = db.get_value_name_key(name, 'chat_id')
        if chat_id:
            try:
                # print(chat_id, url)
                chat = bot.get_chat(chat_id=str(chat_id))
                chat_username = chat.username if (chat.username and chat.type != 'private') else None
                text = message + '\n\nt.me/' + (chat_username or BOT_NAME)
                result = bot.send_message(chat_id=chat_id, text=text, disable_web_page_preview=disable_page_preview)
                # result = True
                if not result:
                    errors(chat_id=chat_id, url=url)
                else:
                    is_update_url = True
            except telebot.apihelper.ApiException as _:
                errors(chat_id, url)
    return is_update_url


def errors(chat_id, url=None):
    """ Error handling """
    try:
        if url:
            db.disable_url_chat(chat_id)
            logger.error(f'disable url {url} for chat_id {chat_id} from chat list')
        else:
            db.disable_chat_id_daily_liturgy(chat_id)
            logger.error(f'disable chat_id {chat_id} from chat list daily liturgy')

    except ValueError as _:
        logger.error(f"error ValueError {str(_)}")


if __name__ == "__main__":
    parse_parallel()
