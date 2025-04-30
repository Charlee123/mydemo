import gitlab
import pandas as pd
from tqdm import tqdm
import time
from urllib.parse import urlparse

# -----------------------------
# GitLab Connection Setup
# -----------------------------
GITLAB_URL = 'https://gitlab.com'  # Change this if self-hosted
ACCESS_TOKEN = 'glpat-wJXweM94RF94Vbd-e9xy'  # Replace with your token

gl = gitlab.Gitlab(GITLAB_URL, private_token=ACCESS_TOKEN)

# -----------------------------
# Read CSV File with Repo URLs
# -----------------------------
input_file = 'inactive_repos.csv'
df = pd.read_csv(input_file)

# Extract project path from URL
def extract_project_path(repo_url):
    parsed = urlparse(repo_url)
    return parsed.path.strip('/')

df['project_path'] = df['Repo URL'].apply(extract_project_path)
repo_paths = df['project_path'].tolist()

# -----------------------------
# Archive Repositories
# -----------------------------
successful_archives = []
failed_archives = []

print("\nArchiving Repos 🚀:")

for repo_path in tqdm(repo_paths, desc="Archiving Repos 🚀", unit="repo"):
    try:
        project = gl.projects.get(repo_path)

        if project.archived:
            print(f"ℹ️ Already archived: {repo_path}")
            successful_archives.append({'repo_path': repo_path, 'status': 'Already Archived'})
        else:
            project.archive()
            print(f"✅ Successfully archived: {repo_path}")
            successful_archives.append({'repo_path': repo_path, 'status': 'Archived'})

    except gitlab.exceptions.GitlabGetError as e:
        print(f"⚠️ Repo not found or inaccessible: {repo_path}")
        failed_archives.append({'repo_path': repo_path, 'reason': str(e)})

    except gitlab.exceptions.GitlabAuthenticationError:
        print("🔒 Authentication error. Check your token.")
        break

    except Exception as e:
        print(f"❌ Error archiving '{repo_path}': {str(e)}")
        failed_archives.append({'repo_path': repo_path, 'reason': str(e)})

    # Optional delay for rate limiting
    time.sleep(5)

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
