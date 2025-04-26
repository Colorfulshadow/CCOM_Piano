"""
@Author: Tianyi Zhang
@Date: 2025/4/26
@Description: 
"""
from app import db


class Room(db.Model):
    __tablename__ = 'rooms'

    id = db.Column(db.Integer, primary_key=True)
    ccom_id = db.Column(db.String(32), unique=True, nullable=False)
    name = db.Column(db.String(64), nullable=False)
    partition = db.Column(db.String(64), nullable=True)
    instruments = db.Column(db.String(256), nullable=True)

    # Relationships
    recurring_reservations = db.relationship('RecurringReservation', backref='room', lazy='dynamic')
    one_time_reservations = db.relationship('OneTimeReservation', backref='room', lazy='dynamic')
    reservation_history = db.relationship('ReservationHistory', backref='room', lazy='dynamic')

    def __repr__(self):
        return f'<Room {self.name}>'

    @staticmethod
    def import_from_csv(csv_path):
        """Import rooms from the devices_data.csv file"""
        import csv

        try:
            # 尝试不同的编码
            encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030']

            for encoding in encodings:
                try:
                    with open(csv_path, 'r', encoding=encoding) as csvfile:
                        reader = csv.DictReader(csvfile)
                        for row in reader:
                            room = Room.query.filter_by(ccom_id=row['ID']).first()
                            if not room:
                                room = Room(
                                    ccom_id=row['ID'],
                                    name=row['Name'],
                                    partition=row['Partition'],
                                    instruments=row['Instruments']
                                )
                                db.session.add(room)
                        db.session.commit()
                    return True  # 如果成功读取，跳出循环
                except UnicodeDecodeError:
                    # 如果当前编码不正确，尝试下一个
                    continue
                except Exception as e:
                    # 其他错误
                    raise e

            # 如果所有编码都失败
            return False
        except Exception as e:
            print(f"Error importing rooms: {str(e)}")
            db.session.rollback()
            return False