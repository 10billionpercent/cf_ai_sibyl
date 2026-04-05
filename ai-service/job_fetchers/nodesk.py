import feedparser

from job_filters import is_internship


def fetch_nodesk_jobs():
    feed = feedparser.parse("https://nodesk.co/remote-jobs/feed/")

    jobs = []

    for entry in feed.entries:

        title = entry.title
        description = entry.summary

        if not is_internship(title + description):
            continue

        jobs.append({
            "title": title,
            "url": entry.link,
            "source": "NoDesk",
            "description": description
        })

    return jobs