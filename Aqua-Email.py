import jenkins
import requests
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
import ssl
import json

# --- Custom HTTPS Adapter to skip SSL verification securely ---
class SSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = context
        self.poolmanager = PoolManager(*args, **kwargs)

# --- Create a session with SSL verification disabled ---
session = requests.Session()
session.mount("https://", SSLAdapter())

# --- Patch the python-jenkins session with our custom session ---
jenkins.requests = requests
jenkins.requests.Session = lambda: session

# --- Jenkins credentials and URL ---
jenkins_url = 'https://jenkins-ca-prod.global.iff.com'
username = 'your_username_here'  # Replace with your Jenkins username
api_token = 'your_api_token_here'  # Replace with your Jenkins API token or password

# --- Connect to Jenkins server ---
server = jenkins.Jenkins(jenkins_url, username=username, password=api_token)

# --- Example: Get Jenkins user and version info ---
try:
    user = server.get_whoami()
    version = server.get_version()
    print(f"Connected to Jenkins {version} as {user['fullName']}")
except Exception as e:
    print("Error connecting to Jenkins:", str(e))

# --- Function to fetch all jobs ---
def get_all_jobs():
    try:
        jobs = server.get_all_jobs()
        print(f"Found {len(jobs)} jobs:")
        for job in jobs:
            print(f" - {job['fullname']}")
        return jobs
    except jenkins.JenkinsException as e:
        print(f"Error fetching jobs: {str(e)}")

# --- Function to trigger a job ---
def trigger_job(job_name):
    try:
        server.build_job(job_name)
        print(f"Triggered job: {job_name}")
    except jenkins.JenkinsException as e:
        print(f"Error triggering job {job_name}: {str(e)}")

# --- Function to get job build status ---
def get_job_build_status(job_name):
    try:
        builds = server.get_job_info(job_name)['builds']
        last_build = builds[0]
        build_status = last_build['result']
        print(f"Last build status for {job_name}: {build_status}")
        return build_status
    except jenkins.JenkinsException as e:
        print(f"Error fetching build status for job {job_name}: {str(e)}")

# --- Function to fetch job's console output ---
def get_job_console_output(job_name, build_number=1):
    try:
        console_output = server.get_build_console_output(job_name, build_number)
        print(f"Console output for {job_name} build {build_number}:")
        print(console_output)
    except jenkins.JenkinsException as e:
        print(f"Error fetching console output for job {job_name}: {str(e)}")

# --- Function to handle jobs, retry, and email logic ---
def main():
    try:
        # Fetch all jobs
        all_jobs = get_all_jobs()

        for job in all_jobs:
            job_name = job['fullname']

            # Check last build status for each job
            build_status = get_job_build_status(job_name)

            if build_status != 'SUCCESS':
                print(f"Build failed for job {job_name}, sending email...")

                # Logic to trigger an email alert (if any)
                # Implement email alert functionality here
                # For now, it's just a placeholder for the email functionality
                send_email_alert(job_name, build_status)

    except Exception as e:
        print(f"Error during main execution: {str(e)}")

# --- Placeholder for email sending (you can implement this function) ---
def send_email_alert(job_name, build_status):
    print(f"Sending email alert for {job_name} with status: {build_status}")
    # You can use an email sending library like smtplib to send alerts here
    pass

# --- Run the script ---
if __name__ == "__main__":
    main()
