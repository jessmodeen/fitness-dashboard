import os
import secrets
import requests
from datetime import datetime
from urllib.parse import urlencode

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from dotenv import load_dotenv

from token_store import TokenStore
from whoop_client import WhoopClient
from strava_client import StravaClient
from claude_client import generate_recommendation

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

token_store = TokenStore()

WHOOP_AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
WHOOP_TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"


# ─── Jinja2 helpers ──────────────────────────────────────────────────────────

@app.template_filter("ms_to_hm")
def ms_to_hm(ms):
    if not ms:
        return "—"
    total_min = int(ms) // 60000
    h, m = divmod(total_min, 60)
    return f"{h}h {m}m"


@app.template_filter("ms_to_min")
def ms_to_min(ms):
    if not ms:
        return "—"
    return f"{int(ms) // 60000} min"


@app.template_filter("round1")
def round1(val):
    try:
        return round(float(val), 1)
    except (TypeError, ValueError):
        return val


@app.context_processor
def inject_now():
    return {"now": datetime.now()}


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    whoop_tokens = token_store.get("whoop")
    strava_tokens = token_store.get("strava")

    if not whoop_tokens and not strava_tokens:
        return redirect(url_for("setup"))

    data = {}
    errors = {}

    if whoop_tokens:
        try:
            whoop = WhoopClient(whoop_tokens, token_store)
            data["recovery"] = whoop.get_latest_recovery()
            data["sleep"] = whoop.get_latest_sleep()
            data["cycle"] = whoop.get_latest_cycle()
            data["workouts"] = whoop.get_recent_workouts(limit=5)
        except Exception as e:
            errors["whoop"] = str(e)

    if strava_tokens:
        try:
            strava = StravaClient(strava_tokens, token_store)
            data["strava_activities"] = strava.get_recent_activities(limit=7)
        except Exception as e:
            errors["strava"] = str(e)

    return render_template(
        "dashboard.html",
        data=data,
        errors=errors,
        whoop_connected=bool(whoop_tokens),
        strava_connected=bool(strava_tokens),
    )


@app.route("/setup")
def setup():
    missing = []
    for key in ("WHOOP_CLIENT_ID", "WHOOP_CLIENT_SECRET", "STRAVA_CLIENT_ID",
                "STRAVA_CLIENT_SECRET", "ANTHROPIC_API_KEY", "FLASK_SECRET_KEY"):
        if not os.environ.get(key) or os.environ.get(key, "").startswith("paste_"):
            missing.append(key)

    return render_template(
        "setup.html",
        whoop_connected=bool(token_store.get("whoop")),
        strava_connected=bool(token_store.get("strava")),
        anthropic_configured=bool(
            os.environ.get("ANTHROPIC_API_KEY")
            and not os.environ.get("ANTHROPIC_API_KEY", "").startswith("paste_")
        ),
        missing_env=missing,
    )


# ─── Whoop OAuth ─────────────────────────────────────────────────────────────

@app.route("/auth/whoop")
def auth_whoop():
    state = secrets.token_urlsafe(16)
    session["whoop_oauth_state"] = state

    params = {
        "client_id": os.environ.get("WHOOP_CLIENT_ID", ""),
        "redirect_uri": url_for("auth_whoop_callback", _external=True),
        "response_type": "code",
        "scope": "offline read:recovery read:sleep read:workout read:cycles read:body_measurement",
        "state": state,
    }
    return redirect(f"{WHOOP_AUTH_URL}?{urlencode(params)}")


@app.route("/auth/whoop/callback")
def auth_whoop_callback():
    if request.args.get("state") != session.pop("whoop_oauth_state", None):
        return render_template("error.html", message="Security check failed (state mismatch). Please try again."), 400

    code = request.args.get("code")
    if not code:
        err = request.args.get("error_description", request.args.get("error", "Unknown error"))
        return render_template("error.html", message=f"Whoop authorization failed: {err}"), 400

    try:
        resp = requests.post(
            WHOOP_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": url_for("auth_whoop_callback", _external=True),
                "client_id": os.environ["WHOOP_CLIENT_ID"],
                "client_secret": os.environ["WHOOP_CLIENT_SECRET"],
            },
            timeout=15,
        )
        resp.raise_for_status()
        token_store.set("whoop", resp.json())
    except Exception as e:
        return render_template("error.html", message=f"Failed to connect Whoop: {e}"), 500

    return redirect(url_for("setup"))


# ─── Strava OAuth ────────────────────────────────────────────────────────────

@app.route("/auth/strava")
def auth_strava():
    state = secrets.token_urlsafe(16)
    session["strava_oauth_state"] = state

    params = {
        "client_id": os.environ.get("STRAVA_CLIENT_ID", ""),
        "redirect_uri": url_for("auth_strava_callback", _external=True),
        "response_type": "code",
        "scope": "activity:read_all",
        "state": state,
        "approval_prompt": "auto",
    }
    return redirect(f"{STRAVA_AUTH_URL}?{urlencode(params)}")


@app.route("/auth/strava/callback")
def auth_strava_callback():
    if request.args.get("state") != session.pop("strava_oauth_state", None):
        return render_template("error.html", message="Security check failed (state mismatch). Please try again."), 400

    code = request.args.get("code")
    if not code:
        err = request.args.get("error", "Unknown error")
        return render_template("error.html", message=f"Strava authorization failed: {err}"), 400

    try:
        resp = requests.post(
            STRAVA_TOKEN_URL,
            data={
                "client_id": os.environ["STRAVA_CLIENT_ID"],
                "client_secret": os.environ["STRAVA_CLIENT_SECRET"],
                "code": code,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
        resp.raise_for_status()
        token_store.set("strava", resp.json())
    except Exception as e:
        return render_template("error.html", message=f"Failed to connect Strava: {e}"), 500

    return redirect(url_for("setup"))


@app.route("/auth/disconnect/<service>")
def disconnect(service):
    if service in ("whoop", "strava"):
        token_store.delete(service)
    return redirect(url_for("setup"))


# ─── API endpoints (called by JS) ────────────────────────────────────────────

@app.route("/api/recommendation")
def api_recommendation():
    whoop_tokens = token_store.get("whoop")
    strava_tokens = token_store.get("strava")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return jsonify({"success": False, "error": "ANTHROPIC_API_KEY is not set in your .env file."}), 400

    data = {}

    if whoop_tokens:
        try:
            whoop = WhoopClient(whoop_tokens, token_store)
            data["recovery"] = whoop.get_latest_recovery()
            data["sleep"] = whoop.get_latest_sleep()
            data["cycle"] = whoop.get_latest_cycle()
            data["workouts"] = whoop.get_recent_workouts(limit=5)
        except Exception as e:
            data["whoop_error"] = str(e)

    if strava_tokens:
        try:
            strava = StravaClient(strava_tokens, token_store)
            data["strava_activities"] = strava.get_recent_activities(limit=7)
        except Exception as e:
            data["strava_error"] = str(e)

    try:
        recommendation = generate_recommendation(data)
        return jsonify({"success": True, "recommendation": recommendation})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("FLASK_PORT", 5000))
    print(f"\n  Dashboard → http://localhost:{port}\n")
    app.run(debug=True, port=port)
