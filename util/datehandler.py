import pytz
import datetime
from dateutil import parser


class DateHandler:
    datetime = datetime.datetime

    @staticmethod
    def get_datetime_now():
        # Strip seconds from datetime
        date_string = str(
            datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
        naive_date = datetime.datetime.utcnow().strptime(date_string, "%Y-%m-%d %H:%M:%S")

        # Make datetime aware of timezone
        aware_date = pytz.utc.localize(naive_date)
        result = aware_date.astimezone(pytz.timezone("America/Belem"))
        return result

    @staticmethod
    def parse_datetime(date_time):
        result = parser.parse(date_time)

        if result.tzinfo is None:
            aware_date = pytz.utc.localize(result)
            result = aware_date.astimezone(pytz.timezone("America/Belem"))

        return result
