from job_fetchers.ashby import fetch_ashby_jobs
from job_fetchers.greenhouse import fetch_greenhouse_jobs


def fetch_all_jobs():
    jobs = []

    try:
        print("Fetching Ashby jobs...")
        jobs.extend(fetch_ashby_jobs())
    except Exception as e:
        print("Ashby failed:", e)

    try:
        print("Fetching Greenhouse jobs...")
        jobs.extend(fetch_greenhouse_jobs())
    except Exception as e:
        print("Greenhouse failed:", e)

    print(f"\nTotal jobs fetched: {len(jobs)}")

    return jobs
