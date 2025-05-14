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
        Send a push notification to a user, handling multiple notification keys with improved logging

        Args:
            user_id: User ID
            title: Notification title
            message: Notification message
            icon: Icon URL (optional)
            group: Notification group (optional)

        Returns:
            bool: True if at least one notification was sent successfully
        """
        # Check if notifications are enabled
        if not current_app.config.get('NOTIFICATION_ENABLED', False):
            current_app.logger.info("Notifications are disabled in configuration")
            return False

        # Get the user
        user = User.query.get(user_id)
        if not user:
            current_app.logger.warning(f"Cannot send notification: User ID {user_id} not found")
            return False

        if not user.push_notification_key:
            current_app.logger.warning(f"Cannot send notification: User {user.username} has no notification key")
            return False

        # Support for multiple notification keys (comma-separated)
        notification_keys = [key.strip() for key in user.push_notification_key.split(',') if key.strip()]

        if not notification_keys:
            current_app.logger.warning(f"User {user.username} has empty notification key(s)")
            return False

        current_app.logger.info(f"Sending notification to user {user.username} with {len(notification_keys)} keys")

        # Log the notification content (without sensitive data)
        current_app.logger.info(f"Notification title: {title}")
        current_app.logger.info(f"Notification message: {message}")

        success = False
        for i, key in enumerate(notification_keys):
            try:
                # Mask the key for logging purposes
                masked_key = key[:5] + '...' if len(key) > 5 else '***'
                current_app.logger.info(f"Sending to key #{i + 1}: {masked_key}")

                server_url = f"https://notice.zty.ink/{key}"

                payload = {
                    'title': title,
                    'body': message
                }

                if icon:
                    payload['icon'] = icon
                if group:
                    payload['group'] = group

                # Send the notification with a timeout
                response = requests.post(server_url, data=payload, timeout=10)

                # Log the response
                current_app.logger.info(f"Response for key #{i + 1}: Status {response.status_code}")

                if response.status_code == 200:
                    success = True
                    current_app.logger.info(f"Successfully sent notification to key #{i + 1}")
                else:
                    current_app.logger.warning(
                        f"Failed to send notification to key #{i + 1}. Status: {response.status_code}")
                    try:
                        current_app.logger.warning(f"Error response: {response.text[:100]}")
                    except:
                        pass

            except requests.exceptions.Timeout:
                current_app.logger.error(f"Timeout sending notification to key #{i + 1}")
            except requests.exceptions.ConnectionError:
                current_app.logger.error(f"Connection error sending notification to key #{i + 1}")
            except Exception as e:
                current_app.logger.error(f"Error sending notification to key #{i + 1}: {str(e)}")

        return success

    @staticmethod
    def send_reservation_success(user_id, room_name, date, start_time, end_time):
        """Send notification about successful reservation"""
        formatted_time = f"{start_time[:2]}:{start_time[2:]} - {end_time[:2]}:{end_time[2:]}"
        message = f"恭喜！已成功预订于 {date} {formatted_time}的{room_name}。请按时前往"

        return NotificationService.send_notification(
            user_id=user_id,
            title="琴房预约成功",
            message=message,
            icon="https://api.zty.ink/api/v2/objects/icon/se2ezd5tzxgsubc0rx.png",
            group="CCOM Piano Reservation"
        )

    @staticmethod
    def send_reservation_failure(user_id, room_name, date, start_time, end_time, reason):
        """Send notification about failed reservation"""
        formatted_time = f"{start_time[:2]}:{start_time[2:]} - {end_time[:2]}:{end_time[2:]}"
        message = f"很抱歉，预定的于 {date} {formatted_time} 的 {room_name}  失败。原因：{reason}"

        return NotificationService.send_notification(
            user_id=user_id,
            title="琴房预约失败",
            message=message,
            icon="https://api.zty.ink/api/v2/objects/icon/fi9tl1ylkeyi8yoirb.png",
            group="CCOM琴房预约"
        )

    @staticmethod
    def send_bulk_reservation_results(results):
        """
        Send notifications for bulk reservation results with direct history query

        Args:
            results: Results from ReservationService.execute_reservations()

        Returns:
            int: Number of notifications sent
        """
        # Import needed models
        from app.models.reservation import ReservationHistory
        from app.models.user import User
        from app.models.room import Room

        current_app.logger.info("Beginning to send bulk reservation notifications")

        # Use a much wider time window - last 60 minutes to be safe
        sixty_min_ago = datetime.now() - timedelta(minutes=60)

        # Log the query time range
        current_app.logger.info(f"Looking for history entries created after: {sixty_min_ago}")

        # Get recent history entries
        histories = ReservationHistory.query.filter(
            ReservationHistory.created_at >= sixty_min_ago
        ).all()

        current_app.logger.info(f"Found {len(histories)} recent history entries for notification")

        # If no histories found, try to get the most recent ones regardless of time
        if not histories:
            current_app.logger.info("No recent history entries found, trying to get most recent ones")
            histories = ReservationHistory.query.order_by(
                ReservationHistory.created_at.desc()
            ).limit(20).all()
            current_app.logger.info(f"Found {len(histories)} history entries from broader search")

        # Create a unique set of histories to avoid duplicate notifications
        notification_entries = {}  # key: (user_id, room_id, date, start_time) -> latest history entry

        for history in histories:
            if not history.user_id or not history.room_id or not history.reservation_date:
                continue

            # Log each history entry we found
            current_app.logger.info(f"Processing history entry: ID={history.id}, "
                                    f"User={history.user_id}, Room={history.room_id}, "
                                    f"Date={history.reservation_date}, Status={history.status}, "
                                    f"Created={history.created_at}")

            # Create a unique key for this reservation
            key = (history.user_id, history.room_id,
                   history.reservation_date.isoformat(),
                   history.start_time)

            # If we already have an entry for this key, only replace it if this one is newer
            if key in notification_entries:
                if history.created_at > notification_entries[key].created_at:
                    notification_entries[key] = history
            else:
                notification_entries[key] = history

        current_app.logger.info(f"Found {len(notification_entries)} unique reservations for notification")

        # Now send notifications for each unique reservation
        notifications_sent = 0

        for history in notification_entries.values():
            # Explicitly load related objects to avoid lazy loading issues
            try:
                # Make sure we have the room and user objects
                room = Room.query.get(history.room_id)
                user = User.query.get(history.user_id)

                if not room or not user:
                    current_app.logger.warning(f"Missing room or user for history {history.id}")
                    continue

                room_name = room.name
                date_str = history.reservation_date.strftime('%Y-%m-%d')

                # Log before attempting to send
                current_app.logger.info(
                    f"Sending notification for {date_str} {room_name} to user {user.username}, status={history.status}")

                # Check if user has notification keys
                if not user.push_notification_key:
                    current_app.logger.info(f"User {user.username} has no notification keys, skipping")
                    continue

                # Determine notification type by status
                if history.status == 'successful':
                    sent = NotificationService.send_reservation_success(
                        user_id=history.user_id,
                        room_name=room_name,
                        date=date_str,
                        start_time=history.start_time,
                        end_time=history.end_time
                    )
                else:
                    # Skip notification for "duplicate request" failures
                    if history.message and "重复请求" in history.message:
                        current_app.logger.info(f"Skipping notification for duplicate request: {history.id}")
                        continue

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
                    current_app.logger.info(f"Successfully sent notification for history {history.id}")
                else:
                    current_app.logger.warning(f"Failed to send notification for history {history.id}")

            except Exception as e:
                current_app.logger.error(f"Error sending notification for history {history.id}: {str(e)}")
                import traceback
                current_app.logger.error(traceback.format_exc())

        current_app.logger.info(f"Finished sending notifications. Total sent: {notifications_sent}")
        return notifications_sent