from fastapi import FastAPI, UploadFile, File

from resume_parser import parse_resume
from job_fetcher import fetch_all_jobs
from job_matcher import match_jobs
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

    # get latest resume
    resume = resumes_collection.find_one(
        sort=[("created_at", -1)]
    )

    if not resume:
        return {"error": "No resume found"}

    jobs = fetch_all_jobs()

    # add timestamp
    for job in jobs:
        job["created_at"] = datetime.now(timezone.utc)

    # store in mongodb
    if jobs:
        inserted = jobs_collection.insert_many(jobs)

        # still convert _id for API response
        for job, _id in zip(jobs, inserted.inserted_ids):
            job["_id"] = str(_id)

    # match jobs
    matched = await match_jobs(resume, jobs)

    return {
        "count": len(matched),
        "jobs": matched
    }