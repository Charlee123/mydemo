import jenkins
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

# 🔹 Fetch Jenkins CSRF token (Crumb)
try:
    logging.info("🔍 Fetching CSRF protection token...")
    crumb_response = session.get(f"{JENKINS_URL}/crumbIssuer/api/json", verify=False)
    crumb_token = crumb_response.json().get("crumb")
    session.headers.update({"Jenkins-Crumb": crumb_token})
    logging.info(f"✅ CSRF Token Acquired: {crumb_token}")
except Exception as e:
    logging.error(f"⚠️ Failed to fetch CSRF Token: {e}")

# 🔹 SMTP config (for sending reports)
SENDER_EMAIL = 'your-email@gmail.com'
APP_PASSWORD = 'your-app-password'
RECIPIENT_EMAIL = ['your-team@company.com']
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587

# 🔹 Branch keyword matching (handles dynamic names)
TARGET_BRANCHES = ["main", "master", "dev", "qas", "prod"]
ATTACHMENT_FILE = "jenkins_missing_aqua_stages.csv"

# 🔹 Connect to Jenkins using **USERNAME + PASSWORD**
server = jenkins.Jenkins(JENKINS_URL, username=USERNAME, password=PASSWORD)

def get_application_jobs():
    """Retrieve jobs inside the 'application' folder only"""
    application_folder = "application"  # Target folder name
    logging.info(f"🔍 Scanning jobs inside folder: {application_folder}")

    jobs = server.get_jobs(application_folder)  # Fetch jobs inside 'application'
    all_jobs = []

    for job in jobs:
        name = job['name']
        job_class = job['_class']

        if 'folder' in job_class:  # Navigate inside subfolders if necessary
            sub_jobs = server.get_jobs(f"{application_folder}/{name}")
            for sub_job in sub_jobs:
                all_jobs.append({"name": f"{application_folder}/{name}/{sub_job['name']}", "_class": sub_job["_class"]})
        else:
            all_jobs.append({"name": f"{application_folder}/{name}", "_class": job_class})

    logging.info(f"✅ Found {len(all_jobs)} jobs in '{application_folder}' folder.")
    return all_jobs

def check_aqua_stage():
    """Check if Aqua Security Scan is present in console output"""
    all_jobs = get_application_jobs()
    missing_aqua = []

    for job in all_jobs:
        job_name = job["name"]
        logging.info(f"🔎 Checking job: {job_name}")

        if 'multibranch' in job["_class"]:
            branches = server.get_job_info(job_name)['jobs']

            for branch in branches:
                branch_name = branch['name']

                # Check if branch name contains any target keyword
                if not any(keyword in branch_name for keyword in TARGET_BRANCHES):
                    continue

                try:
                    branch_builds = server.get_job_info(f"{job_name}/{branch_name}")['builds']
                    valid_builds = [b for b in branch_builds if isinstance(b.get('number'), int)]
                    sorted_builds = sorted(valid_builds, key=lambda b: b['number'], reverse=True)

                    for build in sorted_builds[:5]:  # Check last 5 builds
                        build_number = build['number']
                        logging.info(f"📜 Fetching console log for Build {build_number} in {branch_name}")
                        console_output = server.get_build_console_output(f"{job_name}/{branch_name}", build_number)

                        if "Aqua Security Scan" in console_output:
                            logging.info(f"✅ Aqua detected in: {job_name} -> {branch_name} (Build {build_number})")
                            break
                    else:
                        logging.warning(f"❌ Aqua stage missing in all recent builds: {job_name} -> {branch_name}")
                        missing_aqua.append({"Project Name": job_name, "Branch Name": branch_name})

                except Exception as e:
                    logging.error(f"⚠️ Error checking branch {branch_name} of {job_name}: {e}")
        else:
            try:
                job_builds = server.get_job_info(job_name)['builds']
                valid_builds = [b for b in job_builds if isinstance(b.get('number'), int)]
                sorted_builds = sorted(valid_builds, key=lambda b: b['number'], reverse=True)

                for build in sorted_builds[:5]:  # Check last 5 builds
                    build_number = build['number']
                    logging.info(f"📜 Fetching console log for Build {build_number} in {job_name}")
                    console_output = server.get_build_console_output(job_name, build_number)

                    if "Aqua Security Scan" in console_output:
                        logging.info(f"✅ Aqua detected in: {job_name} (Build {build_number})")
                        break
                else:
                    logging.warning(f"❌ Aqua stage missing in all recent builds: {job_name}")
                    missing_aqua.append({"Project Name": job_name, "Branch Name": "N/A"})

            except Exception as e:
                logging.error(f"⚠️ Error checking job {job_name}: {e}")

    # 🔹 Write only missing Aqua jobs to CSV
    if missing_aqua:
        with open(ATTACHMENT_FILE, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=["Project Name", "Branch Name"])
            writer.writeheader()
            writer.writerows(missing_aqua)
        logging.info(f"\n📁 Saved {len(missing_aqua)} job(s) missing Aqua stage to: {ATTACHMENT_FILE}")
    else:
        logging.info("✅ All branches have Aqua Security Scan. No CSV generated.")

def send_email():
    """Send an email report with missing Aqua stages"""
    if not os.path.exists(ATTACHMENT_FILE):
        logging.info("✅ No missing Aqua stages detected. Skipping email notification.")
        return

    msg = MIMEMultipart()
    msg['From'] = f'Jenkins Automation <{SENDER_EMAIL}>'
    msg['To'] = ', '.join(RECIPIENT_EMAIL)
    msg['Subject'] = '🚨 Jenkins Aqua Stage Missing Report'

    body = "Hi Team,\n\nPlease find the attached report of branches missing the Aqua Security Scan stage.\n\nThis is an automated email.\n\nThanks,\nDevSecOps Team"
    msg.attach(MIMEText(body, 'plain'))

    with open(ATTACHMENT_FILE, 'rb') as file:
        msg.attach(MIMEText(file.read(), 'base64', 'utf-8'))
        msg.add_header('Content-Disposition', f'attachment; filename="{ATTACHMENT_FILE}"')

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
