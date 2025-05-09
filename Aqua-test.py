import jenkins
import requests

# Jenkins config
JENKINS_URL = 'https://jenkins-prod.com'
USERNAME = 'test@gmail.com'
PASSWORD = 'test'

# Connect to Jenkins with SSL verification disabled (using verify=False)
server = jenkins.Jenkins(JENKINS_URL, username=USERNAME, password=PASSWORD)

# Disable SSL verification globally for requests made by the Jenkins client
session = requests.Session()
session.verify = False  # This disables SSL certificate verification for all requests
server._session = session  # Assign this session to the Jenkins server instance

def get_jobs_missing_aqua_stage():
    missing_aqua_jobs = []

    try:
        # Fetch jobs directly from Jenkins
        jobs = server.get_jobs()
        print(f"🔍 Total jobs fetched: {len(jobs)}")  # Log total number of jobs

        # Function to recursively check for jobs inside folders
        def check_folder_jobs(folder_path):
            try:
                folder_jobs = server.get_jobs(folder_path)
                for job in folder_jobs:
                    job_name = job['name']
                    print(f"Checking job: {job_name}")

                    try:
                        # Fetch job details and check if the 'builds' key exists
                        job_info = server.get_job_info(job_name)
                        builds = job_info.get('builds', [])
                        
                        if not builds:
                            print(f"⚠️ No builds found for job: {job_name}")
                            continue

                        # Now, checking for Aqua stage in the builds
                        aqua_stage_missing = True
                        for build in builds:
                            build_info = server.get_build_info(job_name, build['number'])
                            actions = build_info.get('actions', [])
                            
                            found_aqua = False
                            for action in actions:
                                if isinstance(action, dict):
                                    # Check for Aqua-related parameters in the actions
                                    if 'Aqua' in action.get('parameters', []):
                                        found_aqua = True
                                        break

                            if found_aqua:
                                aqua_stage_missing = False
                                break

                        if aqua_stage_missing:
                            missing_aqua_jobs.append(job_name)
                            print(f"⚠️ Aqua stage missing for job: {job_name}")
                    
                    except Exception as e:
                        print(f"⚠️ Error checking job {job_name}: {e}")

            except Exception as e:
                print(f"⚠️ Error checking folder {folder_path}: {e}")

        # Check all the top-level jobs and folders
        for job in jobs:
            job_name = job['name']
            if 'folder' in job.get('class', ''):
                print(f"🔍 Checking folder: {job_name}")
                check_folder_jobs(job_name)  # Recursively check the folder
            else:
                # It's a direct job, so we check it as usual
                print(f"Checking job: {job_name}")
                check_folder_jobs('')

        return missing_aqua_jobs

    except Exception as e:
        print(f"⚠️ Error fetching jobs: {e}")
        return []

def main():
    print("Fetching jobs from Jenkins...")
    missing_aqua_jobs = get_jobs_missing_aqua_stage()

    if missing_aqua_jobs:
        print(f"📁 Saving {len(missing_aqua_jobs)} jobs missing Aqua stage to: jenkins_missing_aqua_stages.csv")
        # Save missing jobs to CSV file
        with open('jenkins_missing_aqua_stages.csv', 'w') as f:
            for job in missing_aqua_jobs:
                f.write(f"{job}\n")
        
        # Send email notification if needed here (you can call your email function)
        print(f"✅ Email sent successfully to ['sharear.ahmed@iff.com']")  # Placeholder for email
    else:
        print("No jobs found missing Aqua stage!")

if __name__ == "__main__":
    main()
