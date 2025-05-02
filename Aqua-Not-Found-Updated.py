import jenkins
import csv
import xml.etree.ElementTree as ET
import requests
import urllib3
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Disable SSL warnings
urllib3.disable_warnings(InsecureRequestWarning)

# Patch requests session used by python-jenkins
import jenkins
original_init = jenkins.Jenkins.__init__

def patched_init(self, url, username=None, password=None, timeout=10, ssl_verify=True):
    original_init(self, url, username=username, password=password, timeout=timeout)
    self._session.verify = False  # <--- this line disables SSL cert verification
    self._session.headers.update({'User-Agent': 'python-jenkins'})

jenkins.Jenkins.__init__ = patched_init

# Jenkins config
JENKINS_URL = 'https://your-jenkins-url.com/'  # Replace with your actual URL
USERNAME = 'devsecops'
API_TOKEN = 'your-api-token'  # Replace with actual token

# Branches to scan
TARGET_BRANCHES = ["main", "master", "dev", "qas", "prod"]

# Connect to Jenkins
server = jenkins.Jenkins(JENKINS_URL, username=USERNAME, password=API_TOKEN)

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

# Get all jobs
all_jobs = get_all_jobs()
print(f"🔍 Total jobs found: {len(all_jobs)}")

# Filter multibranch pipeline jobs
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
            config_xml = server.get_job_config(f"{job_name}/{branch_name}")

            if "Aqua Security Scan" not in config_xml:
                print(f"❌ Aqua stage missing in: {job_name} -> {branch_name}")
                missing_aqua.append({"Project Name": job_name, "Branch Name": branch_name})

        except Exception as e:
            print(f"⚠️ Error checking branch {branch_name} of {job_name}: {e}")

# Write result to CSV
csv_file = "jenkins_missing_aqua_stages.csv"
with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
    writer = csv.DictWriter(file, fieldnames=["Project Name", "Branch Name"])
    writer.writeheader()
    writer.writerows(missing_aqua)

print(f"\n📁 Saved {len(missing_aqua)} job(s) missing Aqua stage to: {csv_file}")
