import pandas as pd
import requests
import csv
import sys
import logging
import warnings
from tqdm import tqdm
from time import sleep
from requests.packages.urllib3.exceptions import InsecureRequestWarning  # type: ignore

# Disable SSL warnings
warnings.simplefilter('ignore', InsecureRequestWarning)

# -----------------------------
# Configuration
# -----------------------------
AQUA_API_INFO = 'https://api.supply-chain.cloud.aquasec.com'
INPUT_CSV = 'inactive_repos.csv'
OUTPUT_CSV = 'fetched_repos.csv'
LOG_FILE = 'fetch_repos.log'

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
    test_url = f'{AQUA_API_INFO}/v2/build/repositories'
    try:
        response = requests.get(test_url, headers=get_headers(api_token), timeout=10, verify=False)
        return response.status_code == 200
    except Exception as e:
        logging.error(f"Token validation error: {e}")
        return False

# -----------------------------
# Get Repo Info with Pagination
# -----------------------------
def get_repository_info(repo_name, api_token):
    page = 1
    page_size = 50

    while True:
        try:
            url = f'{AQUA_API_INFO}/v2/build/repositories'
            params = {'name': repo_name, 'page': page, 'limit': page_size}
            response = requests.get(url, headers=get_headers(api_token), params=params, timeout=15, verify=False)

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
            sleep(0.2)  # Be nice to the API
        except requests.exceptions.RequestException as e:
            return 'error', '', f"Network error: {e}"

# -----------------------------
# Load Input
# -----------------------------
try:
    df = pd.read_csv(INPUT_CSV)
    if 'Repo Name' not in df.columns:
        raise ValueError(f"'Repo Name' column not found in {INPUT_CSV}")
    repo_list = df['Repo Name'].dropna().tolist()
    logging.info(f"Loaded {len(repo_list)} repo names from {INPUT_CSV}")
except Exception as e:
    logging.error(f"Failed to load input file: {e}")
    sys.exit(1)

# -----------------------------
# Start Fetching Repo Info
# -----------------------------
api_token = prompt_for_token()
results = []

for repo_name in tqdm(repo_list, desc="Fetching Aqua Repos", unit="repo"):
    while True:
        status, repo_id, message = get_repository_info(repo_name, api_token)

        if status == 'unauthorized':
            api_token = prompt_for_token()
            continue
        elif status == 'error':
            logging.error(f"[{repo_name}] Fetch failed: {message}")
        elif status == 'ok':
            logging.info(f"[{repo_name}] → ID: {repo_id if repo_id else 'N/A'} | {message}")
        break

    results.append({
        'Repo Name': repo_name,
        'Repository ID': repo_id,
        'Status': message
    })

# -----------------------------
# Save to CSV
# -----------------------------
try:
    keys = ['Repo Name', 'Repository ID', 'Status']
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(results)
    logging.info(f"Results saved to {OUTPUT_CSV}")
except Exception as e:
    logging.error(f"Failed to write output CSV: {e}")
