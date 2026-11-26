from __future__ import annotations

import asyncio
import html
import os
import re
import time
from html.parser import HTMLParser
from typing import Any, Awaitable, Callable

import httpx

CACHE_TTL_SECONDS = max(60, int(os.getenv("JOB_CACHE_TTL_SECONDS", "1800")))
MAX_PER_PROVIDER = 20
_cache: dict[tuple[str, str], tuple[float, Any]] = {}


class JobProviderError(Exception):
    """A safe error returned by an external job provider."""


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def plain_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    parser = _TextExtractor()
    try:
        parser.feed(value)
        return re.sub(r"\s+", " ", html.unescape(" ".join(parser.parts))).strip()
    except Exception:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip()


def _csv_env(name: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


def _is_configured(provider: str) -> bool:
    if provider == "indianapi":
        return bool(os.getenv("INDIANAPI_API_KEY", "").strip())
    return False


def provider_configuration() -> list[dict[str, Any]]:
    """Return provider configuration status without exposing credentials."""
    definitions = [
        ("indianapi", "Indian API", "INDIANAPI_API_KEY", "India-focused aggregator")
    ]
    return [
        {
            "id": key,
            "name": name,
            "kind": kind,
            "configured": _is_configured(key),
            "configuration": config,
        }
        for key, name, config, kind in definitions
    ]


def _city_aliases(value: str) -> str:
    text = (value or "").lower()
    aliases = {
        "bengaluru": "bangalore",
        "bangalore": "bengaluru",
        "gurugram": "gurgaon",
        "gurgaon": "gurugram",
        "mumbai": "bombay",
        "bombay": "mumbai",
        "chennai": "madras",
        "madras": "chennai",
        "kochi": "cochin",
        "cochin": "kochi",
        "thiruvananthapuram": "trivandrum",
        "trivandrum": "thiruvananthapuram",
    }
    for first, second in aliases.items():
        if first in text:
            text += " " + second
    return text


_INDIA_LOCATIONS = {
    "india", "bengaluru", "bangalore", "hyderabad", "chennai", "mumbai",
    "pune", "new delhi", "delhi", "noida", "gurugram", "gurgaon",
    "kolkata", "ahmedabad", "jaipur", "indore", "chandigarh", "coimbatore",
    "mysore", "mangalore", "visakhapatnam", "vizag", "bhubaneswar", "nagpur",
    "lucknow", "bhopal", "surat", "vadodara", "patna", "ranchi", "dehradun",
    "guwahati", "thiruvananthapuram", "trivandrum", "kochi", "cochin", "kerala",
    "tamil nadu", "karnataka", "telangana", "maharashtra", "west bengal",
    "uttar pradesh", "haryana", "punjab", "rajasthan", "madhya pradesh",
    "andhra pradesh", "odisha", "assam", "jharkhand", "goa",
}


def is_india_listing(job: dict[str, Any]) -> bool:
    country = str(job.get("country") or "").strip().upper()
    if country:
        return country in {"IN", "IND", "INDIA"}
    location = _city_aliases(str(job.get("location") or ""))
    if not location:
        return False
    return any(place in location for place in _INDIA_LOCATIONS)


def _infer_type(title: str, employment_type: str, description: str = "") -> str:
    text = f"{title} {employment_type} {description[:1200]}".lower()
    if re.search(r"\b(intern(ship)?|summer intern|apprentice(ship)?)\b", text):
        return "Internship"
    if re.search(r"\b(full[ -]?time|permanent)\b", text):
        return "Full-time"
    if "part-time" in text or "part time" in text:
        return "Part-time"
    return employment_type or "Not specified"


def _normalize(
    *,
    provider: str,
    provider_job_id: Any,
    title: Any,
    company: Any,
    location: Any,
    employment_type: Any = "",
    work_model: Any = "",
    description: Any = "",
    skills: Any = None,
    apply_url: Any = None,
    source_url: Any = None,
    posted_at: Any = None,
    country: Any = None,
    salary: Any = None,
) -> dict[str, Any]:
    title_text = str(title or "Untitled role").strip()
    description_text = plain_text(description) if isinstance(description, str) else ""
    type_text = _infer_type(title_text, str(employment_type or ""), description_text)
    if not isinstance(skills, list):
        skills = []
    return {
        "id": f"{provider}:{provider_job_id or title_text}",
        "provider_job_id": str(provider_job_id or ""),
        "title": title_text,
        "company": str(company or "Company not specified").strip(),
        "location": str(location or "Location not specified").strip(),
        "country": str(country or ""),
        "employment_type": type_text,
        "work_model": str(work_model or ""),
        "experience_level": "",
        "description": description_text,
        "skills": [str(skill) for skill in skills if skill],
        "salary": salary,
        "posted_at": posted_at,
        "apply_url": str(apply_url or source_url or "") or None,
        "source_url": str(source_url or apply_url or "") or None,
        "source": provider,
        "is_demo": False,
    }


def _matches_type(job: dict[str, Any], selected_type: str) -> bool:
    selected = (selected_type or "all").strip().lower()
    if selected in {"", "all"}:
        return True
    label = f"{job.get('employment_type', '')} {job.get('title', '')}".lower()
    if selected in {"intern", "internship"}:
        return "intern" in label or "apprentice" in label
    if selected in {"full-time", "full time", "fulltime"}:
        return "full" in label or "permanent" in label
    return selected in label


def _matches_query_and_location(job: dict[str, Any], q: str, location: str) -> bool:
    haystack = " ".join([
        str(job.get("title") or ""),
        str(job.get("company") or ""),
        str(job.get("description") or ""),
        " ".join(job.get("skills") or []),
    ]).lower()
    terms = [term for term in q.lower().split() if term]
    if terms and not all(term in haystack for term in terms):
        return False
    if location:
        job_location = _city_aliases(str(job.get("location") or ""))
        wanted = _city_aliases(location)
        if not all(token in job_location for token in wanted.split()):
            return False
    return True


async def _cached(provider: str, key: str, loader: Callable[[], Awaitable[Any]]) -> Any:
    cache_key = (provider, key)
    now = time.monotonic()
    entry = _cache.get(cache_key)
    if entry and entry[0] > now:
        return entry[1]
    data = await loader()
    _cache[cache_key] = (now + CACHE_TTL_SECONDS, data)
    return data


async def _request_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs: Any,
) -> Any:
    response = await client.request(method, url, **kwargs)
    if response.status_code == 401 or response.status_code == 403:
        raise JobProviderError("The provider rejected its API credentials. Check the key in backend/.env.")
    if response.status_code == 429:
        raise JobProviderError("The provider request limit has been reached. Try again after its quota resets.")
    if response.status_code >= 500:
        raise JobProviderError(f"The provider is temporarily unavailable (HTTP {response.status_code}).")
    if response.status_code >= 400:
        raise JobProviderError(f"The provider returned HTTP {response.status_code}.")
    try:
        return response.json()
    except ValueError as exc:
        raise JobProviderError("The provider returned an unreadable response.") from exc


