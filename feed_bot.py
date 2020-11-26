import logging
from datetime import timedelta
from multiprocessing.dummy import Pool as ThreadPool
from time import sleep

import telebot
from decouple import config

from util.database import DatabaseHandler
from util.datehandler import DateHandler
from util.feedhandler import FeedHandler

ADMINS = ['26072030']  # Escreva a ID do seu Usuáro no telegram

LOG = config('LOG')
DB = config('DB')
BOT_NAME = config('BOT_NAME')
API_TOKEN = config('DEV_TOKEN')  # Tokens do Bot de Desenvolvimento

logging.basicConfig(level=LOG, format='%(name)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

bot = telebot.TeleBot(API_TOKEN)
db = DatabaseHandler(DB)


def parse_parallel():
    time_started = DateHandler.datetime.now()
    print(time_started)
    urls = db.get_urls_activated()
    threads = len(urls)
    pool = ThreadPool(threads)
    pool.map(update_feed, urls)
    pool.close()

    time_ended = DateHandler.datetime.now()
    duration = time_ended - time_started
    logger.info(f"Finished updating! Parsed {str(len(urls))} rss feeds in {str(duration)}! {BOT_NAME}")
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
                    result = send_newest_messages(message, url)
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


def send_newest_messages(text, url):
    names_url = db.get_names_for_user_activated(url)
    is_update_url = False
    for name in names_url:
        chat_id = int(db.get_value_name_key(name, 'chat_id'))
        if chat_id:
            result = bot.send_message(chat_id=chat_id, text=text, parse_mode='html')
            if not result:
                errors(chat_id=chat_id, url=url)
            else:
                is_update_url = True
    return is_update_url


def errors(chat_id, url):
    """ Error handling """
    try:
        db.disable_url_chat(chat_id)

        logger.error(f'disable url {url} for chat_id {chat_id} from chat list')

    except ValueError as _:
        logger.error(f"error ValueError {str(_)}")


if __name__ == "__main__":
    while True:
        parse_parallel()
        sleep(10)