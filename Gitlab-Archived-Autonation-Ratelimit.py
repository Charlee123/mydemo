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

def check_rate_limit():
    # Get rate limit status from the GitLab API headers
    rate_limit = gl.get('/application/settings')
    remaining = rate_limit['rate_limit_remaining']  # Remaining requests
    reset = rate_limit['rate_limit_reset']  # When the limit resets (timestamp)
    return remaining, reset

for idx, repo_name in enumerate(tqdm(repo_list, desc="Archiving Repos 🚀", unit="repo")):
    retry_count = 0
    while retry_count < 3:  # Retry a repository up to 3 times if 403 occurs
        # Check rate limit
        remaining, reset_timestamp = check_rate_limit()

        # If remaining requests are 0, calculate sleep time based on reset timestamp
        if remaining == 0:
            reset_time = reset_timestamp - int(time.time())  # Time left for reset
            if reset_time > 0:
                print(f"\n🕒 Rate limit reached. Waiting for {reset_time} seconds for reset...\n")
                time.sleep(reset_time)

        try:
            print(f"\n🔍 Processing repo: {repo_name} (Attempt {retry_count + 1}/3)...")
            projects = gl.projects.list(search=repo_name, get_all=True)

            if not projects:
                print(f"⚠️ Repo not found: {repo_name}")
                failed_archives.append({'repo_name': repo_name, 'reason': 'Not found'})
                break

            project = projects[0]

            if project.archived:
                print(f"ℹ️ Repo '{repo_name}' is already archived.")
                successful_archives.append({'repo_name': repo_name, 'status': 'Already Archived'})
                break

            print(f"📦 Archiving repo: {repo_name}...")
            project.archive()
            print(f"✅ Successfully archived: {repo_name}")
            successful_archives.append({'repo_name': repo_name, 'status': 'Archived'})
            break  # Break out of the retry loop if successful

        except gitlab.exceptions.GitlabHttpError as e:
            if e.response_code == 403:
                print(f"❌ Rate limit hit for '{repo_name}'. Skipping and waiting for rate limit reset.")
                remaining, reset_timestamp = check_rate_limit()
                if remaining == 0:
                    reset_time = reset_timestamp - int(time.time())
                    print(f"⏳ Waiting for {reset_time} seconds before retrying...")
                    time.sleep(reset_time)
                retry_count += 1
                if retry_count >= 3:
                    print(f"⚠️ Maximum retries reached for '{repo_name}'. Skipping for now.")
                    failed_archives.append({'repo_name': repo_name, 'reason': 'Rate limit hit (403) - Max retries'})
                else:
                    print(f"🔄 Retrying ({retry_count}/3) for '{repo_name}'...")

            else:
                print(f"❌ Error archiving '{repo_name}': {str(e)}")
                failed_archives.append({'repo_name': repo_name, 'reason': str(e)})
                break  # Exit the retry loop after a different error

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
