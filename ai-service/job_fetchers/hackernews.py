import requests
import time

from job_filters import is_internship


def fetch_hn_jobs():

    one_week_ago = int(time.time()) - (7 * 24 * 60 * 60)

    url = (
        "https://hn.algolia.com/api/v1/search_by_date?"
        "tags=story"
        f"&numericFilters=created_at_i>{one_week_ago}"
    )

    headers = {
        "User-Agent": "Sibyl Internship Agent"
    }

    response = requests.get(url, headers=headers)

    data = response.json()

    jobs = []

    for item in data.get("hits", []):

        title = item.get("title") or ""
        description = item.get("story_text") or ""

        # Only include hiring related posts
        if not is_internship(title + description):
            continue

        jobs.append({
            "title": title,
            "url": item.get("url") or f"https://news.ycombinator.com/item?id={item.get('objectID')}",
            "source": "HackerNews",
            "description": description
        })

    return jobs