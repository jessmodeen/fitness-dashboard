# Morning Fitness Dashboard

A personal morning dashboard that pulls your **Whoop** recovery/sleep/strain data and **Strava** activity history, then uses **Claude AI** to generate a fully personalized daily training plan.

---

## What it does

Every morning, open your browser to `http://localhost:5000` and the dashboard will:

1. Show your **Whoop recovery score** (green/yellow/red), HRV, resting heart rate, and SpO2
2. Show last night's **sleep data** — total time, REM, deep sleep, disturbances
3. Show **yesterday's strain** and your most recent workouts
4. Show your **recent Strava activities** for training load context
5. **Auto-generate a complete daily training plan** using Claude AI, scaled to your recovery score:
   - A specific Peloton class recommendation
   - An upper body strength routine with exact weights/sets/reps
   - A daily core routine (mandatory every day)

---

## Setup (do this once)

### Requirements
- Python 3.9 or newer ([python.org/downloads](https://python.org/downloads))
- A Whoop account and Whoop developer credentials
- A Strava account and Strava API credentials
- An Anthropic API key

### Step 1 — Download and open the project folder

If you're reading this on GitHub, click the green **Code** button → **Download ZIP**, then unzip it. Or if you cloned it:

```
cd fitness-dashboard
```

### Step 2 — Run the setup script

Open your terminal (on Mac: Spotlight → Terminal) and type:

```bash
bash setup.sh
```

This creates a Python virtual environment and installs all dependencies.

### Step 3 — Fill in your API credentials

Open the `.env` file in any text editor (TextEdit on Mac, Notepad on Windows). You'll see placeholders for:

**Whoop credentials:**
1. Go to [developer.whoop.com](https://developer.whoop.com) — sign in with your Whoop account
2. Click **Create Application**
3. Set the **Redirect URI** to exactly: `http://localhost:5000/auth/whoop/callback`
4. Copy your **Client ID** → paste as `WHOOP_CLIENT_ID`
5. Copy your **Client Secret** → paste as `WHOOP_CLIENT_SECRET`

**Strava credentials:**
1. Go to [strava.com/settings/api](https://www.strava.com/settings/api)
2. Create an app; set **Authorization Callback Domain** to `localhost`
3. Copy **Client ID** → `STRAVA_CLIENT_ID`
4. Copy **Client Secret** → `STRAVA_CLIENT_SECRET`

**Anthropic (Claude AI):**
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Click **API Keys** → **Create Key**
3. Paste as `ANTHROPIC_API_KEY`

**Flask secret key** (one-time, run this in your terminal):
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```
Paste the output as `FLASK_SECRET_KEY`.

### Step 4 — Start the dashboard

```bash
bash run.sh
```

Then open [http://localhost:5000](http://localhost:5000) in your browser.

You'll see a **Setup page** — click the buttons to connect Whoop and Strava (this opens their login pages and brings you back automatically).

### Step 5 — Done!

Click **Open Dashboard**. Your morning dashboard is ready. Every time you want to use it, just run `bash run.sh`.

---

## Every morning

1. Run `bash run.sh` (or keep it running)
2. Open [http://localhost:5000](http://localhost:5000)
3. Your Whoop data loads instantly; Claude generates your plan in ~10 seconds
4. Follow your plan!

---

## Project structure

```
fitness-dashboard/
├── app.py              # Flask web server + OAuth flows
├── whoop_client.py     # Whoop API wrapper
├── strava_client.py    # Strava API wrapper
├── claude_client.py    # Claude AI recommendation generator
├── token_store.py      # Stores OAuth tokens securely in your home folder
├── requirements.txt    # Python dependencies
├── .env.example        # Credentials template (copy → .env and fill in)
├── setup.sh            # First-time setup script
├── run.sh              # Start the dashboard
├── templates/          # HTML pages
└── static/             # CSS + JavaScript
```

Your OAuth tokens are stored in `~/.fitness_dashboard_tokens.json` (in your home folder, never in the git repo).

---

## Security notes

- Your `.env` file is in `.gitignore` — it will never be committed to git
- API tokens are stored locally in your home folder, not in the project
- This is a single-user personal tool; don't expose it to the internet
