import os
import time
import requests

STRAVA_API_BASE = "https://www.strava.com/api/v3"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"


class StravaClient:
    def __init__(self, tokens, token_store):
        self.tokens = tokens
        self.token_store = token_store
        self._ensure_valid_token()

    def _ensure_valid_token(self):
        # Strava access tokens expire after 6 hours; expires_at is a Unix timestamp
        expires_at = self.tokens.get("expires_at", 0)
        if time.time() > expires_at - 60:
            self._refresh_token()

    def _refresh_token(self):
        resp = requests.post(
            STRAVA_TOKEN_URL,
            data={
                "client_id": os.environ["STRAVA_CLIENT_ID"],
                "client_secret": os.environ["STRAVA_CLIENT_SECRET"],
                "grant_type": "refresh_token",
                "refresh_token": self.tokens["refresh_token"],
            },
            timeout=15,
        )
        resp.raise_for_status()
        self.tokens = resp.json()
        self.token_store.set("strava", self.tokens)

    def _get(self, endpoint, params=None):
        headers = {"Authorization": f"Bearer {self.tokens['access_token']}"}
        resp = requests.get(
            f"{STRAVA_API_BASE}{endpoint}",
            headers=headers,
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def get_recent_activities(self, limit=7):
        return self._get("/athlete/activities", params={"per_page": limit})

    def get_athlete(self):
        return self._get("/athlete")
