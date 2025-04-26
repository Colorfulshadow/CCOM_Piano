"""
@Author: Tianyi Zhang
@Date: 2025/4/26
@Description: 
"""
from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.models.reservation import RecurringReservation, OneTimeReservation, ReservationHistory
from app.models.room import Room
from datetime import datetime, timedelta, date
from app.utils.time_utils import get_day_of_week, get_day_name
from sqlalchemy import func
import pytz

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """首页"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('main/index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """用户控制面板"""
    # 获取即将到来的预约（未来7天）
    today = date.today()
    next_week = today + timedelta(days=7)

    # 获取未来7天的成功历史条目
    upcoming_reservations = ReservationHistory.query.filter(
        ReservationHistory.user_id == current_user.id,
        ReservationHistory.status == 'successful',
        ReservationHistory.reservation_date >= today,
        ReservationHistory.reservation_date <= next_week
    ).order_by(ReservationHistory.reservation_date, ReservationHistory.start_time).all()

    # 获取当前循环预约
    recurring_reservations = RecurringReservation.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()

    # 获取待处理的一次性预约
    pending_reservations = OneTimeReservation.query.filter_by(
        user_id=current_user.id,
        status='pending'
    ).order_by(OneTimeReservation.reservation_date, OneTimeReservation.start_time).all()

    # 获取预约统计
    total_successful = ReservationHistory.query.filter_by(
        user_id=current_user.id,
        status='successful'
    ).count()

    total_failed = ReservationHistory.query.filter_by(
        user_id=current_user.id,
        status='failed'
    ).count()

    # 获取最常使用的琴房
    most_used_room = Room.query.join(ReservationHistory).filter(
        ReservationHistory.user_id == current_user.id,
        ReservationHistory.status == 'successful'
    ).group_by(Room.id).order_by(func.count(ReservationHistory.id).desc()).first()

    # 获取最常使用的星期几
    most_used_day_query = ReservationHistory.query.filter_by(
        user_id=current_user.id,
        status='successful'
    ).with_entities(
        func.dayofweek(ReservationHistory.reservation_date).label('day_of_week'),
        func.count().label('count')
    ).group_by('day_of_week').order_by(func.count().desc()).first()

    most_used_day = None
    if most_used_day_query:
        # 将星期几从MySQL格式（1=星期日，2=星期一）转换为我们的格式（0=星期一）
        day_num = (int(most_used_day_query.day_of_week) - 2) % 7
        most_used_day = get_day_name(day_num)

    # 计算下一次预约时间
    beijing_tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(beijing_tz)
    reservation_time = now.replace(hour=21, minute=30, second=0, microsecond=0)

    # 如果今天已经过了预约时间，则设置为明天
    if now > reservation_time:
        reservation_time = reservation_time + timedelta(days=1)

    # 计算距离下一次预约窗口的时间
    time_until_reservation = reservation_time - now
    hours, remainder = divmod(time_until_reservation.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    time_until_str = f"{hours}小时 {minutes}分钟"

    # 获取明天的星期几，用于下一次预约日
    next_reservation_day = get_day_name(get_day_of_week(date.today() + timedelta(days=1)))

    context = {
        'upcoming_reservations': upcoming_reservations,
        'recurring_reservations': recurring_reservations,
        'pending_reservations': pending_reservations,
        'statistics': {
            'total_successful': total_successful,
            'total_failed': total_failed,
            'success_rate': (total_successful / (total_successful + total_failed) * 100) if (
                                                                                                        total_successful + total_failed) > 0 else 0,
            'most_used_room': most_used_room.name if most_used_room else None,
            'most_used_day': most_used_day
        },
        'next_reservation_time': reservation_time.strftime('%H:%M'),
        'next_reservation_day': next_reservation_day,
        'time_until_reservation': time_until_str,
        'next_reservation_date': reservation_time.strftime('%Y-%m-%d')
    }

    return render_template('main/dashboard.html', **context)


@main_bp.route('/about')
def about():
    """关于页面，包含系统信息"""
    system_info = {
        'max_daily_reservations': current_app.config['MAX_DAILY_RESERVATIONS'],
        'max_reservation_hours': current_app.config['MAX_RESERVATION_HOURS'],
        'reservation_open_time': current_app.config['RESERVATION_OPEN_TIME'],
        'notifications_enabled': current_app.config['NOTIFICATION_ENABLED'],
        'reservation_count': ReservationHistory.query.count(),
        'user_count': len(set([r.user_id for r in ReservationHistory.query.all()])),
        'room_count': Room.query.count()
    }

    return render_template('main/about.html', system_info=system_info)