import os
import json
import httpx
import time
import hashlib

from fastapi import FastAPI, UploadFile, File

from resume_parser import parse_resume
from job_fetcher import fetch_all_jobs
from job_matcher import match_jobs
from db import resumes_collection, jobs_collection

from dotenv import load_dotenv
from datetime import datetime, timezone


app = FastAPI()

load_dotenv()

CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_DATABASE_ID = os.getenv("CLOUDFLARE_DATABASE_ID")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")

D1_ENDPOINT = (
    f"https://api.cloudflare.com/client/v4/accounts/"
    f"{CLOUDFLARE_ACCOUNT_ID}/d1/database/{CLOUDFLARE_DATABASE_ID}/query"
)


async def execute_query(sql: str, params: list = []):
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                D1_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
                    "Content-Type": "application/json"
                },
                json={
                    "sql": sql,
                    "params": params
                }
            )
        try:
            data = response.json()
        except Exception:
            print("D1 error: invalid JSON response")
            return {"success": False, "error": "invalid_json"}

        if not data.get("success"):
            print("D1 error:", data)

        return data
    except Exception as e:
        print("D1 error:", str(e))
        return {"success": False, "error": str(e)}


async def insert_event_log(
    event_type,
    source=None,
    company=None,
    status="success",
    message=""
):
    sql = """
    INSERT INTO event_logs (event_type, source, company, status, message, created_at)
    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """
    await execute_query(sql, [event_type, source, company, status, message])


async def insert_job_log(job, match_result):
    def _norm(value):
        if value is None:
            return ""
        return str(value).strip().lower()

    def _s(value):
        if value is None:
            return ""
        return str(value)

    job_id = hashlib.sha256(
        f"{_norm(job.get('source'))}|{_norm(job.get('company'))}|{_norm(job.get('title'))}|{_norm(job.get('location'))}|{_norm(job.get('apply_url'))}|{_norm(job.get('job_url'))}".encode("utf-8")
    ).hexdigest()

    score = match_result.get("score")
    if score is None:
        score = match_result.get("match_score", 0)

    try:
        score_val = float(score)
    except Exception:
        score_val = 0

    if score_val >= 8:
        decision = "high"
    elif score_val >= 6:
        decision = "medium"
    else:
        decision = "ignore"

    matched_skills = json.dumps(match_result.get("matched_skills", []))
    missing_skills = json.dumps(match_result.get("missing_skills", match_result.get("missing", [])))

    uncertainty = match_result.get("uncertainty")
    if isinstance(uncertainty, list):
        uncertainty = json.dumps(uncertainty)
    elif uncertainty is None:
        uncertainty = ""

    sql = """
    INSERT OR IGNORE INTO job_logs (
        job_id, company, source, title, location, score, decision,
        matched_skills, missing_skills, uncertainty,
        apply_url, job_url, first_seen_at, last_seen_at
    )
    VALUES (
        ?, ?, ?, ?, ?, ?, ?,
        ?, ?, ?,
        ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
    )
    """

    params = [
        job_id,
        _s(job.get("company")),
        _s(job.get("source")),
        _s(job.get("title")),
        _s(job.get("location")),
        score_val,
        decision,
        matched_skills,
        missing_skills,
        uncertainty,
        _s(job.get("apply_url")),
        _s(job.get("job_url"))
    ]

    await execute_query(sql, params)


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

    try:
        total_start = time.perf_counter()

        try:
            fetch_start = time.perf_counter()
            jobs = fetch_all_jobs()
            fetch_seconds = time.perf_counter() - fetch_start
            await insert_event_log(
                event_type="fetch_complete",
                source="multi",
                status="success",
                message=f"Fetched {len(jobs)} jobs in {fetch_seconds:.2f}s"
            )
        except Exception as e:
            await insert_event_log(
                event_type="fetch_fail",
                source="multi",
                status="fail",
                message=str(e)
            )
            raise

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
        match_start = time.perf_counter()
        matched = await match_jobs(resume, jobs)
        match_seconds = time.perf_counter() - match_start
        await insert_event_log(
            event_type="match_complete",
            source="multi",
            status="success",
            message=f"Matched {len(matched)} jobs in {match_seconds:.2f}s"
        )

        for job in jobs:
            match_result = job.get("match", {})
            await insert_job_log(job, match_result)

        total_seconds = time.perf_counter() - total_start
        await insert_event_log(
            event_type="pipeline_complete",
            source="multi",
            status="success",
            message=f"Pipeline finished in {total_seconds:.2f}s"
        )

        return {
            "count": len(matched),
            "jobs": matched
        }

    except Exception as e:
        await insert_event_log(
            event_type="system_error",
            status="fail",
            message=str(e)
        )
        return {"error": "System error"}
