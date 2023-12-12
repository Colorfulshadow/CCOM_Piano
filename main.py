import requests
from datetime import datetime, timedelta, timezone
import time
import subprocess
import re
import json

with open('config.json', 'r') as config_file:
    config = json.load(config_file)
class TimeCalculator:
    def __init__(self, server_url):
        self.server_url = server_url

    def get_server_time(self):
        print("正在获取服务器时间...")
        response = requests.head(self.server_url)
        date_str = response.headers['Date']
        server_time = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S GMT')
        print("服务器时间(UTC+0)获取成功:",server_time)
        return server_time

    def measure_latency(self, count=4):
        print("测量与服务器之间的延迟...")
        # ping_cmd = f"ping -n {count} {self.ping_host}"
        # process = subprocess.Popen(ping_cmd.split(), stdout=subprocess.PIPE)
        # output, _ = process.communicate()
        # output = output.decode('GBK')
        r = requests.get(self.server_url,proxies=None)
        # matcher = re.search(r'平均 = (\d+)ms', output)
        rtt = r.elapsed.microseconds/1000
        if rtt:
            print("服务器单边延迟:",rtt/2.0,'ms')
            return rtt / 2.0  # 估计单向延迟
        return None

    def convert_to_timestamp_auto(time_str, add_day=False):
        beijing_timezone = timezone(timedelta(hours=8))
        current_time = datetime.now(beijing_timezone)

        base_date = current_time.date()

        hour = int(time_str[:2])
        minute = int(time_str[2:])

        target_datetime = datetime(year=base_date.year, month=base_date.month, day=base_date.day,
                                   hour=hour, minute=minute, tzinfo=beijing_timezone) + timedelta(days=1)
        timestamp_milliseconds = int(target_datetime.timestamp() * 1000)
        return timestamp_milliseconds

    def calculate_send_time(self, target_time, add_day=False):
        print("计算发送时间点中...")
        server_time_utc = self.get_server_time()
        one_way_latency = self.measure_latency() / 1000  # 转换为秒

        beijing_timezone = timezone(timedelta(hours=8))
        server_time = server_time_utc.replace(tzinfo=timezone.utc).astimezone(beijing_timezone)

        current_time = datetime.now(beijing_timezone).replace(tzinfo=None)

        if add_day:
            target_datetime = datetime.combine(current_time.date() + timedelta(days=1), target_time)
        else:
            target_datetime = datetime.combine(current_time.date(), target_time)

        time_diff = current_time - server_time.replace(tzinfo=None)
        target_timestamp = target_datetime.timestamp() - time_diff.total_seconds() - one_way_latency
        print("计算出的发送POST请求的时间:", datetime.fromtimestamp(target_timestamp, beijing_timezone))
        return datetime.fromtimestamp(target_timestamp, beijing_timezone)

def login():
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)

    token = config.get('token')

    # 检查token是否存在且有效
    if token:
        print("token存在，正在检查是否有效...")
        verify_url = 'https://saas.tansiling.com/order/applet/order/getRecentOrder'
        headers = {
            'Authorization': token,
            'Content-Type': 'application/json;charset=UTF-8',
        }
        verify_response = requests.get(verify_url, headers=headers, proxies=None)
        verify_data = verify_response.json()

        if verify_data.get('status') == 200:
            print("token有效")
            return token

    # 如果token不存在或无效，则执行登录过程
    print("token不存在或失效，正在登陆尝试获取token...")
    login_url = 'https://saas.tansiling.com/service-zuul/applet/login/login'
    headers = {'Content-Type': 'application/json;charset=UTF-8'}

    if config['lessee_mode'] == 1:
        password = config['password_traditonal']
        lessee = 151
    elif config['lessee_mode'] == 2:
        password = config['password_smart']
        lessee = 128

    body = {
        "accountNumber": config['username'],
        "lessee": lessee,
        "password": password,
        "code": None
    }
    body_json = json.dumps(body)
    headers['Content-Length'] = str(len(body_json))

    response = requests.post(login_url, headers=headers, data=body_json, proxies=None)
    response_data = response.json()

    if response_data.get('status') == 200 and response_data.get('msg') == '成功':
        new_token = response_data['data']['token']
        # 更新config.json中的token
        config['token'] = new_token
        with open('config.json', 'w') as config_file:
            json.dump(config, config_file, indent=4)
        print("登陆成功，保存token到config")
        return new_token
    else:
        print("登陆失败，请检查账号密码是否有误")
        return None

