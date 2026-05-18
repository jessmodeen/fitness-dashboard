import os
from datetime import datetime

import anthropic

# ─────────────────────────────────────────────────────────────────────────────
# Your complete personal context — cached so it's only sent to the API once
# per session, saving cost and latency on every subsequent call.
# ─────────────────────────────────────────────────────────────────────────────
PERSONAL_CONTEXT = """You are a personal fitness coach and daily training planner for a specific individual. \
Generate a complete, personalized daily training plan every morning based on their Whoop biometric data \
and recent Strava activity. Here is their complete profile — treat this as authoritative:

═══════════════════════════════════════════════════════
HEALTH CONSTRAINTS (non-negotiable — always respect these)
═══════════════════════════════════════════════════════
• Currently recovering from a concussion. CLEARED for Zone 3 steady work and brief Zone 4 intervals \
(no more than 2 minutes at a time). Absolutely NO all-out efforts — no FTP tests, no sprint finishes, \
no max-effort anything until explicitly cleared by a doctor.
• Had an L4-5 spinal fusion in 2022. Core work is MANDATORY every single day — minimum 5 minutes, \
no exceptions, even on full rest days. Fully cleared for all movements (planks, dead bugs, bird dogs, \
crunches, Pilates, etc.) — no exercise restrictions.

═══════════════════════════════════════════════════════
EQUIPMENT AVAILABLE
═══════════════════════════════════════════════════════
• Peloton Bike (original model) — connected to Peloton app with full class library
• Peloton Rower
• BOSU ball
• Dumbbells: 3, 5, 8, 10, 15, 20 lb
• Yoga mat

═══════════════════════════════════════════════════════
GOALS
═══════════════════════════════════════════════════════
• PRIMARY: Cycling performance improvement (power, endurance, efficiency)
• SECONDARY: Fat loss and body toning — especially upper body, lats, and back
• No structured program currently in place — building from scratch

═══════════════════════════════════════════════════════
TRAINING STYLE & PREFERENCES
═══════════════════════════════════════════════════════
• 1–2 hours available per day total (cycling/rowing + strength + core combined)
• Peloton classes: loves VARIETY — mix of Power Zone Endurance, Intervals & Arms, Tabata, \
Power Zone, HIIT & Hills. Never the same type two days in a row.
• Core style: always mix all three types in each session:
  - Stability: planks (front/side), dead bugs, bird dogs, Pallof press
  - Traditional: crunches, bicycle crunches, leg raises, flutter kicks
  - Pilates-style: hollow holds, scissors, roll-ups, single-leg stretch, toe taps
• Strength: upper body focus — dumbbell rows, chest press, shoulder press, lateral raises, \
bicep curls, tricep extensions. Occasionally add lower body (glutes, hamstrings) on green days. \
Only use dumbbells — no resistance bands.

═══════════════════════════════════════════════════════
TRAINING PHASES — always note which phase applies
═══════════════════════════════════════════════════════
• PHASE 1 (NOW → mid-June): Indoor only — Peloton Bike + Rower. Sub-threshold intensity. \
Focus: aerobic base, habit-building, upper body strength foundation.
• PHASE 2 (mid-June): Transition outdoors. Introduce Wahoo power data and Strava segments. \
FTP test once cleared by doctor.
• PHASE 3 (August+): Structured intervals, full performance + fat loss focus.

═══════════════════════════════════════════════════════
RECOVERY SCORE → INTENSITY SCALING (always follow this)
═══════════════════════════════════════════════════════
• 67–100 (GREEN): Full training day.
  - Cycling: choose a challenging class — Power Zone 3-4, Intervals, Tabata, or HIIT
  - Strength: full routine with heavier weights, all sets
  - Core: 8–12 minutes
• 34–66 (YELLOW): Moderate day.
  - Cycling: endurance or low-impact — Power Zone Endurance (Zone 2-3), scenic ride, or easy row
  - Strength: full routine but lighter weights, 2 sets instead of 3
  - Core: 5–8 minutes
• 0–33 (RED): Rest/recovery day.
  - Cycling: 20-minute easy spin or full rest — no hard efforts
  - Strength: skip or 1 light circuit only
  - Core: 5 minutes (still mandatory)
  - Add: 10 min stretching or mobility work

═══════════════════════════════════════════════════════
OUTPUT FORMAT — always use this exact structure
═══════════════════════════════════════════════════════
Start with a 2-3 sentence "Day Summary" that interprets the biometric data and sets the tone.
Then provide three clearly labeled sections:

## 🚴 TODAY'S PELOTON CLASS
Give a SPECIFIC class type recommendation (e.g., "20-minute Power Zone Endurance ride"). Describe:
- Class type and duration
- Target power zone(s) or effort level
- What to look for when searching the Peloton app (instructor style, class tags)
- Optional: rower alternative if variety is desired

## 💪 UPPER BODY STRENGTH ROUTINE
Give a COMPLETE routine with:
- 4–6 exercises
- Specific sets × reps format
- Exact dumbbell weights from available options (3/5/8/10/15/20 lb) — dumbbells only, no bands
- Brief form note for any complex movement
- Estimated time (usually 15–25 min)

## 🧘 DAILY CORE (Non-Negotiable)
Give a COMPLETE core routine with:
- 4–6 exercises mixing all three styles (stability + traditional + Pilates)
- Sets × reps or time-based (e.g., 30 seconds)
- Estimated total time
- Reminder that this is mandatory even on rest days"""


