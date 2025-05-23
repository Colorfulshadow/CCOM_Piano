"""
@Author: Tianyi Zhang
@Date: 2025/4/26
@Description: Fixed reservation processing implementation with correct history record creation
"""
from datetime import datetime, timedelta, date
from flask import current_app
from sqlalchemy.orm import scoped_session
from app import db
from app.models.user import User
from app.models.room import Room
from app.models.reservation import RecurringReservation, OneTimeReservation, ReservationHistory
from app.services.ccom_client import CCOMClient
from app.utils.time_utils import get_current_time, get_day_of_week, ServerTimeHelper, convert_to_timestamp
from app.utils.exceptions import ReservationLimitExceeded, DurationLimitExceeded
import pytz
from concurrent.futures import ThreadPoolExecutor, as_completed
import concurrent.futures
import threading
import time

from app.services.notification_service import NotificationService


# Thread-local storage for database session management
thread_local = threading.local()

class ReservationService:
    @staticmethod
    def get_db_session():
        """Get a thread-local database session"""
        if not hasattr(thread_local, "session"):
            # Create a new scoped session using SQLAlchemy's Session factory
            thread_local.session = scoped_session(db.session.registry)
        return thread_local.session

    @staticmethod
    def close_db_session():
        """Close the thread-local database session properly"""
        if hasattr(thread_local, "session"):
            thread_local.session.remove()
            delattr(thread_local, "session")

    @staticmethod
    def get_user_daily_reservations(user_id, target_date=None):
        """Get user reservations for a specific date - Use the main session for this"""
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
    def split_reservation_time(target_date, start_time, end_time, max_hours=3):
        """
        Split a reservation time range into segments of maximum 3 hours each

        Args:
            target_date: Date for the reservation
            start_time: Start time string (format: "1400")
            end_time: End time string (format: "1600")
            max_hours: Maximum hours per segment (default: 3)

        Returns:
            list: List of (start_timestamp, end_timestamp) tuples
        """
        # Convert time strings to datetime objects
        start_hour, start_minute = int(start_time[:2]), int(start_time[2:])
        end_hour, end_minute = int(end_time[:2]), int(end_time[2:])

        # Create datetime objects
        start_datetime = datetime.combine(
            target_date,
            datetime.strptime(f"{start_hour:02d}:{start_minute:02d}", "%H:%M").time()
        )

        end_datetime = datetime.combine(
            target_date,
            datetime.strptime(f"{end_hour:02d}:{end_minute:02d}", "%H:%M").time()
        )

        # Handle case where end time is on the next day
        if end_datetime <= start_datetime:
            end_datetime += timedelta(days=1)

        # Split into segments of max_hours
        segments = []
        current_start = start_datetime

        while current_start < end_datetime:
            # Calculate segment end (either max_hours from start or end time, whichever is sooner)
            segment_end = min(current_start + timedelta(hours=max_hours), end_datetime)

            # Convert to timestamps (milliseconds since epoch)
            start_timestamp = int(current_start.timestamp() * 1000)
            end_timestamp = int(segment_end.timestamp() * 1000)

            segments.append((start_timestamp, end_timestamp))

            # Move to next segment
            current_start = segment_end

        return segments

    @staticmethod
    def attempt_reservation(client, room_ccom_id, start_timestamp, end_timestamp, max_attempts=5, retry_delay=0.5):
        """
        Attempt to make a reservation, correctly handling all response types

        Args:
            client: CCOMClient instance
            room_ccom_id: Room CCOM ID
            start_timestamp: Start time (millisecond timestamp)
            end_timestamp: End time (millisecond timestamp)
            max_attempts: Maximum number of attempts
            retry_delay: Delay between attempts in seconds

        Returns:
            tuple: (success, error_message)
        """
        for attempt in range(max_attempts):
            try:
                response = client.reserve_room(room_ccom_id, start_timestamp, end_timestamp)

                # Check response message
                msg = response.get('msg', '')
                status = response.get('status', 0)

                # IMPORTANT: Only consider it a success if status is 200 AND msg is "成功"
                if status == 200 and msg == '成功':
                    current_app.logger.info(f"Reservation successful on attempt {attempt + 1}")
                    return True, None

                # Handle specific failure cases

                # "琴房暂未开放" means the piano room is not open yet - this is a failure
                if '琴房暂未开放' in msg:
                    current_app.logger.warning(f"Piano room not open yet on attempt {attempt + 1}")
                    # This is a definite failure, not a retry condition
                    return False, msg

                # Already chosen is considered a success
                if '已选择' in msg:
                    current_app.logger.info(f"Room already reserved successfully")
                    return True, None

                # Exceeded order limit is a definite failure
                if '超出预约订单数量限制' in msg:
                    current_app.logger.warning(f"Reservation failed: Exceeded limit")
                    return False, msg

                # For duplicate request errors, continue trying
                if '重复请求' in msg:
                    if attempt < max_attempts - 1:
                        current_app.logger.info(
                            f"Retrying after duplicate request (attempt {attempt + 1}/{max_attempts})")
                        time.sleep(retry_delay)
                        continue
                    else:
                        # If all attempts result in duplicate requests, it may be already successful
                        # or there's a system issue - mark as failure to be safe
                        return False, "Maximum duplicate requests"

                # For other failures, retry if not the last attempt
                if attempt < max_attempts - 1:
                    current_app.logger.info(f"Retrying reservation (attempt {attempt + 1}/{max_attempts}): {msg}")
                    time.sleep(retry_delay)
                    continue

                # All attempts failed with non-specific errors
                return False, msg

            except Exception as e:
                if attempt < max_attempts - 1:
                    current_app.logger.info(
                        f"Exception during reservation (attempt {attempt + 1}/{max_attempts}): {str(e)}")
                    time.sleep(retry_delay)
                    continue
                return False, str(e)

        return False, "Maximum attempts reached"

    @staticmethod
    def process_single_recurring_reservation(reservation, target_date, results_dict, lock):
        """
        Process a single recurring reservation with improved debugging and direct notifications

        Args:
            reservation: RecurringReservation instance
            target_date: Target date for reservation
            results_dict: Shared dictionary to accumulate results
            lock: Threading lock for safe update of results_dict

        Returns:
            None (updates results_dict in place)
        """
        session = None
        history_id = None  # Track created history ID for debugging

        try:
            # Get thread-local session
            session = ReservationService.get_db_session()

            # Skip if user already has MAX_DAILY_RESERVATIONS successful reservations
            existing_reservations = ReservationService.get_user_daily_reservations(
                reservation.user_id, target_date
            )
            if len(existing_reservations) >= current_app.config['MAX_DAILY_RESERVATIONS']:
                with lock:
                    results_dict['skipped'] += 1
                return

            # Process the reservation
            user = session.query(User).get(reservation.user_id)
            if not user:
                with lock:
                    results_dict['failed'] += 1
                    results_dict['errors'].append(f"User not found: {reservation.user_id}")
                return

            client = CCOMClient(user.username, user.get_ccom_password(), user.ccom_token)

            # Ensure we're logged in
            if not client.soft_login():
                with lock:
                    results_dict['failed'] += 1
                    results_dict['errors'].append(f"Failed to login for user {user.username}")
                return

            # Update user token
            user.ccom_token = client.token
            session.commit()

            # Get room
            room = session.query(Room).get(reservation.room_id)
            if not room:
                with lock:
                    results_dict['failed'] += 1
                    results_dict['errors'].append(f"Room not found: {reservation.room_id}")
                return

            # Split reservation into segments (max 3 hours each)
            time_segments = ReservationService.split_reservation_time(
                target_date,
                reservation.start_time,
                reservation.end_time
            )

            # Process all segments with improved error handling
            all_segments_succeeded = True
            all_errors = []

            for start_timestamp, end_timestamp in time_segments:
                # Try to reserve this segment with multiple attempts
                success, error_msg = ReservationService.attempt_reservation(
                    client, room.ccom_id, start_timestamp, end_timestamp
                )

                if not success:
                    all_segments_succeeded = False
                    # Only add non-None, non-empty error messages
                    if error_msg:
                        all_errors.append(error_msg)

            # Record results
            with lock:
                results_dict['processed'] += 1

                if all_segments_succeeded:
                    results_dict['successful'] += 1
                    status = 'successful'
                    message = 'Reservation successful'
                else:
                    results_dict['failed'] += 1
                    status = 'failed'
                    message = '; '.join(all_errors) if all_errors else "Unknown error"

            # Always create a new history entry for better tracking and to ensure we have a record
            # First, create the new history entry
            new_history = ReservationHistory(
                user_id=reservation.user_id,
                room_id=reservation.room_id,
                reservation_date=target_date,
                start_time=reservation.start_time,
                end_time=reservation.end_time,
                status=status,
                message=message,
                source_type='recurring',
                source_id=reservation.id,
                created_at=datetime.utcnow()  # Explicitly set creation time
            )

            # Add to session and commit immediately
            session.add(new_history)

            try:
                session.flush()  # Flush to get the ID before commit
                history_id = new_history.id
                session.commit()
                current_app.logger.info(f"Successfully created new history entry: ID={history_id}")
            except Exception as commit_error:
                session.rollback()
                current_app.logger.error(f"Error creating history: {str(commit_error)}")
                # Try one more time with a new session
                try:
                    session.close()
                    session = ReservationService.get_db_session()

                    # Create a new history entry with a fresh session
                    history = ReservationHistory(
                        user_id=reservation.user_id,
                        room_id=reservation.room_id,
                        reservation_date=target_date,
                        start_time=reservation.start_time,
                        end_time=reservation.end_time,
                        status=status,
                        message=message,
                        source_type='recurring',
                        source_id=reservation.id,
                        created_at=datetime.utcnow()
                    )
                    session.add(history)
                    session.flush()
                    history_id = history.id
                    session.commit()
                    current_app.logger.info(f"Successfully saved history on second attempt: ID={history_id}")
                except Exception as retry_error:
                    current_app.logger.error(f"Final error saving history: {str(retry_error)}")
                    with lock:
                        results_dict['errors'].append(f"Could not save history: {str(retry_error)}")

            # Log the creation of history entry for debugging
            current_app.logger.info(f"Created/updated history entry: ID={history_id}, "
                                    f"User={reservation.user_id}, Room={reservation.room_id}, "
                                    f"Date={target_date}, Status={status}")

            # Send notification directly after processing the reservation
            try:
                # Check if notifications are enabled in the configuration
                if current_app.config.get('NOTIFICATION_ENABLED', False):
                    current_app.logger.info(f"Sending direct notification for history ID {history_id}")

                    if status == 'successful':
                        NotificationService.send_reservation_success(
                            user_id=reservation.user_id,
                            room_name=room.name,
                            date=target_date.strftime('%Y-%m-%d'),
                            start_time=reservation.start_time,
                            end_time=reservation.end_time
                        )
                    else:
                        NotificationService.send_reservation_failure(
                            user_id=reservation.user_id,
                            room_name=room.name,
                            date=target_date.strftime('%Y-%m-%d'),
                            start_time=reservation.start_time,
                            end_time=reservation.end_time,
                            reason=message
                        )
            except Exception as notification_error:
                current_app.logger.error(
                    f"Error sending notification for history {history_id}: {str(notification_error)}")
                # Don't let notification failure affect the reservation result
                pass

            # Include created history information in results
            with lock:
                if 'created_histories' not in results_dict:
                    results_dict['created_histories'] = []
                results_dict['created_histories'].append(history_id)

        except Exception as e:
            with lock:
                results_dict['failed'] += 1
                results_dict['errors'].append(str(e))
            current_app.logger.error(f"Error processing recurring reservation {reservation.id}: {str(e)}")
        finally:
            # Make sure to properly close the session
            if session:
                ReservationService.close_db_session()

            return history_id

    @staticmethod
    def process_single_one_time_reservation(reservation, target_date, results_dict, lock):
        """
        Process a single one-time reservation with guaranteed single history entry and direct notifications

        Args:
            reservation: OneTimeReservation instance
            target_date: Target date for reservation
            results_dict: Shared dictionary to accumulate results
            lock: Threading lock for safe update of results_dict

        Returns:
            None (updates results_dict in place)
        """
        session = None
        history_id = None

        try:
            # Get thread-local session
            session = ReservationService.get_db_session()

            user = session.query(User).get(reservation.user_id)
            if not user:
                reservation.status = 'failed'
                session.commit()
                with lock:
                    results_dict['failed'] += 1
                    results_dict['errors'].append(f"User not found: {reservation.user_id}")
                return

            client = CCOMClient(user.username, user.get_ccom_password(), user.ccom_token)

            # Ensure we're logged in
            if not client.soft_login():
                reservation.status = 'failed'
                session.commit()

                with lock:
                    results_dict['failed'] += 1
                    results_dict['errors'].append(f"Failed to login for user {user.username}")
                return

            # Update user token
            user.ccom_token = client.token
            session.commit()

            # Get room
            room = session.query(Room).get(reservation.room_id)
            if not room:
                reservation.status = 'failed'
                session.commit()
                with lock:
                    results_dict['failed'] += 1
                    results_dict['errors'].append(f"Room not found: {reservation.room_id}")
                return

            # Process cancellation
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
                    # Make multiple attempts to cancel
                    success = False
                    error_msg = "No attempts made"

                    for attempt in range(3):  # Try up to 3 times
                        response = client.cancel_reservation(order_id)

                        if response.get('status') == 200 and response.get('msg') == '成功':
                            success = True
                            error_msg = None
                            break

                        if attempt < 2:  # Not the last attempt
                            time.sleep(0.5)  # Wait before retry

                        error_msg = response.get('msg', 'Unknown error')
                else:
                    success = False
                    error_msg = 'No matching reservation found to cancel'

                # Record results
                with lock:
                    results_dict['processed'] += 1

                    if success:
                        reservation.status = 'successful'
                        results_dict['successful'] += 1
                        status = 'successful'
                        message = 'Successfully cancelled'
                    else:
                        reservation.status = 'failed'
                        results_dict['failed'] += 1
                        status = 'failed'
                        message = error_msg

                session.commit()

            else:
                # Regular reservation - Split into segments (max 3 hours each)
                time_segments = ReservationService.split_reservation_time(
                    target_date,
                    reservation.start_time,
                    reservation.end_time
                )

                # Process all segments
                all_segments_succeeded = True
                all_errors = []

                for start_timestamp, end_timestamp in time_segments:
                    # Try to reserve this segment with multiple attempts
                    success, error_msg = ReservationService.attempt_reservation(
                        client, room.ccom_id, start_timestamp, end_timestamp
                    )

                    if not success:
                        all_segments_succeeded = False
                        # Only add non-None, non-empty error messages
                        if error_msg:
                            all_errors.append(error_msg)

                # Record results
                with lock:
                    results_dict['processed'] += 1

                    if all_segments_succeeded:
                        reservation.status = 'successful'
                        results_dict['successful'] += 1
                        status = 'successful'
                        message = 'Reservation successful'
                    else:
                        reservation.status = 'failed'
                        results_dict['failed'] += 1
                        status = 'failed'
                        message = '; '.join(all_errors) if all_errors else "Unknown error"

                session.commit()

            # Always create a new history entry for better tracking and to ensure we have a record
            # First, create the new history entry
            new_history = ReservationHistory(
                user_id=reservation.user_id,
                room_id=reservation.room_id,
                reservation_date=target_date,
                start_time=reservation.start_time,
                end_time=reservation.end_time,
                status=status,
                message=message,
                source_type='one_time',
                source_id=reservation.id,
                created_at=datetime.utcnow()  # Explicitly set creation time
            )

            # Add to session and commit immediately
            session.add(new_history)

            try:
                session.flush()  # Flush to get the ID before commit
                history_id = new_history.id
                session.commit()
                current_app.logger.info(f"Successfully created new one-time history entry: ID={history_id}")
            except Exception as commit_error:
                session.rollback()
                current_app.logger.error(f"Error creating one-time history: {str(commit_error)}")
                # Try one more time with a new session
                try:
                    session.close()
                    session = ReservationService.get_db_session()

                    # Create a new history entry with a fresh session
                    history = ReservationHistory(
                        user_id=reservation.user_id,
                        room_id=reservation.room_id,
                        reservation_date=target_date,
                        start_time=reservation.start_time,
                        end_time=reservation.end_time,
                        status=status,
                        message=message,
                        source_type='one_time',
                        source_id=reservation.id,
                        created_at=datetime.utcnow()
                    )
                    session.add(history)
                    session.flush()
                    history_id = history.id
                    session.commit()
                    current_app.logger.info(f"Successfully saved one-time history on second attempt: ID={history_id}")
                except Exception as retry_error:
                    current_app.logger.error(f"Final error saving one-time history: {str(retry_error)}")
                    with lock:
                        results_dict['errors'].append(f"Could not save one-time history: {str(retry_error)}")

            # Log the creation of history entry
            current_app.logger.info(f"Created/updated one-time history entry: ID={history_id}, "
                                    f"User={reservation.user_id}, Room={reservation.room_id}, "
                                    f"Date={target_date}, Status={status}")

            # Send notification directly after processing the reservation
            try:
                # Check if notifications are enabled in the configuration
                if current_app.config.get('NOTIFICATION_ENABLED', False):
                    current_app.logger.info(f"Sending direct notification for one-time history ID {history_id}")

                    if status == 'successful':
                        NotificationService.send_reservation_success(
                            user_id=reservation.user_id,
                            room_name=room.name,
                            date=target_date.strftime('%Y-%m-%d'),
                            start_time=reservation.start_time,
                            end_time=reservation.end_time
                        )
                    else:
                        NotificationService.send_reservation_failure(
                            user_id=reservation.user_id,
                            room_name=room.name,
                            date=target_date.strftime('%Y-%m-%d'),
                            start_time=reservation.start_time,
                            end_time=reservation.end_time,
                            reason=message
                        )
            except Exception as notification_error:
                current_app.logger.error(
                    f"Error sending notification for one-time history {history_id}: {str(notification_error)}")
                # Don't let notification failure affect the reservation result
                pass

        except Exception as e:
            try:
                if reservation and session:
                    reservation.status = 'failed'
                    session.commit()
            except:
                pass

            with lock:
                results_dict['failed'] += 1
                results_dict['errors'].append(str(e))
            current_app.logger.error(f"Error processing one-time reservation {reservation.id}: {str(e)}")
        finally:
            # Make sure to properly close the session
            if session:
                ReservationService.close_db_session()

    @staticmethod
    def process_user_login(user, results, lock):
        """Process a single user pre-login"""
        session = None
        try:
            # Get thread-local session
            session = ReservationService.get_db_session()

            client = CCOMClient(user.username, user.get_ccom_password(), user.ccom_token)

            if client.soft_login():
                # Update the token in the database
                user.ccom_token = client.token
                session.commit()
                with lock:
                    results['successful'] += 1
                current_app.logger.info(f"Pre-login successful for user {user.username}")
            else:
                with lock:
                    results['failed'] += 1
                    results['errors'].append(f"Pre-login failed for user {user.username}")
                current_app.logger.error(f"Pre-login failed for user {user.username}")
        except Exception as e:
            with lock:
                results['failed'] += 1
                results['errors'].append(f"Error during pre-login for user {user.username}: {str(e)}")
            current_app.logger.error(f"Error during pre-login for user {user.username}: {str(e)}")
        finally:
            # Make sure to properly close the session
            if session:
                ReservationService.close_db_session()

    @staticmethod
    def process_recurring_reservations(target_date=None, max_workers=10):
        """
        Process all recurring reservations for the given date in parallel

        Args:
            target_date: Target date (default: tomorrow)
            max_workers: Maximum number of parallel threads

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

        # Initialize results dictionary with thread-safe counters
        results = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }

        # Thread lock for updating results dictionary
        lock = threading.Lock()

        # Create app context for each worker thread to use
        from flask import current_app
        app = current_app._get_current_object()

        # Process reservations in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks - each with its own app context
            futures = []
            for reservation in recurring_reservations:
                def process_with_context(res=reservation):
                    with app.app_context():
                        return ReservationService.process_single_recurring_reservation(
                            res, target_date, results, lock
                        )

                futures.append(executor.submit(process_with_context))

            # Wait for all tasks to complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    with app.app_context():
                        current_app.logger.error(f"Unexpected thread error: {str(e)}")
                    with lock:
                        results['errors'].append(f"Thread error: {str(e)}")

        return results

    @staticmethod
    def process_one_time_reservations(target_date=None, max_workers=10):
        """
        Process all one-time reservations for the given date in parallel

        Args:
            target_date: Target date (default: tomorrow)
            max_workers: Maximum number of parallel threads

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

        # Initialize results dictionary with thread-safe counters
        results = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'errors': []
        }

        # Thread lock for updating results dictionary
        lock = threading.Lock()

        # Create app context for each worker thread to use
        from flask import current_app
        app = current_app._get_current_object()

        # Process reservations in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks - each with its own app context
            futures = []
            for reservation in one_time_reservations:
                def process_with_context(res=reservation):
                    with app.app_context():
                        return ReservationService.process_single_one_time_reservation(
                            res, target_date, results, lock
                        )

                futures.append(executor.submit(process_with_context))

            # Wait for all tasks to complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    with app.app_context():
                        current_app.logger.error(f"Unexpected thread error: {str(e)}")
                    with lock:
                        results['errors'].append(f"Thread error: {str(e)}")

        return results

    @staticmethod
    def perform_pre_login(max_workers=10):
        """
        Perform soft login for all users with pending reservations for tomorrow in parallel
        to refresh their tokens before the actual reservation process

        Args:
            max_workers: Maximum number of parallel threads

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
        users = list({user.id: user for user in recurring_users + one_time_users}.values())

        # Initialize results
        results = {
            'total_users': len(users),
            'successful': 0,
            'failed': 0,
            'errors': []
        }

        # Thread lock for updating results dictionary
        lock = threading.Lock()

        # Create app context for each worker thread to use
        from flask import current_app
        app = current_app._get_current_object()

        # Process user logins in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks - each with its own app context
            futures = []
            for user in users:
                def process_with_context(u=user):
                    with app.app_context():
                        return ReservationService.process_user_login(u, results, lock)

                futures.append(executor.submit(process_with_context))

            # Wait for all tasks to complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    with app.app_context():
                        current_app.logger.error(f"Unexpected thread error in pre-login: {str(e)}")
                    with lock:
                        results['errors'].append(f"Thread error in pre-login: {str(e)}")

        return results

    @staticmethod
    def execute_reservations(max_workers=10):
        """
        Execute all pending reservations for tomorrow in parallel

        Args:
            max_workers: Maximum number of parallel threads

        Returns:
            dict: Combined processing results
        """
        target_date = date.today() + timedelta(days=1)

        # Process recurring and one-time reservations in parallel
        recurring_results = ReservationService.process_recurring_reservations(target_date, max_workers)
        one_time_results = ReservationService.process_one_time_reservations(target_date, max_workers)

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