import csv
import smtplib
import logging
import requests
import urllib3
import concurrent.futures
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os

# 🔹 Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 🔹 Optimize logging level to reduce unnecessary outputs
logging.basicConfig(level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s")

# 🔹 Jenkins Configuration
JENKINS_URL = "https://your-office-jenkins-url/"
USERNAME = "your-username"
PASSWORD = "your-password"

# 🔹 Configure Jenkins API Session
session = requests.Session()
session.auth = (USERNAME, PASSWORD)
session.verify = False
session.headers.update({"Accept": "application/json"})

# 🔹 SMTP configuration
SENDER_EMAIL = "your-email@gmail.com"
APP_PASSWORD = "your-app-password"
RECIPIENT_EMAIL = ["your-team@company.com"]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

def get_crumb():
    """Fetch a fresh CSRF crumb before API calls."""
    try:
        response = session.get(f"{JENKINS_URL}/crumbIssuer/api/json", verify=False)
        if response.status_code == 200:
            crumb_token = response.json().get("crumb")
            session.headers.update({"Jenkins-Crumb": crumb_token})
            return crumb_token
    except Exception:
        logging.error("⚠️ Failed to fetch CSRF token.")
    return None

def get_application_jobs():
    """Retrieve jobs from the 'application' folder."""
    application_folder = "application"

    get_crumb()
    response = session.get(f"{JENKINS_URL}/job/{application_folder}/api/json", verify=False)

    if response.status_code == 200:
        jobs_data = response.json().get("jobs", [])
        return [{"name": job["name"], "url": job["url"]} for job in jobs_data]
    logging.error("⚠️ Failed to retrieve jobs.")
    return []

def check_aqua_stage_for_job(job):
    """Check if Aqua Code Scan is present for a single job."""
    job_name = job["name"]
    job_url = job["url"]

    get_crumb()
    response = session.get(f"{job_url}/api/json", verify=False)

    if response.status_code == 200:
        job_data = response.json()
        builds = job_data.get("builds", [])

        if not builds:
            logging.warning(f"🚫 No builds for {job_name}, skipping log check.")
            return None

        for build in builds[:3]:  # Check only latest 3 builds
            console_response = session.get(f"{job_url}/{build['number']}/consoleText", verify=False)
            if console_response.status_code == 200 and "Aqua Code Scan" in console_response.text:
                return None
        return {"Project Name": job_name, "Branch Name": "N/A"}

    logging.warning(f"⚠️ Failed to retrieve job info for {job_name}")
    return None

def check_aqua_stage():
    """Check Aqua Code Scan in parallel for all jobs."""
    all_jobs = get_application_jobs()
    missing_aqua = []

    total_jobs = len(all_jobs)
    completed_jobs = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:  # Run 10 jobs in parallel
        future_to_job = {executor.submit(check_aqua_stage_for_job, job): job for job in all_jobs}

        for future in concurrent.futures.as_completed(future_to_job):
            result = future.result()
            completed_jobs += 1
            print(f"✅ Completed {completed_jobs}/{total_jobs} jobs", end="\r")  # Live update in terminal
            if result:
                missing_aqua.append(result)

    print("\n🎯 Processing complete.")

    if missing_aqua:
        with open("jenkins_missing_aqua_stages.csv", mode="w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["Project Name", "Branch Name"])
            writer.writeheader()
            writer.writerows(missing_aqua)
        logging.warning(f"\n📁 Saved {len(missing_aqua)} missing Aqua jobs to CSV.")
    else:
        logging.info("✅ All jobs contain Aqua Code Scan.")

def send_email():
    """Send an email report with missing Aqua Code Scan."""
    if not os.path.exists("jenkins_missing_aqua_stages.csv"):
        logging.info("✅ No missing Aqua Code Scan detected. Skipping email notification.")
        return

    msg = MIMEMultipart()
    msg["From"] = f"Jenkins Automation <{SENDER_EMAIL}>"
    msg["To"] = ", ".join(RECIPIENT_EMAIL)
    msg["Subject"] = "🚨 Jenkins Aqua Code Scan Missing Report"

    body = "Hi Team,\n\nFind the attached report of branches missing the Aqua Code Scan stage.\n\nAutomated email.\n\nThanks,\nDevSecOps Team"
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
