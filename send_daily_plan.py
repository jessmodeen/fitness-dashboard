#!/usr/bin/env python3

import base64
import os
import re
import smtplib
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic
import requests
from fpdf import FPDF
from nacl import encoding as nacl_encoding
from nacl import public as nacl_public

WHOOP_V1 = "https://api.prod.whoop.com/developer/v1"
WHOOP_V2 = "https://api.prod.whoop.com/developer/v2"
WHOOP_TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
TO_EMAIL = "modeenjessica@gmail.com"

SPORT_NAMES = {
    -1: "Activity", 0: "Running", 1: "Cycling", 18: "Rowing",
    43: "Pilates", 44: "Yoga", 45: "Weightlifting", 65: "Walking",
    70: "Elliptical", 71: "Stairmaster", 79: "Indoor Cycling",
    83: "Spinning", 84: "Circuit Training", 86: "HIIT",
    88: "Cross Training", 89: "Cardiovascular", 126: "Strength Training",
}


def refresh_whoop_token():
    resp = requests.post(WHOOP_TOKEN_URL, data={
        "grant_type": "refresh_token",
        "refresh_token": os.environ["WHOOP_REFRESH_TOKEN"],
        "client_id": os.environ["WHOOP_CLIENT_ID"],
        "client_secret": os.environ["WHOOP_CLIENT_SECRET"],
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()


def whoop_get(access_token, base, endpoint, params=None):
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(f"{base}{endpoint}", headers=headers, params=params, timeout=15)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def fetch_whoop_data(access_token):
    data = {}

    cycles = whoop_get(access_token, WHOOP_V1, "/cycle", {"limit": 5})
    if cycles:
        for record in cycles.get("records", []):
            recovery = whoop_get(access_token, WHOOP_V2, f"/cycle/{record['id']}/recovery")
            if recovery and recovery.get("score_state") == "SCORED":
                data["recovery"] = recovery
                break

    sleep_data = whoop_get(access_token, WHOOP_V2, "/activity/sleep", {"limit": 1})
    if sleep_data:
        records = sleep_data.get("records", [])
        for r in records:
            if not r.get("nap"):
                data["sleep"] = r
                break
        if "sleep" not in data and records:
            data["sleep"] = records[0]

    cycle_data = whoop_get(access_token, WHOOP_V1, "/cycle", {"limit": 2})
    if cycle_data:
        records = cycle_data.get("records", [])
        if len(records) > 1 and records[1].get("score_state") == "SCORED":
            data["cycle"] = records[1]
        elif records:
            data["cycle"] = records[0]

    workout_data = whoop_get(access_token, WHOOP_V1, "/activity/workout", {"limit": 5})
    if workout_data:
        workouts = workout_data.get("records", [])
        for w in workouts:
            w["sport_name"] = SPORT_NAMES.get(w.get("sport_id", -1), "Workout")
        data["workouts"] = workouts

    return data


def rotate_whoop_refresh_token(new_refresh_token):
    pat = os.environ.get("GH_PAT")
    repo = os.environ.get("GH_REPO")
    if not pat or not repo:
        print("Warning: GH_PAT/GH_REPO not set -- skipping token rotation")
        return

    headers = {
        "Authorization": f"token {pat}",
        "Accept": "application/vnd.github.v3+json",
    }
    r = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers=headers,
    )
    r.raise_for_status()
    key_data = r.json()

    pk = nacl_public.PublicKey(key_data["key"].encode(), nacl_encoding.Base64Encoder())
    encrypted = base64.b64encode(
        nacl_public.SealedBox(pk).encrypt(new_refresh_token.encode())
    ).decode()

    r = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/WHOOP_REFRESH_TOKEN",
        headers=headers,
        json={"encrypted_value": encrypted, "key_id": key_data["key_id"]},
    )
    r.raise_for_status()
    print("Whoop refresh token rotated successfully")


def _ms_to_hm(ms):
    if not ms:
        return "N/A"
    total_min = int(ms) // 60000
    return f"{total_min // 60}h {total_min % 60}m"