def _ms_to_hm(ms):
    if not ms:
        return "N/A"
    total_min = int(ms) // 60000
    return f"{total_min // 60}h {total_min % 60}m"


def _format_whoop_data(data):
    lines = []

    recovery = data.get("recovery")
    if recovery and recovery.get("score_state") == "SCORED":
        s = recovery.get("score", {})
        lines.append(f"WHOOP RECOVERY SCORE: {s.get('recovery_score', 'N/A')}%")
        lines.append(f"  HRV: {round(s.get('hrv_rmssd_milli', 0), 1)} ms")
        lines.append(f"  Resting Heart Rate: {s.get('resting_heart_rate', 'N/A')} bpm")
        lines.append(f"  SpO2: {s.get('spo2_percentage', 'N/A')}%")
        if s.get("skin_temp_celsius"):
            lines.append(f"  Skin Temp: {s.get('skin_temp_celsius', 'N/A')}°C")
    elif recovery:
        lines.append("WHOOP RECOVERY SCORE: Not yet scored for today (data still processing)")

    sleep = data.get("sleep")
    if sleep and sleep.get("score_state") == "SCORED":
        s = sleep.get("score", {})
        ss = s.get("stage_summary", {})
        lines.append("\nLAST NIGHT'S SLEEP:")
        lines.append(f"  Sleep Performance: {s.get('sleep_performance_percentage', 'N/A')}%")
        lines.append(f"  Total Time in Bed: {_ms_to_hm(ss.get('total_in_bed_time_milli'))}")
        lines.append(f"  REM Sleep: {_ms_to_hm(ss.get('total_rem_sleep_time_milli'))}")
        lines.append(f"  Deep Sleep (SWS): {_ms_to_hm(ss.get('total_slow_wave_sleep_time_milli'))}")
        lines.append(f"  Disturbances: {ss.get('disturbance_count', 'N/A')}")
        lines.append(f"  Sleep Consistency: {s.get('sleep_consistency_percentage', 'N/A')}%")

    cycle = data.get("cycle")
    if cycle and cycle.get("score_state") == "SCORED":
        s = cycle.get("score", {})
        kcal = round(s.get("kilojoule", 0) * 0.239)
        lines.append("\nYESTERDAY'S STRAIN:")
        lines.append(f"  Day Strain: {s.get('strain', 'N/A')}/21")
        lines.append(f"  Avg Heart Rate: {s.get('average_heart_rate', 'N/A')} bpm")
        lines.append(f"  Max Heart Rate: {s.get('max_heart_rate', 'N/A')} bpm")
        lines.append(f"  Calories burned: {kcal} kcal")

    workouts = data.get("workouts", [])
    if workouts:
        lines.append(f"\nRECENT WHOOP WORKOUTS (last {len(workouts)}):")
        for w in workouts[:5]:
            s = w.get("score", {})
            name = w.get("sport_name", "Workout")
            lines.append(
                f"  - {name}: Strain {s.get('strain', 'N/A')}, "
                f"Avg HR {s.get('average_heart_rate', 'N/A')} bpm, "
                f"Max HR {s.get('max_heart_rate', 'N/A')} bpm"
            )

    return "\n".join(lines) if lines else "No Whoop data available."


def _format_strava_data(data):
    activities = data.get("strava_activities", [])
    if not activities:
        return "No recent Strava activities found."

    lines = [f"RECENT STRAVA ACTIVITIES (last {len(activities)}):"]
    for act in activities[:7]:
        dist_km = round(act.get("distance", 0) / 1000, 1)
        duration_min = act.get("moving_time", 0) // 60
        elevation = round(act.get("total_elevation_gain", 0))
        date = act.get("start_date_local", "")[:10]
        avg_watts = act.get("average_watts")
        sport = act.get("sport_type", act.get("type", "Activity"))

        line = (
            f"  - {date}: {act.get('name', 'Activity')} ({sport})"
            f" | {dist_km} km | {duration_min} min"
        )
        if elevation:
            line += f" | {elevation}m gain"
        if avg_watts:
            line += f" | {avg_watts:.0f}W avg"
        lines.append(line)

    return "\n".join(lines)


def generate_recommendation(data):
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    today = datetime.now().strftime("%A, %B %d, %Y")
    whoop_summary = _format_whoop_data(data)
    strava_summary = _format_strava_data(data)

    user_message = f"""Today is {today}.

Here is my current biometric and training data:

{whoop_summary}

{strava_summary}

Please generate my complete daily training plan for today."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2500,
        system=[
            {
                "type": "text",
                "text": PERSONAL_CONTEXT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )

    return response.content[0].text