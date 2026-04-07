import os
import httpx
import json
import numpy as np
import asyncio
import re

from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from bson import ObjectId

load_dotenv()

ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_DATABASE_ID = os.getenv("CLOUDFLARE_DATABASE_ID")
GROQ_API_TOKEN = os.getenv("GROQ_API_KEY")
GROQ_FAST_MODEL = os.getenv("GROQ_FAST_MODEL", "llama-3.1-8b-instant")
GROQ_SLOW_MODEL = os.getenv("GROQ_SLOW_MODEL", "llama-3.3-70b-versatile")
GROQ_SLOW_TOP_N = int(os.getenv("GROQ_SLOW_TOP_N", "0"))
GROQ_FAST_SLEEP = float(os.getenv("GROQ_FAST_SLEEP", "8"))
GROQ_SLOW_SLEEP = float(os.getenv("GROQ_SLOW_SLEEP", "15"))
GROQ_SLOW_BATCH_SIZE = int(os.getenv("GROQ_SLOW_BATCH_SIZE", "4"))
GROQ_SLOW_BATCH_SLEEP = float(os.getenv("GROQ_SLOW_BATCH_SLEEP", "60"))
GROQ_MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", "300"))
JOB_DESC_MAX_CHARS = int(os.getenv("JOB_DESC_MAX_CHARS", "1200"))
RESUME_LIST_MAX = int(os.getenv("RESUME_LIST_MAX", "12"))
PROMPT_PATH = Path("prompts/job_match_prompt.txt")
D1_ENDPOINT = (
    f"https://api.cloudflare.com/client/v4/accounts/"
    f"{ACCOUNT_ID}/d1/database/{CLOUDFLARE_DATABASE_ID}/query"
)


