import gitlab
import csv
import os
from datetime import datetime, timedelta

# GitLab configuration
GITLAB_URL = 'https://gitlab.com'
ACCESS_TOKEN = 'glpat-wJXweM94RF94Vbd-e9xy'  # Secure way to handle tokens


# Initialize GitLab connection
gl = gitlab.Gitlab(GITLAB_URL, private_token=ACCESS_TOKEN)

# Set time threshold (6 months ago)
six_months_ago = datetime.now() - timedelta(minutes=1)

# Prepare data for CSV
repos_data = []

# Loop through all groups
groups = gl.groups.list(all=True)
for group in groups:
    try:
        projects = group.projects.list(all=True, include_subgroups=True)
    except gitlab.exceptions.GitlabGetError as e:
        print(f"[Error] Could not retrieve projects for group '{group.name}': {e}")
        continue

    for project in projects:
        try:
            project_detail = gl.projects.get(project.id)
            last_activity_raw = project_detail.last_activity_at

            # Parse last activity timestamp
            try:
                last_activity = datetime.strptime(last_activity_raw, '%Y-%m-%dT%H:%M:%S.%fZ')
            except ValueError:
                last_activity = datetime.strptime(last_activity_raw, '%Y-%m-%dT%H:%M:%SZ')

            if last_activity < six_months_ago:
                commits = project_detail.commits.list(per_page=1)
                if commits:
                    last_commit = commits[0]
                    last_commit_date = last_commit.committed_date
                    last_committer = last_commit.author_name
                else:
                    last_commit_date = "No commits"
                    last_committer = "N/A"

                repos_data.append({
                    "Group Name": group.name,
                    "Repo Name": project_detail.name,
                    "Repo URL": project_detail.web_url,
                    "Archived": project_detail.archived,
                    "Last Activity Day": last_activity.date(),
                    "Last Commit Day": last_commit_date,
                    "Last Committer": last_committer
                })

        except gitlab.exceptions.GitlabGetError as e:
            print(f"[Error] Failed to fetch project '{project.name}': {e}")
            continue

# Write to CSV
csv_file = 'inactive_repos.csv'
with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
    fieldnames = ["Group Name", "Repo Name", "Repo URL", "Archived", "Last Activity Day", "Last Commit Day", "Last Committer"]
    writer = csv.DictWriter(file, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(repos_data)

print(f"[✓] Data saved to '{csv_file}'")
