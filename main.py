import threading
import time
import itchat
import pytz
from client import Client
from datetime import datetime, timedelta, timezone
from config import config
from caltime import SendTimeCalculator, TimeUtils

class AsyncPostSender:
    def __init__(self, send_time, room_name, start_time, end_time, max_count):
        self.client = Client(config)
        self.client.soft_login()
        self.calculator = SendTimeCalculator()
        self.start_time = start_time
        self.end_time = end_time
        self.max_count = max_count
        self.send_time = self.calculator.calculate_send_time(send_time)
        self.room_id = self.client.get_room_id(room_name)
        self.thread = threading.Thread(target=self.run)
        self.thread.daemon = True  # 设为守护线程

    def start(self):
        self.thread.start()

    def run(self):
        count = 0
        last_message = ""
        logged_in = False
        login_time = self.send_time - timedelta(minutes=1)
        while count < self.max_count:
            current_time = datetime.now(pytz.timezone('Asia/Shanghai'))
            if current_time >= login_time and not logged_in:
                self.client.soft_login()
                logged_in = True
            if current_time >= self.send_time:
                resp = self.client.chose_room(self.room_id,self.start_time,self.end_time)
                if resp.get('status') == 200 and resp.get('msg') == '成功':
                    return True, "已选上对应时间段"
                if resp.get('msg') != '重复请求,请稍后再试.':
                    last_message = resp.get('msg')
                count += 1
            else:
                time.sleep(0.05)  # 根据需要调整睡眠时间
        return False, last_message

if __name__ == '__main__':
    timeutils= TimeUtils()
    segments= timeutils.split_time('2100','2130',3)
    for start_segment, end_segment in segments:
        sender = AsyncPostSender('2130', "琴810", start_segment, end_segment, 50)
        sender.start()
    # sender = AsyncPostSender('1337', "琴810",timeutils.convert_to_timestamp("1330"), timeutils.convert_to_timestamp("1430"),5)
    # sender.start()
    time.sleep(100)
