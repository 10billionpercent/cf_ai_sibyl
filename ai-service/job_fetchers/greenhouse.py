# C:\Users\shrey\Desktop\sibyl\ai-service\job_fetchers\greenhouse.py
import random
import time
import re
import requests
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

from db import db


_INTERNSHIP_RE = re.compile(r"\bintern(ship)?s?\b", re.IGNORECASE)
ROLE_KEYWORDS = [
    "software engineer",
    "software developer",
    "swe",
    "web developer",
    "web development",
    "full stack",
    "full-stack",
    "fullstack",
    "frontend",
    "frontend engineer",
    "front-end"
]
SPECIALIZATION_KEYWORDS = [
    "full stack",
    "full-stack",
    "fullstack",
    "frontend",
    "front-end",
    "frontend engineer",
    "web",
    "ui",
    "user interface"
]
SPECIALIZATION_ALLOWLIST_TERMS = [
    "summer",
    "winter",
    "spring",
    "fall",
    "autumn",
    "placement",
    "industry placement",
    "co-op",
    "coop",
    "remote",
    "hybrid",
    "on-site",
    "onsite",
    "part-time",
    "full-time",
    "12 month",
    "12-month",
    "6 month",
    "6-month",
    "2025",
    "2026",
    "2027",
    "2028"
]
HEADERS = {"User-Agent": "Sibyl Internship Agent"}
RECENT_DAYS = 7


def _is_internship_title(title):
    if not title:
        return False
    return _INTERNSHIP_RE.search(title) is not None


def _is_target_role(title, role_keywords, specialization_keywords):
    if not title:
        return False
    t = title.lower()
    if any(k in t for k in role_keywords):
        match = re.search(r"software (engineering )?engineer[^a-z0-9]*intern", t)
        if match:
            segment = t[match.end():]
            segment = segment.strip(" ,:-–—()[]")
            if segment:
                if any(k in segment for k in specialization_keywords):
                    return True
                if any(k in segment for k in SPECIALIZATION_ALLOWLIST_TERMS):
                    return True
                return False
        return True
    return False


def _location_name(location):
    if isinstance(location, dict):
        name = location.get("name")
        if isinstance(name, str):
            return name.strip()
    if isinstance(location, str):
        return location.strip()
    return ""


def _parse_dt(value):
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _is_recent(value):
    dt = _parse_dt(value)
    if not dt:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    cutoff = datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)
    return dt >= cutoff


def fetch_greenhouse_jobs(role_keywords=None, specialization_keywords=None):
    companies = _load_companies("greenhouse")
    role_keywords = role_keywords or ROLE_KEYWORDS
    specialization_keywords = specialization_keywords or SPECIALIZATION_KEYWORDS

    jobs = []

    total = len(companies)
    for i, company in enumerate(companies, start=1):
        slug = (company.get("slug") or "").strip()
        if not slug:
            continue

        print(f"Fetching {i}/{total} {slug}...")
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"

        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            if response.status_code != 200:
                time.sleep(random.uniform(0.5, 1.0))
                continue
            data = response.json()
        except Exception:
            time.sleep(random.uniform(0.5, 1.0))
            continue

        entries = data.get("jobs", [])
        if not isinstance(entries, list):
            time.sleep(random.uniform(0.5, 1.0))
            continue

        internship_jobs = [
            j for j in entries
            if _is_internship_title(j.get("title", ""))
            and _is_target_role(j.get("title", ""), role_keywords, specialization_keywords)
            and _is_recent(j.get("updated_at") or j.get("created_at"))
        ]

        print(f"Found {len(internship_jobs)} internships")
        if not internship_jobs:
            time.sleep(random.uniform(0.5, 1.0))
            continue

        for job in internship_jobs:
            title = (job.get("title") or "").strip()
            location = _location_name(job.get("location"))
            apply_url = (job.get("absolute_url") or "").strip()
            posted_at = job.get("updated_at") or job.get("created_at") or None

            normalized = {
                "job_id": str(job.get("id", "")),
                "title": title,
                "company": slug,
                "source": "greenhouse",
                "location": location,
                "is_remote": "remote" in location.lower(),
                "employment_type": None,
                "department": None,
                "team": None,
                "apply_url": apply_url,
                "job_url": apply_url,
                "url": apply_url,
                "description": (job.get("content") or "").strip()
                if isinstance(job.get("content"), str)
                else "",
                "posted_at": posted_at,
            }

            if normalized["job_id"] and normalized["apply_url"]:
                jobs.append(normalized)

        time.sleep(random.uniform(0.5, 1.0))

    return jobs


def _load_companies(source):
    try:
        companies_collection = db["companies"]
        companies = list(companies_collection.find({"source": source}))
        if companies:
            return companies
    except Exception:
        pass

    # fallback to companies.json
    for path in [Path("companies.json"), Path("..") / "companies.json"]:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return [c for c in data if c.get("source") == source]
            except Exception:
                continue

    return []
