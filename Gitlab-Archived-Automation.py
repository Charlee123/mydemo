import gitlab
import openpyxl
import pandas as pd
from tqdm import tqdm

# -----------------------------
# GitLab Connection Setup
# -----------------------------
GITLAB_URL = 'https://gitlab.com'
ACCESS_TOKEN = 'test'  # Personal Access Token (not username/password)

gl = gitlab.Gitlab(GITLAB_URL, private_token=ACCESS_TOKEN)

# -----------------------------
# Read Excel File with Repos
# -----------------------------
input_file = 'inactive_repos.csv'  # Replace with your file path
df = pd.read_csv(input_file)

# Assuming your Excel file has a column named 'repository_name'
repo_list = df['Repo Name'].tolist()

# -----------------------------
# Archive Repositories
# -----------------------------
successful_archives = []
failed_archives = []

print("\nArchiving Repos 🚀:")

for repo_name in tqdm(repo_list, desc="Archiving Repos 🚀", unit="repo"):
    try:
        # Fetch the project using search
        projects = gl.projects.list(search=repo_name, get_all=True)

        # If no project found
        if not projects:
            print(f"⚠️ Repo not found: {repo_name}")
            failed_archives.append({'repo_name': repo_name, 'reason': 'Not found'})
            continue

        # Assuming first match (you can improve matching logic)
        project = projects[0]

        # Check if the project is already archived
        if project.archived:
            print(f"ℹ️ Already archived: {repo_name}")
            successful_archives.append({'repo_name': repo_name, 'status': 'Already Archived'})
            continue

        # Archive the project
        project.archive()
        print(f"✅ Successfully archived: {repo_name}")
        successful_archives.append({'repo_name': repo_name, 'status': 'Archived'})

    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"🔒 Authentication error. Check your token.")
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
    print(f"📄 Failed repos saved to 'failed_to_archive_repos.csv'")
if successful_archives:
    print(f"📄 Successful repos saved to 'successful_archived_repos.csv'")