def format_whoop_summary(data):
    lines = []
    recovery = data.get("recovery")
    if recovery and recovery.get("score_state") == "SCORED":
        s = recovery.get("score", {})
        lines.append(f"WHOOP RECOVERY SCORE: {s.get('recovery_score', 'N/A')}%")
        lines.append(f"  HRV: {round(s.get('hrv_rmssd_milli', 0), 1)} ms")
        lines.append(f"  Resting Heart Rate: {s.get('resting_heart_rate', 'N/A')} bpm")
        lines.append(f"  SpO2: {s.get('spo2_percentage', 'N/A')}%")

    sleep = data.get("sleep")
    if sleep and sleep.get("score_state") == "SCORED":
        s = sleep.get("score", {})
        ss = s.get("stage_summary", {})
        lines.append("\nLAST NIGHT'S SLEEP:")
        lines.append(f"  Sleep Performance: {s.get('sleep_performance_percentage', 'N/A')}%")
        lines.append(f"  Total Time in Bed: {_ms_to_hm(ss.get('total_in_bed_time_milli'))}")
        lines.append(f"  REM Sleep: {_ms_to_hm(ss.get('total_rem_sleep_time_milli'))}")
        lines.append(f"  Deep Sleep: {_ms_to_hm(ss.get('total_slow_wave_sleep_time_milli'))}")
        lines.append(f"  Disturbances: {ss.get('disturbance_count', 'N/A')}")

    cycle = data.get("cycle")
    if cycle and cycle.get("score_state") == "SCORED":
        s = cycle.get("score", {})
        lines.append("\nYESTERDAY'S STRAIN:")
        lines.append(f"  Day Strain: {round(s.get('strain', 0), 1)}/21")
        lines.append(f"  Avg HR: {s.get('average_heart_rate', 'N/A')} bpm")

    return "\n".join(lines) if lines else "No Whoop data available."


