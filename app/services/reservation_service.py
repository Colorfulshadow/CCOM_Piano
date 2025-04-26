"""
@Author: Tianyi Zhang
@Date: 2025/4/26
@Description: 
"""
from datetime import datetime, timedelta, date
from flask import current_app
from app import db
from app.models.user import User
from app.models.room import Room
from app.models.reservation import RecurringReservation, OneTimeReservation, ReservationHistory
from app.services.ccom_client import CCOMClient
from app.utils.time_utils import split_time, get_current_time, get_day_of_week, ServerTimeHelper
from app.utils.exceptions import ReservationLimitExceeded, DurationLimitExceeded
import pytz


class ReservationService:
    @staticmethod
    def get_user_daily_reservations(user_id, target_date=None):
        """Get user reservations for a specific date"""
        if target_date is None:
            target_date = date.today() + timedelta(days=1)  # Default to tomorrow

        return ReservationHistory.query.filter_by(
            user_id=user_id,
            reservation_date=target_date,
            status='successful'
        ).all()

    @staticmethod
    def check_reservation_limits(user_id, target_date, start_time, end_time):
        """
        Check if a new reservation exceeds the user's daily limits

        Args:
            user_id: User ID
            target_date: Target date
            start_time: Start time (format: "1400")
            end_time: End time (format: "1600")

        Returns:
            bool: True if within limits, raises exception otherwise
        """
        from app.utils.time_utils import calculate_duration_hours

        # Check duration limit
        duration = calculate_duration_hours(start_time, end_time)
        if duration > current_app.config['MAX_RESERVATION_HOURS']:
            raise DurationLimitExceeded(
                f"Reservation exceeds maximum duration of {current_app.config['MAX_RESERVATION_HOURS']} hours")

        # Check daily reservation count limit
        existing_reservations = ReservationService.get_user_daily_reservations(user_id, target_date)
        if len(existing_reservations) >= current_app.config['MAX_DAILY_RESERVATIONS']:
            raise ReservationLimitExceeded(
                f"You already have {len(existing_reservations)} reservations on {target_date}")

        return True

    @staticmethod
    def process_recurring_reservations(target_date=None):
        """
        Process all recurring reservations for the given date

        Args:
            target_date: Target date (default: tomorrow)

        Returns:
            dict: Processing results
        """
        if target_date is None:
            target_date = date.today() + timedelta(days=1)

        day_of_week = get_day_of_week(target_date)

        # Get all active recurring reservations for this day of week
        recurring_reservations = RecurringReservation.query.filter_by(
            day_of_week=day_of_week,
            is_active=True
        ).all()

        results = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }

        for reservation in recurring_reservations:
            try:
                # Skip if user already has MAX_DAILY_RESERVATIONS successful reservations
                existing_reservations = ReservationService.get_user_daily_reservations(
                    reservation.user_id, target_date
                )
                if len(existing_reservations) >= current_app.config['MAX_DAILY_RESERVATIONS']:
                    results['skipped'] += 1
                    continue

                # Process the reservation
                user = User.query.get(reservation.user_id)
                client = CCOMClient(user.username, user.get_ccom_password(), user.ccom_token)

                # Ensure we're logged in
                if not client.soft_login():
                    results['failed'] += 1
                    results['errors'].append(f"Failed to login for user {user.username}")
                    continue

                # Update user token
                user.ccom_token = client.token
                db.session.commit()
                target_datetime = datetime.combine(target_date, datetime.min.time())

                # Now, you can safely call timestamp() on the datetime object
                start_timestamp = int(target_datetime.timestamp() * 1000)  # Convert to milliseconds

                # Add the hours and minutes from start_time
                start_timestamp += int(reservation.start_time[:2]) * 3600 * 1000  # Add hours (in milliseconds)
                start_timestamp += int(reservation.start_time[2:]) * 60 * 1000  # Add minutes (in milliseconds)

                # Similarly for end_time
                end_timestamp = int(target_datetime.timestamp() * 1000)  # Convert to milliseconds
                end_timestamp += int(reservation.end_time[:2]) * 3600 * 1000  # Add hours (in milliseconds)
                end_timestamp += int(reservation.end_time[2:]) * 60 * 1000  # Add minutes (in milliseconds)

                # Get room CCOM ID
                room = Room.query.get(reservation.room_id)

                # Make the reservation
                response = client.reserve_room(room.ccom_id, start_timestamp, end_timestamp)

                # Record results
                results['processed'] += 1

                if response.get('status') == 200 and response.get('msg') == '成功':
                    results['successful'] += 1
                    status = 'successful'
                    message = 'Reservation successful'
                else:
                    results['failed'] += 1
                    status = 'failed'
                    message = response.get('msg', 'Unknown error')

                # Save to history
                history = ReservationHistory(
                    user_id=reservation.user_id,
                    room_id=reservation.room_id,
                    reservation_date=target_date,
                    start_time=reservation.start_time,
                    end_time=reservation.end_time,
                    status=status,
                    message=message,
                    source_type='recurring',
                    source_id=reservation.id
                )
                db.session.add(history)
                db.session.commit()

            except Exception as e:
                results['failed'] += 1
                results['errors'].append(str(e))
                current_app.logger.error(f"Error processing recurring reservation {reservation.id}: {str(e)}")

        return results

    @staticmethod
    def process_one_time_reservations(target_date=None):
        """
        Process all one-time reservations for the given date

        Args:
            target_date: Target date (default: tomorrow)

        Returns:
            dict: Processing results
        """
        if target_date is None:
            target_date = date.today() + timedelta(days=1)

        # Get all pending one-time reservations for this date
        one_time_reservations = OneTimeReservation.query.filter_by(
            reservation_date=target_date,
            status='pending'
        ).all()

        results = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'errors': []
        }

        for reservation in one_time_reservations:
            try:
                user = User.query.get(reservation.user_id)
                client = CCOMClient(user.username, user.get_ccom_password(), user.ccom_token)

                # Ensure we're logged in
                if not client.soft_login():
                    reservation.status = 'failed'
                    db.session.commit()

                    results['failed'] += 1
                    results['errors'].append(f"Failed to login for user {user.username}")
                    continue

                # Update user token
                user.ccom_token = client.token
                db.session.commit()

                # Calculate timestamps
                start_timestamp = int(target_date.strftime('%s')) * 1000  # Convert to milliseconds
                start_timestamp += int(reservation.start_time[:2]) * 3600 * 1000  # Add hours
                start_timestamp += int(reservation.start_time[2:]) * 60 * 1000  # Add minutes

                end_timestamp = int(target_date.strftime('%s')) * 1000  # Convert to milliseconds
                end_timestamp += int(reservation.end_time[:2]) * 3600 * 1000  # Add hours
                end_timestamp += int(reservation.end_time[2:]) * 60 * 1000  # Add minutes

                # Get room CCOM ID
                room = Room.query.get(reservation.room_id)

                # Make reservation or cancellation
                if reservation.is_cancellation:
                    # First, get the user's current reservations
                    orders = client.get_order_list()
                    order_id = None

                    if orders.get('status') == 200:
                        for order in orders.get('data', []):
                            # Check if this order matches our reservation
                            order_date = datetime.fromtimestamp(
                                order['startTime'] / 1000,
                                pytz.timezone('Asia/Shanghai')
                            ).date()

                            if (order_date == target_date and
                                    str(order['device']) == str(room.ccom_id)):
                                order_id = order['id']
                                break

                    if order_id:
                        response = client.cancel_reservation(order_id)
                    else:
                        response = {'status': 400, 'msg': 'No matching reservation found to cancel'}
                else:
                    # Regular reservation
                    response = client.reserve_room(room.ccom_id, start_timestamp, end_timestamp)

                # Record results
                results['processed'] += 1

                if response.get('status') == 200 and response.get('msg') == '成功':
                    reservation.status = 'successful'
                    results['successful'] += 1
                    status = 'successful'
                    message = 'Successfully ' + ('cancelled' if reservation.is_cancellation else 'reserved')
                else:
                    reservation.status = 'failed'
                    results['failed'] += 1
                    status = 'failed'
                    message = response.get('msg', 'Unknown error')

                db.session.commit()

                # Save to history
                history = ReservationHistory(
                    user_id=reservation.user_id,
                    room_id=reservation.room_id,
                    reservation_date=target_date,
                    start_time=reservation.start_time,
                    end_time=reservation.end_time,
                    status=status,
                    message=message,
                    source_type='one_time',
                    source_id=reservation.id
                )
                db.session.add(history)
                db.session.commit()

            except Exception as e:
                reservation.status = 'failed'
                db.session.commit()

                results['failed'] += 1
                results['errors'].append(str(e))
                current_app.logger.error(f"Error processing one-time reservation {reservation.id}: {str(e)}")

        return results

    @staticmethod
    def perform_pre_login():
        """
        Perform soft login for all users with pending reservations for tomorrow
        to refresh their tokens before the actual reservation process

        Returns:
            dict: Pre-login results
        """
        target_date = date.today() + timedelta(days=1)
        day_of_week = get_day_of_week(target_date)

        # Get all users with active recurring reservations for tomorrow
        recurring_users = db.session.query(User).join(RecurringReservation).filter(
            RecurringReservation.day_of_week == day_of_week,
            RecurringReservation.is_active == True
        ).distinct().all()

        # Get all users with pending one-time reservations for tomorrow
        one_time_users = db.session.query(User).join(OneTimeReservation).filter(
            OneTimeReservation.reservation_date == target_date,
            OneTimeReservation.status == 'pending'
        ).distinct().all()

        # Combine the two lists, removing duplicates
        users = set(recurring_users + one_time_users)

        results = {
            'total_users': len(users),
            'successful': 0,
            'failed': 0,
            'errors': []
        }

        for user in users:
            try:
                client = CCOMClient(user.username, user.get_ccom_password(), user.ccom_token)

                if client.soft_login():
                    # Update the token in the database
                    user.ccom_token = client.token
                    db.session.commit()
                    results['successful'] += 1
                    current_app.logger.info(f"Pre-login successful for user {user.username}")
                else:
                    results['failed'] += 1
                    results['errors'].append(f"Pre-login failed for user {user.username}")
                    current_app.logger.error(f"Pre-login failed for user {user.username}")
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"Error during pre-login for user {user.username}: {str(e)}")
                current_app.logger.error(f"Error during pre-login for user {user.username}: {str(e)}")

        return results

    @staticmethod
    def execute_reservations():
        """
        Execute all pending reservations for tomorrow

        Returns:
            dict: Combined processing results
        """
        target_date = date.today() + timedelta(days=1)

        # First process recurring reservations
        recurring_results = ReservationService.process_recurring_reservations(target_date)

        # Then process one-time reservations
        one_time_results = ReservationService.process_one_time_reservations(target_date)

        # Combine results
        combined_results = {
            'target_date': target_date,
            'recurring': recurring_results,
            'one_time': one_time_results,
            'total_processed': recurring_results['processed'] + one_time_results['processed'],
            'total_successful': recurring_results['successful'] + one_time_results['successful'],
            'total_failed': recurring_results['failed'] + one_time_results['failed'],
            'errors': recurring_results['errors'] + one_time_results['errors']
        }

        return combined_results