import os
import csv
import jenkins
import urllib3
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from xml.etree import ElementTree as ET

# ──────────────────────────────────────────────────────────────────────────────
#  ⚙️ CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

JENKINS_URL = 'https://jenkins-ca-prod.global.iff.com/'
USERNAME = 'devsecops'
API_TOKEN = '11eca10940c16f371ded6738424553213f'

SENDER_EMAIL = 'sharear.appsec@gmail.com'
APP_PASSWORD = 'bgse sbdh yvgl nfbv'
TO_EMAILS = ['sharear.ahmed@iff.com']
CC_EMAILS = ['sharear.ahmed@iff.com']
EMAIL_SUBJECT = '🔔 Jenkins Aqua Stage Check Report'
EMAIL_BODY = """\
Hi Team,

Please find the attached report for Jenkins jobs/branches missing the Aqua Security Scan stage.

This is an automated email.

Thanks,  
DevSecOps Team
"""
ATTACHMENT_FILE = 'jenkins_missing_aqua_stages.csv'
TARGET_BRANCHES = ["main", "master", "dev", "qas", "prod"]

# ──────────────────────────────────────────────────────────────────────────────
#  📜 DISABLE SSL VERIFICATION AND WARNINGS
# ──────────────────────────────────────────────────────────────────────────────

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Patch requests to disable SSL cert check
import requests
from requests.sessions import Session
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

class UnsafeAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        kwargs['cert_reqs'] = 'CERT_NONE'
        kwargs['assert_hostname'] = False
        return super().init_poolmanager(*args, **kwargs)

def patch_requests():
    for attr in ('get', 'post', 'put', 'delete', 'head'):
        setattr(requests, attr, getattr(requests.Session(), attr))
    s = Session()
    s.mount('https://', UnsafeAdapter())
    s.verify = False
    requests.sessions.Session.request = s.request

patch_requests()

# ──────────────────────────────────────────────────────────────────────────────
#  🔗 JENKINS CONNECTION
# ──────────────────────────────────────────────────────────────────────────────

server = jenkins.Jenkins(JENKINS_URL, username=USERNAME, password=API_TOKEN)

def get_all_jobs(jobs=None, prefix=''):
    if jobs is None:
        jobs = server.get_jobs()

    all_jobs = []
    for job in jobs:
        name = job['name']
        job_class = job['_class']

        if job_class == 'com.cloudbees.hudson.plugins.folder.Folder':
            sub_jobs = server.get_jobs(f"{prefix}{name}/")
            all_jobs.extend(get_all_jobs(sub_jobs, f"{prefix}{name}/"))
        else:
            all_jobs.append({"name": f"{prefix}{name}", "_class": job_class})
    return all_jobs

# ──────────────────────────────────────────────────────────────────────────────
#  📧 EMAIL SENDING
# ──────────────────────────────────────────────────────────────────────────────

def send_email():
    if not os.path.exists(ATTACHMENT_FILE):
        print(f"⚠️ Attachment file not found: {ATTACHMENT_FILE}")
        return

    msg = MIMEMultipart()
    msg['From'] = f'DevSecOps Team <{SENDER_EMAIL}>'
    msg['To'] = ', '.join(TO_EMAILS)
    msg['Cc'] = ', '.join(CC_EMAILS)
    msg['Subject'] = EMAIL_SUBJECT
    msg.attach(MIMEText(EMAIL_BODY, 'plain'))

    with open(ATTACHMENT_FILE, 'rb') as f:
        part = MIMEApplication(f.read(), Name=os.path.basename(ATTACHMENT_FILE))
        part['Content-Disposition'] = f'attachment; filename="{os.path.basename(ATTACHMENT_FILE)}"'
        msg.attach(part)

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as s:
            s.starttls()
            s.login(SENDER_EMAIL, APP_PASSWORD)
            s.sendmail(SENDER_EMAIL, TO_EMAILS + CC_EMAILS, msg.as_string())
        print("✅ Email sent successfully.")
    except Exception as e:
        print(f"⚠️ Failed to send email: {e}")

# ──────────────────────────────────────────────────────────────────────────────
#  🔍 MAIN LOGIC
# ──────────────────────────────────────────────────────────────────────────────

def main():
    all_jobs = get_all_jobs()
    print(f"🔍 Total jobs found: {len(all_jobs)}")

    multibranch_jobs = [j for j in all_jobs if 'workflow.multibranch' in j['_class']]
    print(f"🔍 Multibranch jobs: {len(multibranch_jobs)}")

    missing_aqua = []

    for job in multibranch_jobs:
        job_name = job['name']
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
                config_xml = server.get_job_config(f"{job_name}/{branch_name}")
                if "Aqua Security Scan" not in config_xml:
                    print(f"❌ Aqua stage missing in: {job_name} -> {branch_name}")
                    missing_aqua.append({"Project Name": job_name, "Branch Name": branch_name})
            except Exception as e:
                print(f"⚠️ Error for {job_name}/{branch_name}: {e}")

    with open(ATTACHMENT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["Project Name", "Branch Name"])
        writer.writeheader()
        writer.writerows(missing_aqua)

    print(f"\n📁 Report saved to: {ATTACHMENT_FILE}")
    send_email()

if __name__ == "__main__":
    main()
