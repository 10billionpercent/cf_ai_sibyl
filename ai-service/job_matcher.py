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
GROQ_API_TOKEN = os.getenv("GROQ_API_KEY")
PROMPT_PATH = Path("prompts/job_match_prompt.txt")


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


async def call_llm(job, resume, max_retries=6, retry_delay=8):
    prompt = PROMPT_PATH.read_text()

    safe_job = make_json_safe(job)

    # Strip embedding to keep prompt clean
    resume_safe = make_json_safe({k: v for k, v in resume.items() if k != "embedding"})

    full_prompt = f"""
{prompt}

Candidate Profile:

{json.dumps(resume_safe, indent=2)}

Job Posting:

{json.dumps(safe_job, indent=2)}
"""

    url = "https://api.groq.com/openai/v1/chat/completions"

    async with httpx.AsyncClient(timeout=60) as client:
        for attempt in range(1, max_retries + 1):
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {GROQ_API_TOKEN}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.3-70b-versatile",
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
                    "temperature": 0
                }
            )

            result = response.json()

            if result.get("error", {}).get("code") == "rate_limit_exceeded":
                message = result.get("error", {}).get("message", "")
                wait_seconds = _parse_retry_seconds(message) or retry_delay
                wait_seconds = max(wait_seconds, 2)
                print(f"Groq rate limited, retrying in {wait_seconds:.2f}s (attempt {attempt}/{max_retries})")
                await asyncio.sleep(wait_seconds)
                continue

            print("Groq response:", result)
            break
        else:
            raise RuntimeError("Groq rate limit exceeded after retries")

    content = result["choices"][0]["message"]["content"]

    content = content.strip()

    if content.startswith("```"):
        content = content.strip("`")
        content = content.replace("json", "").strip()

    return json.loads(content)


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

    # explain every job
    BATCH_SIZE = 8

    for i, job in enumerate(all_jobs, start=1):

        try:

            await asyncio.sleep(8)
            result = await call_llm(job, resume)

            job["match"] = result
            matched.append(job)

            if i % BATCH_SIZE == 0:
                await asyncio.sleep(30)

        except Exception as e:
            print("Match failed:", e)

    return matched
