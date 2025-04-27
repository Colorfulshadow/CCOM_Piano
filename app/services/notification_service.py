"""
@Author: Tianyi Zhang
@Date: 2025/4/26
@Description: Notification service for reservation system
"""
import requests
from flask import current_app
from app.models.user import User
from app import db
from datetime import datetime, timedelta


class NotificationService:
    @staticmethod
    def send_notification(user_id, title, message, icon=None, group=None):
        """
        Send a push notification to a user

        Args:
            user_id: User ID
            title: Notification title
            message: Notification message
            icon: Icon URL (optional)
            group: Notification group (optional)

        Returns:
            bool: True if successful, False otherwise
        """
        if not current_app.config.get('NOTIFICATION_ENABLED', False):
            current_app.logger.info("Notifications are disabled")
            return False

        user = User.query.get(user_id)
        if not user or not user.push_notification_key:
            current_app.logger.warning(f"Cannot send notification: User {user_id} has no notification key")
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
                current_app.logger.info(f"Notification sent to user {user.username}")
                return True
            else:
                current_app.logger.error(f"Failed to send notification. Status code: {response.status_code}")
                return False

        except Exception as e:
            current_app.logger.error(f"Error sending notification: {str(e)}")
            return False

    @staticmethod
    def send_reservation_success(user_id, room_name, date, start_time, end_time):
        """Send notification about successful reservation"""
        formatted_time = f"{start_time[:2]}:{start_time[2:]} - {end_time[:2]}:{end_time[2:]}"
        message = f"{room_name} has been reserved for {date} at {formatted_time}"

        return NotificationService.send_notification(
            user_id=user_id,
            title="Piano Room Reservation Successful",
            message=message,
            icon="https://api.zty.ink/api/v2/objects/icon/se2ezd5tzxgsubc0rx.png",
            group="CCOM Piano Reservation"
        )

    @staticmethod
    def send_reservation_failure(user_id, room_name, date, start_time, end_time, reason):
        """Send notification about failed reservation"""
        formatted_time = f"{start_time[:2]}:{start_time[2:]} - {end_time[:2]}:{end_time[2:]}"
        message = f"Failed to reserve {room_name} for {date} at {formatted_time}. Reason: {reason}"

        return NotificationService.send_notification(
            user_id=user_id,
            title="Piano Room Reservation Failed",
            message=message,
            icon="https://api.zty.ink/api/v2/objects/icon/fi9tl1ylkeyi8yoirb.png",
            group="CCOM Piano Reservation"
        )

    @staticmethod
    def send_bulk_reservation_results(results):
        """
        Send notifications for bulk reservation results

        Args:
            results: Results from ReservationService.execute_reservations()

        Returns:
            int: Number of notifications sent
        """
        from app.models.reservation import ReservationHistory

        # Get all histories created in the last 5 minutes
        five_min_ago = datetime.now() - timedelta(minutes=5)
        histories = ReservationHistory.query.filter(
            ReservationHistory.created_at >= five_min_ago
        ).all()

        notifications_sent = 0

        for history in histories:
            if not history.user_id or not history.room_id:
                continue

            room_name = history.room.name if history.room else "Unknown Room"
            date_str = history.reservation_date.strftime('%Y-%m-%d') if history.reservation_date else "Unknown Date"

            if history.status == 'successful':
                sent = NotificationService.send_reservation_success(
                    user_id=history.user_id,
                    room_name=room_name,
                    date=date_str,
                    start_time=history.start_time,
                    end_time=history.end_time
                )
            else:
                sent = NotificationService.send_reservation_failure(
                    user_id=history.user_id,
                    room_name=room_name,
                    date=date_str,
                    start_time=history.start_time,
                    end_time=history.end_time,
                    reason=history.message or "Unknown error"
                )

            if sent:
                notifications_sent += 1

        return notifications_sent