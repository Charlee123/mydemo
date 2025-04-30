import gitlab
import openpyxl
import pandas as pd
from tqdm import tqdm
import time

# -----------------------------
# GitLab Connection Setup
# -----------------------------
GITLAB_URL = 'https://gitlab.com'
ACCESS_TOKENS = ['glpat-wJXweM94RF94Vbd-e9xy', 'glpat-xxxxxx', 'glpat-yyyyyy']  # List of Personal Access Tokens (not username/password)

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

# Function to switch to the next token if rate limit is hit
def get_gitlab_connection(token):
    return gitlab.Gitlab(GITLAB_URL, private_token=token)

# -----------------------------
# Archive Repos with Rate Limit Handling
# -----------------------------
print("\nArchiving Repos 🚀:")

# Token Index for rotating through tokens
token_idx = 0

for repo_name in tqdm(repo_list, desc="Archiving Repos 🚀", unit="repo"):
    retries = 0  # To track retries on 403 errors

    while retries < 5:  # Retry limit, can be adjusted
        try:
            gl = get_gitlab_connection(ACCESS_TOKENS[token_idx])

            # Fetch the project using search
            projects = gl.projects.list(search=repo_name, get_all=True)

            # If no project found
            if not projects:
                print(f"⚠️ Repo not found: {repo_name}")
                failed_archives.append({'repo_name': repo_name, 'reason': 'Not found'})
                break

            # Assuming first match (you can improve matching logic)
            project = projects[0]

            # Check if the project is already archived
            if project.archived:
                print(f"ℹ️ Already archived: {repo_name}")
                successful_archives.append({'repo_name': repo_name, 'status': 'Already Archived'})
                break

            # Archive the project
            project.archive()
            print(f"✅ Successfully archived: {repo_name}")
            successful_archives.append({'repo_name': repo_name, 'status': 'Archived'})
            break

        except gitlab.exceptions.GitlabAuthenticationError:
            print(f"🔒 Authentication error. Check your token.")
            break

        except gitlab.exceptions.GitlabForbiddenError:
            print(f"❌ 403 Forbidden. Waiting 70 seconds before retrying for '{repo_name}'...")
            retries += 1
            time.sleep(70)  # Wait for 70 seconds before retrying

            # Switch to the next token if 5 retries have been reached for the current token
            if retries == 5:
                print(f"🔄 Switching to next token...")
                token_idx = (token_idx + 1) % len(ACCESS_TOKENS)
                retries = 0  # Reset retry count after switching tokens

        except Exception as e:
            print(f"❌ Error archiving '{repo_name}': {str(e)}")
            failed_archives.append({'repo_name': repo_name, 'reason': str(e)})
            break

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
