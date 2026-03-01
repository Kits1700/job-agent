"""
Job scrapers — ALL API-based, no browser scraping.
Works reliably from GitHub Actions / cloud servers.

Sources:
1. Adzuna API (UK, EU, India — free, needs API key)
2. Reed API (UK — free, needs API key)
3. Arbeitnow API (EU — free, no key needed)
4. Greenhouse API (company career pages — no key needed)
5. Lever API (company career pages — no key needed)
"""
import asyncio
import hashlib
import base64
import logging

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("job_agent.scrapers")


def _make_id(source: str, key: str) -> str:
    return hashlib.sha256(f"{source}:{key}".encode()).hexdigest()[:16]


# ─────────────────────────────────────────────────
# 1. ADZUNA API (UK, EU, India)
# Free: https://developer.adzuna.com/
# ─────────────────────────────────────────────────

ADZUNA_COUNTRIES = {
    "United Kingdom": "gb", "London": "gb", "Cambridge": "gb",
    "Edinburgh": "gb", "Manchester": "gb", "Birmingham": "gb",
    "Berlin": "de", "Munich": "de", "Amsterdam": "nl",
    "Dublin": "ie", "Paris": "fr", "Stockholm": "se", "Zurich": "ch",
    "Bangalore": "in", "Bengaluru": "in", "Remote": "gb",
}

async def scrape_adzuna(search_queries: list[str], locations: list[str],
                         app_id: str = "", app_key: str = "") -> list[dict]:
    if not app_id or not app_key:
        logger.warning("Adzuna: No API key — skipping. Get one free at developer.adzuna.com")
        return []

    jobs = []
    seen_countries = set()

    async with httpx.AsyncClient(timeout=15) as client:
        for query in search_queries:
            for loc in locations:
                code = ADZUNA_COUNTRIES.get(loc, "gb")
                cache_key = f"{query}:{code}"
                if cache_key in seen_countries:
                    continue
                seen_countries.add(cache_key)

                try:
                    params = {
                        "app_id": app_id, "app_key": app_key,
                        "results_per_page": 15, "what": query,
                        "max_days_old": 3, "full_time": 1,
                        "content-type": "application/json",
                    }
                    if loc not in ("United Kingdom", "Remote"):
                        params["where"] = loc

                    resp = await client.get(
                        f"https://api.adzuna.com/v1/api/jobs/{code}/search/1",
                        params=params
                    )
                    if resp.status_code != 200:
                        continue

                    for r in resp.json().get("results", []):
                        salary = ""
                        if r.get("salary_min") and r.get("salary_max"):
                            salary = f"{r['salary_min']:.0f}-{r['salary_max']:.0f}"

                        jobs.append({
                            "external_id": _make_id("adzuna", str(r.get("id", ""))),
                            "title": r.get("title", ""),
                            "company": r.get("company", {}).get("display_name", "Unknown"),
                            "location": r.get("location", {}).get("display_name", ""),
                            "url": r.get("redirect_url", ""),
                            "source": "adzuna",
                            "description": r.get("description", "")[:5000],
                            "salary": salary,
                            "job_type": "full-time",
                        })

                    await asyncio.sleep(0.3)
                except Exception as e:
                    logger.error(f"Adzuna error ({code}, '{query}'): {e}")

    logger.info(f"Adzuna: found {len(jobs)} jobs")
    return jobs


# ─────────────────────────────────────────────────
# 2. REED API (UK only)
# Free: https://www.reed.co.uk/developers
# ─────────────────────────────────────────────────

