
import logging

from decouple import config
from pyrogram import filters, Client
from pyrogram.types import ReplyKeyboardMarkup

BOT_NAME = config('BOT_NAME')
API_TOKEN = config('DEV_TOKEN')  # Tokens do Bot de Desenvolvimento

CHOOSING, TYPING_REPLY, TYPING_CHOICE = range(3)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

app = Client(session_name=BOT_NAME, bot_token=API_TOKEN)

reply_keyboard = [
    ['Age', 'Favourite colour'],
    ['Number of siblings', 'Something else...'],
    ['Done'],
]

markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)


@app.on_message(filters.regex(r'^/(start|help)($|@\w+)'))
def start(client, update) -> int:
    update.reply_text(
        "Hi! My name is Doctor Botter. I will hold a more complex conversation with you. "
        "Why don't you tell me something about yourself?",
        reply_markup=markup,
    )

    return regular_choice


@app.on_callback_query()
def regular_choice(client, update) -> int:
    print(update)
    text = update.text
    # client.user_data['choice'] = text
    update.answer(text=text)
    update.reply_text(f'Your {text.lower()}? Yes, I would love to hear about that!')

    return 1


app.run()
