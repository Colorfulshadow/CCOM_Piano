"""
@Author: Tianyi Zhang
@Date: 2025/4/26
@Description: 
"""
import requests
import json
from flask import current_app
from app.models.room import Room
from app import db
import csv
import os
import time
from app.utils.exceptions import ApiError, LoginError, AlreadyChosen, FailedToChoose, FailedToDelChosen, FailedToFind


class CCOMClient:
    def __init__(self, username, password=None, token=None):
        """
        Initialize CCOM client

        Args:
            username: CCOM username
            password: CCOM password - can be None if token is provided
            token: Authentication token - can be None if password is provided
        """
        self.username = username
        self.password = password  # Now accepts password directly
        self.token = token
        self.root = current_app.config['CCOM_API_ROOT']
        self.ua = current_app.config['CCOM_API_UA']

    def soft_login(self):
        """Try to use existing token, fall back to full login if that fails"""
        if self.token:
            try:
                result = self.get_basic_info()
                if result['data']['studentNumber'].lower() == self.username.lower():
                    current_app.logger.info(f"Soft login successful for user {self.username}")
                    return True
            except Exception as e:
                current_app.logger.error(f"Soft login failed: {str(e)}")

        # Only attempt login if we have a password
        if self.password:
            return self.login()
        else:
            raise LoginError("No password or valid token available for login")

    def login(self):
        """Perform full login to the CCOM system"""
        if not self.password:
            raise LoginError("Password is required for login")

        url = f"{self.root}/service-zuul/applet/login/login"
        headers = {'Content-Type': 'application/json;charset=UTF-8'}
        body = {
            "accountNumber": self.username,
            "lessee": "151",
            "password": self.password,
            "code": None
        }

        try:
            body_json = json.dumps(body)
            headers['Content-Length'] = str(len(body_json))
            resp = requests.post(url, headers=headers, data=body_json, proxies=None)
            resp_data = resp.json()

            if resp_data.get('status') == 200 and resp_data.get('msg') == '成功':
                self.token = resp_data['data']['token']
                current_app.logger.info(f"Login successful for user {self.username}")
                return True
            else:
                current_app.logger.error(f"Login failed: {resp_data}")
                raise LoginError(f"Login failed: {resp_data.get('msg')}")
        except Exception as e:
            current_app.logger.error(f"Login error: {str(e)}")
            raise LoginError(f"Login error: {str(e)}")

    def _call_api(self, method, api_name, data=None):
        """Generic method to call CCOM API endpoints"""
        if self.token is None:
            raise LoginError("You must call `login` or `soft_login` before calling other APIs")

        url = f"{self.root}/order/applet/order/{api_name}"
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'User-Agent': self.ua,
            'Authorization': self.token,
        }

        try:
            if method.lower() == 'get':
                resp = requests.get(url, headers=headers, proxies=None)
            elif method.lower() == 'post':
                resp = requests.post(url, json=data, headers=headers, proxies=None)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if resp.status_code != 200:
                raise ApiError(f"Server error with HTTP status code: {resp.status_code}")

            return resp.json()
        except Exception as e:
            current_app.logger.error(f"API call error: {str(e)}")
            raise ApiError(f"API call error: {str(e)}")

    def get_basic_info(self):
        """Get user's basic information"""
        url = f"{self.root}/service-zuul/applet/login/basicInfo"
        headers = {
            'Content-Type': 'application/json;charset=utf-8',
            'User-Agent': self.ua,
            'Authorization': self.token,
        }

        resp = requests.get(url, headers=headers, proxies=None)
        return resp.json()

    def get_order_list(self):
        """Get user's current reservations"""
        return self._call_api('get', 'getOrderList?type=0', {})

    def reserve_room(self, room_id, start_time, end_time, max_retries=4, retry_delay=0.1):
        """Make a room reservation with retry logic in case of failure"""
        data = {
            "device": room_id,
            'subscribeList': [{"startTime": start_time, "endTime": end_time, "aiMonitoringNum": None}]
        }

        for attempt in range(max_retries):
            try:
                result = self._call_api('post', 'placeAnOrder', data)
                return result
            except ApiError as e:
                current_app.logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)  # Wait before retrying
                else:
                    raise
        return None


    def cancel_reservation(self, order_id):
        """Cancel an existing reservation"""
        data = {'id': order_id, 'type': '6'}
        result = self._call_api('post', 'cancel', data)
        return result

    def find_available_rooms(self, piano_only=True):
        """Find all available rooms, optionally filtering for piano rooms only"""
        results = []
        rooms = Room.query.all()

        for room in rooms:
            # Skip non-piano rooms if piano_only is True
            if piano_only and "无钢琴" in (room.instruments or ""):
                continue

            device_id = int(room.ccom_id)
            api_response = self._call_api('get', f'getReserveInformation?device={device_id}', {})
            parsed_response = self._parse_response(api_response)
            parsed_response['room'] = {
                'id': room.id,
                'ccom_id': room.ccom_id,
                'name': room.name,
                'partition': room.partition,
                'instruments': room.instruments
            }
            results.append(parsed_response)

        return results

    def find_room_availability(self, room_id):
        """Check availability for a specific room"""
        device_id = Room.query.get(room_id).ccom_id
        api_response = self._call_api('get', f'getReserveInformation?device={device_id}', {})
        return self._parse_response(api_response)

    def _parse_response(self, api_response):
        """Parse the availability response from the API"""
        if api_response['status'] != 200:
            return {'error': 'API call failed', 'details': api_response}

        data = api_response['data']
        return {
            'openDays': data.get('openDays', []),
            'startTime': data.get('startTime'),
            'endTime': data.get('endTime'),
            'remainingTimeList': data.get('remainingTimeList', [])
        }