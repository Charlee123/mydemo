import pandas as pd
import requests
import sys
import csv
import logging
import warnings
from tqdm import tqdm
from urllib.parse import quote_plus
from requests.packages.urllib3.exceptions import InsecureRequestWarning  # type: ignore

# Suppress SSL warnings
warnings.simplefilter('ignore', InsecureRequestWarning)

# -----------------------------
# Aqua API Configuration
# -----------------------------
AQUA_API_INFO = 'https://api.supply-chain.cloud.aquasec.com'

def get_headers(api_token):
    return {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json'
    }

# -----------------------------
# Logging Setup
# -----------------------------
logging.basicConfig(
    filename='fetch_repo_info.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# -----------------------------
# Validate Aqua API Token
# -----------------------------
def validate_api_token(api_token):
    test_url = f'{AQUA_API_INFO}/v2/build/repositories'
    try:
        response = requests.get(test_url, headers=get_headers(api_token), timeout=10, verify=False)
        if response.status_code == 401:
            return False
        elif response.status_code != 200:
            tqdm.write(f"[ERROR] Failed to validate token. Status Code: {response.status_code}")
            tqdm.write(response.text)
            return False
        return True
    except requests.exceptions.RequestException as e:
        tqdm.write(f"[ERROR] Network error while validating token: {e}")
        return False

# -----------------------------
# Prompt for new token
# -----------------------------
def prompt_for_token():
    while True:
        new_token = input("Your API token is invalid or expired. Please enter a new Aqua API token: ").strip()
        if validate_api_token(new_token):
            return new_token
        else:
            print("Invalid token. Please try again.\n")

# -----------------------------
# Read input repo list
# -----------------------------
input_file = 'successful_archived_repos.csv'

try:
    df = pd.read_csv(input_file)
    if 'Repo Name' not in df.columns:
        raise ValueError(f"'Repo Name' column not found in {input_file}")
except FileNotFoundError:
    tqdm.write(f"[ERROR] File '{input_file}' not found.")
    sys.exit(1)
except Exception as e:
    tqdm.write(f"[ERROR] Reading CSV: {e}")
    sys.exit(1)

repo_list = df['Repo Name'].dropna().tolist()

# -----------------------------
# Get Repository Info
# -----------------------------
def get_repository_info(name, api_token):
    try:
        encoded_name = quote_plus(name)
        url = f'{AQUA_API_INFO}/v2/build/repositories?name={encoded_name}'
        response = requests.get(url, headers=get_headers(api_token), timeout=10, verify=False)

        if response.status_code == 200:
            data = response.json()
            if data.get('total', 0) > 0:
                repo_id = data['data'][0].get('repository_id', '')
                return 'found', repo_id, 'Found'
            else:
                return 'not_found', '', 'Not Found in Aqua'
        elif response.status_code == 401:
            return 'unauthorized', '', 'Unauthorized - Invalid Token'
        else:
            return 'error', '', f"Fetch Error: {response.status_code} {response.text}"
    except requests.exceptions.RequestException as e:
        return 'error', '', f"Network Error: {e}"

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

    tqdm.write(f"Repo Name: {repo_name} | Repository ID: {repo_id or 'N/A'} | Status: {message}")
    logging.info(f"Repo: {repo_name}, ID: {repo_id}, Status: {message}")

    results.append({
        'Repo Name': repo_name,
        'Repository ID': repo_id,
        'Status': message
    })

# -----------------------------
# Save Results to CSV
# -----------------------------
output_file = 'repo_fetch_results.csv'
try:
    keys = ['Repo Name', 'Repository ID', 'Status']
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        dict_writer = csv.DictWriter(f, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(results)
    tqdm.write(f"[INFO] Results written to '{output_file}'")
except Exception as e:
    tqdm.write(f"[ERROR] Could not write to output CSV: {e}")
