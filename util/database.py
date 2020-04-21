from redis import StrictRedis


class DatabaseHandler(object):

    def __init__(self, db):

        self.redis = StrictRedis(host='localhost',
                                 port=6379,
                                 # password='password',
                                 charset='utf-8',
                                 decode_responses=True,
                                 db=db
                                 )

    def get_group_urls(self, chat_id):
        keys = self.find_keys('user_url:' + str(chat_id) + ':*')
        keys.sort()
        url_group = []
        for key in keys:
            url = self.extract_urls_from_keys([key])
            key_url = [key, url[0]]
            url_info = self.find_key_value(key_url)
            url_group.append(url_info[0])
        return url_group

    @staticmethod
    def extract_urls_from_keys(keys):
        if keys:
            uncompress_keys = [key.split('^') for key in keys]
            urls = sorted(
                set(
                    ['{}'.format(key[1]) for key in uncompress_keys]
                )
            )
            return urls
        return ()

    def extract_user_id_from_key(self, key):
        if key:
            return self.redis.hvals(key)
        return ()

    def find_key_value(self, key_url):
        key = self.redis.hkeys(key_url[0])
        value = self.redis.hvals(key_url[0])
        url = key_url[1]
        i = 0
        url_list = []
        while i < len(key):
            url_group = {'url': url, 'chat_id': value[i], 'chat_name': key[i]}
            url_list.append(url_group)
            i += 1
        return url_list

    def set_new_or_update_web(self, url, last_update='2000-01-01 00:00:00+00:00', last_url='http://www.exemplo.com'):
        update = self.redis.hmset('url:^' + str(url) + '^', {'last_update': str(last_update), 'last_url': last_url})
        return True if update else False

    def set_url_to_group(self, chat_id, url, user_id, user_name):
        key_url = self.redis.exists('url:^' + str(url) + '^')
        if not key_url:
            self.set_new_or_update_web(url=str(url))

        key_url_group = self.exist_url_to_group(chat_id, user_id, url)
        if not key_url_group:
            self.redis.hset('user_url:' + str(chat_id) + ':user_id:' + str(user_id) +
                            ':^' + str(url) + '^', user_name, str(user_id))
            return True
        else:
            return False

    def exist_url_to_group(self, chat_id, user_id, url):
        key = self.redis.hexists('user_url:' + str(chat_id) + ':user_id:' + str(user_id) +
                                 ':^' + str(url) + '^', '*')
        return True if key else False

    def get_user_id(self, chat_id, url, user_name=None):
        keys = self.find_keys('user_url:' + str(chat_id) + '*' + url + '*')
        if user_name:
            active_keys = sorted(set([key for key in keys if self.redis.hget(key, user_name)]))
        else:
            active_keys = sorted(set([key for key in keys if keys]))

        result = None
        for key in active_keys:
            if user_name:
                result = {'user_id': self.redis.hget(key, user_name), 'key': key}
            else:
                result = {'user_id': self.redis.hvals(key), 'key': key}

            if result:
                break
        return result

    def find_keys(self, search):
        cursor = None
        keys = []
        while cursor != 0:
            if cursor is None:
                cursor = 0
            fined = self.redis.scan(cursor, str(search))
            cursor = fined[0]
            keys.extend(fined[1])
        return keys

    def get_update_url(self, url):
        if self.redis.exists('url:^' + str(url) + '^'):
            last_update = self.redis.hgetall('url:^' + str(url) + '^')
            last_update['url'] = url
            return last_update
        return False

    def get_urls(self, url=None):
        if not url:
            keys = self.find_keys('user_url*')
        else:
            keys = self.find_keys('user_url*' + str(url) + '*')

        if not keys:
            return []

        return self.extract_url_from_keys(keys)

    def get_all_urls(self, url=None):
        if not url:
            keys = self.find_keys('url:*')
        else:
            keys = self.find_keys('url:*' + str(url) + '*')

        if not keys:
            return []

        return self.extract_url_from_keys(keys)

    def get_group_id_from_user_id(self, chat_id=None):
        if not chat_id:
            keys = self.find_keys('user_url*')
        else:
            keys = self.find_keys('user_url*' + str(chat_id) + '*')

        if not keys:
            return []

        return self.extract_group_id_from_keys(keys)

    @staticmethod
    def extract_url_from_keys(keys):
        if keys:
            uncompress_keys = [key.split('^') for key in keys]
            users_ids = sorted(
                set(
                    [key[1] for key in uncompress_keys]
                )
            )
            return users_ids
        return []

    @staticmethod
    def extract_group_id_from_keys(keys):
        if keys:
            uncompress_keys = [key.split(':') for key in keys]
            users_ids = sorted(
                set(
                    [key[3] for key in uncompress_keys]
                )
            )
            return users_ids
        return []
