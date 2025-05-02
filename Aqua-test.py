import jenkins
import requests

# Jenkins config
JENKINS_URL = 'https://jenkins-ca-prod.global.iff.com/'
USERNAME = 'test@gmail.com'
PASSWORD = 'test'

# Connect to Jenkins with SSL verification disabled (using verify=False)
server = jenkins.Jenkins(JENKINS_URL, username=USERNAME, password=PASSWORD)

# Disable SSL verification globally for requests made by the Jenkins client
session = requests.Session()
session.verify = False  # This disables SSL certificate verification for all requests
server._session = session  # Assign this session to the Jenkins server instance

def get_all_jobs():
    try:
        # Fetch jobs directly from Jenkins and print the response
        jobs = server.get_jobs()
        print("Raw Response from Jenkins:", jobs)  # Log raw response
        return jobs
    except Exception as e:
        print(f"⚠️ Error fetching jobs: {e}")
        return []

def main():
    print("Fetching jobs from Jenkins...")
    all_jobs = get_all_jobs()
    
    if not all_jobs:
        print("⚠️ No jobs found or unable to fetch jobs from Jenkins!")
    else:
        print(f"🔍 Total jobs found: {len(all_jobs)}")
        # Further logic can go here if you want to process the jobs after this point.

if __name__ == "__main__":
    main()
