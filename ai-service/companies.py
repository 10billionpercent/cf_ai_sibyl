import os
import time
import httpx
import asyncio
from urllib.parse import urlparse
from dotenv import load_dotenv

# --- NEW: MongoDB writing ---
from datetime import datetime, timezone
from pymongo import MongoClient, UpdateOne

# ---------------------------
# LOAD ENV
# ---------------------------
load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")

if not SERPAPI_KEY:
    raise ValueError("❌ SERPAPI_API_KEY not found")

# --- NEW: MongoDB config (same DB as resumes/jobs) ---
MONGO_URI = os.getenv("MONGODB_URI")
if not MONGO_URI:
    raise ValueError("❌ MONGODB_URI not found")

mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client["sibyl"]
companies_collection = mongo_db["companies"]

# ---------------------------
# CONFIG
# ---------------------------
GOOGLE_QUERIES = [
    # Ashby
    'site:jobs.ashbyhq.com "engineer"',
    'site:jobs.ashbyhq.com "software"',
    'site:jobs.ashbyhq.com "developer"',
    'site:jobs.ashbyhq.com "frontend"',
    'site:jobs.ashbyhq.com "backend"',
    'site:jobs.ashbyhq.com "intern"',
    'site:jobs.ashbyhq.com "full stack"',
    'site:jobs.ashbyhq.com "react"',

    # Greenhouse
    'site:job-boards.greenhouse.io "engineer"',
    'site:job-boards.greenhouse.io "software"',
    'site:job-boards.greenhouse.io "developer"',
    'site:job-boards.greenhouse.io "frontend"',
    'site:job-boards.greenhouse.io "backend"',
    'site:job-boards.greenhouse.io "intern"',
    'site:job-boards.greenhouse.io "full stack"',
    'site:job-boards.greenhouse.io "react"',
]

MAX_PAGES = 5
REQUEST_DELAY = 1.0

# ---------------------------
# FETCH GOOGLE LINKS
# ---------------------------
def fetch_google_links(query):
    print(f"\n🔍 {query}")
    url = "https://serpapi.com/search.json"
    all_links = []

    for page in range(MAX_PAGES):
        start = page * 10

        params = {
            "q": query,
            "engine": "google",
            "api_key": SERPAPI_KEY,
            "num": 10,
            "start": start
        }

        for attempt in range(3):
            try:
                with httpx.Client(timeout=15) as client:
                    r = client.get(url, params=params)
                    data = r.json()

                if "error" in data:
                    print("❌ SERPAPI ERROR:", data["error"])
                    return all_links

                results = data.get("organic_results", [])
                print(f"📄 Page {page+1}: {len(results)}")

                if not results:
                    return all_links

                for res in results:
                    link = res.get("link")
                    if link:
                        all_links.append(link)

                break

            except httpx.ReadTimeout:
                print(f"⚠️ Timeout page {page+1}, retry {attempt+1}")
                time.sleep(2)

            except Exception as e:
                print(f"❌ Error: {e}")
                break

        time.sleep(1)

    return all_links


# ---------------------------
# SLUG EXTRACTION
# ---------------------------
def get_slug_and_source(url):
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    parts = path.split("/")

    if not parts:
        return None, None

    slug = parts[0].lower()

    if slug in ["", "jobs"]:
        return None, None

    if "ashbyhq.com" in url:
        return slug, "ashby"

    if "greenhouse.io" in url:
        return slug, "greenhouse"

    return None, None


# ---------------------------
# COLLECT SLUGS
# ---------------------------
def collect_slugs():
    companies = {}

    for query in GOOGLE_QUERIES:
        links = fetch_google_links(query)

        for link in links:
            slug, source = get_slug_and_source(link)
            if slug:
                companies[slug] = source

        time.sleep(1)

    print(f"\n✅ Found {len(companies)} UNIQUE companies")
    return companies


# ---------------------------
# FETCH JOBS
# ---------------------------
async def fetch_ashby_jobs(client, slug):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    try:
        r = await client.get(url, timeout=10)
        if r.status_code != 200:
            return []
        return r.json().get("jobs", [])
    except:
        return []


