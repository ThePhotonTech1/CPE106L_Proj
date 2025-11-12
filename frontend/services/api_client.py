import requests

class ApiClient:
    def __init__(self, base_url: str, token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token

    # NEW: allow GUI to set/clear the token
    def set_token(self, token: str | None):
        self.token = token

    def clear_token(self):
        self.token = None

    def headers(self):
        h = {"Accept": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def get(self, path: str, **kwargs):
        return requests.get(f"{self.base_url}{path}", headers=self.headers(), **kwargs)

    def post(self, path: str, json=None, params=None, **kwargs):
        return requests.post(
            f"{self.base_url}{path}",
            json=json,
            params=params,
            headers=self.headers(),
            **kwargs,
        )
