"""
@Author: Tianyi Zhang
@Date: 2025/4/26
@Description: Improved scheduler to support parallel processing of reservations
"""
from flask import current_app
from datetime import datetime
import pytz
from app.services.reservation_service import ReservationService
from app.services.notification_service import NotificationService
from app import db
from flask import Flask

# Store a reference to the app instance that will be set during initialization
flask_app = None

def initialize_scheduler(scheduler, app):
    """Initialize the task scheduler with reservation tasks"""
    # Store the app reference globally for the scheduler jobs to use
    global flask_app
    flask_app = app

    # Schedule daily reservation task at 21:30 Beijing time
    scheduler.add_job(
        id='execute_reservations',
        func=execute_scheduled_reservations,
        trigger='cron',
        hour=21,
        minute=30,
        timezone=pytz.timezone('Asia/Shanghai')
    )

    # Add a new task for pre-login at 21:28 (2 minutes before reservations)
    scheduler.add_job(
        id='execute_pre_login',
        func=execute_pre_login,
        trigger='cron',
        hour=21,
        minute=28,
        timezone=pytz.timezone('Asia/Shanghai')
    )

    # Add a test task that runs every minute (for development)
    if app.config.get('DEBUG', False):
        scheduler.add_job(
            id='test_scheduler',
            func=test_scheduler_function,
            trigger='interval',
            minutes=1
        )

    app.logger.info("Scheduler initialized with reservation tasks")
    return scheduler


def execute_pre_login():
    """Perform pre-login to refresh tokens before the actual reservation process"""
    # Use the global app reference instead of trying to get current_app
    global flask_app

    if not flask_app:
        print("ERROR: Flask app reference not set for scheduler job")
        return {'error': 'Flask app reference not set'}

    with flask_app.app_context():
        flask_app.logger.info("Starting pre-login process")

        try:
            # Calculate the number of workers based on server resources
            # A reasonable default is the number of CPU cores + 1
            import multiprocessing
            max_workers = min(multiprocessing.cpu_count() + 1, 16)  # Cap at 16 workers to prevent overloading

            # Perform pre-login for all users with pending reservations using parallel processing
            results = ReservationService.perform_pre_login(max_workers=max_workers)

            # Log results
            flask_app.logger.info(
                f"Pre-login completed: "
                f"{results['successful']} successful, "
                f"{results['failed']} failed"
            )

            return results

        except Exception as e:
            flask_app.logger.error(f"Error in pre-login process: {str(e)}")
            return {'error': str(e)}


def execute_scheduled_reservations():
    """Execute all pending reservations for tomorrow using parallel processing"""
    # Use the global app reference instead of trying to get current_app
    global flask_app

    if not flask_app:
        print("ERROR: Flask app reference not set for scheduler job")
        return {'error': 'Flask app reference not set'}

    with flask_app.app_context():
        flask_app.logger.info("Starting scheduled reservation execution with parallel processing")

        try:
            # Calculate the number of workers based on server resources
            # A reasonable default is the number of CPU cores + 1
            import multiprocessing
            max_workers = min(multiprocessing.cpu_count() + 1, 16)  # Cap at 16 workers to prevent overloading

            # Execute all reservations with parallel processing
            results = ReservationService.execute_reservations(max_workers=max_workers)

            # Send notifications
            notification_count = NotificationService.send_bulk_reservation_results(results)

            # Log results
            flask_app.logger.info(
                f"Parallel reservation execution completed: "
                f"{results['total_successful']} successful, "
                f"{results['total_failed']} failed, "
                f"{notification_count} notifications sent. "
                f"Using {max_workers} worker threads."
            )

            return results

        except Exception as e:
            flask_app.logger.error(f"Error in scheduled reservation execution: {str(e)}")
            return {'error': str(e)}


def test_scheduler_function():
    """Test function to verify the scheduler is working"""
    # Use the global app reference instead of trying to get current_app
    global flask_app

    if not flask_app:
        print("ERROR: Flask app reference not set for scheduler job")
        return

    with flask_app.app_context():
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        flask_app.logger.info(f"Test scheduler function executed at {current_time}")