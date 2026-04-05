import feedparser

from job_filters import is_internship


def fetch_workwithindies():
    feed = feedparser.parse("https://www.workwithindies.com/rss")

    jobs = []

    for entry in feed.entries:

        title = entry.title
        description = entry.summary

        if not is_internship(title + description):
            continue

        jobs.append({
            "title": title,
            "url": entry.link,
            "source": "WorkWithIndies",
            "description": description
        })

    return jobs