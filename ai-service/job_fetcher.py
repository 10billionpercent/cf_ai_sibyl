from job_fetchers.ashby import fetch_ashby_jobs
from job_fetchers.greenhouse import fetch_greenhouse_jobs

DEFAULT_ROLE_KEYWORDS = [
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
    "front-end",
    "ui"
]
DEFAULT_SPECIALIZATION_KEYWORDS = [
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
DEFAULT_EXCLUDE_KEYWORDS = [
    "machine learning",
    "ml",
    "ai",
    "data scientist",
    "data science",
    "deep learning",
    "nlp",
    "computer vision",
    "robotics"
]


def _resume_text(resume):
    if not resume:
        return ""
    parts = []
    for key in ("role", "experience_level"):
        value = resume.get(key)
        if isinstance(value, str):
            parts.append(value)
    for key in ("skills", "preferences", "technologies"):
        value = resume.get(key) or []
        if isinstance(value, list):
            parts.extend([str(v) for v in value if v])
    return " ".join(parts).lower()


def _build_role_filters(resume):
    if not resume:
        return DEFAULT_ROLE_KEYWORDS, DEFAULT_SPECIALIZATION_KEYWORDS

    text = _resume_text(resume)

    want_frontend = any(
        k in text for k in [
            "frontend", "front-end", "ui", "user interface", "react", "javascript", "html", "css"
        ]
    )
    want_fullstack = any(
        k in text for k in [
            "full stack", "full-stack", "fullstack", "node", "express", "backend", "api"
        ]
    )
    want_web = "web" in text or "web app" in text or "web application" in text

    role_keywords = [
        "software engineer",
        "software developer",
        "swe",
    ]
    specialization_keywords = []

    if want_web:
        role_keywords.extend(["web developer", "web development"])
        specialization_keywords.append("web")
    if want_fullstack:
        role_keywords.extend(["full stack", "full-stack", "fullstack"])
        specialization_keywords.extend(["full stack", "full-stack", "fullstack"])
    if want_frontend:
        role_keywords.extend(["frontend", "frontend engineer", "front-end", "ui"])
        specialization_keywords.extend(["frontend", "frontend engineer", "front-end", "ui", "user interface"])

    if not specialization_keywords:
        specialization_keywords = DEFAULT_SPECIALIZATION_KEYWORDS
    return role_keywords, specialization_keywords


def _build_exclude_keywords(resume):
    if not resume:
        return DEFAULT_EXCLUDE_KEYWORDS

    text = _resume_text(resume)

    wants_ai = any(
        k in text for k in [
            "machine learning", "ml", "data science", "deep learning", "nlp", "computer vision"
        ]
    )
    frontend_signals = any(
        k in text for k in [
            "frontend", "front-end", "ui", "react", "javascript", "html", "css"
        ]
    )

    if wants_ai and not frontend_signals:
        return [
            "frontend",
            "front-end",
            "full stack",
            "full-stack",
            "fullstack",
            "web developer",
            "web development",
            "ui",
            "user interface"
        ]

    return DEFAULT_EXCLUDE_KEYWORDS


def fetch_all_jobs(resume=None):
    jobs = []
    role_keywords, specialization_keywords = _build_role_filters(resume)
    exclude_keywords = _build_exclude_keywords(resume)

    try:
        print("Fetching Ashby jobs...")
        jobs.extend(fetch_ashby_jobs(role_keywords, specialization_keywords))
    except Exception as e:
        print("Ashby failed:", e)

    try:
        print("Fetching Greenhouse jobs...")
        jobs.extend(fetch_greenhouse_jobs(role_keywords, specialization_keywords))
    except Exception as e:
        print("Greenhouse failed:", e)

    if exclude_keywords:
        exclude = [k.lower() for k in exclude_keywords]
        filtered = []
        for job in jobs:
            title = (job.get("title") or "").lower()
            if any(k in title for k in exclude):
                continue
            filtered.append(job)
        jobs = filtered

    print(f"\nTotal jobs fetched: {len(jobs)}")

    return jobs
