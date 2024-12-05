import json
import os


class Config:
    __slots__ = ('path', '_username', '_password', '_token', '_send_keys')

    def __init__(self):
        self.path = os.path.join(os.path.dirname(__file__), 'config.json')
        self._username = ''
        self._password = ''
        self._token = ''
        self._send_keys = []
        if not os.path.exists(self.path):
            self._save()
            print("please fill config.json with username and password")
            exit(0)
        self._load()
        if not self._username or not self._password:
            print("please fill config.json with username and password")
            exit(0)

    def _save(self):
        c = {
            'username': self._username,
            'password': self._password,
            'token': self._token,
            'send_keys': self._send_keys
        }
        with open(self.path, 'w') as f:
            json.dump(c, f, indent=4)

    def _load(self):
        with open(self.path, 'r') as f:
            j = json.load(f)
            self._username = j['username']
            self._password = j['password']
            self._token = j['token']
            self._send_keys = j['send_keys']

    @property
    def username(self):
        return self._username

    @username.setter
    def username(self, value):
        self._username = value
        self._save()

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, value):
        self._password = value
        self._save()

    @property
    def token(self):
        return self._token

    @token.setter
    def token(self, value):
        self._token = value
        self._save()

    @property
    def send_keys(self):
        return self._send_keys

    @send_keys.setter
    def send_keys(self, values):
        self._send_keys = values
        self._save()


config = Config()

root = "https://saas.tansiling.com"

ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.109 Safar"