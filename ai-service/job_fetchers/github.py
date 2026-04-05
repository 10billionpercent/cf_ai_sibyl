import requests
from datetime import datetime, timedelta

from job_filters import is_internship


def fetch_github_jobs():

    last_week = datetime.utcnow() - timedelta(days=7)
    date_str = last_week.strftime("%Y-%m-%d")

    query = f"internship state:open created:>{date_str}"

    url = f"https://api.github.com/search/issues?q={query}"

    headers = {
        "User-Agent": "Sibyl Internship Agent"
    }

    response = requests.get(url, headers=headers)

    data = response.json()

    jobs = []

    for item in data.get("items", []):

        title = item.get("title") or ""
        description = item.get("body") or ""

        if not is_internship(title + description):
            continue

        jobs.append({
            "title": title,
            "url": item.get("html_url"),
            "source": "GitHub",
            "description": description
        })

    return jobs