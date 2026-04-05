from job_fetcher import fetch_all_jobs

jobs = fetch_all_jobs()

print("\nSample jobs:\n")

for job in jobs[:5]:
    print(job)
    print("-" * 50)