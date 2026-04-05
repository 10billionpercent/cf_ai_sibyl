from fastapi import FastAPI, UploadFile, File
from resume_parser import parse_resume
from job_fetcher import fetch_all_jobs

from db import resumes_collection

from datetime import datetime


app = FastAPI()


# -----------------------
# PARSE RESUME ENDPOINT
# -----------------------

@app.post("/parse-resume")
async def parse_resume_endpoint(file: UploadFile = File(...)):

    content = await file.read()

    result = await parse_resume(content)

    # add timestamp
    result["created_at"] = datetime.utcnow()

    # store in mongodb
    inserted = resumes_collection.insert_one(result)

    # convert ObjectId to string
    result["_id"] = str(inserted.inserted_id)

    return result


# -----------------------
# FETCH JOBS ENDPOINT
# -----------------------

@app.get("/fetch-jobs")
async def fetch_jobs():

    jobs = fetch_all_jobs()

    return {
        "count": len(jobs),
        "jobs": jobs
    }