import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
import os
import json
import re
from datetime import datetime, timedelta


# ================= CONFIG =================

URL = "https://www.bamf.de/DE/Themen/Integration/ZugewanderteTeilnehmende/Integrationskurse/Abschlusspruefung/abschlusspruefung-node.html"

# For testing
TARGET_DATE = "26.01.2026"
# Later change to: "04.02.2026"

STATE_FILE = "state.json"

SENDER_EMAIL = os.environ["EMAIL_USER"]
APP_PASSWORD = os.environ["EMAIL_PASS"]
RECEIVER_EMAIL = os.environ["EMAIL_RECEIVER"]

# Stop monitoring X days after first appearance
TERMINATION_AFTER_DAYS = 14

# ==========================================


# ------------------------------------------
# Send Email
# ------------------------------------------
def send_email(subject, body):

    print("Sending email...")

    msg = MIMEText(body)

    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.send_message(msg)

    print("Email sent successfully.")


# ------------------------------------------
# Extract Status Date
# ------------------------------------------
def get_status_date(text):

    # Normalize spaces (remove weird unicode spaces)
    text = text.replace("\xa0", " ")
    text = " ".join(text.split())

    # Find sentence containing "Prüfungsdatum"
    for part in text.split("."):

        if "Prüfungsdatum" in part:

            # Extract any date in this part
            match = re.search(r"\d{2}\.\d{2}\.\d{4}", part)

            if match:
                return match.group(0)

    return None

# ------------------------------------------
# Load State
# ------------------------------------------
def load_state():

    if not os.path.exists(STATE_FILE):
        return {
            "last_date": None,
            "target_found_at": None,
            "terminated": False
        }

    with open(STATE_FILE, "r") as f:
        return json.load(f)


# ------------------------------------------
# Save State
# ------------------------------------------
def save_state(state):

    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


# ------------------------------------------
# Fetch Page
# ------------------------------------------
def check_page():

    import time

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    }

    for attempt in range(5):

        try:
            print(f"Attempt {attempt + 1} to fetch page...")

            response = requests.get(
                URL,
                headers=headers,
                timeout=30
            )

            print("HTTP Status:", response.status_code)

            response.raise_for_status()

            return response.text

        except Exception as e:
            print("Fetch error:", e)
            time.sleep(5)

    print("All fetch attempts failed.")
    return None


# ------------------------------------------
# Main Logic
# ------------------------------------------
def main():

    state = load_state()

    if state["terminated"]:
        print("Monitoring already terminated.")
        return


    print("Checking BAMF page...")


    # Fetch page
    page_text = check_page()

    if page_text is None:
        print("Could not fetch page. Exiting run.")
        return


    # Extract date
    status_date = get_status_date(page_text)

    print("Status date found:", status_date)
    print("Target date:", TARGET_DATE)

    if status_date is None:
        print("Official sentence not found.")
        return


    now = datetime.utcnow()


    # -------------------------
    # CASE 1: Target appears
    # -------------------------
    if status_date == TARGET_DATE and state["target_found_at"] is None:

        print("Triggering FIRST notification email")

        state["target_found_at"] = now.isoformat()
        state["last_date"] = TARGET_DATE

        send_email(
            "BAMF Update: Target Date Appeared",
            f"""
Hello Vrush,

The official BAMF status now shows:

Prüfungsdatum {TARGET_DATE}

Monitoring will continue for {TERMINATION_AFTER_DAYS} days.

Link:
{URL}
"""
        )


    # -------------------------
    # CASE 2: Date changed
    # -------------------------
    elif state["last_date"] == TARGET_DATE and status_date != TARGET_DATE:

        print("Triggering DATE CHANGE email")

        state["last_date"] = status_date

        send_email(
            "BAMF Update: Date Changed",
            f"""
Hello Vrush,

The previously detected target date {TARGET_DATE}
has changed to:

{status_date}

Link:
{URL}
"""
        )


    # -------------------------
    # CASE 3: Termination
    # -------------------------
    if state["target_found_at"]:

        first_seen = datetime.fromisoformat(state["target_found_at"])

        if now >= first_seen + timedelta(days=TERMINATION_AFTER_DAYS):

            print("Triggering TERMINATION email")

            state["terminated"] = True

            send_email(
                "BAMF Monitor Terminated",
                f"""
Hello Vrush,

Monitoring service has now been terminated.

Reason:
{TERMINATION_AFTER_DAYS} days passed after
target date {TARGET_DATE} appeared.

No further checks will be performed.

Regards,
BAMF Monitor
"""
            )


    save_state(state)


# ------------------------------------------

if __name__ == "__main__":
    main()