def send_post_request(start_time, end_time, token):
    start_timestamp = TimeCalculator.convert_to_timestamp_auto(start_time,add_day=True)
    end_timestamp = TimeCalculator.convert_to_timestamp_auto(end_time,add_day=True)

    url = 'https://saas.tansiling.com/order/applet/order/placeAnOrder'
    headers = {
        'Authorization': token,
        'Content-Type': 'application/json;charset=UTF-8',
        'Content-Length': '110',
    }
    data = {
        'device': config['device_id'],
        'subscribeList': [{'startTime': start_timestamp, 'endTime': end_timestamp, 'aiMonitoringNum': None}]
    }

    # response = requests.post(url, json=data, headers=headers, proxies=None)
    response = requests.post(url, json=data, headers=headers, proxies=None)
    response_data = response.json()

    if response_data.get('status') == 200 and response_data.get('msg') == '成功':
        current_time = datetime.now(timezone(timedelta(hours=8)))
        print("已选上对应时间段，选上时间:",current_time)
    elif response_data.get('status') == 4001:
        print("未选上，正在重试...信息：", response_data.get('msg'))
    return response

def send_post_at_calculated_time(start_time,end_time,send_time,token):
    print("准备抢选中...抢选时间段",start_time,"-",end_time)
    while True:
        current_time = datetime.now(timezone(timedelta(hours=8)))
        # segments = split_into_three_hour_segments(start_time, end_time)
        if current_time >= send_time:
            # for segment in segments:
            #     start_segment, end_segment = segment
            #     print(f"正在发送请求的时间段: {start_segment} - {end_segment}")
            response = send_post_request(start_time, end_time, token)
            return response
            # while True:
            #     response = send_post_request(start_time, end_time, token)
            #     response_data = response.json()
            #
            #     if response_data.get('status') == 200 and response_data.get('msg') == '成功':
            #         return response
            #     # elif response_data.get('status') == 4001:
            #     #     print("时间范围已被选择，停止尝试。信息：", response_data.get('msg'))
            #     #     break
            #     else:
            #         time.sleep(0.1)  # 短暂等待后重试，可以根据需要调整等待时间
            # break  # 成功选上或遇到特定错误后退出外层循环
        else:
            time.sleep(0.001)  # 短暂等待，避免过度占用CPU

def get_free_time_slots(start_time, end_time, token):
    print("查找空闲时间段中...")
    url = "https://saas.tansiling.com/order/applet/order/getReserveInformation?device=1403"
    headers = {"Authorization": token}
    response = requests.get(url, headers=headers, proxies=None)
    print(response.text)
    data = response.json()

    free_time_slots = []
    for slot in data["data"]["takeUpTimeList"]:
        if slot["orderType"] == 1 :
            free_time_slots.append((slot["startTime"], slot["endTime"]))
            start_datetime = datetime.fromtimestamp(slot["startTime"] / 1000, timezone(timedelta(hours=8)))
            end_datetime = datetime.fromtimestamp(slot["endTime"] / 1000, timezone(timedelta(hours=8)))
            print(f"Free slot: {start_datetime.strftime('%Y-%m-%d %H:%M:%S')} to {end_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    return free_time_slots

def split_into_three_hour_segments(start_time_str, end_time_str):
    print("正在分割时间段...")
    # 将时间字符串转换为datetime对象
    start_datetime = datetime.strptime(start_time_str, '%H%M')
    end_datetime = datetime.strptime(end_time_str, '%H%M')

    # 分割时间段
    segments = []
    while start_datetime < end_datetime:
        # 计算下一个时间段的结束时间
        next_datetime = min(start_datetime + timedelta(hours=3), end_datetime)
        # 将datetime对象转换回字符串格式
        segment_start_str = start_datetime.strftime('%H%M')
        segment_end_str = next_datetime.strftime('%H%M')
        segments.append((segment_start_str, segment_end_str))
        # 更新开始时间为当前段的结束时间
        start_datetime = next_datetime
    print("已分割时间段为", segments)
    return segments

# 主程序
if __name__ == '__main__':
    # calculator = TimeCalculator("https://saas.tansiling.com", "saas.tansiling.com")
    # target_time = datetime.strptime("22:35", "%H:%M").time()  # 设定目标时间
    # send_time = calculator.calculate_send_time(target_time, add_day=False)
    # send_post_at_calculated_time(send_time)
    token = login()
    if token:
        calculator = TimeCalculator("https://saas.tansiling.com")
        if config['mode'] == 1:
            target_time = datetime.strptime("21:29", "%H:%M").time()  # 设定目标时间
            send_time = calculator.calculate_send_time(target_time, add_day=False)
            segments = split_into_three_hour_segments(config["start_time"], config["end_time"])
            remaining_segments = segments.copy()
            while remaining_segments:
                next_round_segments = []
                for segment in remaining_segments:
                    start_segment, end_segment = segment
                    response = send_post_at_calculated_time(start_segment,end_segment,send_time,token)
                    response_data = response.json()
                    if response_data.get('status') == 200 and response_data.get('msg') == '成功':
                        print("时间段",{start_segment} - {end_segment},"发送成功")
                    else:
                        next_round_segments.append(segment)
                remaining_segments = next_round_segments
                # elif response_data.get('status') == 4001:
                #     print("时间范围已被选择，停止尝试。信息：", response_data.get('msg'))
                #     break
                # else:
                #     time.sleep(0.1)  # 短暂等待后重试，可以根据需要调整等待时间
        elif config['mode'] == 2:
            pass