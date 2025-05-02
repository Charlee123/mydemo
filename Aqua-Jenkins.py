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

# Logging setup: to file AND console
logger = logging.getLogger("JenkinsAquaCheck")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler("jenkins_aqua_check.log")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
logger.addHandler(console_handler)

# Session setup
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
        logger.error(f"Failed to fetch URL: {url} - {e}")
        return None


def get_all_jobs(folder_url):
    jobs = []
    data = get_json(folder_url)
    if not data:
        logger.error("❌ Failed to retrieve jobs in folder.")
        return jobs

    logger.info(f"📁 Found {len(data.get('jobs', []))} items in '{FOLDER_PATH}' folder.")
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

    logger.info(f"🔍 Total jobs/branches to check: {len(jobs)}")
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
    logger.info("🚀 Starting Jenkins Aqua Code Scan audit...")

    folder_url = urljoin(JENKINS_URL + "/", f"job/{FOLDER_PATH}")
    logger.info(f"🔐 Authenticating to Jenkins at {JENKINS_URL}...")

    # Quick check to verify Jenkins is reachable
    test = get_json(folder_url)
    if not test:
        logger.error("❌ Authentication failed or Jenkins not reachable.")
        return
    logger.info("✅ Jenkins authenticated successfully.")

    jobs = get_all_jobs(folder_url)
    missing_aqua = []

    for job in jobs:
        logger.info(f"🔎 Checking job: {job['name']}")
        try:
            found, reason = has_aqua_stage(job["url"])
            if not found:
                logger.warning(f"⚠️  Missing Aqua stage in: {job['name']} — {reason}")
                missing_aqua.append({
                    "Application/Job": job["name"],
                    "Reason": reason
                })
            else:
                logger.info(f"✅ Aqua stage found in: {job['name']}")
        except Exception as e:
            logger.exception(f"Error checking {job['name']}: {e}")

    # Write report
    with open("missing_aqua_stages.csv", "w", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["Application/Job", "Reason"])
        writer.writeheader()
        writer.writerows(missing_aqua)

    logger.info("📄 CSV report saved as: missing_aqua_stages.csv")
    logger.info(f"✅ Audit complete. {len(missing_aqua)} jobs missing Aqua Code Scan stage.")


if __name__ == "__main__":
    main()
