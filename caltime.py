from datetime import datetime, timedelta, timezone
from config import root
import requests

SERVER_ROOT_URL = root
BEIJING_TIMEZONE = timezone(timedelta(hours=8))

class TimeUtils:
    @staticmethod
    def get_current_time(timezone=BEIJING_TIMEZONE):
        return datetime.now(timezone)

    @staticmethod
    def convert_to_timestamp(input_time, add_day=False):
        if isinstance(input_time, datetime):
            # 如果输入是 datetime 对象
            target_datetime = input_time
        else:
            # 如果输入是字符串
            current_time = TimeUtils.get_current_time()
            hour, minute = map(int, [input_time[:2], input_time[2:]])
            target_datetime = datetime(year=current_time.year, month=current_time.month,
                                       day=current_time.day, hour=hour, minute=minute,
                                       tzinfo=BEIJING_TIMEZONE)

        if add_day:
            target_datetime += timedelta(days=1)

        # 确保日期时间是合理的
        if target_datetime.year < 1970:
            raise ValueError("Date is too early to convert to UNIX timestamp.")
        return int(target_datetime.timestamp() * 1000)




    @staticmethod
    def split_time(start_time, end_time, segment_hours=3):
        current_date = TimeUtils.get_current_time().date()
        next_date = current_date + timedelta(days=1)  # 获取第二天的日期

        start_datetime = datetime.combine(next_date, datetime.strptime(start_time, '%H%M').time())
        end_datetime = datetime.combine(next_date, datetime.strptime(end_time, '%H%M').time())

        segments = []
        while start_datetime < end_datetime:
            next_datetime = min(start_datetime + timedelta(hours=segment_hours), end_datetime)

            start_timestamp = TimeUtils.convert_to_timestamp(start_datetime)
            end_timestamp = TimeUtils.convert_to_timestamp(next_datetime)

            segments.append((start_timestamp, end_timestamp))
            start_datetime = next_datetime

        return segments

class ServerTime:
    def __init__(self):
        self.server_url = SERVER_ROOT_URL

    def get_server_time(self):
        response = requests.head(self.server_url)
        date_str = response.headers.get('Date')
        if date_str:
            server_time_utc = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S GMT').replace(tzinfo=timezone.utc)
            return server_time_utc
        raise ValueError("Unable to retrieve server time")

    def measure_latency(self):
        response = requests.get(self.server_url)
        return response.elapsed.microseconds / 1000 / 2  # Return one-way latency in milliseconds

class SendTimeCalculator:
    def __init__(self):
        self.server_time_util = ServerTime()

    def calculate_send_time(self, target_time_str, add_day=False):
        server_time_utc = self.server_time_util.get_server_time()
        server_time = server_time_utc.astimezone(BEIJING_TIMEZONE)
        current_time = TimeUtils.get_current_time()
        target_datetime = datetime.combine(current_time.date(), datetime.strptime(target_time_str, '%H%M').time())
        if add_day:
            target_datetime += timedelta(days=1)
        one_way_latency = self.server_time_util.measure_latency() / 1000  # Convert to seconds
        adjusted_target_timestamp = target_datetime.timestamp() - (current_time - server_time).total_seconds() - one_way_latency
        return datetime.fromtimestamp(adjusted_target_timestamp, BEIJING_TIMEZONE)
