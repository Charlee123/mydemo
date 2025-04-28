import gitlab
import csv
import os
from datetime import datetime, timedelta
from tqdm import tqdm   # 🚀 NEW: Progress bar

# GitLab configuration
GITLAB_URL = 'https://gitlab.com'
ACCESS_TOKEN = 'test'

# Initialize GitLab connection
gl = gitlab.Gitlab(GITLAB_URL, private_token=ACCESS_TOKEN)

# Set time threshold (example: 6 months ago)
six_months_ago = datetime.now() - timedelta(minutes=1)

# Prepare data for CSV
repos_data = []

# Loop through all groups
groups = gl.groups.list(all=True)
for group in tqdm(groups, desc="Processing Groups 🚀", unit="group"):   # 🚀 Progress bar for groups
    try:
        projects = group.projects.list(all=True, include_subgroups=True)
    except gitlab.exceptions.GitlabGetError as e:
        print(f"[Error] Could not retrieve projects for group '{group.name}': {e}")
        continue

    # NEW: Progress bar for projects inside each group
    for project in tqdm(projects, desc=f"Group: {group.name}", leave=False, unit="repo"):
        try:
            try:
                project_detail = gl.projects.get(project.id)
            except gitlab.exceptions.GitlabGetError as e:
                if e.response_code == 404:
                    print(f"[Warning] Skipping inaccessible repo '{project.name}' (404 Not Found)")
                    continue
                else:
                    print(f"[Error] Failed to fetch project '{project.name}': {e}")
                    continue

            last_activity_raw = project_detail.last_activity_at

            try:
                last_activity = datetime.strptime(last_activity_raw, '%Y-%m-%dT%H:%M:%S.%fZ')
            except ValueError:
                last_activity = datetime.strptime(last_activity_raw, '%Y-%m-%dT%H:%M:%SZ')

            if last_activity < six_months_ago:
                try:
                    commits = project_detail.commits.list(per_page=1)
                    if commits:
                        last_commit = commits[0]
                        last_commit_date = last_commit.committed_date
                        last_committer = last_commit.author_name
                    else:
                        last_commit_date = "No commits"
                        last_committer = "N/A"
                except gitlab.exceptions.GitlabListError:
                    last_commit_date = "Error fetching commits"
                    last_committer = "Unknown"

                repos_data.append({
                    "Group Name": group.name,
                    "Repo Name": project_detail.name,
                    "Repo URL": project_detail.web_url,
                    "Archived": project_detail.archived,
                    "Last Activity Day": last_activity.date(),
                    "Last Commit Day": last_commit_date,
                    "Last Committer": last_committer
                })

        except Exception as ex:
            print(f"[Unhandled Error] Project '{project.name}': {ex}")
            continue

# Write to CSV
csv_file = 'inactive_repos.csv'
if repos_data:
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        fieldnames = ["Group Name", "Repo Name", "Repo URL", "Archived", "Last Activity Day", "Last Commit Day", "Last Committer"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(repos_data)

    print(f"[✓] Data saved to '{csv_file}'")
else:
    print("[!] No inactive repositories found or no access to them.")
