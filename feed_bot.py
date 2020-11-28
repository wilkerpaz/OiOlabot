import logging
from datetime import timedelta
from multiprocessing.dummy import Pool as ThreadPool

import telebot
from decouple import config

from util.database import DatabaseHandler
from util.datehandler import DateHandler
from util.feedhandler import FeedHandler

LOG = config('LOG')
DB = config('DB')
BOT_NAME = config('BOT_NAME')
API_TOKEN = config('DEV_TOKEN')  # Tokens do Bot de Desenvolvimento

THREADS = config('THREADS')
PATH_REDIS = config('PATH_REDIS')

logging.basicConfig(level='INFO', format='%(name)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

bot = telebot.TeleBot(API_TOKEN, skip_pending=True)
bot.stop_polling()
db = DatabaseHandler(DB)


def backup():
    if db.backup():
        list_admins = db.list_admins()
        for chat_id in list_admins:
            logger.info(f"Send backup {PATH_REDIS} for {chat_id}")
            doc = open(PATH_REDIS, 'rb')
            bot.send_document(chat_id=chat_id, data=doc)


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
    backup()
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
            # for index, post in enumerate(feed):
            date_published = DateHandler.parse_datetime(post.published)

            if hasattr(post, "daily_liturgy"):
                if date_published > date_last_url and post.link != last_url \
                        and post.daily_liturgy != '':
                    message = post.title + '\n' + post.daily_liturgy
                    result = send_newest_messages(text=message, url=url, disable_page_preview=True)
                    if post == feed[-1] and result:
                        update_url(url=url, last_update=date_published, last_url=post.link)
            elif date_published > date_last_url and post.link != last_url:
                message = post.title + '\n' + post.link
                result = send_newest_messages(message, url)
                if result:
                    update_url(url=url, last_update=date_published, last_url=post.link)
            else:
                pass
    except TypeError as _:
        logger.error(f"TypeError {url} {str(_)}")


def update_url(url, last_update, last_url):
    db.update_url(url=url, last_update=last_update, last_url=last_url)


def send_newest_messages(text, url, disable_page_preview=None):
    names_url = db.get_names_for_user_activated(url)
    is_update_url = False
    for name in names_url:
        chat_id = int(db.get_value_name_key(name, 'chat_id'))
        if chat_id:
            try:
                # print(chat_id, url)
                chat = bot.get_chat(chat_id=str(chat_id))
                for admin in db.list_admins():
                    bot.send_message(chat_id=str(admin), text=str(text) + '\n' + str(chat), disable_notification=True)
                chat_username = chat.username if (chat.username and chat.type != 'private') else None
                text = text + '\n\nt.me/' + (chat_username if chat_username else BOT_NAME)
                result = bot.send_message(chat_id=chat_id, text=text, disable_web_page_preview=disable_page_preview)
                if not result:
                    errors(chat_id=chat_id, url=url)
                else:
                    is_update_url = True
            except telebot.apihelper.ApiException as _:
                errors(chat_id, url)
    return is_update_url


def errors(chat_id, url):
    """ Error handling """
    try:
        db.disable_url_chat(chat_id)

        logger.error(f'disable url {url} for chat_id {chat_id} from chat list')

    except ValueError as _:
        logger.error(f"error ValueError {str(_)}")


if __name__ == "__main__":
    parse_parallel()
