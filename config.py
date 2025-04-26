"""
@Author: Tianyi Zhang
@Date: 2025/4/26
@Description: 
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(os.path.dirname(basedir), '.env'))


class Config:
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-should-change-this-in-production'

    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'mysql+pymysql://root:zty20030204@localhost/ccom_piano'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Application specific configuration
    CCOM_API_ROOT = "https://saas.tansiling.com"
    CCOM_API_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.109 Safari"
    BEIJING_TIMEZONE_OFFSET = 8  # UTC+8

    # APScheduler configuration
    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = "Asia/Shanghai"

    # Notification settings
    NOTIFICATION_ENABLED = True

    # Reservation settings
    MAX_DAILY_RESERVATIONS = 2
    MAX_RESERVATION_HOURS = 3
    RESERVATION_OPEN_TIME = "2130"  # 9:30 PM Beijing time

    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)