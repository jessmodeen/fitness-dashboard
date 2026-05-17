import os
import requests

WHOOP_API_BASE = "https://api.prod.whoop.com/developer/v1"
WHOOP_TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"

SPORT_NAMES = {
    -1: "Activity",
    0: "Running",
    1: "Cycling",
    16: "Baseball",
    17: "Basketball",
    18: "Rowing",
    21: "Football",
    27: "Rugby",
    29: "Skiing",
    30: "Soccer",
    33: "Swimming",
    34: "Tennis",
    38: "Wrestling",
    39: "Boxing",
    43: "Pilates",
    44: "Yoga",
    45: "Weightlifting",
    52: "Hiking",
    56: "Martial Arts",
    57: "Mountain Biking",
    61: "Powerlifting",
    62: "Rock Climbing",
    64: "Triathlon",
    65: "Walking",
    66: "Surfing",
    70: "Elliptical",
    71: "Stairmaster",
    73: "Meditation",
    79: "Indoor Cycling",
    83: "Spinning",
    84: "Circuit Training",
    86: "HIIT",
    88: "Cross Training",
    89: "Cardiovascular",
    96: "Canoeing",
    108: "Snowboarding",
    126: "Strength Training",
}


class WhoopClient:
    def __init__(self, tokens, token_store):
        self.tokens = tokens
        self.token_store = token_store

    def _refresh_if_needed(self):
        # Whoop tokens include an expires_in but not always expires_at.
        # We always attempt a refresh on 401.
        pass

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
        resp.raise_for_status()
        return resp.json()

    def get_latest_recovery(self):
        # Recovery must be fetched by cycle ID — there is no list endpoint
        cycles = self._get("/cycle", params={"limit": 1})
        records = cycles.get("records", [])
        if not records:
            return None
        cycle_id = records[0]["id"]
        try:
            return self._get(f"/recovery/{cycle_id}")
        except Exception:
            return None

    def get_latest_sleep(self):
        data = self._get("/sleep", params={"limit": 1})
        records = data.get("records", [])
        # Skip naps
        for record in records:
            if not record.get("nap"):
                return record
        return records[0] if records else None

    def get_latest_cycle(self):
        data = self._get("/cycle", params={"limit": 1})
        records = data.get("records", [])
        return records[0] if records else None

    def get_recent_workouts(self, limit=5):
        data = self._get("/workout", params={"limit": limit})
        workouts = data.get("records", [])
        for w in workouts:
            w["sport_name"] = SPORT_NAMES.get(w.get("sport_id", -1), "Workout")
        return workouts
