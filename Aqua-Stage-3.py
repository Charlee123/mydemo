import csv
import smtplib
import logging
import asyncio
import aiohttp
import ssl
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Suppress SSL warnings
ssl._create_default_https_context = ssl._create_unverified_context

# Enable logging for debugging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Jenkins Configuration
JENKINS_URL = "https://your-office-jenkins-url/"
USERNAME = "your-username"
PASSWORD = "your-password"

# SMTP configuration
SENDER_EMAIL = "your-email@gmail.com"
APP_PASSWORD = "your-app-password"
RECIPIENT_EMAIL = ["your-team@company.com"]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

async def get_crumb(session):
    """Fetch a fresh CSRF crumb before API calls."""
    try:
        logging.info("🔍 Fetching CSRF protection token...")
        async with session.get(f"{JENKINS_URL}/crumbIssuer/api/json") as response:
            if response.status == 200:
                data = await response.json()
                return data.get("crumb")
            else:
                logging.error(f"⚠️ Failed to fetch CSRF Token: {response.status}")
                return None
    except Exception as e:
        logging.error(f"⚠️ Error fetching CSRF Token: {e}")
        return None

async def get_application_jobs(session, csrf_token):
    """Retrieve jobs from the 'application' folder."""
    application_folder = "application"
    logging.info(f"🔍 Scanning jobs inside folder: {application_folder}")

    headers = {"Jenkins-Crumb": csrf_token} if csrf_token else {}

    async with session.get(f"{JENKINS_URL}/job/{application_folder}/api/json", headers=headers) as response:
        if response.status == 200:
            data = await response.json()
            all_jobs = [{"name": job["name"], "url": job["url"]} for job in data.get("jobs", [])]
            logging.info(f"✅ Found {len(all_jobs)} jobs in '{application_folder}' folder.")
            return all_jobs
        else:
            logging.error(f"⚠️ Failed to retrieve jobs: {response.status}")
            return []

async def fetch_job_data(session, job, csrf_token):
    """Retrieve recent builds and check for Aqua Security Scan."""
    headers = {"Jenkins-Crumb": csrf_token} if csrf_token else {}

    async with session.get(f"{job['url']}/api/json", headers=headers) as response:
        if response.status == 200:
            job_data = await response.json()
            for build in job_data.get("builds", [])[:1]:  # Check only latest build
                async with session.get(f"{build['url']}/consoleText", headers=headers) as console_response:
                    if console_response.status == 200:
                        console_text = await console_response.text()
                        if "Aqua Security Scan" in console_text:
                            return None
        return {"Project Name": job["name"], "Branch Name": "N/A"}

async def check_aqua_stage():
    """Run parallel async requests to check for missing Aqua Security Scan."""
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(USERNAME, PASSWORD), connector=aiohttp.TCPConnector(ssl=False)) as session:
        csrf_token = await get_crumb(session)
        all_jobs = await get_application_jobs(session, csrf_token)

        tasks = [fetch_job_data(session, job, csrf_token) for job in all_jobs]
        results = await asyncio.gather(*tasks)

        missing_aqua = [job for job in results if job]

        if missing_aqua:
            with open("jenkins_missing_aqua_stages.csv", mode="w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=["Project Name", "Branch Name"])
                writer.writeheader()
                writer.writerows(missing_aqua)
            logging.info(f"\n📁 Saved {len(missing_aqua)} job(s) missing Aqua stage to: jenkins_missing_aqua_stages.csv")
        else:
            logging.info("✅ All branches have Aqua Security Scan. No CSV generated.")

async def send_email():
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

async def main():
    await check_aqua_stage()
    await send_email()

if __name__ == "__main__":
    asyncio.run(main())
