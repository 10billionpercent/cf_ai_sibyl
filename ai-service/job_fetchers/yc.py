import requests
import time
from bs4 import BeautifulSoup

from job_filters import is_internship


HEADERS = {
    "User-Agent": "Sibyl Internship Agent"
}


CAREER_KEYWORDS = [
    "careers",
    "jobs",
    "join",
    "hiring",
    "work with us",
    "open roles",
    "positions"
]


COMMON_PATHS = [
    "/careers",
    "/jobs",
    "/join",
    "/work-with-us",
    "/join-us"
]


def find_careers_page(website):

    try:
        # try common paths first (fast)
        for path in COMMON_PATHS:
            url = website.rstrip("/") + path

            response = requests.get(url, headers=HEADERS, timeout=5)

            if response.status_code == 200:
                return url

        # fallback → parse homepage
        response = requests.get(website, headers=HEADERS, timeout=5)

        soup = BeautifulSoup(response.text, "html.parser")

        for link in soup.find_all("a"):

            text = (link.text or "").lower()
            href = link.get("href")

            if not href:
                continue

            if any(keyword in text for keyword in CAREER_KEYWORDS):

                if href.startswith("http"):
                    return href

                return website.rstrip("/") + "/" + href.lstrip("/")

    except Exception:
        return None

    return None


def fetch_yc_jobs():

    url = "https://yc-oss.github.io/api/companies/hiring.json"

    response = requests.get(url, headers=HEADERS)

    companies = response.json()

    jobs = []

    # polite limit
    for company in companies[:30]:

        website = company.get("website")

        if not website:
            continue

        # polite delay
        time.sleep(1)

        careers = find_careers_page(website)

        if not careers:
            continue

        description = (
            company.get("long_description")
            or company.get("one_liner")
            or ""
        )

        if not is_internship(description):
            continue

        jobs.append({
            "title": f"{company.get('name')} — Internship",
            "url": careers,
            "source": "YCombinator",
            "description": description
        })

    return jobs