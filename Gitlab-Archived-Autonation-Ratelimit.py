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
RATE_LIMIT_WAIT = 70  # Wait time after a 403 error (70 seconds)
MAX_RETRIES = 3  # Maximum retries for a repo

# Initialize Logging
logging.basicConfig(filename='archiving_process.log', level=logging.INFO, format='%(asctime)s - %(message)s')
logging.info("Archiving process started.")

def get_gitlab_connection(token):
    """Return a GitLab connection object for a specific token"""
    try:
        gl = gitlab.Gitlab(GITLAB_URL, private_token=token, ssl_verify=False)
        return gl
    except Exception as e:
        logging.error(f"Error connecting with token {token}: {str(e)}")
        return None

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

# Token Index Tracker
token_idx = 0
requests_made = 0

# -----------------------------
# Function to Archive Repos with Retry
# -----------------------------
def archive_repo(repo_name, gl, retries=0):
    try:
        # Fetch the project using search
        projects = gl.projects.list(search=repo_name, get_all=True)
        
        # If no project found
        if not projects:
            logging.warning(f"⚠️ Repo not found: {repo_name}")
            failed_archives.append({'repo_name': repo_name, 'reason': 'Repo not found'})
            return False

        project = projects[0]

        # Check if the project is already archived
        if project.archived:
            logging.info(f"ℹ️ Already archived: {repo_name}")
            successful_archives.append({'repo_name': repo_name, 'status': 'Already Archived'})
            return True

        # Archive the project
        project.archive()
        logging.info(f"✅ Successfully archived: {repo_name}")
        successful_archives.append({'repo_name': repo_name, 'status': 'Archived'})
        return True

    except gitlab.exceptions.GitlabAuthenticationError:
        logging.error(f"🔒 Authentication error on repo '{repo_name}'. Check your token.")
        return False

    except gitlab.exceptions.GitlabError as e:
        if '403' in str(e) and retries < MAX_RETRIES:  # Rate limit error (403)
            wait_time = RATE_LIMIT_WAIT * (2 ** retries)  # Exponential backoff
            logging.warning(f"⚠️ Rate limit hit for token {ACCESS_TOKENS[token_idx]}. Waiting for {wait_time} seconds...")
            time.sleep(wait_time)  # Wait before retrying
            return archive_repo(repo_name, gl, retries + 1)  # Retry with exponential backoff
        logging.error(f"❌ Error on repo '{repo_name}': {str(e)}")
        failed_archives.append({'repo_name': repo_name, 'reason': str(e)})
        return False

    except Exception as e:
        logging.error(f"❌ Error on repo '{repo_name}': {str(e)}")
        failed_archives.append({'repo_name': repo_name, 'reason': str(e)})
        return False

# -----------------------------
# Main Loop to Archive Repositories
# -----------------------------
logging.info("🔧 Archiving Repositories...")

for repo_name in tqdm(repo_list, desc="Archiving Repos 🚀", unit="repo"):
    gl = get_gitlab_connection(ACCESS_TOKENS[token_idx])
    
    if not gl:
        logging.error("Error with GitLab connection. Skipping repo.")
        continue

    success = archive_repo(repo_name, gl)

    if success:
        requests_made += 1
    
    # After every 5 requests, rotate the token
    if requests_made >= REQUESTS_PER_TOKEN:
        token_idx = (token_idx + 1) % len(ACCESS_TOKENS)
        gl = get_gitlab_connection(ACCESS_TOKENS[token_idx])
        requests_made = 0

# -----------------------------
# Save Result Files
# -----------------------------
if failed_archives:
    pd.DataFrame(failed_archives).to_csv('failed_to_archive_repos.csv', index=False)
    logging.info(f"❌ Failed to archive some repos. Results saved in 'failed_to_archive_repos.csv'.")

if successful_archives:
    pd.DataFrame(successful_archives).to_csv('successful_archived_repos.csv', index=False)
    logging.info(f"✅ Successfully archived repos. Results saved in 'successful_archived_repos.csv'.")

# -----------------------------
# Summary
# -----------------------------
logging.info("\n🎯 Archiving Summary:")
logging.info(f"✅ Successfully Archived: {len(successful_archives)}")
logging.info(f"❌ Failed to Archive: {len(failed_archives)}")
logging.info(f"📄 Failed repos saved to 'failed_to_archive_repos.csv'")
logging.info(f"📄 Successful repos saved to 'successful_archived_repos.csv'")
