import threading
import time
#import itchat
import pytz
from client import Client
from datetime import datetime, timedelta, timezone
from config import config
from caltime import SendTimeCalculator, TimeUtils
import requests

def send_message(message,status):
    send_keys = [config.send_keys[i] for i in [0, 1]]
    for send_key in send_keys:
        server_url = f'https://notice.zty.ink/{send_key}'
        if status:
            payload = {
                'title': '抢琴房成功啦',
                'body': message,
                'icon': 'https://api.zty.ink/api/v2/objects/icon/se2ezd5tzxgsubc0rx.png',
                'group': '每日一抢琴房'
            }
        else:
            payload = {
                'title': '好可惜，没抢到琴房',
                'body': message,
                'icon': 'https://api.zty.ink/api/v2/objects/icon/fi9tl1ylkeyi8yoirb.png',
                'group': '每日一抢琴房'
            }
        try:
            response = requests.post(server_url, data=payload)
            if response.status_code == 200:
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Message sent successfully.")
            else:
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Failed to send message. Status code: {response.status_code}")
        except Exception as e:
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Error sending message: {e}")

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
                    send_message(f"已选上对应时间段 {self.start_time_date.strftime('%H:%M')}-{self.end_time_date.strftime('%H:%M')}",status=True)
                    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 已选上对应时间段 {self.start_time_date.strftime('%H:%M')}~{self.end_time_date.strftime('%H:%M')} 脚本结束")
                    return True, "已选上对应时间段"
                if resp.get('msg') != '重复请求,请稍后再试.':
                    self.last_message = resp.get('msg')
                count += 1
            else:
                time.sleep(0.05)  # 根据需要调整睡眠时间
        send_message(f"{self.start_time_date.strftime('%H:%M')}-{self.end_time_date.strftime('%H:%M')} 抢琴房失败，原因：{self.last_message}",status=False)
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {self.start_time_date.strftime('%H:%M')}~{self.end_time_date.strftime('%H:%M')} 抢琴房失败，原因：{self.last_message}")
        return False, self.last_message

if __name__ == '__main__':
    timeutils= TimeUtils()
    segments= timeutils.split_time('1830','2330',3)
    for start_segment, end_segment in segments:
        sender = AsyncPostSender('2130', "教827", start_segment, end_segment, 20)
        sender.start()
    time.sleep(600)
