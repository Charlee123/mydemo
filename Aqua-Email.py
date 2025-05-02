import jenkins
import csv
import xml.etree.ElementTree as ET
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import os
import requests
import warnings
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL certificate warnings
warnings.simplefilter('ignore', InsecureRequestWarning)

# Jenkins config
JENKINS_URL = 'https://your-jenkins-url.com/'  # Replace with your Jenkins URL
USERNAME = 'devsecops'
API_TOKEN = 'your_api_token_here'  # Replace with your API token

# Gmail SMTP config
SENDER_EMAIL = 'sharear.appsec@gmail.com'
APP_PASSWORD = 'bgse sbdh yvgl nfbv'
TO_EMAILS = ['sharear.ahmed@iff.com']
CC_EMAILS = ['sharear.ahmed@iff.com']
EMAIL_SUBJECT = '🔔 Jenkins Aqua Stage Check Report'
EMAIL_BODY = """
Hi Team,

Please find the attached report for Jenkins jobs/branches missing the Aqua Security Scan stage.

This is an automated email.

Thanks,
DevSecOps Team
"""
RECIPIENT_EMAIL = 'joseph.vinikoor@iff.com'  # Optional individual recipient

# Branches to scan
TARGET_BRANCHES = ["main", "master", "dev", "qas", "prod"]

# Output CSV
ATTACHMENT_FILE = "jenkins_missing_aqua_stages.csv"

# Get crumb for CSRF protection
def get_crumb():
    try:
        crumb_url = f"{JENKINS_URL}crumbIssuer/api/json"
        response = requests.get(crumb_url, auth=HTTPBasicAuth(USERNAME, API_TOKEN), verify=False)
        response.raise_for_status()
        crumb_data = response.json()
        return {crumb_data['crumbRequestField']: crumb_data['crumb']}
    except Exception as e:
        print(f"⚠️ Failed to fetch crumb: {e}")
        return {}

# Patch Jenkins connection to support SSL disable + crumb
class CustomJenkins(jenkins.Jenkins):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._crumb_header = get_crumb()
        self.requester._session.verify = False
        if self._crumb_header:
            self.requester._session.headers.update(self._crumb_header)

# Connect to Jenkins
server = CustomJenkins(JENKINS_URL, username=USERNAME, password=API_TOKEN)

# Recursively get all jobs (including nested folders)
def get_all_jobs(jobs=None, prefix=''):
    if jobs is None:
        jobs = server.get_jobs()

    all_jobs = []

    for job in jobs:
        name = job['name']
        job_class = job['_class']

        if job_class == 'com.cloudbees.hudson.plugins.folder.Folder':
            subfolder_path = f"{prefix}{name}/"
            sub_jobs = server.get_jobs(subfolder_path)
            all_jobs.extend(get_all_jobs(sub_jobs, subfolder_path))
        else:
            job_path = f"{prefix}{name}"
            all_jobs.append({"name": job_path, "_class": job_class})

    return all_jobs

# Send email with the CSV attachment
def send_email():
    if not os.path.exists(ATTACHMENT_FILE):
        print(f"⚠️ Attachment file not found: {ATTACHMENT_FILE}")
        return

    msg = MIMEMultipart()
    msg['From'] = 'DevSecOps Team <{}>'.format(SENDER_EMAIL)
    msg['To'] = ', '.join(TO_EMAILS)
    msg['Cc'] = ', '.join(CC_EMAILS)
    msg['Subject'] = EMAIL_SUBJECT

    msg.attach(MIMEText(EMAIL_BODY, 'plain'))

    with open(ATTACHMENT_FILE, 'rb') as file:
        part = MIMEApplication(file.read(), Name=os.path.basename(ATTACHMENT_FILE))
        part['Content-Disposition'] = f'attachment; filename="{os.path.basename(ATTACHMENT_FILE)}"'
        msg.attach(part)

    try:
        all_recipients = TO_EMAILS + CC_EMAILS
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.starttls()
            smtp.login(SENDER_EMAIL, APP_PASSWORD)
            smtp.sendmail(SENDER_EMAIL, all_recipients, msg.as_string())
        print(f"✅ Email sent successfully to {all_recipients}")
    except Exception as e:
        print(f"⚠️ Failed to send email: {e}")

# Main logic
def main():
    all_jobs = get_all_jobs()
    print(f"🔍 Total jobs found: {len(all_jobs)}")

    missing_aqua = []

    for job in all_jobs:
        job_name = job["name"]
        job_class = job["_class"]

        if 'workflow.multibranch' in job_class:
            try:
                branches = server.get_job_info(job_name)['jobs']
            except Exception as e:
                print(f"⚠️ Failed to get branches for {job_name}: {e}")
                continue

            for branch in branches:
                branch_name = branch['name']
                if branch_name not in TARGET_BRANCHES:
                    continue

                try:
                    branch_builds = server.get_job_info(f"{job_name}/{branch_name}")['builds']
                    valid_builds = [b for b in branch_builds if isinstance(b.get('number'), int)]

                    if not valid_builds:
                        continue

                    config_xml = server.get_job_config(f"{job_name}/{branch_name}")
                    if "Aqua Security Scan" not in config_xml:
                        print(f"❌ Aqua stage missing in: {job_name} -> {branch_name}")
                        missing_aqua.append({"Project Name": job_name, "Branch Name": branch_name})
                except Exception as e:
                    print(f"⚠️ Error checking branch {branch_name} of {job_name}: {e}")
        else:
            # Single-branch freestyle or pipeline job
            try:
                config_xml = server.get_job_config(job_name)
                if "Aqua Security Scan" not in config_xml:
                    print(f"❌ Aqua stage missing in: {job_name} -> N/A")
                    missing_aqua.append({"Project Name": job_name, "Branch Name": "N/A"})
            except Exception as e:
                print(f"⚠️ Error checking job {job_name}: {e}")

    # Write CSV
    with open(ATTACHMENT_FILE, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=["Project Name", "Branch Name"])
        writer.writeheader()
        writer.writerows(missing_aqua)

    print(f"\n📁 Saved {len(missing_aqua)} job(s) missing Aqua stage to: {ATTACHMENT_FILE}")

    send_email()

if __name__ == "__main__":
    main()
