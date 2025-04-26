"""
@Author: Tianyi Zhang
@Date: 2025/4/26
@Description: 
"""
import requests
from flask import current_app
from app.models.user import User
from app import db


class NotificationService:
    @staticmethod
    def send_notification(user_id, title, message, icon=None, group=None):
        """
        向用户发送推送通知

        参数:
            user_id: 用户ID
            title: 通知标题
            message: 通知消息
            icon: 图标URL（可选）
            group: 通知分组（可选）

        返回:
            bool: 成功返回True，否则返回False
        """
        if not current_app.config.get('NOTIFICATION_ENABLED'):
            current_app.logger.info("通知功能已禁用")
            return False

        user = User.query.get(user_id)
        if not user or not user.push_notification_key:
            current_app.logger.warning(f"无法发送通知：用户 {user_id} 没有通知密钥")
            return False

        try:
            server_url = f"https://notice.zty.ink/{user.push_notification_key}"

            payload = {
                'title': title,
                'body': message
            }

            if icon:
                payload['icon'] = icon
            if group:
                payload['group'] = group

            response = requests.post(server_url, data=payload)

            if response.status_code == 200:
                current_app.logger.info(f"已向用户 {user.username} 发送通知")
                return True
            else:
                current_app.logger.error(f"发送通知失败。状态码：{response.status_code}")
                return False

        except Exception as e:
            current_app.logger.error(f"发送通知时出错：{str(e)}")
            return False

    @staticmethod
    def send_reservation_success(user_id, room_name, date, start_time, end_time):
        """发送关于预约成功的通知"""
        formatted_time = f"{start_time[:2]}:{start_time[2:]} - {end_time[:2]}:{end_time[2:]}"
        message = f"{room_name} 已预约，日期：{date} 时间：{formatted_time}"

        return NotificationService.send_notification(
            user_id=user_id,
            title="钢琴琴房预约成功",
            message=message,
            icon="https://api.zty.ink/api/v2/objects/icon/se2ezd5tzxgsubc0rx.png",
            group="CCOM 钢琴预约"
        )

    @staticmethod
    def send_reservation_failure(user_id, room_name, date, start_time, end_time, reason):
        """发送关于预约失败的通知"""
        formatted_time = f"{start_time[:2]}:{start_time[2:]} - {end_time[:2]}:{end_time[2:]}"
        message = f"预约失败：{room_name}，日期：{date} 时间：{formatted_time}。原因：{reason}"

        return NotificationService.send_notification(
            user_id=user_id,
            title="钢琴琴房预约失败",
            message=message,
            icon="https://api.zty.ink/api/v2/objects/icon/fi9tl1ylkeyi8yoirb.png",
            group="CCOM 钢琴预约"
        )

    @staticmethod
    def send_bulk_reservation_results(results):
        """
        发送批量预约结果的通知

        参数:
            results: 来自ReservationService.execute_reservations()的结果

        返回:
            int: 发送的通知数量
        """
        from app.models.reservation import ReservationHistory

        # 获取最近5分钟内创建的所有历史记录
        histories = ReservationHistory.query.filter(
            ReservationHistory.created_at >= db.func.now() - db.func.interval('5 minutes')
        ).all()

        notifications_sent = 0

        for history in histories:
            if history.status == 'successful':
                room_name = history.room.name if history.room else "未知琴房"
                sent = NotificationService.send_reservation_success(
                    user_id=history.user_id,
                    room_name=room_name,
                    date=history.reservation_date.strftime('%Y-%m-%d'),
                    start_time=history.start_time,
                    end_time=history.end_time
                )
            else:
                room_name = history.room.name if history.room else "未知琴房"
                sent = NotificationService.send_reservation_failure(
                    user_id=history.user_id,
                    room_name=room_name,
                    date=history.reservation_date.strftime('%Y-%m-%d'),
                    start_time=history.start_time,
                    end_time=history.end_time,
                    reason=history.message
                )

            if sent:
                notifications_sent += 1

        return notifications_sent