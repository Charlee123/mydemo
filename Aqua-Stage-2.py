import csv
import smtplib
import logging
import ssl
import requests
import urllib3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os

# 🔹 Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 🔹 Enable logging for debug output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 🔹 Jenkins config (USERNAME + PASSWORD authentication)
JENKINS_URL = 'https://your-office-jenkins-url/'  # Ensure HTTPS is used
USERNAME = 'your-username'
PASSWORD = 'your-password'  # ✅ Using password-based authentication

# 🔹 Configure Jenkins API Session (Disable SSL verification)
session = requests.Session()
session.auth = (USERNAME, PASSWORD)
session.verify = False  # ✅ Ignore SSL certificate errors
session.headers.update({"Accept": "application/json"})

def get_crumb():
    """Fetch a fresh CSRF crumb before every API call."""
    try:
        logging.info("🔍 Fetching new CSRF protection token...")
        crumb_response = session.get(f"{JENKINS_URL}/crumbIssuer/api/json", verify=False)
        crumb_token = crumb_response.json().get("crumb")
        session.headers.update({"Jenkins-Crumb": crumb_token})
        logging.info(f"✅ New CSRF Token Acquired: {crumb_token}")
    except Exception as e:
        logging.error(f"⚠️ Failed to fetch CSRF Token: {e}")

def get_application_jobs():
    """Retrieve jobs inside the 'application' folder only"""
    application_folder = "application"  # Target folder name
    logging.info(f"🔍 Scanning jobs inside folder: {application_folder}")
    
    get_crumb()  # Fetch fresh CSRF token before making the request
    response = session.get(f"{JENKINS_URL}/job/{application_folder}/api/json", verify=False)
    
    if response.status_code == 200:
        jobs_data = response.json().get("jobs", [])
        all_jobs = [{"name": job["name"], "url": job["url"]} for job in jobs_data]
        logging.info(f"✅ Found {len(all_jobs)} jobs in '{application_folder}' folder.")
        return all_jobs
    else:
        logging.error(f"⚠️ Failed to retrieve jobs: {response.status_code}")
        return []

def check_aqua_stage():
    """Check if Aqua Security Scan is present in console output"""
    all_jobs = get_application_jobs()
    missing_aqua = []

    for job in all_jobs:
        job_name = job["name"]
        job_url = job["url"]
        logging.info(f"🔎 Checking job: {job_name}")

        get_crumb()  # Fetch fresh CSRF token for each job request
        response = session.get(f"{job_url}/api/json", verify=False)

        if response.status_code == 200:
            job_data = response.json()
            if "builds" in job_data:
                builds = job_data["builds"][:5]  # Check last 5 builds

                for build in builds:
                    build_number = build["number"]
                    logging.info(f"📜 Fetching console log for Build {build_number} in {job_name}")
                    get_crumb()  # Fetch fresh CSRF token before fetching logs
                    console_response = session.get(f"{job_url}/{build_number}/consoleText", verify=False)

                    if console_response.status_code == 200:
                        console_output = console_response.text
                        if "Aqua Security Scan" in console_output:
                            logging.info(f"✅ Aqua detected in: {job_name} (Build {build_number})")
                            break
                    else:
                        logging.warning(f"⚠️ Failed to retrieve console output for Build {build_number}")
                else:
                    logging.warning(f"❌ Aqua stage missing in all recent builds: {job_name}")
                    missing_aqua.append({"Project Name": job_name, "Branch Name": "N/A"})
        else:
            logging.error(f"⚠️ Failed to retrieve job info for {job_name}")

    # 🔹 Write only missing Aqua jobs to CSV
    if missing_aqua:
        with open("jenkins_missing_aqua_stages.csv", mode='w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=["Project Name", "Branch Name"])
            writer.writeheader()
            writer.writerows(missing_aqua)
        logging.info(f"\n📁 Saved {len(missing_aqua)} job(s) missing Aqua stage to: jenkins_missing_aqua_stages.csv")
    else:
        logging.info("✅ All branches have Aqua Security Scan. No CSV generated.")

def send_email():
    """Send an email report with missing Aqua stages"""
    if not os.path.exists("jenkins_missing_aqua_stages.csv"):
        logging.info("✅ No missing Aqua stages detected. Skipping email notification.")
        return

    msg = MIMEMultipart()
    msg['From'] = f'Jenkins Automation <{SENDER_EMAIL}>'
    msg['To'] = ', '.join(RECIPIENT_EMAIL)
    msg['Subject'] = '🚨 Jenkins Aqua Stage Missing Report'

    body = "Hi Team,\n\nPlease find the attached report of branches missing the Aqua Security Scan stage.\n\nThis is an automated email.\n\nThanks,\nDevSecOps Team"
    msg.attach(MIMEText(body, 'plain'))

    with open("jenkins_missing_aqua_stages.csv", 'rb') as file:
        msg.attach(MIMEText(file.read(), 'base64', 'utf-8'))
        msg.add_header('Content-Disposition', 'attachment; filename="jenkins_missing_aqua_stages.csv"')

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
