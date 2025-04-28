import jenkins
import csv
import xml.etree.ElementTree as ET

# Jenkins config
JENKINS_URL = 'http://localhost:8080/'
USERNAME = 'devsecops'
API_TOKEN = 'test'

# Connect to Jenkins
server = jenkins.Jenkins(JENKINS_URL, username=USERNAME, password=API_TOKEN)

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
            all_jobs.append(job_path)
    
    return all_jobs

# Get all jobs
all_jobs = get_all_jobs()
print(f"🔍 Total jobs found: {len(all_jobs)}")

# List of jobs missing stage('Aqua')
missing_aqua_jobs = []

for job_path in all_jobs:
    try:
        config_xml = server.get_job_config(job_path)
        if "Aqua Security Scan" not in config_xml:
            print(f"❌ stage('Aqua') not found in job: {job_path}")
            missing_aqua_jobs.append({"Job Name": job_path})
    except Exception as e:
        print(f"⚠️ Skipped job {job_path} due to error: {e}")

# Write results to CSV
csv_file = "jenkins_jobs_missing_aqua.csv"
with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
    writer = csv.DictWriter(file, fieldnames=["Job Name"])
    writer.writeheader()
    writer.writerows(missing_aqua_jobs)

print(f"\n📁 Saved {len(missing_aqua_jobs)} job(s) missing `stage('Aqua')` to: {csv_file}")
