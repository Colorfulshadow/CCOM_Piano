"""
@Author: Tianyi Zhang
@Date: 2025/4/26
@Description: 
"""
from app import db
from datetime import datetime, date


class RecurringReservation(db.Model):
    __tablename__ = 'recurring_reservations'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Monday, 6=Sunday
    start_time = db.Column(db.String(4), nullable=False)  # Format: "1400" for 2:00 PM
    end_time = db.Column(db.String(4), nullable=False)  # Format: "1600" for 4:00 PM
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<RecurringReservation {self.id}: {self.room.name} {self.get_day_name()} {self.start_time}-{self.end_time}>'

    def get_day_name(self):
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        return days[self.day_of_week]

    def is_valid_duration(self):
        """Check if the reservation duration is within the allowed limit"""
        from app.utils.time_utils import calculate_duration_hours

        duration = calculate_duration_hours(self.start_time, self.end_time)
        return duration <= 3  # Maximum 3 hours per reservation


class OneTimeReservation(db.Model):
    __tablename__ = 'one_time_reservations'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    reservation_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(4), nullable=False)
    end_time = db.Column(db.String(4), nullable=False)
    is_cancellation = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='pending')  # pending, successful, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        action = "Cancel" if self.is_cancellation else "Reserve"
        return f'<OneTime{action} {self.id}: {self.room.name} {self.reservation_date} {self.start_time}-{self.end_time}>'

    def is_valid_duration(self):
        """Check if the reservation duration is within the allowed limit"""
        from app.utils.time_utils import calculate_duration_hours

        duration = calculate_duration_hours(self.start_time, self.end_time)
        return duration <= 3  # Maximum 3 hours per reservation


class ReservationHistory(db.Model):
    __tablename__ = 'reservation_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    reservation_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(4), nullable=False)
    end_time = db.Column(db.String(4), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # successful, failed
    message = db.Column(db.Text, nullable=True)
    source_type = db.Column(db.String(20), nullable=True)  # recurring, one_time
    source_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ReservationHistory {self.id}: {self.room.name} {self.reservation_date} {self.start_time}-{self.end_time} {self.status}>'