async def fetch_greenhouse_jobs(client, slug):
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    try:
        r = await client.get(url, timeout=10)
        if r.status_code != 200:
            return []
        return r.json().get("jobs", [])
    except:
        return []


# ---------------------------
# ANALYSIS
# ---------------------------
def analyze_jobs(jobs):
    internship_keywords = ["intern", "internship"]
    internship_count = 0

    for job in jobs:
        title = job.get("title", "").lower()
        if any(k in title for k in internship_keywords):
            internship_count += 1

    score = internship_count * 2
    return internship_count, score


def assign_tier(score):
    if score >= 6:
        return "TIER 1 😈"
    elif score >= 2:
        return "TIER 2 🙂"
    else:
        return "TIER 3 💤"


# ---------------------------
# ENRICH COMPANIES
# ---------------------------
async def enrich_companies(companies):
    enriched = []

    async with httpx.AsyncClient() as client:
        for i, (slug, source) in enumerate(companies.items()):
            print(f"⚡ [{i+1}/{len(companies)}] {slug}")

            if source == "ashby":
                jobs = await fetch_ashby_jobs(client, slug)
            else:
                jobs = await fetch_greenhouse_jobs(client, slug)

            internship_count, score = analyze_jobs(jobs)
            tier = assign_tier(score)

            url = (
                f"https://jobs.ashbyhq.com/{slug}"
                if source == "ashby"
                else f"https://job-boards.greenhouse.io/{slug}"
            )

            enriched.append({
                "slug": slug,
                "source": source,
                "url": url,
                "active": True,
                "last_checked": None,
                "last_job_count": len(jobs),
                "internship_count": internship_count,
                "score": score,
                "tier": tier
            })

            await asyncio.sleep(0.5)

    return enriched


# ---------------------------
# SAVE TO MONGODB (NEW)
# ---------------------------
def save_companies_to_mongodb(enriched):
    ts = datetime.now(timezone.utc)

    ops = []
    for c in enriched:
        ops.append(
            UpdateOne(
                {"slug": c["slug"], "source": c["source"]},
                {
                    "$set": {
                        "url": c["url"],
                        "active": c.get("active", True),
                        "last_checked": c.get("last_checked", None),
                        "last_job_count": c.get("last_job_count", 0),
                        "internship_count": c.get("internship_count", 0),
                        "score": c.get("score", 0),
                        "tier": c.get("tier", "TIER 3"),
                        "updated_at": ts,
                    },
                    "$setOnInsert": {
                        "created_at": ts,
                    },
                },
                upsert=True,
            )
        )

    if not ops:
        print("🗄️ No companies to write to MongoDB")
        return

    res = companies_collection.bulk_write(ops, ordered=False)
    print(f"🗄️ MongoDB upserts={res.upserted_count}, modified={res.modified_count}")

    # optional safety: unique identity
    companies_collection.create_index([("slug", 1), ("source", 1)], unique=True)


# ---------------------------
# SAVE TO FILE
# ---------------------------
def save_companies(enriched, filename="companies.txt"):
    existing = set()

    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                existing.add(line.strip())

    new_count = 0

    with open(filename, "a", encoding="utf-8") as f:
        for c in enriched:
            line = f"{c['slug']} | {c['source']} | {c['url']} | {c['tier']} | score={c['score']}"

            if line not in existing:
                f.write(line + "\n")
                new_count += 1

    print(f"💾 Added {new_count} enriched companies")


# ---------------------------
# MAIN
# ---------------------------
def main():
    print("\n🔥 FULL INTELLIGENCE MODE 😈🔥")

    companies = collect_slugs()

    enriched = asyncio.run(enrich_companies(companies))

    enriched.sort(key=lambda x: x["score"], reverse=True)

    print("\n🔥 TOP COMPANIES:\n")
    for c in enriched[:20]:
        print(c)

    save_companies(enriched)

    # NEW: write to MongoDB (same DB as resumes/jobs)
    save_companies_to_mongodb(enriched)

    print("\n🏁 DONE. SIBYL IS EVOLVING 😤🔥")


if __name__ == "__main__":
    main()
