import gitlab
import pandas as pd
from tqdm import tqdm
import time

# -----------------------------
# GitLab Connection Setup
# -----------------------------
GITLAB_URL = 'https://gitlab.com'
ACCESS_TOKEN = 'glpat-wJXweM94RF94Vbd-e9xy'  # Replace with your token

gl = gitlab.Gitlab(GITLAB_URL, private_token=ACCESS_TOKEN)

# -----------------------------
# Read CSV File with Repos
# -----------------------------
input_file = 'inactive_repos.csv'
df = pd.read_csv(input_file)

repo_list = df['Repo Name'].tolist()

# -----------------------------
# Archive Repositories
# -----------------------------
successful_archives = []
failed_archives = []

print("\nArchiving Repos 🚀:")

for repo_name in tqdm(repo_list, desc="Archiving Repos 🚀", unit="repo"):
    try:
        # Fetch the project
        projects = gl.projects.list(search=repo_name, get_all=True)

        if not projects:
            print(f"⚠️ Repo not found: {repo_name}")
            failed_archives.append({'repo_name': repo_name, 'reason': 'Not found'})
        else:
            project = projects[0]

            if project.archived:
                print(f"ℹ️ Already archived: {repo_name}")
                successful_archives.append({'repo_name': repo_name, 'status': 'Already Archived'})
            else:
                project.archive()
                print(f"✅ Successfully archived: {repo_name}")
                successful_archives.append({'repo_name': repo_name, 'status': 'Archived'})

    except gitlab.exceptions.GitlabAuthenticationError:
        print("🔒 Authentication error. Check your token.")
        break

    except Exception as e:
        print(f"❌ Error archiving '{repo_name}': {str(e)}")
        failed_archives.append({'repo_name': repo_name, 'reason': str(e)})

    # ✅ Delay to avoid rate limits
    time.sleep(20)

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
