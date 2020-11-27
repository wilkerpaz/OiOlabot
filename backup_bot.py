from datetime import time, datetime

import telebot
from decouple import config

from util.database import DatabaseHandler

DB = config('DB')
PATH_REDIS = config('PATH_REDIS')
API_TOKEN = config('DEV_TOKEN')  # Tokens do Bot de Desenvolvimento


def backup():
    if time(22, 10) <= datetime.now().time() <= time(22, 15):
        db.redis.save()
        list_admins = db.list_admins()
        for chat_id in list_admins:
            bot.send_document(chat_id=chat_id, data=PATH_REDIS)


if __name__ == "__main__":
    if time(22, 10) <= datetime.now().time() <= time(22, 15):
        backup()