def _type_query(q: str, selected_type: str) -> str:
    query = q.strip()
    selected = selected_type.lower()
    if selected in {"intern", "internship"} and "intern" not in query.lower():
        query = f"{query} internship".strip()
    elif selected in {"full-time", "full time", "fulltime"} and not any(
        phrase in query.lower() for phrase in ("full-time", "full time", "permanent")
    ):
        query = f"{query} full-time".strip()
    return query



async def _indianapi(q: str, location: str, selected_type: str, limit: int) -> list[dict[str, Any]]:
    api_key = os.getenv("INDIANAPI_API_KEY", "").strip()
    if not api_key:
        return []
    # The provider's published docs mark title/location/job_type filters as unconfirmed.
    # Request a bounded listing page, then filter locally to avoid relying on undocumented filters.
    cache_key = f"{q.lower()}|{location.lower()}|{selected_type}|{limit}"

    async def load() -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=22.0) as client:
            payload = await _request_json(
                client, "GET", "https://jobs.indianapi.in/jobs",
                params={"limit": min(max(limit * 3, 20), 100)},
                headers={"X-Api-Key": api_key},
            )
        records = payload if isinstance(payload, list) else (
            payload.get("jobs") or payload.get("data") or payload.get("results") or []
            if isinstance(payload, dict) else []
        )
        if not isinstance(records, list):
            raise JobProviderError("Indian API returned an unexpected response format.")
        result = []
        for item in records:
            if not isinstance(item, dict):
                continue
            job = _normalize(
                provider="Indian API",
                provider_job_id=item.get("id") or item.get("job_id"),
                title=item.get("title") or item.get("job_title"),
                company=item.get("company"), location=item.get("location"),
                employment_type=item.get("job_type"),
                description=" ".join(str(item.get(key) or "") for key in (
                    "job_description", "role_and_responsibility", "education_and_skills", "about_company"
                )),
                apply_url=item.get("apply_link"), source_url=item.get("apply_link"),
                posted_at=item.get("posted_date"),
                country=item.get("country") or item.get("country_code"),
            )
            if is_india_listing(job):
                result.append(job)
        return result

    return await _cached("indianapi", cache_key, load)




