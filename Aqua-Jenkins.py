import requests
import csv

JENKINS_URL = "https://my.jenkins.com"
FOLDER_PATH = "application"
AQUA_STAGE_NAME = "Aqua Code Scan"

# Replace these with your Jenkins user and API token
USERNAME = "devsecops"
API_TOKEN = "test"

AUTH = (USERNAME, API_TOKEN)

def get_json(url):
    full_url = f"{url}/api/json"
    response = requests.get(full_url, auth=AUTH)
    response.raise_for_status()
    return response.json()

def get_all_jobs(folder):
    url = f"{JENKINS_URL}/job/{folder}"
    data = get_json(url)
    jobs = []

    for job in data.get('jobs', []):
        if job['_class'] in ('com.cloudbees.hudson.plugins.folder.Folder',):
            # Nested folder - optional to recurse
            continue
        jobs.append({
            "name": job['name'],
            "url": job['url'].rstrip("/")
        })

    return jobs

def aqua_stage_present(job_url):
    # Check last successful build's pipeline stages
    try:
        build_data = get_json(f"{job_url}/lastSuccessfulBuild")
        build_id = build_data.get("id")
        if not build_id:
            return False, "No successful build"
        
        stages_url = f"{job_url}/lastSuccessfulBuild/executions"
        stage_data = get_json(stages_url)

        stages = [s.get("name") for s in stage_data.get("pipelines", []) if s.get("name")]
        if AQUA_STAGE_NAME in stages:
            return True, ""
        else:
            return False, "Aqua Code Scan stage not found"

    except requests.HTTPError:
        return False, "Error accessing build data"

def main():
    jobs = get_all_jobs(FOLDER_PATH)
    missing_aqua = []

    for job in jobs:
        print(f"Checking {job['name']}...")
        present, reason = aqua_stage_present(job["url"])
        if not present:
            missing_aqua.append({
                "Application/Job": job["name"],
                "Reason": reason
            })

    with open("missing_aqua_stages.csv", "w", newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["Application/Job", "Reason"])
        writer.writeheader()
        writer.writerows(missing_aqua)

    print("✅ Report generated: missing_aqua_stages.csv")

if __name__ == "__main__":
    main()
