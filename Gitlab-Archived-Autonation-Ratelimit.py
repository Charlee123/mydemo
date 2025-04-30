import gitlab
import openpyxl
import pandas as pd
from tqdm import tqdm
import time
import requests  # Import requests to manually check rate limit

# -----------------------------
# GitLab Connection Setup
# -----------------------------
GITLAB_URL = 'https://gitlab.com'
ACCESS_TOKENS = ['glpat-wJXweM94RF94Vbd-e9xy', 'test']  # Replace with your actual token

REQUESTS_PER_TOKEN = 5  # GitLab rate limit per minute

INPUT_FILE = 'inactive_repos.csv'

# -----------------------------
# Token Management
# -----------------------------
def get_gitlab_connection(token):
    try:
        gl = gitlab.Gitlab(GITLAB_URL, private_token=token)
        gl.auth()
        return gl
    except Exception as e:
        print(f"❌ Failed to connect with token {token[:10]}... — {str(e)}")
        return None

# -----------------------------
# Initialize
# -----------------------------
df = pd.read_csv(INPUT_FILE)
repo_list = df['Repo Name'].tolist()

successful_archives = []
failed_archives = []

token_idx = 0
request_count = 0
gl = get_gitlab_connection(ACCESS_TOKENS[token_idx])
if gl is None:
    raise Exception("🛑 Failed to establish initial GitLab connection.")

# -----------------------------
# Archive Logic
# -----------------------------
print("\n🔧 Archiving Repositories...\n")

i = 0
while i < len(repo_list):
    repo_name = repo_list[i]
    print(f"\n🔍 Processing repo: {repo_name}")

    try:
        if request_count >= REQUESTS_PER_TOKEN:
            token_idx = (token_idx + 1) % len(ACCESS_TOKENS)
            gl = get_gitlab_connection(ACCESS_TOKENS[token_idx])
            if gl is None:
                print("🛑 All tokens failed. Exiting.")
                break
            request_count = 0
            print(f"🔄 Switched to token {token_idx + 1}/{len(ACCESS_TOKENS)}")

        projects = gl.projects.list(search=repo_name, get_all=True)
        request_count += 1

        if not projects:
            print(f"⚠️ Repo not found: {repo_name}")
            failed_archives.append({'repo_name': repo_name, 'reason': 'Not found'})
            i += 1
            continue

        project = projects[0]

        if project.archived:
            print(f"ℹ️ Already archived: {repo_name}")
            successful_archives.append({'repo_name': repo_name, 'status': 'Already Archived'})
            i += 1
            continue

        project.archive()
        request_count += 1
        print(f"✅ Successfully archived: {repo_name}")
        successful_archives.append({'repo_name': repo_name, 'status': 'Archived'})
        i += 1

    except gitlab.exceptions.GitlabHttpError as e:
        if e.response_code == 403:
            print(f"⏳ 403 Rate Limit. Waiting 70 seconds before retry...")
            time.sleep(70)
            continue  # retry same repo
        else:
            print(f"❌ GitLab HTTP error on '{repo_name}': {str(e)}")
            failed_archives.append({'repo_name': repo_name, 'reason': str(e)})
            i += 1
    except Exception as e:
        print(f"❌ Unexpected error on '{repo_name}': {str(e)}")
        failed_archives.append({'repo_name': repo_name, 'reason': str(e)})
        i += 1

# -----------------------------
# Save Results
# -----------------------------
if failed_archives:
    failed_file = 'failed_to_archive_repos.csv'
    pd.DataFrame(failed_archives).to_csv(failed_file, index=False)
    print(f"\n❌ Failed repos saved to: {failed_file}")

if successful_archives:
    success_file = 'successful_archived_repos.csv'
    pd.DataFrame(successful_archives).to_csv(success_file, index=False)
    print(f"\n✅ Successfully archived repos saved to: {success_file}")

# -----------------------------
# Summary
# -----------------------------
print("\n📊 Archiving Summary:")
print(f"✅ Successful: {len(successful_archives)}")
print(f"❌ Failed: {len(failed_archives)}")
