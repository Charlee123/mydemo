import csv
import smtplib
import logging
import ssl
import requests
import urllib3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import concurrent.futures

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Enable logging for debugging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Jenkins Configuration
JENKINS_URL = "https://your-office-jenkins-url/"
USERNAME = "your-username"
PASSWORD = "your-password"

# Configure Jenkins API Session
session = requests.Session()
session.auth = (USERNAME, PASSWORD)
session.verify = False
session.headers.update({"Accept": "application/json"})

# SMTP configuration
SENDER_EMAIL = "your-email@gmail.com"
APP_PASSWORD = "your-app-password"
RECIPIENT_EMAIL = ["your-team@company.com"]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

def get_crumb():
    """Fetch a fresh CSRF crumb before API calls."""
    try:
        logging.info("🔍 Fetching CSRF protection token...")
        crumb_response = session.get(f"{JENKINS_URL}/crumbIssuer/api/json", verify=False)
        if crumb_response.status_code == 200:
            crumb_token = crumb_response.json().get("crumb")
            session.headers.update({"Jenkins-Crumb": crumb_token})
            logging.info(f"✅ CSRF Token Acquired: {crumb_token}")
        else:
            logging.error(f"⚠️ Failed to fetch CSRF Token: {crumb_response.status_code}")
    except Exception as e:
        logging.error(f"⚠️ Error fetching CSRF Token: {e}")

def get_application_jobs():
    """Retrieve jobs from the 'application' folder."""
    application_folder = "application"
    logging.info(f"🔍 Scanning jobs inside folder: {application_folder}")

    get_crumb()
    response = session.get(f"{JENKINS_URL}/job/{application_folder}/api/json", verify=False)

    if response.status_code == 200:
        jobs_data = response.json().get("jobs", [])
        all_jobs = [{"name": job["name"], "url": job["url"]} for job in jobs_data]
        logging.info(f"✅ Found {len(all_jobs)} jobs in '{application_folder}' folder.")
        return all_jobs
    else:
        logging.error(f"⚠️ Failed to retrieve jobs: {response.status_code}")
        return []

def fetch_job_data(job):
    """Retrieve recent builds and check for Aqua Security Scan."""
    job_url = job["url"]
    response = session.get(f"{job_url}/api/json", verify=False)

    if response.status_code == 200:
        job_data = response.json()
        for build in job_data.get("builds", [])[:1]:  # Check only latest build
            console_response = session.get(f"{build['url']}/consoleText", verify=False)
            if console_response.status_code == 200 and "Aqua Security Scan" in console_response.text:
                return None
    return {"Project Name": job["name"], "Branch Name": "N/A"}

def check_aqua_stage():
    """Run parallel requests to check for missing Aqua Security Scan."""
    all_jobs = get_application_jobs()
    missing_aqua = []

    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = executor.map(fetch_job_data, all_jobs)
        missing_aqua = [job for job in results if job]

    if missing_aqua:
        with open("jenkins_missing_aqua_stages.csv", mode="w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["Project Name", "Branch Name"])
            writer.writeheader()
            writer.writerows(missing_aqua)
        logging.info(f"\n📁 Saved {len(missing_aqua)} job(s) missing Aqua stage to: jenkins_missing_aqua_stages.csv")
    else:
        logging.info("✅ All branches have Aqua Security Scan. No CSV generated.")

def send_email():
    """Send an email report with missing Aqua stages."""
    if not os.path.exists("jenkins_missing_aqua_stages.csv"):
        logging.info("✅ No missing Aqua stages detected. Skipping email notification.")
        return

    msg = MIMEMultipart()
    msg["From"] = f"Jenkins Automation <{SENDER_EMAIL}>"
    msg["To"] = ", ".join(RECIPIENT_EMAIL)
    msg["Subject"] = "🚨 Jenkins Aqua Stage Missing Report"

    body = "Hi Team,\n\nPlease find the attached report of branches missing the Aqua Security Scan stage.\n\nThis is an automated email.\n\nThanks,\nDevSecOps Team"
    msg.attach(MIMEText(body, "plain"))

    with open("jenkins_missing_aqua_stages.csv", "rb") as file:
        msg.attach(MIMEText(file.read(), "base64", "utf-8"))
        msg.add_header("Content-Disposition", "attachment; filename=jenkins_missing_aqua_stages.csv")

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())

        logging.info(f"✅ Email sent successfully to {RECIPIENT_EMAIL}")
    except Exception as e:
        logging.error(f"⚠️ Failed to send email: {e}")

if __name__ == "__main__":
    check_aqua_stage()
    send_email()