async def scrape_reed(search_queries: list[str], locations: list[str],
                       api_key: str = "") -> list[dict]:
    if not api_key:
        logger.warning("Reed: No API key — skipping. Get one free at reed.co.uk/developers")
        return []

    jobs = []
    uk_locs = [l for l in locations if l in (
        "London", "Cambridge", "Edinburgh", "Manchester",
        "Birmingham", "United Kingdom", "Remote"
    )]
    auth = base64.b64encode(f"{api_key}:".encode()).decode()

    async with httpx.AsyncClient(timeout=15) as client:
        for query in search_queries:
            for loc in uk_locs:
                try:
                    params = {"keywords": query, "resultsToTake": 15, "postedWithin": 3}
                    if loc not in ("United Kingdom", "Remote"):
                        params["locationName"] = loc

                    resp = await client.get(
                        "https://www.reed.co.uk/api/1.0/search",
                        params=params,
                        headers={"Authorization": f"Basic {auth}"}
                    )
                    if resp.status_code != 200:
                        continue

                    for r in resp.json().get("results", []):
                        salary = ""
                        if r.get("minimumSalary") and r.get("maximumSalary"):
                            salary = f"£{r['minimumSalary']:.0f}-£{r['maximumSalary']:.0f}"

                        jobs.append({
                            "external_id": _make_id("reed", str(r.get("jobId", ""))),
                            "title": r.get("jobTitle", ""),
                            "company": r.get("employerName", "Unknown"),
                            "location": r.get("locationName", ""),
                            "url": r.get("jobUrl", ""),
                            "source": "reed",
                            "description": r.get("jobDescription", "")[:5000],
                            "salary": salary,
                            "job_type": "full-time",
                        })

                    await asyncio.sleep(0.3)
                except Exception as e:
                    logger.error(f"Reed error ('{query}' in {loc}): {e}")

    logger.info(f"Reed: found {len(jobs)} jobs")
    return jobs


# ─────────────────────────────────────────────────
# 3. ARBEITNOW API (EU — no key needed)
# Free: https://arbeitnow.com/api
# ─────────────────────────────────────────────────

async def scrape_arbeitnow(search_queries: list[str]) -> list[dict]:
    jobs = []
    async with httpx.AsyncClient(timeout=15) as client:
        for query in search_queries:
            try:
                resp = await client.get(
                    "https://arbeitnow.com/api/job-board-api",
                    params={"search": query}
                )
                if resp.status_code != 200:
                    continue

                for r in resp.json().get("data", []):
                    desc = r.get("description", "")
                    if "<" in desc:
                        desc = BeautifulSoup(desc, "html.parser").get_text("\n", strip=True)

                    loc = r.get("location", "")
                    if r.get("remote"):
                        loc = f"{loc} (Remote)" if loc else "Remote"

                    jobs.append({
                        "external_id": _make_id("arbeitnow", r.get("slug", r.get("url", ""))),
                        "title": r.get("title", ""),
                        "company": r.get("company_name", "Unknown"),
                        "location": loc,
                        "url": r.get("url", ""),
                        "source": "arbeitnow",
                        "description": desc[:5000],
                        "salary": "",
                        "job_type": "full-time",
                    })

                await asyncio.sleep(0.3)
            except Exception as e:
                logger.error(f"Arbeitnow error ('{query}'): {e}")

    logger.info(f"Arbeitnow: found {len(jobs)} jobs")
    return jobs


# ─────────────────────────────────────────────────
# 4. GREENHOUSE API (company boards)
# ─────────────────────────────────────────────────

BROAD_TERMS = [
    "research", "ux", "user", "design", "hci", "human",
    "ai", "product", "insight", "experience", "interaction",
    "ethics", "safety", "governance", "trust", "responsible",
    "qualitative", "usability",
]

async def scrape_greenhouse(search_queries: list[str], locations: list[str],
                             boards: list[str] = None) -> list[dict]:
    if not boards:
        return []

    jobs = []
    location_lower = [l.lower() for l in locations]

    async with httpx.AsyncClient(timeout=15) as client:
        for board in boards:
            try:
                resp = await client.get(
                    f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
                    params={"content": "true"}
                )
                if resp.status_code != 200:
                    continue

                for job in resp.json().get("jobs", []):
                    job_loc = job.get("location", {}).get("name", "")
                    title = job.get("title", "")

                    if not any(l in job_loc.lower() for l in location_lower) and "remote" not in job_loc.lower():
                        continue
                    if not any(t in title.lower() for t in BROAD_TERMS):
                        continue

                    desc = BeautifulSoup(job.get("content", ""), "html.parser").get_text("\n", strip=True)

                    jobs.append({
                        "external_id": _make_id("greenhouse", str(job["id"])),
                        "title": title,
                        "company": board.replace("-", " ").title(),
                        "location": job_loc,
                        "url": job["absolute_url"],
                        "source": "greenhouse",
                        "description": desc[:5000],
                        "salary": "",
                        "job_type": "full-time",
                        "_greenhouse_id": job["id"],
                        "_board": board,
                    })
            except Exception as e:
                logger.error(f"Greenhouse error for {board}: {e}")

    logger.info(f"Greenhouse: found {len(jobs)} jobs")
    return jobs


