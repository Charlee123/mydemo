import pandas as pd
import requests
import sys
import csv
import warnings
from tqdm import tqdm
from requests.packages.urllib3.exceptions import InsecureRequestWarning  # type: ignore

warnings.simplefilter('ignore', InsecureRequestWarning)

# -----------------------------
# Aqua Security API Setup
# -----------------------------
AQUA_API_URL = 'https://test.aquasec.com'  # Replace with your Aqua API URL
AQUA_API_INFO = 'https://test.cloud.aquasec.com'

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
            return False
        elif response.status_code != 200:
            print(f"[ERROR] Failed to validate token. Status Code: {response.status_code}")
            print(response.text)
            return False
        return True
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Network error while validating token: {e}")
        return False

# Prompt user for token if 401
def prompt_for_token():
    while True:
        new_token = input("Your API token is invalid or expired. Please enter a new Aqua API token: ").strip()
        if validate_api_token(new_token):
            return new_token
        else:
            print("Invalid token. Please try again.\n")

# -----------------------------
# Read CSV File with Repository Names
# -----------------------------
input_file = 'successful_archived_repos.csv'

try:
    df = pd.read_csv(input_file)
    if 'Repo Name' not in df.columns:
        raise ValueError(f"'Repo Name' column not found in {input_file}")
except FileNotFoundError:
    print(f"[ERROR] File '{input_file}' not found.")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Reading CSV: {e}")
    sys.exit(1)

repo_list = df['Repo Name'].dropna().tolist()

# -----------------------------
# Get Repository Information from Aqua
# -----------------------------
def get_repository_info(name, api_token):
    try:
        url = f'{AQUA_API_INFO}/v2/build/repositories'
        params = {'name': name}
        response = requests.get(url, headers=get_headers(api_token), params=params, timeout=10, verify=False)

        if response.status_code == 200:
            data = response.json()
            if data.get('total', 0) > 0:
                for repo in data.get('data', []):
                    if repo.get('name') == name:
                        return repo
                return None  # Not found in exact match
            else:
                return None
        elif response.status_code == 401:
            return 'unauthorized'
        else:
            return {'error': f"Failed with status {response.status_code}: {response.text}"}
    except requests.exceptions.RequestException as e:
        return {'error': str(e)}

# -----------------------------
# Delete Repositories from Aqua
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
# Main Execution
# -----------------------------
api_token = input("Enter your Aqua API token: ").strip()

while not validate_api_token(api_token):
    api_token = prompt_for_token()

repo_ids_to_delete = []
results = []

for repo_name in tqdm(repo_list, desc="Fetching Info", unit="repo"):
    while True:
        repo_info = get_repository_info(repo_name, api_token)
        if repo_info == 'unauthorized':
            print(f"[WARNING] Token unauthorized while getting repo info for '{repo_name}'.")
            api_token = prompt_for_token()
            continue
        break

    if repo_info is None:
        results.append({'Repo Name': repo_name, 'Repository ID': '', 'Status': 'Not Found in Aqua'})
    elif isinstance(repo_info, dict) and 'error' in repo_info:
        results.append({'Repo Name': repo_name, 'Repository ID': '', 'Status': f"Fetch Error: {repo_info['error']}"})
    else:
        repo_id = repo_info.get('repository_id', '')
        if not repo_id:
            results.append({'Repo Name': repo_name, 'Repository ID': '', 'Status': 'Missing repository_id'})
        else:
            print(f"[INFO] Repo matched: {repo_name} | repository_id: {repo_id}")
            repo_ids_to_delete.append({'id': repo_id, 'name': repo_name})
            results.append({'Repo Name': repo_name, 'Repository ID': repo_id, 'Status': 'Pending Deletion'})

# -----------------------------
# Delete in Batches & Log Status
# -----------------------------
if repo_ids_to_delete:
    batch_size = 100
    for i in tqdm(range(0, len(repo_ids_to_delete), batch_size), desc="Deleting Batches", unit="batch"):
        batch = repo_ids_to_delete[i:i + batch_size]
        batch_ids = [r['id'] for r in batch]

        while True:
            result, status_msg = delete_repositories(batch_ids, api_token)
            if result == 'unauthorized':
                print(f"[WARNING] Token unauthorized during deletion batch {i}–{i+batch_size}")
                api_token = prompt_for_token()
                continue
            break

        for r in batch:
            for res in results:
                if res['Repo Name'] == r['name']:
                    res['Status'] = status_msg if result else f"Delete Failed: {status_msg}"
else:
    print("[INFO] No repositories found to delete.")

# -----------------------------
# Save Results to CSV
# -----------------------------
output_file = 'deletion_results.csv'
try:
    keys = ['Repo Name', 'Repository ID', 'Status']
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        dict_writer = csv.DictWriter(f, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(results)
    print(f"[INFO] Results written to {output_file}")
except Exception as e:
    print(f"[ERROR] Could not write to output CSV: {e}")
