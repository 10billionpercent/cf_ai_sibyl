from fastapi import FastAPI, UploadFile, File
from resume_parser import parse_resume

from job_fetcher import fetch_all_jobs   

app = FastAPI()


@app.post("/parse-resume")
async def parse_resume_endpoint(file: UploadFile = File(...)):

    content = await file.read()

    result = await parse_resume(content)

    return result


# -----------------------
# FETCH JOBS ENDPOINT
# -----------------------

@app.get("/fetch-jobs")
async def fetch_jobs():

    jobs = fetch_all_jobs()

    return {
        "count": len(jobs),
        "jobs": jobs[:10]   # limit for now
    }