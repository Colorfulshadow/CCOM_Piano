"""
@Author: Tianyi Zhang
@Date: 2025/4/26
@Description: 
"""
from datetime import datetime, timedelta, timezone
import pytz
from flask import current_app
import requests

# Constants
BEIJING_TIMEZONE = timezone(timedelta(hours=8))


def get_current_time(tz=BEIJING_TIMEZONE):
    """Get current time in the specified timezone (default Beijing)"""
    return datetime.now(tz)


def convert_to_timestamp(input_time, add_day=False):
    """
    Convert a time string or datetime to a timestamp

    Args:
        input_time: Time string (e.g., "1400") or datetime object
        add_day: Whether to add a day to the result

    Returns:
        int: Timestamp in milliseconds
    """
    if isinstance(input_time, datetime):
        target_datetime = input_time
    else:
        current_time = get_current_time()
        hour, minute = map(int, [input_time[:2], input_time[2:]])
        target_datetime = datetime(
            year=current_time.year,
            month=current_time.month,
            day=current_time.day,
            hour=hour,
            minute=minute,
            tzinfo=BEIJING_TIMEZONE
        )

    if add_day:
        target_datetime += timedelta(days=1)

    if target_datetime.year < 1970:
        raise ValueError("Date is too early to convert to UNIX timestamp.")

    return int(target_datetime.timestamp() * 1000)


def split_time(start_time, end_time, segment_hours=3):
    """
    Split a time range into segments of specified hours

    Args:
        start_time: Start time string (e.g., "1400")
        end_time: End time string (e.g., "1700")
        segment_hours: Maximum hours per segment

    Returns:
        list: List of (start_timestamp, end_timestamp) tuples
    """
    current_date = get_current_time().date()
    next_date = current_date + timedelta(days=1)

    start_datetime = datetime.combine(next_date, datetime.strptime(start_time, '%H%M').time())
    end_datetime = datetime.combine(next_date, datetime.strptime(end_time, '%H%M').time())

    segments = []
    while start_datetime < end_datetime:
        next_datetime = min(start_datetime + timedelta(hours=segment_hours), end_datetime)

        start_timestamp = convert_to_timestamp(start_datetime)
        end_timestamp = convert_to_timestamp(next_datetime)

        segments.append((start_timestamp, end_timestamp))
        start_datetime = next_datetime

    return segments


def convert_to_datetime(timestamp_ms, timezone_str='Asia/Shanghai'):
    """
    Convert a Unix timestamp in milliseconds to a datetime

    Args:
        timestamp_ms: Unix timestamp in milliseconds
        timezone_str: Timezone string

    Returns:
        datetime: Datetime object in the specified timezone
    """
    timestamp_s = timestamp_ms / 1000
    dt_utc = datetime.utcfromtimestamp(timestamp_s)
    dt_utc = pytz.utc.localize(dt_utc)
    dt_tz = pytz.timezone(timezone_str).normalize(dt_utc.astimezone(pytz.timezone(timezone_str)))
    return dt_tz


def calculate_duration_hours(start_time, end_time):
    """
    Calculate the duration between two time strings in hours

    Args:
        start_time: Start time string (e.g., "1400")
        end_time: End time string (e.g., "1700")

    Returns:
        float: Duration in hours
    """
    start_hour, start_minute = int(start_time[:2]), int(start_time[2:])
    end_hour, end_minute = int(end_time[:2]), int(end_time[2:])

    # Handle cases where end time is on the next day
    if end_hour < start_hour or (end_hour == start_hour and end_minute < start_minute):
        end_hour += 24

    start_minutes = start_hour * 60 + start_minute
    end_minutes = end_hour * 60 + end_minute

    return (end_minutes - start_minutes) / 60


def get_day_of_week(date_obj=None):
    """
    Get the day of week as integer (0=Monday, 6=Sunday)

    Args:
        date_obj: Date object (default: today)

    Returns:
        int: Day of week (0-6)
    """
    if date_obj is None:
        date_obj = get_current_time().date()

    # weekday() returns 0 for Monday, 6 for Sunday
    return date_obj.weekday()


def get_day_name(day_of_week):
    """
    Get the name of a day from its index

    Args:
        day_of_week: Day index (0-6)

    Returns:
        str: Day name
    """
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return days[day_of_week]


class ServerTimeHelper:
    """Helper class to interact with the server time"""

    def __init__(self):
        self.server_url = current_app.config['CCOM_API_ROOT']

    def get_server_time(self):
        """Get the server's current time"""
        response = requests.head(self.server_url)
        date_str = response.headers.get('Date')
        if date_str:
            server_time_utc = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S GMT').replace(tzinfo=timezone.utc)
            return server_time_utc
        raise ValueError("Unable to retrieve server time")

    def measure_latency(self):
        """Measure the one-way latency to the server in milliseconds"""
        response = requests.get(self.server_url)
        return response.elapsed.microseconds / 1000 / 2  # Return one-way latency in milliseconds

    def calculate_send_time(self, target_time_str, add_day=False):
        """
        Calculate when to send a request to hit the server at the target time

        Args:
            target_time_str: Target time string (e.g., "2130")
            add_day: Whether to target the next day

        Returns:
            datetime: Time to send the request
        """
        server_time_utc = self.get_server_time()
        server_time = server_time_utc.astimezone(BEIJING_TIMEZONE)
        current_time = get_current_time()

        target_datetime = datetime.combine(
            current_time.date(),
            datetime.strptime(target_time_str, '%H%M').time()
        )

        if add_day:
            target_datetime += timedelta(days=1)

        one_way_latency = self.measure_latency() / 1000  # Convert to seconds
        time_diff = (current_time - server_time).total_seconds()

        # Adjust the target time based on server time difference and latency
        adjusted_target_timestamp = target_datetime.timestamp() - time_diff - one_way_latency

        return datetime.fromtimestamp(adjusted_target_timestamp, BEIJING_TIMEZONE)