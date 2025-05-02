import pandas as pd
import requests
import sys
import csv
import logging
from tqdm import tqdm
from time import sleep
from urllib.parse import quote
from requests.packages.urllib3.exceptions import InsecureRequestWarning  # type: ignore
import warnings

# Suppress SSL warnings
warnings.simplefilter('ignore', InsecureRequestWarning)

# -----------------------------
# Configure Logging
# -----------------------------
logging.basicConfig(
    filename='repo_fetch.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# -----------------------------
# Aqua Security API Setup
# -----------------------------
AQUA_API_INFO = 'https://api.supply-chain.cloud.aquasec.com'

def get_headers(api_token):
    return {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json'
    }

# -----------------------------
# Validate Aqua API Token
# -----------------------------
def validate_api_token(api_token):
    test_url = f'{AQUA_API_INFO}/v2/build/repositories'
    try:
        response = requests.get(test_url, headers=get_headers(api_token), timeout=10, verify=False)
        if response.status_code == 401:
            logging.error("Token validation failed with 401 Unauthorized")
            return False
        elif response.status_code != 200:
            logging.error(f"Token validation failed with status {response.status_code}: {response.text}")
            return False
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Network error during token validation: {e}")
        return False

# -----------------------------
# Prompt user for token
# -----------------------------
def prompt_for_token():
    while True:
        new_token = input("Your API token is invalid or expired. Please enter a new Aqua API token: ").strip()
        if validate_api_token(new_token):
            return new_token
        else:
            print("Invalid token. Please try again.\n")

# -----------------------------
# Read CSV with Repo Names
# -----------------------------
input_file = 'successful_archived_repos.csv'

try:
    df = pd.read_csv(input_file)
    if 'Repo Name' not in df.columns:
        raise ValueError(f"'Repo Name' column not found in {input_file}")
    repo_list = df['Repo Name'].dropna().tolist()
except Exception as e:
    logging.error(f"Failed to read input CSV: {e}")
    print(f"[ERROR] {e}")
    sys.exit(1)

# -----------------------------
# Fetch Repo Info by Name
# -----------------------------
def get_repository_info(repo_name, api_token):
    page = 1
    page_size = 50

    while True:
        try:
            encoded_name = quote(repo_name)
            url = f'{AQUA_API_INFO}/v2/build/repositories?name={encoded_name}&page={page}&limit={page_size}'
            response = requests.get(url, headers=get_headers(api_token), timeout=15, verify=False)

            if response.status_code == 401:
                logging.warning(f"Unauthorized while fetching repo '{repo_name}'.")
                return 'unauthorized', '', 'Unauthorized'

            if response.status_code != 200:
                return 'error', '', f"HTTP {response.status_code}: {response.text}"

            data = response.json()
            repos = data.get('data', [])
            total = data.get('total', 0)

            for repo in repos:
                if repo.get('name') == repo_name:
                    return 'ok', repo.get('repository_id', ''), 'Found'

            if page * page_size >= total:
                return 'ok', '', 'Not Found (name mismatch)'
            page += 1
            sleep(0.2)
        except requests.exceptions.RequestException as e:
            logging.error(f"Network error for repo '{repo_name}': {e}")
            return 'error', '', f"Network error: {e}"

# -----------------------------
# Main Execution
# -----------------------------
api_token = input("Enter your Aqua API token: ").strip()

while not validate_api_token(api_token):
    api_token = prompt_for_token()

results = []

for repo_name in tqdm(repo_list, desc="Fetching Repositories", unit="repo"):
    while True:
        status, repo_id, message = get_repository_info(repo_name, api_token)
        if status == 'unauthorized':
            api_token = prompt_for_token()
            continue
        break
    # Print to console
    print(f"Repo Name: {repo_name} | Repository ID: {repo_id or 'N/A'} | Status: {message}")
    
    # Log result
    logging.info(f"Repo: {repo_name}, ID: {repo_id}, Status: {message}")

    results.append({
        'Repo Name': repo_name,
        'Repository ID': repo_id,
        'Status': message
    })

# -----------------------------
# Save Results to CSV
# -----------------------------
output_file = 'aqua_repository_lookup_results.csv'

try:
    keys = ['Repo Name', 'Repository ID', 'Status']
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        dict_writer = csv.DictWriter(f, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(results)
    print(f"[INFO] Results written to {output_file}")
    logging.info(f"Results written to {output_file}")
except Exception as e:
    logging.error(f"Failed to write output CSV: {e}")
    print(f"[ERROR] Could not write results to CSV: {e}")
