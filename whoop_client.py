import os
import requests

WHOOP_API_BASE = "https://api.prod.whoop.com/developer/v1"
WHOOP_TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"

SPORT_NAMES = {
    -1: "Activity", 0: "Running", 1: "Cycling", 18: "Rowing",
    43: "Pilates", 44: "Yoga", 45: "Weightlifting", 65: "Walking",
    70: "Elliptical", 71: "Stairmaster", 79: "Indoor Cycling",
    83: "Spinning", 84: "Circuit Training", 86: "HIIT",
    88: "Cross Training", 89: "Cardiovascular", 126: "Strength Training",
}


class WhoopClient:
    def __init__(self, tokens, token_store):
        self.tokens = tokens
        self.token_store = token_store

    def _refresh_token(self):
        resp = requests.post(
            WHOOP_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.tokens["refresh_token"],
                "client_id": os.environ["WHOOP_CLIENT_ID"],
                "client_secret": os.environ["WHOOP_CLIENT_SECRET"],
            },
            timeout=15,
        )
        resp.raise_for_status()
        self.tokens = resp.json()
        self.token_store.set("whoop", self.tokens)

    def _get(self, endpoint, params=None):
        def _do_request():
            headers = {"Authorization": f"Bearer {self.tokens['access_token']}"}
            return requests.get(
                f"{WHOOP_API_BASE}{endpoint}",
                headers=headers,
                params=params,
                timeout=15,
            )
        resp = _do_request()
        if resp.status_code == 401:
            self._refresh_token()
            resp = _do_request()
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def get_latest_recovery(self):
        cycles = self._get("/cycle", params={"limit": 1})
        if not cycles:
            return None
        records = cycles.get("records", [])
        if not records:
            return None
        cycle_id = records[0]["id"]
        return self._get(f"/recovery/{cycle_id}")

    def get_latest_sleep(self):
        data = self._get("/activity/sleep", params={"limit": 1})
        if not data:
            return None
        records = data.get("records", [])
        for record in records:
            if not record.get("nap"):
                return record
        return records[0] if records else None

    def get_latest_cycle(self):
        data = self._get("/cycle", params={"limit": 1})
        if not data:
            return None
        records = data.get("records", [])
        return records[0] if records else None

    def get_recent_workouts(self, limit=5):
        data = self._get("/activity/workout", params={"limit": limit})
        if not data:
            return []
        workouts = data.get("records", [])
        for w in workouts:
            w["sport_name"] = SPORT_NAMES.get(w.get("sport_id", -1), "Workout")
        return workouts
