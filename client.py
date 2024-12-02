from config import root, ua, Config
from typing import Optional
from exceptions import ApiError, LoginError, AlreadyChosen, FailedToChoose, FailedToDelChosen, FailedToFind
import requests
import json
import csv

class Client:
    def __init__(self, config:Config):
        self.config: Config = config
        self.token: Optional[str] = None

    def soft_login(self):
        if self.config.token:
            self.token = self.config.token
            try:
                result = self.get_basic_info()
                if result['data']['studentNumber'].lower() == self.config.username.lower():
                    print("soft login success")
                    return True
            except Exception:
                pass
        return self.login()

    def login(self):
        url = root + "/service-zuul/applet/login/login"
        headers = {'Content-Type': 'application/json;charset=UTF-8'}
        body = {
            "accountNumber": self.config.username,
            "lessee": "151",
            "password": self.config.password,
            "code": None
        }
        body_json = json.dumps(body)
        headers['Content-Length'] = str(len(body_json))
        resp = requests.post(url, headers=headers, data=body_json, proxies=None)
        resp_data = resp.json()
        if resp_data.get('status') == 200 and resp_data.get('msg') == '成功':
            print('login success')
            self.config.token = resp_data['data']['token']
        else:
            raise LoginError

    def _call_api(self, type, api_name: str, data: dict):
        if self.token is None:
            raise LoginError("you must call `login` or `soft_login` before calling other apis")
        url = root + '/order/applet/order/' + api_name

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'User-Agent': ua,
            'Authorization': self.token,
        }
        data_json = json.dumps(data)
        headers['Content-Length'] = str(len(data_json))
        if type == 1:
            headers.pop('Content-Length', None)  # 从 headers 中移除 'Content-Length'
            resp = requests.get(url, headers=headers, proxies=None, verify=False)
        elif type == 2:
            resp = requests.post(url, json=data, headers=headers, proxies=None, verify=False)
        if resp.status_code != 200:
            raise ApiError(f"server panics with http status code: {resp.status_code}")
        api_resp = resp.json()
        return  api_resp

    def get_room_id(self, room_name: str) -> str:
        with open('devices_data.csv', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['Name'] == room_name:
                    return row['ID']
            raise FailedToFind

    def get_basic_info(self):
        url = root + '/service-zuul/applet/login/basicInfo'
        headers = {
            'Content-Type': 'application/json;charset=utf-8',
            'User-Agent': ua,
            'Authorization': self.config.token,
        }
        resp = requests.get(url, headers=headers, proxies=None)
        api_resp = resp.json()
        return  api_resp

    def get_order_list(self):
        result = self._call_api(1,'getOrderList?type=0',{})
        return result

    def chose_room(self,room_id:str, start_time:int,end_time:int):
        result = self._call_api(2,'placeAnOrder',{"device": room_id,'subscribeList': [{"startTime": start_time, "endTime": end_time, "aiMonitoringNum": None}]})
        return result

    def cancel_room(self,order_id:int):
        result = self._call_api(2, 'cancel', {'id': order_id, type:'6'})
        return result

    def find_available_rooms(self):
        results = []
        with open('devices_data.csv', mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if "无钢琴" not in row['Instruments']:
                    device_id = int(row['ID'])
                    api_response = self._call_api(1, 'getReserveInformation?device='+str(device_id),{})
                    results.append(self.parse_response(api_response))
        return results

    def parse_response(self, api_response):
        if api_response['status'] != 200:
            return {'error': 'API call failed'}
        data = api_response['data']
        return {
            'openDays': data['openDays'],
            'startTime': data['startTime'],
            'endTime': data['endTime'],
            'remainingTimeList': data['remainingTimeList']
        }