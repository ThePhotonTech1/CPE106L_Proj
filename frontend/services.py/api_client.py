# frontend/services/api_client.py
import os, requests

API_URL = os.getenv("FOODBRIDGE_API_URL", "http://127.0.0.1:8000")

class ApiClient:
    def __init__(self):
        self.token = None

    def set_token(self, token: str):
        self.token = token

    def _headers(self):
        h = {"Accept":"application/json","Content-Type":"application/json"}
        if self.token: h["Authorization"] = f"Bearer {self.token}"
        return h

    def get(self, path: str):
        r = requests.get(API_URL + path, headers=self._headers(), timeout=15)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, json=None):
        r = requests.post(API_URL + path, headers=self._headers(), json=json, timeout=20)
        r.raise_for_status()
        return r.json()