def generate_plan(whoop_data):
    from claude_client import PERSONAL_CONTEXT
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    today = datetime.now().strftime("%A, %B %d, %Y")
    user_msg = f"""Today is {today}.

{format_whoop_summary(whoop_data)}

Please generate my complete daily training plan for today."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2500,
        system=[{"type": "text", "text": PERSONAL_CONTEXT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_msg}],
    )
    return response.content[0].text


def _strip_emoji(text):
    return re.sub(r'[^\x00-\x7F]', '', text)


def _plain_bullets(section_text):
    items = []
    for line in section_text.split("\n"):
        line = line.strip()
        if re.match(r'^[-*]|\d+\.', line):
            line = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
            line = re.sub(r'^[-*\d.]\s*', '', line).strip()
            if line:
                items.append(f"  - {line}")
    return "\n".join(items)


def _first_lines(section_text, n=3):
    lines = []
    for line in section_text.split("\n"):
        line = re.sub(r'\*\*(.+?)\*\*', r'\1', line.strip())
        line = line.lstrip('#- *').strip()
        if line and not re.match(r'TODAY.S PELOTON|UPPER BODY|DAILY CORE', line, re.I):
            lines.append(line)
        if len(lines) >= n:
            break
    return "\n".join(lines)


def build_email_body(plan_text, whoop_data, date_str):
    recovery = whoop_data.get("recovery")
    recovery_line = ""
    if recovery and recovery.get("score_state") == "SCORED":
        s = recovery.get("score", {})
        score = s.get("recovery_score", 0)
        hrv = round(s.get("hrv_rmssd_milli", 0), 1)
        rhr = s.get("resting_heart_rate", "--")
        label = "Green" if score >= 67 else "Yellow" if score >= 34 else "Red"
        recovery_line = f"Recovery: {score}% ({label})  |  HRV: {hrv}ms  |  RHR: {rhr}bpm"

    sections = re.split(r'\n##\s+', "\n" + _strip_emoji(plan_text))
    cardio = strength = core = ""
    for s in sections:
        if re.match(r'TODAY.S PELOTON', s, re.I):
            cardio = _first_lines(s, 3)
        elif re.match(r'UPPER BODY', s, re.I):
            strength = _plain_bullets(s)
        elif re.match(r'DAILY CORE', s, re.I):
            core = _plain_bullets(s)

    divider = "-" * 44
    return "\n".join([
        f"Good morning! Here is your training plan for {date_str}.",
        "",
        recovery_line,
        "",
        divider,
        "CARDIO",
        divider,
        cardio,
        "",
        divider,
        "STRENGTH",
        divider,
        strength,
        "",
        divider,
        "CORE  (non-negotiable)",
        divider,
        core,
        "",
        "Full plan attached as PDF.",
    ])


def generate_pdf(plan_text, date_str, whoop_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(auto=True, margin=20)

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 10, "Daily Training Plan", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 6, date_str, ln=True)
    pdf.ln(4)

    recovery = whoop_data.get("recovery")
    if recovery and recovery.get("score_state") == "SCORED":
        s = recovery.get("score", {})
        score = s.get("recovery_score", 0)
        hrv = round(s.get("hrv_rmssd_milli", 0), 1)
        rhr = s.get("resting_heart_rate", "--")
        label = "GREEN" if score >= 67 else "YELLOW" if score >= 34 else "RED"
        color = (26, 127, 55) if score >= 67 else (154, 103, 0) if score >= 34 else (207, 34, 46)

        y = pdf.get_y()
        pdf.set_fill_color(245, 247, 250)
        pdf.set_draw_color(208, 215, 222)
        pdf.rect(20, y, 170, 18, "DF")
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*color)
        pdf.cell(0, 7, f"  Recovery: {score}% -- {label}", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(0, 6, f"  HRV: {hrv} ms  |  Resting HR: {rhr} bpm", ln=True)
        pdf.ln(6)

    pdf.set_text_color(30, 30, 30)
    for line in _strip_emoji(plan_text).split("\n"):
        line = line.rstrip()
        if line.startswith("## "):
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(9, 105, 218)
            pdf.cell(0, 8, line[3:].strip(), ln=True)
            pdf.set_draw_color(208, 215, 222)
            pdf.line(20, pdf.get_y(), 190, pdf.get_y())
            pdf.ln(2)
            pdf.set_text_color(30, 30, 30)
        elif line.startswith("### "):
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(60, 60, 60)
            pdf.cell(0, 7, line[4:].strip(), ln=True)
            pdf.set_text_color(30, 30, 30)
        elif re.match(r'^[-*] ', line):
            item = re.sub(r'\*\*(.+?)\*\*', r'\1', line[2:]).strip()
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, f"  - {item}")
        elif line.strip():
            text = re.sub(r'\*\*(.+?)\*\*', r'\1', line).strip()
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, text)
        else:
            pdf.ln(3)

    return bytes(pdf.output())


def send_email(subject, body, pdf_bytes, date_str):
    from_addr = os.environ["GMAIL_FROM"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]

    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = TO_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    part = MIMEBase("application", "octet-stream")
    part.set_payload(pdf_bytes)
    encoders.encode_base64(part)
    safe_date = date_str.replace(", ", "_").replace(" ", "_")
    part.add_header("Content-Disposition", f'attachment; filename="training_plan_{safe_date}.pdf"')
    msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(from_addr, app_password)
        server.sendmail(from_addr, TO_EMAIL, msg.as_string())

    print(f"Email sent to {TO_EMAIL}")


def main():
    print("Refreshing Whoop token...")
    token_data = refresh_whoop_token()
    access_token = token_data["access_token"]
    new_refresh = token_data.get("refresh_token")
    if new_refresh:
        rotate_whoop_refresh_token(new_refresh)

    print("Fetching Whoop data...")
    whoop_data = fetch_whoop_data(access_token)

    print("Generating plan with Claude...")
    plan_text = generate_plan(whoop_data)

    today = datetime.now()
    date_str = today.strftime("%A, %B %d, %Y")

    body = build_email_body(plan_text, whoop_data, date_str)
    pdf_bytes = generate_pdf(plan_text, date_str, whoop_data)

    print("Sending email...")
    send_email(f"Training Plan -- {today.strftime('%a %b %d')}", body, pdf_bytes, date_str)
    print("Done!")


if __name__ == "__main__":
    main()
