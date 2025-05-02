import requests
import csv
import logging
import urllib3
from urllib.parse import urljoin

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Jenkins configuration
JENKINS_URL = "https://my.jenkins.com"
FOLDER_PATH = "application"
AQUA_STAGE_NAME = "Aqua Code Scan"
USERNAME = "your_username"
PASSWORD = "your_password"  # Replace with Jenkins password

# Logging setup
logging.basicConfig(
    filename="jenkins_aqua_check.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Setup session
session = requests.Session()
session.auth = (USERNAME, PASSWORD)
session.verify = False  # Disable SSL verification for self-signed certs
session.headers.update({"Accept": "application/json"})


def get_json(url):
    try:
        res = session.get(f"{url}/api/json")
        res.raise_for_status()
        return res.json()
    except requests.RequestException as e:
        logging.error(f"Failed to fetch URL: {url} - {e}")
        return None


def get_all_jobs(folder_url):
    """Returns all jobs (including multibranch) under the folder"""
    jobs = []
    data = get_json(folder_url)
    if not data:
        return jobs

    for job in data.get("jobs", []):
        job_name = job["name"]
        job_url = job["url"].rstrip("/")
        job_class = job["_class"]

        if "MultiBranchProject" in job_class:
            branch_data = get_json(job_url)
            if branch_data:
                for branch in branch_data.get("jobs", []):
                    jobs.append({
                        "name": f"{job_name}/{branch['name']}",
                        "url": branch["url"].rstrip("/")
                    })
        else:
            jobs.append({"name": job_name, "url": job_url})

    return jobs


def has_aqua_stage(job_url):
    build_data = get_json(f"{job_url}/lastSuccessfulBuild")
    if not build_data or not build_data.get("id"):
        return False, "No successful build"

    execution_data = get_json(f"{job_url}/lastSuccessfulBuild/executions")
    if not execution_data:
        return False, "Failed to get stages"

    stage_names = [stage["name"] for stage in execution_data.get("pipelines", []) if "name" in stage]

    if AQUA_STAGE_NAME in stage_names:
        return True, ""
    else:
        return False, "Aqua Code Scan stage not found"


def main():
    logging.info("Starting Jenkins Aqua stage audit (username/password auth)...")
    folder_url = urljoin(JENKINS_URL + "/", f"job/{FOLDER_PATH}")
    jobs = get_all_jobs(folder_url)
    missing_aqua = []

    for job in jobs:
        logging.info(f"Checking job: {job['name']}")
        try:
            found, reason = has_aqua_stage(job["url"])
            if not found:
                missing_aqua.append({
                    "Application/Job": job["name"],
                    "Reason": reason
                })
        except Exception as e:
            logging.exception(f"Error while checking {job['name']}: {e}")

    # Save to CSV
    with open("missing_aqua_stages.csv", "w", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["Application/Job", "Reason"])
        writer.writeheader()
        writer.writerows(missing_aqua)

    logging.info("✅ Audit complete. Report saved to missing_aqua_stages.csv")


if __name__ == "__main__":
    main()
