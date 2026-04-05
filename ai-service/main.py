from fastapi import FastAPI, UploadFile, File
from resume_parser import parse_resume
from job_fetcher import fetch_all_jobs

from db import resumes_collection, jobs_collection

from datetime import datetime, timezone


app = FastAPI()


# -----------------------
# PARSE RESUME ENDPOINT
# -----------------------

@app.post("/parse-resume")
async def parse_resume_endpoint(file: UploadFile = File(...)):

    content = await file.read()

    result = await parse_resume(content)

    result["created_at"] = datetime.now(timezone.utc)

    inserted = resumes_collection.insert_one(result)

    result["_id"] = str(inserted.inserted_id)

    return result


# -----------------------
# FETCH JOBS ENDPOINT
# -----------------------

@app.get("/fetch-jobs")
async def fetch_jobs():

    jobs = fetch_all_jobs()

    # add timestamp to each job
    for job in jobs:
        job["created_at"] = datetime.now(timezone.utc)

    # insert into mongodb
    if jobs:
        inserted = jobs_collection.insert_many(jobs)
        for job, _id in zip(jobs, inserted.inserted_ids):
            job["_id"] = str(_id)

    return {
        "count": len(jobs),
        "jobs": jobs
    }