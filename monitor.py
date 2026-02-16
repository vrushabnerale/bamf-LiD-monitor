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

TARGET_DATE = "26.01.2026"

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

    msg = MIMEText(body)

    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.send_message(msg)


# ------------------------------------------
# Extract Status Date from Official Sentence
# ------------------------------------------
def get_status_date(text):

    pattern = r"Aktuell wertet das Bundesamt Tests bis Prüfungsdatum (\d{2}\.\d{2}\.\d{4}) aus\."

    match = re.search(pattern, text)

    if match:
        return match.group(1)

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

    response = requests.get(URL, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    return soup.get_text()


# ------------------------------------------
# Main Logic
# ------------------------------------------
def main():

    state = load_state()

    if state["terminated"]:
        print("Monitoring already terminated.")
        return

    print("Checking BAMF page...")

    page_text = check_page()

    status_date = get_status_date(page_text)

    print("Status date found:", status_date)

    if status_date is None:
        print("Official sentence not found.")
        return

    now = datetime.utcnow()


    # -------------------------
    # CASE 1: Target appears
    # -------------------------
    if status_date == TARGET_DATE and state["target_found_at"] is None:

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

        print("Target date detected for first time.")


    # -------------------------
    # CASE 2: Date changed
    # -------------------------
    elif state["last_date"] == TARGET_DATE and status_date != TARGET_DATE:

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

        print("Date change detected.")


    # -------------------------
    # CASE 3: Termination
    # -------------------------
    if state["target_found_at"]:

        first_seen = datetime.fromisoformat(state["target_found_at"])

        if now >= first_seen + timedelta(days=TERMINATION_AFTER_DAYS):

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

            print("Monitoring terminated.")


    save_state(state)


# ------------------------------------------

if __name__ == "__main__":
    main()
