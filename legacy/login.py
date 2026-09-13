from pyrogram import Client
from decouple import config

api_id = config('API_ID')
api_hash = config('API_HASH')
lang_code = "pt-br"

app = Client("LiturgiaDiaria_bot", api_id=api_id, api_hash=api_hash)

app.run()
