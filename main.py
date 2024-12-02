import threading
import time
#import itchat
import pytz
from client import Client
from datetime import datetime, timedelta, timezone
from config import config
from caltime import SendTimeCalculator, TimeUtils
import requests

def send_message(message):
    send_key = config['send_key']
    server_url = f'https://sctapi.ftqq.com/{send_key}.send'  # Server酱 API URL
    payload = {
        'title': '脚本通知',  # 通知标题
        'desp': message  # 通知内容
    }
    try:
        response = requests.post(server_url, data=payload)
        if response.status_code == 200:
            print("Message sent successfully.")
        else:
            print(f"Failed to send message. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error sending message: {e}")

class AsyncPostSender:
    def __init__(self, send_time, room_name, start_time, end_time, max_count):
        self.client = Client(config)
        self.calculator = SendTimeCalculator()
        self.start_time = start_time
        self.end_time = end_time
        self.max_count = max_count
        self.send_time = self.calculator.calculate_send_time(send_time)
        self.room_id = self.client.get_room_id(room_name)
        self.thread = threading.Thread(target=self.run)
        self.thread.daemon = True
        self.last_message = ""
        timeutils = TimeUtils()
        self.start_time_date = timeutils.convert_to_datetime(start_time)
        self.end_time_date = timeutils.convert_to_datetime(end_time)
    def start(self):
        self.thread.start()

    def run(self):
        count = 0
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
                    #  send_message(f"已选上对应时间段 {self.start_time_date}-{self.end_time_date} 脚本结束")
                    print(f"已选上对应时间段 {self.start_time_date}-{self.end_time_date} 脚本结束")
                    return True, "已选上对应时间段"
                if resp.get('msg') != '重复请求,请稍后再试.':
                    self.last_message = resp.get('msg')
                count += 1
            else:
                time.sleep(0.05)  # 根据需要调整睡眠时间
        # send_message(f"已选上对应时间段 {self.start_time_date}-{self.end_time_date} 脚本结束")
        print(f"{self.start_time_date}-{self.end_time_date} 抢琴房失败，原因：{self.last_message}")
        return False, self.last_message

if __name__ == '__main__':
    timeutils= TimeUtils()
    segments= timeutils.split_time('1830','2330',3)
    for start_segment, end_segment in segments:
        sender = AsyncPostSender('2130', "教827", start_segment, end_segment, 20)
        sender.start()
    time.sleep(100)
