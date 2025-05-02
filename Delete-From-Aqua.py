import pandas as pd
import requests
import sys
import logging
import warnings
import csv
from time import sleep
from requests.packages.urllib3.exceptions import InsecureRequestWarning  # type: ignore

# Disable SSL warnings
warnings.simplefilter('ignore', InsecureRequestWarning)

# -----------------------------
# Configuration
# -----------------------------
AQUA_API_URL = 'https://codesec.aquasec.com'  # Replace with your Aqua API URL
INPUT_CSV = 'fetched_repos.csv'  # CSV with Repository IDs and Repo Names
OUTPUT_CSV = 'delete_repos_results.csv'  # File to save the results
LOG_FILE = 'delete_repos.log'

# -----------------------------
# Setup Logging
# -----------------------------
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    filemode='w'
)

console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
console.setFormatter(formatter)
logging.getLogger().addHandler(console)

# -----------------------------
# Get Headers
# -----------------------------
def get_headers(api_token):
    return {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json'
    }

# -----------------------------
# Prompt for a valid token
# -----------------------------
def prompt_for_token():
    while True:
        token = input("Enter a valid Aqua API token: ").strip()
        if validate_api_token(token):
            return token
        else:
            logging.warning("Invalid token. Try again.")

def validate_api_token(api_token):
    test_url = f'{AQUA_API_URL}/api/v1/scans/repositories'
    try:
        response = requests.get(test_url, headers=get_headers(api_token), timeout=10, verify=False)
        return response.status_code == 200
    except Exception as e:
        logging.error(f"Token validation error: {e}")
        return False

# -----------------------------
# Delete Repositories by IDs
# -----------------------------
def delete_repositories(repo_ids, api_token):
    url = f'{AQUA_API_URL}/api/v1/scans/repositories'
    body = {"repositoriesIds": repo_ids}

    try:
        response = requests.delete(url, json=body, headers=get_headers(api_token), timeout=10, verify=False)

        if response.status_code == 200:
            return True, "Deleted Successfully"
        elif response.status_code == 401:
            return 'unauthorized', "Invalid token during deletion"
        elif response.status_code == 400:
            return False, f"Bad Request: {response.text}"
        elif response.status_code == 500:
            return False, f"Server Error: {response.text}"
        else:
            return False, f"Error {response.status_code}: {response.text}"
    except requests.exceptions.RequestException as e:
        return False, f"Network Error: {e}"

# -----------------------------
# Load Input (Repository IDs and Repo Names)
# -----------------------------
try:
    df = pd.read_csv(INPUT_CSV)
    if 'Repository Name' not in df.columns or 'Repository ID' not in df.columns:
        raise ValueError(f"'Repository Name' or 'Repository ID' column not found in {INPUT_CSV}")
    repo_data = df[['Repository Name', 'Repository ID']].dropna()
    logging.info(f"Loaded {len(repo_data)} repository names and IDs from {INPUT_CSV}")
except Exception as e:
    logging.error(f"Failed to load input file: {e}")
    sys.exit(1)

# -----------------------------
# Prepare Results List
# -----------------------------
results = []

# -----------------------------
# Start Deleting Repositories
# -----------------------------
api_token = prompt_for_token()

# Deleting repositories in chunks of 50 (or any other suitable size) for batch processing
chunk_size = 50
for i in range(0, len(repo_data), chunk_size):
    repo_data_chunk = repo_data.iloc[i:i + chunk_size]
    repo_ids_chunk = repo_data_chunk['Repository ID'].tolist()
    repo_names_chunk = repo_data_chunk['Repository Name'].tolist()
    
    success, message = delete_repositories(repo_ids_chunk, api_token)
    
    if not success:
        logging.error(f"Failed to delete repositories {repo_names_chunk}: {message}")
    
    # Log the result to the results list
    for repo_name, repo_id in zip(repo_names_chunk, repo_ids_chunk):
        results.append({
            'Repository Name': repo_name,
            'Repository ID': repo_id,
            'Success': success,
            'Message': message
        })
    
    sleep(1)  # Adding a slight delay between API calls to prevent rate limits

# -----------------------------
# Save Results to CSV
# -----------------------------
try:
    keys = ['Repository Name', 'Repository ID', 'Success', 'Message']
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(results)
    logging.info(f"Results saved to {OUTPUT_CSV}")
except Exception as e:
    logging.error(f"Failed to write output CSV: {e}")

logging.info("Finished processing all repository deletions.")
