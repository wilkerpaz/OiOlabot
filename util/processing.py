import logging

from pyrogram.errors import PeerIdInvalid, FloodWait, ChannelInvalid, UserIsBlocked

from util.datehandler import DateHandler
from util.feedhandler import FeedHandler

logger = logging.getLogger(__name__)
logging.getLogger('processing').setLevel(logging.INFO)


class BatchProcess(object):

    def __init__(self, database, bot):
        self.db = database
        self.bot = bot
        self.run()

    def run(self):
        if self.bot.is_connected:
            urls = self.db.get_urls()
            self.parse_parallel(urls=urls, threads=4)

    def parse_parallel(self, urls, threads):
        if self.bot.is_connected:
            time_started = DateHandler.datetime.now()
            for url in urls:
                self.update_feed(url)

            time_ended = DateHandler.datetime.now()
            duration = time_ended - time_started
            logger.info("Finished updating! Parsed " + str(len(urls)) +
                        " rss feeds in " + str(duration) + " ! " + self.bot.get_me().first_name)

    def update_feed(self, url):
        if self.bot.is_connected:
            try:
                feed = FeedHandler.parse_feed(url, 4)
                for post in feed:
                    # for index, post in enumerate(feed):
                    get_url_info = self.db.get_update_url(url)
                    date_published = DateHandler.parse_datetime(post.published)
                    last_url = get_url_info['last_url']
                    date_last_url = DateHandler.parse_datetime(get_url_info['last_update'])
                    url = get_url_info['url']

                    if hasattr(post, "daily_liturgy"):
                        if date_published > date_last_url and post.link != last_url \
                                and post.daily_liturgy != '':
                            message = post.title + '\n' + post.daily_liturgy
                            self.send_newest_messages(message, url)
                            if post == feed[-1]:
                                self.update_url(url=url, last_update=date_published, last_url=post.link)
                    elif date_published > date_last_url and post.link != last_url:
                        message = post.title + '\n' + post.link
                        self.send_newest_messages(message, url)
                        self.update_url(url=url, last_update=date_published, last_url=post.link)
                    else:
                        pass

            except PeerIdInvalid as e:
                print(e)

    def update_url(self, url, last_update, last_url):
        if self.bot.is_connected:
            self.db.set_new_or_update_web(url=url, last_update=last_update, last_url=last_url)

    def send_newest_messages(self, message, url):
        if self.bot.is_connected:
            key_url = self.db.find_keys('user_url*' + url + '*')
            for url in key_url:
                chat_id = self.db.redis.hvals(url)
                for chat in chat_id:
                    try:
                        self.bot.send_message(chat_id=int(chat), text=message, parse_mode='html')
                        return None
                    except PeerIdInvalid as error:
                        logger.info('Error send message for chat_id ' + chat)
                        print('TelegramError', error, chat)
                    except FloodWait as error:
                        print(error, chat)

                    except ChannelInvalid as error:
                        logger.info('Error send message for chat_id ' + str(chat))
                        print(error, chat)

                    except UserIsBlocked as error:
                        logger.info('Error send message for chat_id ' + str(chat))
                        print(error, chat)

    def error(self, chat_id, error):
        if self.bot.is_connected:
            """ Error handling """
            try:
                list_group = self.db.find_keys('group:*')
                for key in list_group:
                    value = self.db.redis.hvals(key)
                    for k in value:
                        if int(k) == int(chat_id):
                            self.db.redis.delete(key)

                logger.info('Removed chat_id %s from chat list' % chat_id)

                logger.error("An error occurred: %s" % error)

            except ValueError as e:
                print(e)
