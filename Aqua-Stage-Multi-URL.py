import csv
import smtplib
import logging
import ssl
import requests
import urllib3
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os

# 🔹 Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 🔹 Enable logging for debug output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 🔹 Hardcoded list of Jenkins URLs
JENKINS_URLS = [
    "https://mycompany1.jenkins.com",
    "https://mycompany2.jenkins.com",
    "https://mycompany3.jenkins.com"
]

# 🔹 Authentication credentials
USERNAME = "your-username"
PASSWORD = "your-password"

# 🔹 SMTP config for sending reports
SENDER_EMAIL = "your-email@gmail.com"
APP_PASSWORD = "your-app-password"
RECIPIENT_EMAIL = ["your-team@company.com"]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# 🔹 Application folder to check
APPLICATION_FOLDER = "application"

def get_crumb(session, jenkins_url):
    """Fetch a fresh CSRF crumb before every API call."""
    try:
        logging.info(f"🔍 Fetching CSRF token for {jenkins_url}...")
        crumb_response = session.get(f"{jenkins_url}/crumbIssuer/api/json", verify=False)
        crumb_token = crumb_response.json().get("crumb")
        session.headers.update({"Jenkins-Crumb": crumb_token})
        logging.info(f"✅ CSRF Token Acquired for {jenkins_url}")
    except Exception as e:
        logging.error(f"⚠️ Failed to fetch CSRF Token for {jenkins_url}: {e}")

def get_application_jobs(session, jenkins_url):
    """Retrieve jobs inside the 'application' folder only."""
    logging.info(f"🔍 Scanning jobs inside folder '{APPLICATION_FOLDER}' for {jenkins_url}...")
    
    get_crumb(session, jenkins_url)
    time.sleep(2)  # Prevent API overload
    response = session.get(f"{jenkins_url}/job/{APPLICATION_FOLDER}/api/json", verify=False)

    if response.status_code == 200:
        jobs_data = response.json().get("jobs", [])
        all_jobs = [{"name": job["name"], "url": job["url"]} for job in jobs_data]
        logging.info(f"✅ Found {len(all_jobs)} jobs in '{APPLICATION_FOLDER}' for {jenkins_url}.")
        return all_jobs
    else:
        logging.error(f"⚠️ Failed to retrieve jobs for {jenkins_url}: {response.status_code}")
        return []

def check_aqua_stage(session, jenkins_url):
    """Check if Aqua Security Scan is present in console output for each Jenkins instance."""
    all_jobs = get_application_jobs(session, jenkins_url)
    missing_aqua = []

    for job in all_jobs:
        job_name = job["name"]
        job_url = job["url"]
        logging.info(f"🔎 Checking job: {job_name} on {jenkins_url}")

        get_crumb(session, jenkins_url)
        time.sleep(2)  # Prevent Jenkins from rejecting too many requests
        response = session.get(f"{job_url}/api/json", verify=False)

        if response.status_code == 200:
            job_data = response.json()
            if "builds" in job_data and job_data["builds"]:  # ✅ Ensure builds exist before checking
                builds = job_data["builds"][:5]  # Check last 5 builds

                for build in builds:
                    build_number = build["number"]
                    logging.info(f"📜 Fetching console log for Build {build_number} in {job_name} ({jenkins_url})")

                    time.sleep(2)  # Adding delay to prevent connection closure
                    get_crumb(session, jenkins_url)
                    console_response = session.get(f"{job_url}/{build_number}/consoleText", verify=False)

                    if console_response.status_code == 200:
                        console_output = console_response.text
                        if "Aqua Security Scan" in console_output:
                            logging.info(f"✅ Aqua detected in: {job_name} (Build {build_number}) on {jenkins_url}")
                            break
                    else:
                        logging.warning(f"⚠️ Failed to retrieve console output for Build {build_number}")
                else:
                    logging.warning(f"❌ Aqua stage missing in all recent builds: {job_name} ({jenkins_url})")
                    missing_aqua.append({"Project Name": job_name, "Branch Name": "N/A"})
        else:
            logging.error(f"⚠️ Failed to retrieve job info for {job_name} ({jenkins_url})")

    # 🔹 Write only missing Aqua jobs to CSV
    csv_filename = f"jenkins_missing_aqua_stages_{jenkins_url.split('//')[1].split('.')[0]}.csv"
    if missing_aqua:
        with open(csv_filename, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["Project Name", "Branch Name"])
            writer.writeheader()
            writer.writerows(missing_aqua)
        logging.info(f"📁 Saved {len(missing_aqua)} job(s) missing Aqua stage to: {csv_filename}")
    else:
        logging.info(f"✅ All branches have Aqua Security Scan for {jenkins_url}. No CSV generated.")

    return csv_filename if missing_aqua else None

def send_email(csv_files):
    """Send an email report with missing Aqua stages."""
    if not csv_files:
        logging.info("✅ No missing Aqua stages detected in any Jenkins instance. Skipping email notification.")
        return

    msg = MIMEMultipart()
    msg["From"] = f"Jenkins Automation <{SENDER_EMAIL}>"
    msg["To"] = ", ".join(RECIPIENT_EMAIL)
    msg["Subject"] = "🚨 Jenkins Aqua Stage Missing Report"

    body = "Hi Team,\n\nPlease find the attached reports of branches missing the Aqua Security Scan stage.\n\nThis is an automated email.\n\nThanks,\nDevSecOps Team"
    msg.attach(MIMEText(body, "plain"))

    for csv_file in csv_files:
        with open(csv_file, "rb") as file:
            msg.attach(MIMEText(file.read(), "base64", "utf-8"))
            msg.add_header("Content-Disposition", f'attachment; filename="{csv_file}"')

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())

        logging.info(f"✅ Email sent successfully to {RECIPIENT_EMAIL}")
    except Exception as e:
        logging.error(f"⚠️ Failed to send email: {e}")

if __name__ == "__main__":
    csv_files = []
    
    for jenkins_url in JENKINS_URLS:
        logging.info(f"🚀 Processing Jenkins instance: {jenkins_url}")
        session = requests.Session()
        session.auth = (USERNAME, PASSWORD)
        session.verify = False
        session.headers.update({"Accept": "application/json"})
        
        csv_file = check_aqua_stage(session, jenkins_url)
        if csv_file:
            csv_files.append(csv_file)

    send_email(csv_files)