PROVIDER_NAMES = {
    "indianapi": "Indian API",
}


async def search_all_providers(
    q: str = "",
    location: str = "",
    selected_type: str = "all",
    limit: int = 10,
    days: int = 30,
    source: str = "all",
) -> dict[str, Any]:
    """Search all configured providers in parallel, merge and deduplicate India jobs."""
    source = (source or "all").strip().lower()
    if source not in {"all", *PROVIDER_NAMES.keys()}:
        raise JobProviderError("Unknown source filter. Choose all,  indianapi.")

    configured = [p for p in PROVIDER_NAMES if _is_configured(p) and (source == "all" or source == p)]
    not_configured = [p for p in PROVIDER_NAMES if not _is_configured(p) and (source == "all" or source == p)]
    provider_status: list[dict[str, Any]] = []
    all_jobs: list[dict[str, Any]] = []

    adapters: dict[str, Callable[[], Awaitable[list[dict[str, Any]]]]] = {
        "indianapi": lambda: _indianapi(q, location, selected_type, min(limit, 20)),
    }

    async def run_provider(provider: str) -> tuple[str, Any]:
        try:
            return provider, await adapters[provider]()
        except Exception as exc:
            return provider, exc

    fetched = await asyncio.gather(*(run_provider(provider) for provider in configured))
    for provider in not_configured:
        provider_status.append({
            "provider": PROVIDER_NAMES[provider],
            "status": "not_configured",
            "count": 0,
            "detail": "Add its credentials or board identifiers to backend/.env.",
        })

    for provider, value in fetched:
        if isinstance(value, Exception):
            provider_status.append({
                "provider": PROVIDER_NAMES[provider],
                "status": "error",
                "count": 0,
                "detail": str(value)[:240],
            })
            continue
        filtered = [
            job for job in value
            if is_india_listing(job)
            and _matches_type(job, selected_type)
            and _matches_query_and_location(job, q, location)
        ]
        all_jobs.extend(filtered)
        provider_status.append({
            "provider": PROVIDER_NAMES[provider],
            "status": "ok",
            "count": len(filtered),
            "detail": "Search completed.",
        })

    # De-duplicate common cross-posts using title + company + location.
    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    for job in all_jobs:
        key = (
            re.sub(r"\W+", "", str(job.get("title", "")).lower()),
            re.sub(r"\W+", "", str(job.get("company", "")).lower()),
            re.sub(r"\W+", "", str(job.get("location", "")).lower()),
        )
        if key not in unique:
            unique[key] = job
    jobs = list(unique.values())[:max(1, min(limit, 50))]

    ok_sources = [item["provider"] for item in provider_status if item["status"] == "ok"]
    error_sources = [item["provider"] for item in provider_status if item["status"] == "error"]
    if not configured:
        notice = "No external provider is configured yet. Add one or more API keys or company board IDs to backend/.env."
    elif error_sources and jobs:
        notice = "Some providers failed, but results from the others are shown. Check the provider status below."
    elif error_sources:
        notice = "Configured providers could not return results. Check provider status below and verify API credentials."
    elif not jobs:
        notice = "No matching India-based listings were returned. Try a broader keyword or location."
    else:
        notice = "Live India job listings from the configured providers. Apply links open the original provider or employer page."

    return {
        "count": len(jobs),
        "total": len(all_jobs),
        "jobs": jobs,
        "is_demo": False,
        "notice": notice,
        "provider_status": provider_status,
        "active_providers": ok_sources,
    }
