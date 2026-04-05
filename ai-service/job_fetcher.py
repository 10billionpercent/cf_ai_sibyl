from job_fetchers.hackernews import fetch_hn_jobs
from job_fetchers.nodesk import fetch_nodesk_jobs
from job_fetchers.workwithindies import fetch_workwithindies
from job_fetchers.github import fetch_github_jobs
from job_fetchers.yc import fetch_yc_jobs


def fetch_all_jobs():
    jobs = []

    try:
        print("Fetching HackerNews jobs...")
        jobs.extend(fetch_hn_jobs())
    except Exception as e:
        print("HackerNews failed:", e)

    try:
        print("Fetching NoDesk jobs...")
        jobs.extend(fetch_nodesk_jobs())
    except Exception as e:
        print("NoDesk failed:", e)

    try:
        print("Fetching WorkWithIndies jobs...")
        jobs.extend(fetch_workwithindies())
    except Exception as e:
        print("WorkWithIndies failed:", e)

    try:
        print("Fetching GitHub jobs...")
        jobs.extend(fetch_github_jobs())
    except Exception as e:
        print("GitHub failed:", e)

    try:
        print("Fetching YC jobs...")
        jobs.extend(fetch_yc_jobs())
    except Exception as e:
        print("YCombinator failed:", e)

    print(f"\nTotal jobs fetched: {len(jobs)}")

    return jobs