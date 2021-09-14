# A library that allows to create an inline calendar keyboard.
# grcanosa https://github.com/grcanosa
#
"""
Base methods for calendar keyboard creation and processing.
"""

import calendar
import datetime
import locale

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')


def create_callback_data(action, year, month, day):
    """ Create the callback data associated to each button"""
    return ";".join([action, str(year), str(month), str(day)])


def separate_callback_data(data):
    """ Separate the callback data"""
    return data.split(";")


def create_calendar(year=None, month=None):
    """
    Create an inline keyboard with the provided year and month
    :param int year: Year to use in the calendar, if None the current year is used.
    :param int month: Month to use in the calendar, if None the current month is used.
    :return: Returns the InlineKeyboardMarkup object with the calendar.
    """
    now = datetime.datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month
    data_ignore = create_callback_data("IGNORE", year, month, 0)
    keyboard = []
    # First row - Month and Year
    row = [InlineKeyboardButton(calendar.month_name[month].title() + " " + str(year), callback_data=data_ignore)]
    keyboard.append(row)
    # Second row - Week Days
    row = []
    for day in ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]:
        row.append(InlineKeyboardButton(day, callback_data=data_ignore))
    keyboard.append(row)

    my_calendar = calendar.monthcalendar(year, month)
    for week in my_calendar:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data=data_ignore))
            else:
                row.append(InlineKeyboardButton(str(day), callback_data=create_callback_data("DAY", year, month, day)))
        keyboard.append(row)
    # Last row - Buttons
    row = [InlineKeyboardButton("<", callback_data=create_callback_data("PREV-MONTH", year, month, day)),
           InlineKeyboardButton(" ", callback_data=data_ignore),
           InlineKeyboardButton(">", callback_data=create_callback_data("NEXT-MONTH", year, month, day))]
    keyboard.append(row)

    return InlineKeyboardMarkup(keyboard)


def process_calendar_selection(client, update):
    """
    Process the callback_query. This method generates a new calendar if forward or
    backward is pressed. This method should be called inside a CallbackQueryHandler.
    :param telegram.Bot bot: The bot, as provided by the CallbackQueryHandler
    :param telegram.Update update: The update, as provided by the CallbackQueryHandler
    :return: Returns a tuple (Boolean,datetime.datetime), indicating if a date is selected
                and returning the date if so.
    """
    ret_data = (False, None)
    (action, year, month, day) = separate_callback_data(update.data)
    curr = datetime.datetime(int(year), int(month), 1)
    if action == "IGNORE":
        client.answer_callback_query(callback_query_id=update.id)
    elif action == "DAY":
        update.edit_message_text(text=update.message.text, )
        ret_data = True, datetime.datetime(int(year), int(month), int(day))
    elif action == "PREV-MONTH":
        pre = curr - datetime.timedelta(days=1)
        update.edit_message_text(text=update.message.text,
                                 reply_markup=create_calendar(int(pre.year), int(pre.month)))
    elif action == "NEXT-MONTH":
        ne = curr + datetime.timedelta(days=31)
        update.edit_message_text(text=update.message.text,
                                 reply_markup=create_calendar(int(ne.year), int(ne.month)))
    else:
        client.answer_callback_query(callback_query_id=update.id, text="Something went wrong!")
        # UNKNOWN
    return ret_data


EPOCH = 1970
_EPOCH_ORD = datetime.date(EPOCH, 1, 1).toordinal()


def timegm(tuple):
    """Unrelated but handy function to calculate Unix timestamp from GMT."""
    year, month, day, hour, minute, second = tuple[:6]
    days = datetime.date(year, month, 1).toordinal() - _EPOCH_ORD + day - 1
    hours = days * 24 + hour
    minutes = hours * 60 + minute
    seconds = minutes * 60 + second
    return seconds
