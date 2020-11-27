from redis import StrictRedis
from decouple import config

from util.datehandler import DateHandler

password = config('REDIS')


class DatabaseHandler(object):

    def __init__(self, db):

        self.redis = StrictRedis(host='localhost',
                                 port=6379,
                                 password=password,
                                 charset='utf-8',
                                 decode_responses=True,
                                 db=db
                                 )

    '''find names for argument in data base '''

    def _find(self, search):
        cursor = None
        names = []
        while cursor != 0:
            if cursor is None:
                cursor = 0
            fined = self.redis.scan(cursor, str(search))
            cursor = fined[0]
            names.extend(fined[1])
        return names

    def find_names(self, find):
        search = '*' + find + '*'
        return self._find(search)

    def exist_name(self, name):
        return True if self.redis.exists(name) else False

    def exist_key(self, name, key):
        return self.redis.hexists(name, key)

    def get_value_name_key(self, name, key):
        return self.redis.hget(name, key)

    def get_all_keys_for_name(self, name):
        keys = self.redis.hgetall(name)
        return keys if keys else None

    def get_keys_for_name(self, name, *args):
        keys = self.redis.hmget(name, *args)
        return keys if keys else None

    '''set a name and key on database'''

    def set_name_key(self, name, mapping: dict):
        self.redis.hset(name=name, mapping=mapping)
        return bool(self.exist_name(name))

    '''set a name and key on database'''

    def del_names(self, names: list):
        return [self.redis.delete(name) for name in names]

    '''check if group exist'''

    def exist_group(self, chat_id):
        name = 'group:' + str(chat_id)
        return self.exist_name(name)

    def update_owner(self, chat_id, user_id):
        names = self._find('user_url:*' + str(chat_id) + '*')
        for name in names:
            name_update = name.split(':')
            name_update[1] = str(user_id)
            name_update = ';'.join(name_update)
            self.redis.rename(name, name_update)

    '''register or update a url with las_url and last_update'''

    def update_group(self, chat_id, chat_name, chat_title, user_id, update_owner=None):
        name = 'group:' + str(chat_id)
        mapping = {'chat_adm': str(user_id),
                   'chat_id': str(chat_id),
                   'chat_lock': 'True',
                   'chat_name': chat_name,
                   'chat_quiet': 'True',
                   'chat_title': str(chat_title)}
        if update_owner:
            self.update_owner(chat_id, user_id)

        return True if self.set_name_key(name=name, mapping=mapping) else False

    '''check if url exist'''

    def exist_url(self, url):
        name = 'url:^' + str(url) + '^'
        return self.exist_name(name)

    '''register or update a url with las_url and last_update'''

    def update_url(self, url, last_update='2000-01-01 00:00:00+00:00', last_url='http://www.exemplo.com'):
        name = 'url:^' + str(url) + '^'
        mapping = {'last_update': str(last_update), 'last_url': last_url}
        return True if self.set_name_key(name=name, mapping=mapping) else False

    '''check if url exist in chat'''

    def exist_url_to_chat(self, user_id, chat_id, url):
        name = 'user_url:' + str(user_id) + ':chat_id:' + str(chat_id) + ':^' + str(url) + '^'
        return self.exist_name(name)

    '''register a url for user or group'''

    def set_url_to_chat(self, chat_id, chat_name, url, user_id):
        name_url = self.exist_url(url)
        if not name_url:
            self.update_url(url=url)

        name_url_chat = self.exist_url_to_chat(user_id, chat_id, url)
        if not name_url_chat:
            name = 'user_url:' + str(user_id) + ':chat_id:' + str(chat_id) + ':^' + str(url) + '^'
            mapping = {'chat_id': str(chat_id), 'chat_name': chat_name, 'user_id': str(user_id), 'disable': 'False'}
            return True if self.set_name_key(name=name, mapping=mapping) else False
        else:
            return False

    '''extract url for name'''

    @staticmethod
    def extract_url_from_names(names):
        if names:
            uncompress_name = [name.split('^') for name in names]
            urls = sorted(set(['{}'.format(url[1]) for url in uncompress_name]))
            return urls
        return ()

    '''return all url for a chat_id'''

    def get_chat_urls(self, user_id):
        names = self._find('user_url:' + str(user_id) + ':*')
        chat_urls = []
        for name in names:
            keys = self.get_all_keys_for_name(name)
            chat_id = keys.get('chat_id')
            chat_name = keys.get('chat_name')
            user_id = keys.get('user_id')
            url = self.extract_url_from_names([name])[0]

            mapping = {'user_id': str(user_id), 'chat_name': chat_name, 'url': url, 'chat_id': str(chat_id)}
            chat_urls.append(mapping)
        return chat_urls

    '''return info about last update url'''

    def get_update_url(self, url):
        name = 'url:^' + str(url) + '^'
        if self.exist_name(name):
            keys = self.get_all_keys_for_name(name)
            last_update = keys.get('last_update')
            last_url = keys.get('last_url')
            return {'last_update': last_update, 'last_url': last_url}
        return False

    '''return all url activated'''

    def get_urls_activated(self):
        names = self._find('user_url*')
        active_keys = sorted(set([name for name in names if not self.get_value_name_key(name, 'disable') == 'True']))
        return self.extract_url_from_names(active_keys)

    '''return all url deactivated'''

    def get_urls_deactivated(self):
        names = self._find('user_url*')
        return sorted(set([name for name in names if self.get_value_name_key(name, 'disable') == 'True']))

    '''activated all url'''

    def activated_all_urls(self):
        names = self._find('user_url*')
        for name in names:
            self.set_name_key(name, {'disable': 'False'})
        return True

    '''return names for key 'disable' = 'True' from url'''

    def get_names_for_user_activated(self, url):
        names = self._find('user_url*' + url + '*')
        return sorted(set([name for name in names if self.get_value_name_key(name, 'disable') == 'False']))

    '''return all url activated'''

    def get_chat_id_for_chat_name(self, user_id, chat_name):
        names = self._find('user_url:*' + str(user_id) + '*')
        for name in names:
            chat_name_db = self.get_value_name_key(name, 'chat_name')
            chat_id_db = self.get_value_name_key(name, 'chat_id')
            if chat_name_db == chat_name and chat_id_db:
                return chat_id_db
        return None

    '''disable url for chat'''

    def disable_url_chat(self, chat_id):
        names = self._find('user_url:*chat_id:' + str(chat_id) + '*')
        mapping = {'disable': 'True'}
        disables = [self.set_name_key(name=name, mapping=mapping) for name in names] if names else []
        return disables

    '''del url for chat'''

    def del_url_for_chat(self, chat_id, url):
        names = self._find('user_url:*' + str(chat_id) + '*' + url + '*')
        result = self.del_names(names)
        return True if result[0] == 1 else None

    def list_admins(self):
        return self.redis.lrange('admins', 0, self.redis.llen('admins'))

    def backup(self):
        now = DateHandler.get_datetime_now()
        last_backup = self.get_value_name_key('backup', 'last_backup')
        last_backup = DateHandler.parse_datetime(last_backup)
        date_last_backup = DateHandler.date(last_backup)
        hour_last_backup = DateHandler.time(last_backup)
        print(date_last_backup, DateHandler.date(now), date_last_backup < DateHandler.date(now))
        if date_last_backup < DateHandler.date(now):
            if hour_last_backup <= DateHandler.time(now):
                mapping = {'last_backup': str(now)}
                self.set_name_key('backup', mapping=mapping)
                self.redis.save()
                return True
        else:
            return False
