import gitlab
import pandas as pd
import time
from tqdm import tqdm

# -----------------------------
# GitLab Configuration
# -----------------------------
GITLAB_URL = 'https://gitlab.com'  # Or your self-hosted GitLab URL
ACCESS_TOKENS = [
    'glpat-xxxxxxxxxxxxxxxxx1',
    'glpat-xxxxxxxxxxxxxxxxx2',
    'glpat-xxxxxxxxxxxxxxxxx3',
    # Add up to 10 tokens here
]
REQUESTS_PER_TOKEN = 5  # GitLab rate limit per minute

def get_gitlab_connection(token):
    return gitlab.Gitlab(GITLAB_URL, private_token=token, ssl_verify=False)

# -----------------------------
# Load Repository List
# -----------------------------
input_file = 'inactive_repos.csv'
df = pd.read_csv(input_file)
repo_list = df['Repo Name'].tolist()

# -----------------------------
# Archiving Logic
# -----------------------------
successful_archives = []
failed_archives = []

token_idx = 0
request_count = 0
gl = get_gitlab_connection(ACCESS_TOKENS[token_idx])

print("\nArchiving Repos 🚀:\n")

i = 0
while i < len(repo_list):
    repo_name = repo_list[i]
    try:
        if request_count >= REQUESTS_PER_TOKEN:
            token_idx = (token_idx + 1) % len(ACCESS_TOKENS)
            gl = get_gitlab_connection(ACCESS_TOKENS[token_idx])
            request_count = 0
            print(f"🔁 Switched to token {token_idx + 1}. Waiting 65 seconds to respect rate limit...")
            time.sleep(65)

        print(f"🔍 [{i+1}/{len(repo_list)}] Searching for repo: {repo_name}")
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
        else:
            project.archive()
            print(f"✅ Archived: {repo_name}")
            successful_archives.append({'repo_name': repo_name, 'status': 'Archived'})

        request_count += 1
        i += 1

    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"🔒 Authentication error. Token {token_idx + 1} is invalid.")
        failed_archives.append({'repo_name': repo_name, 'reason': 'Auth error'})
        token_idx = (token_idx + 1) % len(ACCESS_TOKENS)
        gl = get_gitlab_connection(ACCESS_TOKENS[token_idx])
        request_count = 0
        time.sleep(5)

    except gitlab.exceptions.GitlabHttpError as e:
        if e.response_code == 403:
            print(f"⏳ 403 Rate limit for token {token_idx + 1}. Waiting 70 seconds...")
            time.sleep(70)
            gl = get_gitlab_connection(ACCESS_TOKENS[token_idx])
            request_count = 0
            # Do not increment `i` → retry same repo
            continue
        else:
            print(f"❌ HTTP error archiving '{repo_name}': {str(e)}")
            failed_archives.append({'repo_name': repo_name, 'reason': str(e)})
            i += 1

    except Exception as e:
        print(f"❌ General error archiving '{repo_name}': {str(e)}")
        failed_archives.append({'repo_name': repo_name, 'reason': str(e)})
        i += 1

# -----------------------------
# Save Results
# -----------------------------
if failed_archives:
    pd.DataFrame(failed_archives).to_csv('failed_to_archive_repos.csv', index=False)
if successful_archives:
    pd.DataFrame(successful_archives).to_csv('successful_archived_repos.csv', index=False)

print("\n🎯 Archiving Summary:")
print(f"✅ Successfully Archived: {len(successful_archives)}")
print(f"❌ Failed: {len(failed_archives)}")
