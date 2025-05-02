import jenkins
import csv
import xml.etree.ElementTree as ET
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import os
import requests
import urllib3

# Suppress only the SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Jenkins config
JENKINS_URL = 'https://your-jenkins-url.com/'  # Use HTTPS URL
USERNAME = 'devsecops'
API_TOKEN = 'your-api-token'

# Gmail SMTP config
SENDER_EMAIL = 'sharear.appsec@gmail.com'
APP_PASSWORD = 'your-app-password'
RECIPIENT_EMAIL = 'joseph.vinikoor@iff.com'
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587

# Branches to scan
TARGET_BRANCHES = ["main", "master", "dev", "qas", "prod"]

# Email Recipients
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

ATTACHMENT_FILE = "jenkins_missing_aqua_stages.csv"

# Connect to Jenkins
server = jenkins.Jenkins(JENKINS_URL, username=USERNAME, password=API_TOKEN)

# Recursively get all jobs
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

# CSRF crumb fetch
def get_crumb():
    try:
        crumb_url = f"{JENKINS_URL}crumbIssuer/api/json"
        response = requests.get(crumb_url, auth=(USERNAME, API_TOKEN), verify=False)
        response.raise_for_status()
        crumb_data = response.json()
        return {crumb_data['crumbRequestField']: crumb_data['crumb']}
    except Exception as e:
        print(f"⚠️ Failed to fetch crumb: {e}")
        return {}

# Secure config fetch for job
def get_job_config_secure(job_path):
    try:
        crumb_header = get_crumb()
        headers = {}
        if crumb_header:
            headers.update(crumb_header)

        config_url = f"{JENKINS_URL}job/{'/'.join(job_path.split('/'))}/config.xml"
        response = requests.get(config_url, auth=(USERNAME, API_TOKEN), headers=headers, verify=False)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"⚠️ Failed to get config for {job_path}: {e}")
        return ""

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
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, all_recipients, msg.as_string())
        print(f"✅ Email sent successfully to {all_recipients}")
    except Exception as e:
        print(f"⚠️ Failed to send email: {e}")

# Main logic
def main():
    all_jobs = get_all_jobs()
    print(f"🔍 Total jobs found: {len(all_jobs)}")

    multibranch_jobs = [job for job in all_jobs if 'workflow.multibranch' in job['_class']]
    print(f"🔍 Multibranch jobs to scan: {len(multibranch_jobs)}")

    missing_aqua = []

    for job in multibranch_jobs:
        job_name = job["name"]
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

                latest_build_number = sorted(valid_builds, key=lambda b: b['number'], reverse=True)[0]['number']
                config_xml = get_job_config_secure(f"{job_name}/{branch_name}")

                if "Aqua Security Scan" not in config_xml:
                    print(f"❌ Aqua stage missing in: {job_name} -> {branch_name}")
                    missing_aqua.append({"Project Name": job_name, "Branch Name": branch_name})

            except Exception as e:
                print(f"⚠️ Error checking branch {branch_name} of {job_name}: {e}")

    # Write results to CSV
    with open(ATTACHMENT_FILE, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=["Project Name", "Branch Name"])
        writer.writeheader()
        writer.writerows(missing_aqua)

    print(f"\n📁 Saved {len(missing_aqua)} job(s) missing Aqua stage to: {ATTACHMENT_FILE}")
    send_email()

if __name__ == "__main__":
    main()
