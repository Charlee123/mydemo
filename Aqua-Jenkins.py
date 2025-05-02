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
PASSWORD = "your_password"  # Replace securely in production

# Setup logging: console + file
logger = logging.getLogger("JenkinsAudit")
logger.setLevel(logging.INFO)

log_format = logging.Formatter("• %(message)s")
file_handler = logging.FileHandler("jenkins_aqua_check.log")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_format)
logger.addHandler(console_handler)

# Setup session
session = requests.Session()
session.auth = (USERNAME, PASSWORD)
session.verify = False
session.headers.update({"Accept": "application/json"})


def get_json(url):
    try:
        res = session.get(f"{url}/api/json")
        res.raise_for_status()
        return res.json()
    except requests.RequestException as e:
        logger.error(f"❌ Failed to fetch URL: {url} - {e}")
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
        return None  # Skip jobs with no successful builds

    execution_data = get_json(f"{job_url}/lastSuccessfulBuild/executions")
    if not execution_data:
        return None  # Skip jobs with no execution data (no stages)

    stages = [stage["name"] for stage in execution_data.get("pipelines", []) if "name" in stage]

    if not stages:
        return None  # Skip jobs that have no stages

    return AQUA_STAGE_NAME in stages


def main():
    logger.info("🚀 Starting Jenkins Aqua Code Scan audit...\n")
    folder_url = urljoin(JENKINS_URL + "/", f"job/{FOLDER_PATH}")

    logger.info(f"🔐 Authenticating to Jenkins: {JENKINS_URL}")
    test = get_json(folder_url)
    if not test:
        logger.error("❌ Authentication failed or Jenkins not reachable.")
        return
    logger.info("✅ Authentication successful.\n")

    jobs = get_all_jobs(folder_url)
    missing_aqua = []

    for job in jobs:
        job_name = job["name"]
        logger.info(f"🔎 Checking job: {job_name}")

        try:
            has_stage = has_aqua_stage(job["url"])
            if has_stage is None:
                logger.info(f"⏭️  Skipping {job_name} — No stages to check.\n")
                continue
            elif not has_stage:
                logger.warning(f"⚠️  Aqua Stage NOT found in: {job_name}\n")
                missing_aqua.append({
                    "Application/Job": job_name,
                    "Reason": "Aqua Stage not implemented"
                })
            else:
                logger.info(f"✅ Aqua Stage found in: {job_name}\n")
        except Exception as e:
            logger.exception(f"❌ Error checking job {job_name}: {e}")

    # Write final report
    if missing_aqua:
        with open("missing_aqua_stages.csv", "w", newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["Application/Job", "Reason"])
            writer.writeheader()
            writer.writerows(missing_aqua)
        logger.info(f"\n📄 Report saved: missing_aqua_stages.csv")
        logger.info(f"✅ {len(missing_aqua)} job(s) missing Aqua Code Scan stage.\n")
    else:
        logger.info("\n✅ All checked jobs include Aqua Code Scan stage. No report generated.")


if __name__ == "__main__":
    main()
