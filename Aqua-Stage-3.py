import csv
import smtplib
import logging
import requests
import urllib3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os

# 🔹 Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 🔹 Optimize logging level to reduce unnecessary outputs
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

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

def check_aqua_stage():
    """Check Aqua Code Scan stage and success criteria for all jobs, sequentially."""
    all_jobs = get_application_jobs()
    missing_aqua = []

    total_jobs = len(all_jobs)
    completed_jobs = 0

    for job in all_jobs:
        job_name = job["name"]
        job_url = job["url"]

        get_crumb()
        response = session.get(f"{job_url}/api/json", verify=False)

        if response.status_code == 200:
            job_data = response.json()
            builds = job_data.get("builds", [])

            if not builds:
                logging.warning(f"🚫 No builds for {job_name}, skipping log check.")
                missing_aqua.append({"Project Name": job_name, "Reason": "No Aqua Stage Found"})
                completed_jobs += 1
                print(f"✅ Completed {completed_jobs}/{total_jobs} jobs", end="\r")  # Live update in terminal
                continue

            for build in builds[:3]:  # Check latest 3 builds only
                console_response = session.get(f"{job_url}/{build['number']}/consoleText", verify=False)

                if console_response.status_code == 200:
                    console_output = console_response.text
                    if "Aqua Security Scan" in console_output:
                        if "Scan Results Summary" in console_output or "Successfully processed file 'results.json'" in console_output:
                            break  # ✅ Aqua scan exists and succeeded
                        else:
                            missing_aqua.append({"Project Name": job_name, "Reason": "Aqua Scan was not successful"})
                            break
            else:
                missing_aqua.append({"Project Name": job_name, "Reason": "No Aqua Stage Found"})

        else:
            logging.warning(f"⚠️ Failed to retrieve job info for {job_name}")
            missing_aqua.append({"Project Name": job_name, "Reason": "Failed to retrieve job data"})

        completed_jobs += 1
        print(f"✅ Completed {completed_jobs}/{total_jobs} jobs", end="\r")  # Live update in terminal

    print("\n🎯 Processing complete.")

    if missing_aqua:
        with open("jenkins_missing_aqua_stages.csv", mode="w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["Project Name", "Reason"])
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
