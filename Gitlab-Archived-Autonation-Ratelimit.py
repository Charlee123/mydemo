import gitlab
import openpyxl
import pandas as pd
from tqdm import tqdm
import time  # Required for time.sleep

# -----------------------------
# GitLab Connection Setup
# -----------------------------
GITLAB_URL = 'https://gitlab.com'
ACCESS_TOKEN = 'glpat-wJXweM94RF94Vbd-e9xy'  # Replace with your actual token

gl = gitlab.Gitlab(GITLAB_URL, private_token=ACCESS_TOKEN)

# -----------------------------
# Read CSV File with Repos
# -----------------------------
input_file = 'inactive_repos.csv'  # Update with your actual file path
df = pd.read_csv(input_file)

repo_list = df['Repo Name'].tolist()

# -----------------------------
# Archive Repositories
# -----------------------------
successful_archives = []
failed_archives = []

print("\nArchiving Repos 🚀:")

for idx, repo_name in enumerate(tqdm(repo_list, desc="Archiving Repos 🚀", unit="repo")):
    # Wait every 5 requests to respect GitLab rate limit
    if idx > 0 and idx % 5 == 0:
        print("\n🔁 Processed 5 repositories.")
        print("🕒 GitLab rate limit reached (5 req/min). Waiting for 65 seconds...\n")
        time.sleep(65)  # Ensure waiting for 65 seconds

    try:
        projects = gl.projects.list(search=repo_name, get_all=True)

        if not projects:
            print(f"⚠️ Repo not found: {repo_name}")
            failed_archives.append({'repo_name': repo_name, 'reason': 'Not found'})
            continue

        project = projects[0]

        if project.archived:
            print(f"ℹ️ Already archived: {repo_name}")
            successful_archives.append({'repo_name': repo_name, 'status': 'Already Archived'})
            continue

        # Retry logic for 403 rate limit errors
        for attempt in range(3):
            try:
                project.archive()
                print(f"✅ Successfully archived: {repo_name}")
                successful_archives.append({'repo_name': repo_name, 'status': 'Archived'})
                break
            except gitlab.exceptions.GitlabHttpError as e:
                if e.response_code == 403:
                    wait_time = (attempt + 1) * 15
                    print(f"⏳ Rate limit hit. Waiting {wait_time}s before retrying...")
                    time.sleep(wait_time)
                else:
                    raise

    except gitlab.exceptions.GitlabAuthenticationError:
        print("🔒 Authentication error. Check your token.")
        break

    except Exception as e:
        print(f"❌ Error archiving '{repo_name}': {str(e)}")
        failed_archives.append({'repo_name': repo_name, 'reason': str(e)})

# -----------------------------
# Save Result Files
# -----------------------------
if failed_archives:
    pd.DataFrame(failed_archives).to_csv('failed_to_archive_repos.csv', index=False)
if successful_archives:
    pd.DataFrame(successful_archives).to_csv('successful_archived_repos.csv', index=False)

# -----------------------------
# Summary
# -----------------------------
print("\n🎯 Archiving Summary:")
print(f"✅ Successful: {len(successful_archives)}")
print(f"❌ Failed: {len(failed_archives)}")
if failed_archives:
    print("📄 Failed repos saved to 'failed_to_archive_repos.csv'")
if successful_archives:
    print("📄 Successful repos saved to 'successful_archived_repos.csv'")
