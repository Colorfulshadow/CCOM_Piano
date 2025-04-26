"""
@Author: Tianyi Zhang
@Date: 2025/4/26
@Description: 
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models.room import Room
from app.models.reservation import RecurringReservation, OneTimeReservation, ReservationHistory
from app.services.ccom_client import CCOMClient
from app.services.reservation_service import ReservationService
from app.utils.exceptions import ReservationLimitExceeded, DurationLimitExceeded
from app.utils.time_utils import get_day_of_week, get_day_name, calculate_duration_hours
from datetime import datetime, timedelta, date
import pytz

reservation_bp = Blueprint('reservation', __name__, url_prefix='/reservation')


@reservation_bp.route('/')
@login_required
def index():
    """预约控制面板"""
    # 暂时重定向到主控制面板
    return redirect(url_for('main.dashboard'))


@reservation_bp.route('/recurring')
@login_required
def recurring_list():
    """列出所有循环预约"""
    reservations = RecurringReservation.query.filter_by(
        user_id=current_user.id
    ).order_by(RecurringReservation.day_of_week, RecurringReservation.start_time).all()

    return render_template('reservation/recurring_list.html', reservations=reservations)


@reservation_bp.route('/recurring/create', methods=['GET', 'POST'])
@login_required
def recurring_create():
    """Create a new recurring reservation with the new time block interface"""
    rooms = Room.query.filter(Room.instruments.notlike('%无钢琴%')).order_by(Room.name).all()

    if request.method == 'POST':
        day_of_week = int(request.form.get('day_of_week'))
        total_blocks = int(request.form.get('total_blocks', 0))

        if total_blocks < 1:
            flash('请至少选择一个预约时段', 'danger')
            return render_template('reservation/recurring_create.html', rooms=rooms)

        # 处理第一个预约块
        if request.form.get('start_time_1') and request.form.get('end_time_1'):
            room_id_1 = request.form.get('room_id_1')
            start_time_1 = request.form.get('start_time_1')
            end_time_1 = request.form.get('end_time_1')

            try:
                # 验证输入并创建预约
                from app.utils.time_utils import calculate_duration_hours
                duration = calculate_duration_hours(start_time_1, end_time_1)

                reservation = RecurringReservation(
                    user_id=current_user.id,
                    room_id=room_id_1,
                    day_of_week=day_of_week,
                    start_time=start_time_1,
                    end_time=end_time_1,
                    is_active=True
                )

                db.session.add(reservation)

                # 如果有第二个预约块
                if total_blocks > 1 and request.form.get('start_time_2') and request.form.get('end_time_2'):
                    room_id_2 = request.form.get('room_id_2')
                    start_time_2 = request.form.get('start_time_2')
                    end_time_2 = request.form.get('end_time_2')

                    duration += calculate_duration_hours(start_time_2, end_time_2)

                    # 检查总时长不超过6小时
                    if duration > 6:
                        db.session.rollback()
                        flash('总预约时长不能超过6小时', 'danger')
                        return render_template('reservation/recurring_create.html', rooms=rooms)

                    reservation2 = RecurringReservation(
                        user_id=current_user.id,
                        room_id=room_id_2,
                        day_of_week=day_of_week,
                        start_time=start_time_2,
                        end_time=end_time_2,
                        is_active=True
                    )

                    db.session.add(reservation2)

                db.session.commit()
                flash('循环预约创建成功！', 'success')
                return redirect(url_for('reservation.recurring_list'))

            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"创建循环预约时出错：{str(e)}")
                flash(f'创建预约时出错：{str(e)}', 'danger')

    return render_template('reservation/recurring_create.html', rooms=rooms)


@reservation_bp.route('/recurring/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def recurring_edit(id):
    """编辑循环预约"""
    reservation = RecurringReservation.query.get_or_404(id)

    # 确保用户拥有此预约
    if reservation.user_id != current_user.id:
        flash('您没有权限编辑此预约。', 'danger')
        return redirect(url_for('reservation.recurring_list'))

    rooms = Room.query.filter(Room.instruments.notlike('%无钢琴%')).order_by(Room.name).all()

    if request.method == 'POST':
        room_id = request.form.get('room_id')
        day_of_week = int(request.form.get('day_of_week'))
        start_time = request.form.get('start_time').replace(':', '')
        end_time = request.form.get('end_time').replace(':', '')
        is_active = 'is_active' in request.form

        try:
            # 检查时长是否在限制范围内
            duration = calculate_duration_hours(start_time, end_time)
            if duration > current_app.config['MAX_RESERVATION_HOURS']:
                flash(
                    f"预约时长超过最大限制 {current_app.config['MAX_RESERVATION_HOURS']} 小时。",
                    'danger')
                return render_template('reservation/recurring_edit.html', reservation=reservation, rooms=rooms)

            # 更新预约
            reservation.room_id = room_id
            reservation.day_of_week = day_of_week
            reservation.start_time = start_time
            reservation.end_time = end_time
            reservation.is_active = is_active

            db.session.commit()

            flash('循环预约更新成功！', 'success')
            return redirect(url_for('reservation.recurring_list'))

        except Exception as e:
            db.session.rollback()
            flash(f'更新预约时出错：{str(e)}', 'danger')

    # 格式化时间用于表单
    formatted_start = f"{reservation.start_time[:2]}:{reservation.start_time[2:]}"
    formatted_end = f"{reservation.end_time[:2]}:{reservation.end_time[2:]}"

    return render_template('reservation/recurring_edit.html',
                           reservation=reservation,
                           rooms=rooms,
                           formatted_start=formatted_start,
                           formatted_end=formatted_end)


@reservation_bp.route('/recurring/<int:id>/delete', methods=['POST'])
@login_required
def recurring_delete(id):
    """删除循环预约"""
    reservation = RecurringReservation.query.get_or_404(id)

    # 确保用户拥有此预约
    if reservation.user_id != current_user.id:
        flash('您没有权限删除此预约。', 'danger')
        return redirect(url_for('reservation.recurring_list'))

    try:
        db.session.delete(reservation)
        db.session.commit()
        flash('循环预约删除成功！', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除预约时出错：{str(e)}', 'danger')

    return redirect(url_for('reservation.recurring_list'))


@reservation_bp.route('/one-time')
@login_required
def one_time_list():
    """列出所有一次性预约"""
    # 获取待处理的一次性预约
    pending = OneTimeReservation.query.filter_by(
        user_id=current_user.id,
        status='pending'
    ).order_by(OneTimeReservation.reservation_date, OneTimeReservation.start_time).all()

    return render_template('reservation/one_time_list.html', reservations=pending)


@reservation_bp.route('/one-time/create', methods=['GET', 'POST'])
@login_required
def one_time_create():
    """创建新的一次性预约"""
    rooms = Room.query.filter(Room.instruments.notlike('%无钢琴%')).order_by(Room.name).all()

    # 计算最小日期（明天）
    min_date = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')

    if request.method == 'POST':
        room_id = request.form.get('room_id')
        reservation_date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        start_time = request.form.get('start_time').replace(':', '')
        end_time = request.form.get('end_time').replace(':', '')
        is_cancellation = 'is_cancellation' in request.form

        try:
            # 检查日期是否有效（明天或之后）
            if reservation_date <= date.today():
                flash('预约日期必须是明天或之后。', 'danger')
                return render_template('reservation/one_time_create.html', rooms=rooms, min_date=min_date)

            # 检查用户是否已达每日限制
            if not is_cancellation:
                try:
                    ReservationService.check_reservation_limits(
                        current_user.id, reservation_date, start_time, end_time
                    )
                except (ReservationLimitExceeded, DurationLimitExceeded) as e:
                    flash(str(e), 'danger')
                    return render_template('reservation/one_time_create.html', rooms=rooms, min_date=min_date)

            # 创建一次性预约/取消
            reservation = OneTimeReservation(
                user_id=current_user.id,
                room_id=room_id,
                reservation_date=reservation_date,
                start_time=start_time,
                end_time=end_time,
                is_cancellation=is_cancellation,
                status='pending'
            )

            db.session.add(reservation)
            db.session.commit()

            action = "取消" if is_cancellation else "预约"
            flash(f'一次性{action}创建成功！将在21:30处理。', 'success')
            return redirect(url_for('reservation.one_time_list'))

        except Exception as e:
            db.session.rollback()
            flash(f'创建一次性预约时出错：{str(e)}', 'danger')

    return render_template('reservation/one_time_create.html', rooms=rooms, min_date=min_date)


@reservation_bp.route('/one-time/<int:id>/delete', methods=['POST'])
@login_required
def one_time_delete(id):
    """删除一次性预约"""
    reservation = OneTimeReservation.query.get_or_404(id)

    # 确保用户拥有此预约
    if reservation.user_id != current_user.id:
        flash('您没有权限删除此预约。', 'danger')
        return redirect(url_for('reservation.one_time_list'))

    # 确保预约仍在待处理状态
    if reservation.status != 'pending':
        flash('只能删除待处理的预约。', 'danger')
        return redirect(url_for('reservation.one_time_list'))

    try:
        db.session.delete(reservation)
        db.session.commit()
        flash('一次性预约删除成功！', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除预约时出错：{str(e)}', 'danger')

    return redirect(url_for('reservation.one_time_list'))


@reservation_bp.route('/history')
@login_required
def history():
    """查看预约历史"""
    # 获取筛选参数
    status = request.args.get('status', 'all')
    date_from = request.args.get('date_from', (date.today() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_to = request.args.get('date_to', date.today().strftime('%Y-%m-%d'))

    # 构建查询
    query = ReservationHistory.query.filter_by(user_id=current_user.id)

    if status != 'all':
        query = query.filter_by(status=status)

    if date_from:
        query = query.filter(ReservationHistory.reservation_date >= datetime.strptime(date_from, '%Y-%m-%d').date())

    if date_to:
        query = query.filter(ReservationHistory.reservation_date <= datetime.strptime(date_to, '%Y-%m-%d').date())

    # 按日期和时间排序
    history_items = query.order_by(
        ReservationHistory.reservation_date.desc(),
        ReservationHistory.start_time
    ).all()

    return render_template('reservation/history.html',
                           history_items=history_items,
                           status=status,
                           date_from=date_from,
                           date_to=date_to)


@reservation_bp.route('/check-availability', methods=['GET'])
@login_required
def check_availability():
    """API endpoint to check room availability"""
    room_id = request.args.get('room_id')
    date_str = request.args.get('date')

    if not room_id or not date_str:
        return jsonify({'error': 'Missing required parameters'}), 400

    try:
        # Get the room
        room = Room.query.get_or_404(room_id)

        # Connect to CCOM
        client = CCOMClient(current_user.username, current_user.get_ccom_password(), current_user.ccom_token)
        if not client.soft_login():
            return jsonify({'error': 'Failed to connect to CCOM. Please check your credentials.'}), 401

        # Update token if needed
        if client.token != current_user.ccom_token:
            current_user.ccom_token = client.token
            db.session.commit()

        # Get availability
        availability = client.find_room_availability(room_id)

        return jsonify(availability)

    except Exception as e:
        current_app.logger.error(f"Error checking availability: {str(e)}")
        return jsonify({'error': str(e)}), 500


@reservation_bp.route('/rooms')
@login_required
def room_list():
    """查看所有琴房"""
    rooms = Room.query.order_by(Room.partition, Room.name).all()

    # 按分区分组琴房
    partitions = {}
    for room in rooms:
        if room.partition not in partitions:
            partitions[room.partition] = []
        partitions[room.partition].append(room)

    return render_template('reservation/room_list.html', partitions=partitions)