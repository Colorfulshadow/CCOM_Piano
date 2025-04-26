"""
@Author: Tianyi Zhang
@Date: 2025/4/26
@Description: 
"""
from app import db, login_manager
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime
from cryptography.fernet import Fernet
import os
from flask import current_app


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(128), nullable=False)
    ccom_password_encrypted = db.Column(db.String(256), nullable=True)  # New field for CCOM password
    ccom_token = db.Column(db.String(256), nullable=True)
    push_notification_key = db.Column(db.String(256), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationships
    recurring_reservations = db.relationship('RecurringReservation', backref='user', lazy='dynamic')
    one_time_reservations = db.relationship('OneTimeReservation', backref='user', lazy='dynamic')
    reservation_history = db.relationship('ReservationHistory', backref='user', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def set_ccom_password(self, ccom_password):
        """Encrypt and store CCOM password"""
        key = self._get_encryption_key()
        fernet = Fernet(key)
        encrypted_password = fernet.encrypt(ccom_password.encode())
        self.ccom_password_encrypted = encrypted_password.decode()

    def get_ccom_password(self):
        """Decrypt and return CCOM password"""
        if not self.ccom_password_encrypted:
            return None

        key = self._get_encryption_key()
        fernet = Fernet(key)
        return fernet.decrypt(self.ccom_password_encrypted.encode()).decode()

    def _get_encryption_key(self):
        """Get or create encryption key from app config"""
        # We use the app's SECRET_KEY to derive an encryption key
        # This is a simple approach - for production, consider using a separate encryption key
        key = current_app.config.get('ENCRYPTION_KEY')
        if not key:
            # If no key is set, use SECRET_KEY to derive one
            import base64
            import hashlib
            key = base64.urlsafe_b64encode(hashlib.sha256(current_app.config['SECRET_KEY'].encode()).digest())
            current_app.config['ENCRYPTION_KEY'] = key
        return key

    def save_ccom_token(self, token):
        self.ccom_token = token
        db.session.commit()

    def update_last_login(self):
        self.last_login = datetime.utcnow()
        db.session.commit()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))