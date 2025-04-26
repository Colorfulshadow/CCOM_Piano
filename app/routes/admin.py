"""
@Author: Tianyi Zhang
@Date: 2025/4/26
@Description: 
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.room import Room
from app.models.reservation import RecurringReservation, OneTimeReservation, ReservationHistory
from app.services.reservation_service import ReservationService
from app.utils.time_utils import ServerTimeHelper
from app.services.notification_service import NotificationService
from datetime import datetime, timedelta, date
from functools import wraps
import os
import csv

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# 管理员访问装饰器
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('您需要管理员权限才能访问此页面。', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)

    return decorated_function


@admin_bp.route('/')
@login_required
@admin_required
def index():
    """管理员控制面板"""
    # 获取系统统计数据
    stats = {
        'user_count': User.query.count(),
        'room_count': Room.query.count(),
        'recurring_count': RecurringReservation.query.count(),
        'one_time_count': OneTimeReservation.query.count(),
        'history_count': ReservationHistory.query.count(),
        'success_count': ReservationHistory.query.filter_by(status='successful').count(),
        'failure_count': ReservationHistory.query.filter_by(status='failed').count()
    }

    # 获取最近历史记录
    recent_history = ReservationHistory.query.order_by(
        ReservationHistory.created_at.desc()
    ).limit(10).all()

    # 获取下一次计划预约时间
    server_time = ServerTimeHelper().get_server_time()

    return render_template('admin/index.html', stats=stats, recent_history=recent_history, server_time=server_time)


@admin_bp.route('/users')
@login_required
@admin_required
def users():
    """管理用户"""
    users_list = User.query.order_by(User.username).all()
    return render_template('admin/users.html', users=users_list)


@admin_bp.route('/users/<int:id>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def toggle_admin(id):
    """切换用户的管理员状态"""
    user = User.query.get_or_404(id)

    # 防止自我降级
    if user.id == current_user.id:
        flash('您不能更改自己的管理员状态。', 'danger')
        return redirect(url_for('admin.users'))

    user.is_admin = not user.is_admin
    db.session.commit()

    action = '授予' if user.is_admin else '撤销'
    flash(f'已{action} {user.username} 的管理员权限。', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def toggle_active(id):
    """切换用户的活跃状态"""
    user = User.query.get_or_404(id)

    # 防止自我停用
    if user.id == current_user.id:
        flash('您不能停用自己的账户。', 'danger')
        return redirect(url_for('admin.users'))

    user.is_active = not user.is_active
    db.session.commit()

    status = '激活' if user.is_active else '停用'
    flash(f'用户 {user.username} 已被{status}。', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/rooms')
@login_required
@admin_required
def rooms():
    """管理琴房"""
    rooms_list = Room.query.order_by(Room.partition, Room.name).all()
    return render_template('admin/rooms.html', rooms=rooms_list)


@admin_bp.route('/rooms/import', methods=['GET', 'POST'])
@login_required
@admin_required
def import_rooms():
    """从CSV导入琴房"""
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('没有文件部分', 'danger')
            return redirect(request.url)

        file = request.files['csv_file']

        if file.filename == '':
            flash('未选择文件', 'danger')
            return redirect(request.url)

        if file:
            try:
                # 临时保存文件
                file_path = os.path.join(current_app.instance_path, 'uploads')
                os.makedirs(file_path, exist_ok=True)

                temp_file = os.path.join(file_path, 'devices_data.csv')
                file.save(temp_file)

                # 导入琴房
                success = Room.import_from_csv(temp_file)

                if success:
                    flash('琴房导入成功！', 'success')
                else:
                    flash('琴房导入失败。查看日志了解详情。', 'danger')

                # 清理
                os.remove(temp_file)

            except Exception as e:
                flash(f'导入琴房时出错：{str(e)}', 'danger')

        return redirect(url_for('admin.rooms'))

    return render_template('admin/import_rooms.html')


@admin_bp.route('/history')
@login_required
@admin_required
def history():
    """查看所有预约历史"""
    # 获取筛选参数
    user_id = request.args.get('user_id')
    status = request.args.get('status')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    # 构建查询
    query = ReservationHistory.query

    if user_id:
        query = query.filter_by(user_id=user_id)

    if status:
        query = query.filter_by(status=status)

    if date_from:
        query = query.filter(ReservationHistory.reservation_date >= datetime.strptime(date_from, '%Y-%m-%d').date())

    if date_to:
        query = query.filter(ReservationHistory.reservation_date <= datetime.strptime(date_to, '%Y-%m-%d').date())

    # 使用分页获取历史条目
    page = request.args.get('page', 1, type=int)
    per_page = 20

    pagination = query.order_by(
        ReservationHistory.created_at.desc()
    ).paginate(page=page, per_page=per_page)

    history_items = pagination.items

    # 获取下拉菜单的所有用户
    users = User.query.order_by(User.username).all()

    return render_template('admin/history.html',
                           history_items=history_items,
                           pagination=pagination,
                           users=users,
                           filters={
                               'user_id': user_id,
                               'status': status,
                               'date_from': date_from,
                               'date_to': date_to
                           })


@admin_bp.route('/system')
@login_required
@admin_required
def system():
    """系统设置和操作"""
    return render_template('admin/system.html')


@admin_bp.route('/system/test-reservation', methods=['POST'])
@login_required
@admin_required
def test_reservation():
    """测试运行预约处理"""
    try:
        # 执行预约
        results = ReservationService.execute_reservations()

        # 如果请求发送通知
        if 'send_notifications' in request.form:
            notification_count = NotificationService.send_bulk_reservation_results(results)
            results['notifications_sent'] = notification_count

        flash('预约处理成功执行！', 'success')
        return render_template('admin/reservation_results.html', results=results)

    except Exception as e:
        flash(f'执行预约处理时出错：{str(e)}', 'danger')
        return redirect(url_for('admin.system'))


@admin_bp.route('/system/server-time')
@login_required
@admin_required
def server_time():
    """检查服务器时间和延迟"""
    try:
        server_helper = ServerTimeHelper()
        server_time = server_helper.get_server_time()
        latency = server_helper.measure_latency()

        # 计算下一次预约时间
        next_reservation_time = server_helper.calculate_send_time(
            current_app.config['RESERVATION_OPEN_TIME'],
            add_day=server_time.hour >= 22  # 如果已经过了晚上10点，则加一天
        )

        return jsonify({
            'server_time': server_time.strftime('%Y-%m-%d %H:%M:%S %Z'),
            'local_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'latency_ms': latency,
            'next_reservation_time': next_reservation_time.strftime('%Y-%m-%d %H:%M:%S %Z')
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500