async def _log_llm_error(reason, retry_count, last_error_message):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                D1_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
                    "Content-Type": "application/json"
                },
                json={
                    "sql": """
                    INSERT INTO event_logs (event_type, source, status, message, created_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    "params": [
                        "llm_error",
                        "llm",
                        "failed",
                        f"reason={reason}; retries={retry_count}; last_error={last_error_message}"
                    ]
                }
            )
    except Exception:
        pass


# -----------------------
# JSON SAFE
# -----------------------

def make_json_safe(obj):

    if isinstance(obj, dict):
        return {
            key: make_json_safe(value)
            for key, value in obj.items()
        }

    elif isinstance(obj, list):
        return [make_json_safe(item) for item in obj]

    elif isinstance(obj, ObjectId):
        return str(obj)

    elif isinstance(obj, datetime):
        return obj.isoformat()

    return obj


# -----------------------
# EMBEDDING (CHEAP)
# -----------------------

async def get_embedding(text):

    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/@cf/baai/bge-small-en-v1.5"

    async with httpx.AsyncClient(timeout=60) as client:

        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "text": text
            }
        )

    result = response.json()

    return result["result"]["data"][0]


# -----------------------
# COSINE SIMILARITY
# -----------------------

def similarity(a, b):

    a = np.array(a)
    b = np.array(b)

    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def _trim_text(value, max_chars):
    if not value or not isinstance(value, str):
        return ""
    text = value.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0].strip()


def _pick_resume_fields(resume):
    return {
        "role": resume.get("role"),
        "experience_level": resume.get("experience_level"),
        "skills": (resume.get("skills") or [])[:RESUME_LIST_MAX],
        "preferences": (resume.get("preferences") or [])[:RESUME_LIST_MAX],
        "technologies": (resume.get("technologies") or [])[:RESUME_LIST_MAX],
    }


def _pick_job_fields(job):
    return {
        "title": job.get("title"),
        "company": job.get("company"),
        "location": job.get("location"),
        "source": job.get("source"),
        "apply_url": job.get("apply_url"),
        "job_url": job.get("job_url"),
        "description": _trim_text(job.get("description", ""), JOB_DESC_MAX_CHARS),
    }


def _extract_json(text):
    if not text or not isinstance(text, str):
        raise ValueError("Empty response content")
    content = text.strip()
    if content.startswith("```"):
        content = content.strip("`")
        content = content.replace("json", "").strip()
    first = content.find("{")
    last = content.rfind("}")
    if first == -1 or last == -1 or last < first:
        raise ValueError("No JSON object found in response")
    return content[first:last + 1]


# -----------------------
# 70B EXPLAIN MATCH (GROQ)
# -----------------------

def _parse_retry_seconds(message):
    if not message:
        return None
    match = re.search(r"try again in ([0-9.]+)s", message)
    if match:
        try:
            return float(match.group(1))
        except Exception:
            return None
    match = re.search(r"try again in ([0-9.]+)ms", message)
    if match:
        try:
            return float(match.group(1)) / 1000.0
        except Exception:
            return None
    return None


async def call_llm(job, resume, model, max_retries=12, retry_delay=12):
    prompt = PROMPT_PATH.read_text()

    safe_job = make_json_safe(_pick_job_fields(job))
    resume_safe = make_json_safe(_pick_resume_fields(resume))

    full_prompt = f"""
{prompt}

Candidate Profile:

{json.dumps(resume_safe, indent=2)}

Job Posting:

{json.dumps(safe_job, indent=2)}
"""

    url = "https://api.groq.com/openai/v1/chat/completions"

    async with httpx.AsyncClient(timeout=60) as client:
        last_error_reason = None
        last_error_message = ""
        for attempt in range(1, max_retries + 1):
            try:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {GROQ_API_TOKEN}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a job matcher. Return JSON only."
                            },
                            {
                                "role": "user",
                                "content": full_prompt
                            }
                        ],
                        "temperature": 0,
                        "max_tokens": GROQ_MAX_TOKENS
                    }
                )
            except httpx.TimeoutException as e:
                last_error_reason = "timeout"
                last_error_message = str(e)
                await asyncio.sleep(retry_delay)
                continue
            except httpx.RequestError as e:
                last_error_reason = "request_error"
                last_error_message = str(e)
                await asyncio.sleep(retry_delay)
                continue

            try:
                result = response.json()
            except Exception:
                raw = await response.aread()
                preview = raw[:1000].decode("utf-8", errors="replace")
                print(
                    f"Groq non-JSON response (status={response.status_code}, model={model}, attempt={attempt}): {preview}"
                )
                raise RuntimeError("Groq returned non-JSON response")

            if result.get("error", {}).get("code") == "rate_limit_exceeded":
                message = result.get("error", {}).get("message", "")
                last_error_reason = "rate_limit"
                last_error_message = message or "rate_limit_exceeded"
                wait_seconds = _parse_retry_seconds(message) or retry_delay
                wait_seconds = max(wait_seconds + 5, 10)
                print(f"Groq rate limited, retrying in {wait_seconds:.2f}s (attempt {attempt}/{max_retries})")
                await asyncio.sleep(wait_seconds)
                continue

            if response.status_code != 200 or "choices" not in result:
                print(
                    "Groq unexpected response:",
                    {"status": response.status_code, "model": model, "attempt": attempt, "result": result}
                )
                raise RuntimeError("Groq returned unexpected response")

            print("Groq response:", result)
            break
        else:
            await _log_llm_error(last_error_reason or "unknown", max_retries, last_error_message or "retries_exhausted")
            raise RuntimeError("Groq rate limit exceeded after retries")

    content = result["choices"][0]["message"]["content"]
    payload = _extract_json(content)
    return json.loads(payload)


async def call_llm_fast(job, resume):
    return await call_llm(job, resume, model=GROQ_FAST_MODEL, max_retries=8, retry_delay=6)


async def call_llm_slow(job, resume):
    return await call_llm(job, resume, model=GROQ_SLOW_MODEL, max_retries=12, retry_delay=12)


# -----------------------
# MAIN MATCH PIPELINE
# -----------------------

async def match_jobs(resume, jobs):

    matched = []

    resume_embedding = resume.get("embedding")

    if not resume_embedding:
        print("No resume embedding found")
        return []

    scored = []

    total = len(jobs)

    # cheap similarity
    for idx, job in enumerate(jobs, start=1):

        job_text = f"""
Title: {job.get("title")}
Source: {job.get("source")}
URL: {job.get("url")}
"""

        try:

            print(f"Embedding {idx}/{total} ... {job.get('company', 'Unknown')} | {job.get('title', 'Untitled')}")
            job_embedding = await get_embedding(job_text)

            score = similarity(resume_embedding, job_embedding)

            scored.append((score, job))

        except Exception as e:
            print("Embedding failed:", e)

    # sort all jobs by similarity
    scored.sort(key=lambda x: x[0], reverse=True)

    all_jobs = [job for score, job in scored]

    print(f"Total jobs to explain: {len(all_jobs)}")

    # explain every job (top N with 70B, rest with fast model)
    for i, job in enumerate(all_jobs, start=1):

        try:

            if i <= GROQ_SLOW_TOP_N:
                await asyncio.sleep(GROQ_SLOW_SLEEP)
                result = await call_llm_slow(job, resume)
            else:
                await asyncio.sleep(GROQ_FAST_SLEEP)
                result = await call_llm_fast(job, resume)

            job["match"] = result
            matched.append(job)

            if i <= GROQ_SLOW_TOP_N and i % GROQ_SLOW_BATCH_SIZE == 0:
                await asyncio.sleep(GROQ_SLOW_BATCH_SLEEP)

        except Exception as e:
            print("Match failed:", e)

    return matched


async def match_jobs_stream(resume, jobs, on_result):

    resume_embedding = resume.get("embedding")

    if not resume_embedding:
        print("No resume embedding found")
        return

    scored = []
    total = len(jobs)

    for idx, job in enumerate(jobs, start=1):

        job_text = f"""
Title: {job.get("title")}
Source: {job.get("source")}
URL: {job.get("url")}
"""

        try:
            print(f"Embedding {idx}/{total} ... {job.get('company', 'Unknown')} | {job.get('title', 'Untitled')}")
            job_embedding = await get_embedding(job_text)
            score = similarity(resume_embedding, job_embedding)
            scored.append((score, job))
        except Exception as e:
            print("Embedding failed:", e)

    scored.sort(key=lambda x: x[0], reverse=True)
    all_jobs = [job for score, job in scored]

    print(f"Total jobs to explain: {len(all_jobs)}")

    for i, job in enumerate(all_jobs, start=1):
        try:
            if i <= GROQ_SLOW_TOP_N:
                await asyncio.sleep(GROQ_SLOW_SLEEP)
                result = await call_llm_slow(job, resume)
            else:
                await asyncio.sleep(GROQ_FAST_SLEEP)
                result = await call_llm_fast(job, resume)
            job["match"] = result
            await on_result(job)

            if i <= GROQ_SLOW_TOP_N and i % GROQ_SLOW_BATCH_SIZE == 0:
                await asyncio.sleep(GROQ_SLOW_BATCH_SLEEP)
        except Exception as e:
            print("Match failed:", e)
