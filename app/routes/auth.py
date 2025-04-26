"""
@Author: Tianyi Zhang
@Date: 2025/4/26
@Description: 
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models.user import User
from app.services.ccom_client import CCOMClient
from datetime import datetime
from werkzeug.urls import url_parse

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login route"""
    # If user is already logged in, redirect to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember_me = 'remember_me' in request.form

        user = User.query.filter_by(username=username).first()

        # If user doesn't exist, try to create with CCOM credentials
        if not user:
            try:
                # Try to login to CCOM with provided credentials
                client = CCOMClient(username, password)
                if client.login():
                    # Create new user in our system
                    user = User(username=username)
                    user.set_password(password)  # Set app password
                    user.set_ccom_password(password)  # Store CCOM password
                    user.ccom_token = client.token
                    db.session.add(user)
                    db.session.commit()
                    flash('Account successfully created with your CCOM credentials.', 'success')
                else:
                    flash('Invalid CCOM credentials.', 'danger')
                    return render_template('auth/login.html')
            except Exception as e:
                current_app.logger.error(f"CCOM login error: {str(e)}")
                flash('Error connecting to CCOM. Please try again later.', 'danger')
                return render_template('auth/login.html')

        # Verify password
        if user and user.check_password(password):
            # Check if CCOM credentials are still valid
            try:
                # Update stored CCOM password if it differs from current one
                if not user.get_ccom_password() or user.get_ccom_password() != password:
                    user.set_ccom_password(password)
                    db.session.commit()

                client = CCOMClient(username, user.get_ccom_password(), user.ccom_token)
                if client.soft_login():
                    # Update token if needed
                    if client.token != user.ccom_token:
                        user.ccom_token = client.token
                        db.session.commit()
                else:
                    flash('Your CCOM credentials are no longer valid. Please update your password.', 'warning')
                    return render_template('auth/login.html')
            except Exception as e:
                current_app.logger.error(f"CCOM verification error: {str(e)}")
                # We will still log the user in but display a warning
                flash('Unable to verify your CCOM credentials. Some features may not work.', 'warning')

            # Update last login time
            user.last_login = datetime.utcnow()
            db.session.commit()

            # Log in the user
            login_user(user, remember=remember_me)
            flash('Login successful!', 'success')

            # Redirect to the page the user was trying to access or to dashboard
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                next_page = url_for('main.dashboard')
            return redirect(next_page)
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """User logout route"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile route"""
    if request.method == 'POST':
        # Handle profile update
        if 'update_profile' in request.form:
            email = request.form.get('email')
            push_key = request.form.get('push_notification_key')

            # Update user profile
            current_user.email = email
            current_user.push_notification_key = push_key
            db.session.commit()

            flash('Profile updated successfully!', 'success')

        # Handle password change
        elif 'change_password' in request.form:
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            update_ccom = 'update_ccom_password' in request.form  # New checkbox for CCOM password update

            # Verify current password
            if not current_user.check_password(current_password):
                flash('Current password is incorrect.', 'danger')
                return redirect(url_for('auth.profile'))

            # Verify new password matches confirmation
            if new_password != confirm_password:
                flash('New passwords do not match.', 'danger')
                return redirect(url_for('auth.profile'))

            # Update application password
            current_user.set_password(new_password)

            # Optionally update CCOM password
            if update_ccom:
                try:
                    client = CCOMClient(current_user.username, new_password)
                    if client.login():
                        # Update stored CCOM password
                        current_user.set_ccom_password(new_password)
                        current_user.ccom_token = client.token
                        db.session.commit()
                        flash('Password updated successfully and synchronized with CCOM!', 'success')
                    else:
                        flash('Failed to authenticate with CCOM using new password. Only app password was updated.', 'warning')
                except Exception as e:
                    current_app.logger.error(f"Password change error: {str(e)}")
                    flash('Error connecting to CCOM. Only app password was updated.', 'warning')
            else:
                # Only update app password, not CCOM password
                db.session.commit()
                flash('Application password updated successfully!', 'success')

    return render_template('auth/profile.html', user=current_user)


@auth_bp.route('/test_notification', methods=['POST'])
@login_required
def test_notification():
    """Test notification system"""
    from app.services.notification_service import NotificationService

    if not current_user.push_notification_key:
        flash('Please set a notification key in your profile first.', 'warning')
        return redirect(url_for('auth.profile'))

    success = NotificationService.send_notification(
        user_id=current_user.id,
        title="Test Notification",
        message="This is a test notification from CCOM Piano Reservation System.",
        group="Test"
    )

    if success:
        flash('Test notification sent successfully!', 'success')
    else:
        flash('Failed to send test notification. Please check your notification key.', 'danger')

    return redirect(url_for('auth.profile'))