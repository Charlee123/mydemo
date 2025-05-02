import requests
import urllib3
import csv
import os

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Jenkins settings
JENKINS_URL = "https://your-jenkins-url"  # Change this
USERNAME = "your-username"                # Change this
API_TOKEN = "your-api-token"              # Change this
auth = (USERNAME, API_TOKEN)

# CSV output
CSV_FILE = "jenkins_missing_aqua_stages.csv"


def get_json(url):
    try:
        response = requests.get(f"{url}/api/json", auth=auth, verify=False)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Failed to fetch {url}: {e}")
        return {}


def find_jobs_missing_aqua(base_url, path=""):
    missing_jobs = []
    data = get_json(base_url)

    jobs = data.get("jobs", [])
    for job in jobs:
        name = job.get("name")
        _class = job.get("_class")
        url = job.get("url")

        if _class and "Folder" in _class:
            # 📁 Recurse into folder
            missing_jobs += find_jobs_missing_aqua(url, path + "/" + name)
        elif _class and "WorkflowJob" in _class:
            # 🧪 Pipeline job
            config_url = f"{url}config.xml"
            try:
                response = requests.get(config_url, auth=auth, verify=False)
                if "Aqua" not in response.text:
                    print(f"🚫 Missing Aqua: {path}/{name}")
                    missing_jobs.append({
                        "folder": path.strip("/"),
                        "job_name": name,
                        "url": url
                    })
                else:
                    print(f"✅ Has Aqua: {path}/{name}")
            except Exception as e:
                print(f"⚠️ Failed to get config for {name}: {e}")
    return missing_jobs


def save_to_csv(missing_jobs):
    with open(CSV_FILE, mode="w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["folder", "job_name", "url"])
        writer.writeheader()
        writer.writerows(missing_jobs)
    print(f"\n📁 Saved {len(missing_jobs)} job(s) missing Aqua stage to: {CSV_FILE}")


def main():
    print("Fetching jobs from Jenkins...\n")
    missing = find_jobs_missing_aqua(JENKINS_URL)
    save_to_csv(missing)


if __name__ == "__main__":
    main()
