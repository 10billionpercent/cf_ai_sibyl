import os
import json
import httpx
import time
import hashlib
import asyncio
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Body

from resume_parser import parse_resume
from job_fetcher import fetch_all_jobs
from job_matcher import match_jobs, match_jobs_stream
from db import resumes_collection, jobs_collection

from dotenv import load_dotenv
from datetime import datetime, timezone


app = FastAPI()

RUNS = {}

load_dotenv()

CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_DATABASE_ID = os.getenv("CLOUDFLARE_DATABASE_ID")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")

D1_ENDPOINT = (
    f"https://api.cloudflare.com/client/v4/accounts/"
    f"{CLOUDFLARE_ACCOUNT_ID}/d1/database/{CLOUDFLARE_DATABASE_ID}/query"
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RESUMES_JSON_PATHS = [REPO_ROOT / "resumes.json"]
JOBS_JSON_PATHS = [REPO_ROOT / "jobs.json"]


def _load_resumes_json():
    for path in RESUMES_JSON_PATHS:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
    return []


def _save_resumes_json(resumes):
    path = RESUMES_JSON_PATHS[0]
    path.write_text(json.dumps(resumes, indent=2), encoding="utf-8")


def _get_latest_resume_fallback():
    resumes = _load_resumes_json()
    if not resumes:
        return None
    def _created_at_key(item):
        value = item.get("created_at")
        if isinstance(value, str):
            return value
        return ""
    return sorted(resumes, key=_created_at_key, reverse=True)[0]


def _load_jobs_json():
    for path in JOBS_JSON_PATHS:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
    return []


def _save_jobs_json(jobs):
    path = JOBS_JSON_PATHS[0]
    path.write_text(json.dumps(jobs, indent=2), encoding="utf-8")


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


def _norm(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def _s(value):
    if value is None:
        return ""
    return str(value)


def compute_job_id(job):
    return hashlib.sha256(
        f"{_norm(job.get('source'))}|{_norm(job.get('company'))}|{_norm(job.get('title'))}|{_norm(job.get('location'))}|{_norm(job.get('apply_url'))}|{_norm(job.get('job_url'))}".encode("utf-8")
    ).hexdigest()


async def insert_job_log(job, match_result):
    job_id = compute_job_id(job)

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

    try:
        inserted = resumes_collection.insert_one(result)
        result["_id"] = str(inserted.inserted_id)
    except Exception:
        resumes = _load_resumes_json()
        safe_result = json.loads(json.dumps(result, default=str))
        resumes.append(safe_result)
        _save_resumes_json(resumes)
        result["_id"] = "local-json"

    return result


# -----------------------
# FETCH JOBS ENDPOINT
# -----------------------

@app.get("/fetch-jobs")
async def fetch_jobs():

    # get latest resume
    try:
        resume = resumes_collection.find_one(
            sort=[("created_at", -1)]
        )
    except Exception:
        resume = None

    if not resume:
        resume = _get_latest_resume_fallback()

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


# -----------------------
# FETCH JOBS (STREAM MODE)
# -----------------------

@app.post("/fetch-jobs-stream")
async def fetch_jobs_stream():

    run_id = str(uuid.uuid4())
    RUNS[run_id] = {
        "status": "running",
        "results": [],
        "total": 0,
        "completed": 0,
        "error": None
    }

    async def on_result(job):
        RUNS[run_id]["results"].append(job)
        RUNS[run_id]["completed"] += 1

    async def runner():
        try:
            try:
                resume = resumes_collection.find_one(
                    sort=[("created_at", -1)]
                )
            except Exception:
                resume = None

            if not resume:
                resume = _get_latest_resume_fallback()

            if not resume:
                RUNS[run_id]["status"] = "error"
                RUNS[run_id]["error"] = "No resume found"
                return

            fetch_start = time.perf_counter()
            jobs = fetch_all_jobs()
            fetch_seconds = time.perf_counter() - fetch_start
            RUNS[run_id]["total"] = len(jobs)

            await insert_event_log(
                event_type="fetch_complete",
                source="multi",
                status="success",
                message=f"Fetched {len(jobs)} jobs in {fetch_seconds:.2f}s"
            )

            for job in jobs:
                job["created_at"] = datetime.now(timezone.utc)

            match_start = time.perf_counter()
            await match_jobs_stream(resume, jobs, on_result)
            match_seconds = time.perf_counter() - match_start

            await insert_event_log(
                event_type="match_complete",
                source="multi",
                status="success",
                message=f"Matched {RUNS[run_id]['completed']} jobs in {match_seconds:.2f}s"
            )

            for job in RUNS[run_id]["results"]:
                match_result = job.get("match", {})
                await insert_job_log(job, match_result)

            total_seconds = time.perf_counter() - fetch_start
            await insert_event_log(
                event_type="pipeline_complete",
                source="multi",
                status="success",
                message=f"Pipeline finished in {total_seconds:.2f}s"
            )

            RUNS[run_id]["status"] = "done"

        except Exception as e:
            RUNS[run_id]["status"] = "error"
            RUNS[run_id]["error"] = str(e)
            await insert_event_log(
                event_type="system_error",
                status="fail",
                message=str(e)
            )

    asyncio.create_task(runner())
    return {"run_id": run_id}


@app.get("/fetch-results")
async def fetch_results(run_id: str, since: int = 0):
    run = RUNS.get(run_id)
    if not run:
        return {"error": "Invalid run_id"}

    results = run["results"][since:]

    return {
        "status": run["status"],
        "total": run["total"],
        "completed": run["completed"],
        "results": results,
        "next": since + len(results),
        "error": run["error"]
    }


# -----------------------
# SAVE JOB (GOOD FEEDBACK)
# -----------------------

@app.post("/save-job")
async def save_job(job: dict = Body(...)):

    def _pick_filter(data):
        if data.get("job_id"):
            return {"job_id": data.get("job_id")}
        if data.get("job_url"):
            return {"job_url": data.get("job_url")}
        if data.get("apply_url"):
            return {"apply_url": data.get("apply_url")}
        return {
            "company": data.get("company"),
            "title": data.get("title"),
            "location": data.get("location")
        }

    now = datetime.now(timezone.utc)
    job["saved_from_feedback"] = True
    job["saved_at"] = now

    try:
        result = jobs_collection.update_one(
            _pick_filter(job),
            {
                "$set": job,
                "$setOnInsert": {"created_at": now}
            },
            upsert=True
        )
        return {"status": "ok", "updated": result.modified_count, "upserted": bool(result.upserted_id)}
    except Exception:
        jobs = _load_jobs_json()
        safe_job = json.loads(json.dumps(job, default=str))
        jobs.append(safe_job)
        _save_jobs_json(jobs)
        return {"status": "ok", "updated": 0, "upserted": True, "fallback": "jobs.json"}


# -----------------------
# SAVE FEEDBACK (GOOD/BAD)
# -----------------------

@app.post("/job-feedback")
async def job_feedback(payload: dict = Body(...)):
    job = payload.get("job") or {}
    feedback = payload.get("feedback")

    if not job or not feedback:
        return {"error": "Missing job or feedback"}

    job_id = compute_job_id(job)

    sql = """
    UPDATE job_logs
    SET user_feedback = ?, last_seen_at = CURRENT_TIMESTAMP
    WHERE job_id = ?
    """
    await execute_query(sql, [feedback, job_id])

    return {"status": "ok"}
