import jenkins
import csv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import os
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning  # type: ignore

# Suppress the InsecureRequestWarning when using requests without SSL verification
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)  # type: ignore

# Jenkins config
JENKINS_URL = 'https://jenkins-prod.com'
USERNAME = 'test@gmail.com'
PASSWORD = 'test'

# Gmail SMTP config
SENDER_EMAIL = 'test@test.com'  # Replace with your Gmail email
APP_PASSWORD = 'test'  # Replace with your generated App Password
RECIPIENT_EMAIL = 'test@test.com'  # Replace with recipient email
SMTP_SERVER = 'smtp.gmail.com'  # SMTP server for Gmail
SMTP_PORT = 587  # SMTP port for TLS

# Branches to scan
TARGET_BRANCHES = ["main", "master", "dev", "qas", "prod"]

# Email Recipients
TO_EMAILS = ['sharear.ahmed@test.com', 'sharear.ahmed@test.com']  # Main recipients
CC_EMAILS = ['sharear.ahmed@test.com', 'sharear.ahmed@test.com']  # CC recipients
EMAIL_SUBJECT = '🔔 Jenkins Aqua Stage Check Report'
EMAIL_BODY = """
Hi Team,

Please find the attached report for Jenkins jobs/branches missing the Aqua Security Scan stage.

This is an automated email.

Thanks,
DevSecOps Team
"""

# Output CSV
ATTACHMENT_FILE = "jenkins_missing_aqua_stages.csv"

# Connect to Jenkins with SSL verification disabled (using verify=False)
server = jenkins.Jenkins(JENKINS_URL, username=USERNAME, password=PASSWORD)

# Disable SSL verification globally for requests made by the Jenkins client
session = requests.Session()
session.verify = False  # This disables SSL certificate verification for all requests
server._session = session  # Assign this session to the Jenkins server instance

# Fetch all jobs and handle folder jobs explicitly
def get_all_jobs():
    print("Fetching jobs from Jenkins...")  # Debug log
    jobs = server.get_jobs()  # Fetch all jobs at the root level
    print(f"Fetched Jobs: {jobs}")  # Debugging the jobs fetched

    all_jobs = []

    for job in jobs:
        job_name = job['name']
        job_class = job['_class']

        # If job is a folder, we skip it and handle folder jobs separately
        if job_class == 'com.cloudbees.hudson.plugins.folder.Folder':
            print(f"⚠️ Skipping folder: {job_name}")  # Debugging folder processing
            continue  # Skip folders completely
        else:
            all_jobs.append({"name": job_name, "_class": job_class})

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

    # Attach the email body
    msg.attach(MIMEText(EMAIL_BODY, 'plain'))

    # Attach the CSV report
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

    missing_aqua = []

    for job in all_jobs:
        job_name = job["name"]
        job_class = job["_class"]
        print(f"Checking job: {job_name}")

        try:
            # Handle multibranch pipeline jobs separately
            if 'workflow.multibranch' in job_class:
                branches = server.get_job_info(job_name)['jobs']
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
                        config_xml = server.get_job_config(f"{job_name}/{branch_name}")

                        if "Aqua Security Scan" not in config_xml:
                            print(f"❌ Aqua stage missing in: {job_name} -> {branch_name}")
                            missing_aqua.append({"Project Name": job_name, "Branch Name": branch_name})

                    except Exception as e:
                        print(f"⚠️ Error checking branch {branch_name} of {job_name}: {e}")
            else:
                # Handle non-multibranch (single-branch) jobs (pipeline/freestyle)
                branch_name = "N/A"
                config_xml = server.get_job_config(job_name)

                if "Aqua Security Scan" not in config_xml:
                    print(f"❌ Aqua stage missing in: {job_name}")
                    missing_aqua.append({"Project Name": job_name, "Branch Name": branch_name})

        except Exception as e:
            print(f"⚠️ Error checking job {job_name}: {e}")

    # Write results to CSV
    with open(ATTACHMENT_FILE, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=["Project Name", "Branch Name"])
        writer.writeheader()
        writer.writerows(missing_aqua)

    print(f"\n📁 Saved {len(missing_aqua)} job(s) missing Aqua stage to: {ATTACHMENT_FILE}")

    # Send the report by email
    send_email()

if __name__ == "__main__":
    main()
