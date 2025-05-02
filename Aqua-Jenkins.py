import requests
import csv
import logging
import urllib3
import sys
from urllib.parse import urljoin
from tqdm import tqdm

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Jenkins Config
JENKINS_URL = "https://my.jenkins.com"
FOLDER_PATH = "application"
AQUA_STAGE_NAME = "Aqua Code Scan"
USERNAME = "your_username"
PASSWORD = "your_password"  # Replace securely

# Logging Setup
logger = logging.getLogger("JenkinsAudit")
logger.setLevel(logging.INFO)

# File log (with full info)
file_handler = logging.FileHandler("jenkins_aqua_check.log", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)

# Console log (clean)
console_handler = logging.StreamHandler(stream=sys.stdout)
console_handler.setFormatter(logging.Formatter("- %(message)s"))
logger.addHandler(console_handler)

# Jenkins API Session
session = requests.Session()
session.auth = (USERNAME, PASSWORD)
session.verify = False
session.headers.update({"Accept": "application/json"})


def get_json(url):
    try:
        response = session.get(f"{url}/api/json")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch URL: {url} — {str(e)}")
        return None


def get_all_jobs(folder_url):
    jobs = []
    data = get_json(folder_url)
    if not data:
        logger.error("Could not retrieve jobs in the folder.")
        return jobs

    logger.info(f"Found {len(data.get('jobs', []))} items in folder '{FOLDER_PATH}'.")
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

    logger.info(f"Total jobs/branches to check: {len(jobs)}")
    return jobs


def has_aqua_stage(job_url):
    build_data = get_json(f"{job_url}/lastSuccessfulBuild")
    if not build_data or not build_data.get("id"):
        return None  # No successful build

    execution_data = get_json(f"{job_url}/lastSuccessfulBuild/executions")
    if not execution_data:
        return None  # No pipeline/stages

    stages = [stage["name"] for stage in execution_data.get("pipelines", []) if "name" in stage]

    if not stages:
        return None  # Build exists, but no stages

    return AQUA_STAGE_NAME in stages


def main():
    logger.info("🔐 Authenticating to Jenkins...")
    folder_url = urljoin(JENKINS_URL + "/", f"job/{FOLDER_PATH}")
    if not get_json(folder_url):
        logger.error("Authentication failed or Jenkins is unreachable.")
        return
    logger.info("✅ Authentication successful.\n")

    jobs = get_all_jobs(folder_url)
    if not jobs:
        logger.info("No jobs found. Exiting.")
        return

    missing_aqua = []

    logger.info("🔎 Starting Aqua Stage checks...\n")
    for job in tqdm(jobs, desc="Checking jobs", unit="job"):
        job_name = job["name"]
        try:
            has_stage = has_aqua_stage(job["url"])
            if has_stage is None:
                continue  # Skip jobs with no stages
            elif not has_stage:
                logger.warning(f"Aqua Stage NOT implemented in: {job_name}")
                missing_aqua.append({
                    "Application/Job": job_name,
                    "Reason": "Aqua Stage not implemented"
                })
        except Exception as e:
            logger.error(f"Error checking job {job_name}: {str(e)}")

    if missing_aqua:
        with open("missing_aqua_stages.csv", "w", newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Application/Job", "Reason"])
            writer.writeheader()
            writer.writerows(missing_aqua)
        logger.info(f"\n📄 Report saved to: missing_aqua_stages.csv")
        logger.info(f"⚠️  {len(missing_aqua)} job(s) missing Aqua Code Scan stage.")
    else:
        logger.info("\n✅ All jobs include Aqua Code Scan stage. No report needed.")


if __name__ == "__main__":
    main()