# ─────────────────────────────────────────────────
# 5. LEVER API (company boards)
# ─────────────────────────────────────────────────

async def scrape_lever(search_queries: list[str], locations: list[str],
                        companies: list[str] = None) -> list[dict]:
    if not companies:
        return []

    jobs = []
    location_lower = [l.lower() for l in locations]

    async with httpx.AsyncClient(timeout=15) as client:
        for company in companies:
            try:
                resp = await client.get(f"https://api.lever.co/v0/postings/{company}")
                if resp.status_code != 200:
                    continue

                for job in resp.json():
                    job_loc = job.get("categories", {}).get("location", "")
                    title = job.get("text", "")

                    if not any(l in job_loc.lower() for l in location_lower) and "remote" not in job_loc.lower():
                        continue
                    if not any(t in title.lower() for t in BROAD_TERMS):
                        continue

                    jobs.append({
                        "external_id": _make_id("lever", job["id"]),
                        "title": title,
                        "company": company.title(),
                        "location": job_loc,
                        "url": job["hostedUrl"],
                        "source": "lever",
                        "description": job.get("descriptionPlain", "")[:5000],
                        "salary": "",
                        "job_type": "full-time",
                        "_lever_id": job["id"],
                        "_company": company,
                    })
            except Exception as e:
                logger.error(f"Lever error for {company}: {e}")

    logger.info(f"Lever: found {len(jobs)} jobs")
    return jobs


# ─────────────────────────────────────────────────
# COMBINED SCRAPER
# ─────────────────────────────────────────────────

async def scrape_all(
    roles: list[dict],
    locations: list[str],
    excluded_companies: list[str] = None,
    excluded_title_keywords: list[str] = None,
    excluded_locations: list[str] = None,
    greenhouse_boards: list[str] = None,
    lever_companies: list[str] = None,
    adzuna_app_id: str = "",
    adzuna_app_key: str = "",
    reed_api_key: str = "",
) -> list[dict]:
    excluded_companies = [c.lower() for c in (excluded_companies or [])]
    excluded_title_keywords = [k.lower() for k in (excluded_title_keywords or [])]
    excluded_locations = [l.lower() for l in (excluded_locations or [])]

    all_queries = []
    for role in roles:
        all_queries.extend(role.get("search_queries", []))
    all_queries = list(dict.fromkeys(all_queries))

    logger.info(f"🔍 Searching with {len(all_queries)} queries across {len(locations)} locations")

    results = await asyncio.gather(
        scrape_adzuna(all_queries, locations, adzuna_app_id, adzuna_app_key),
        scrape_reed(all_queries, locations, reed_api_key),
        scrape_arbeitnow(all_queries),
        scrape_greenhouse(all_queries, locations, boards=greenhouse_boards),
        scrape_lever(all_queries, locations, companies=lever_companies),
        return_exceptions=True,
    )

    all_jobs = []
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Scraper failed: {result}")
        else:
            all_jobs.extend(result)

    seen = set()
    unique = []
    excluded_count = 0

    for job in all_jobs:
        if job["external_id"] in seen:
            continue
        seen.add(job["external_id"])

        if any(e in job.get("company", "").lower() for e in excluded_companies):
            excluded_count += 1; continue
        if any(e in job.get("title", "").lower() for e in excluded_title_keywords):
            excluded_count += 1; continue
        if any(e in job.get("location", "").lower() for e in excluded_locations):
            excluded_count += 1; continue

        unique.append(job)

    logger.info(f"Total: {len(unique)} jobs after filtering ({excluded_count} excluded)")
    return unique
