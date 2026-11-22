from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
# Load backend/.env before importing modules that read environment settings.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.job_provider import JobProviderError, provider_configuration, search_all_providers
from app.matcher import DEMO_JOBS, extract_skills, match_jobs
from app.resume_parser import extract_resume_text

app = FastAPI(
    title="InternHunt API",
    description="India job search and resume analysis.",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://127.0.0.1:5500,http://localhost:5500",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_SUFFIXES = {".pdf", ".docx"}


def search_demo_jobs(q: str, location: str, selected_type: str, limit: int) -> dict:
    """Keep the local demo feed available until at least one provider is configured."""
    query = q.strip().lower()
    place = location.strip().lower()
    results = []

    for job in DEMO_JOBS:
        searchable = " ".join([
            job.get("title", ""),
            job.get("company", ""),
            job.get("description", ""),
            " ".join(job.get("skills", [])),
        ]).lower()

        if query and query not in searchable:
            continue
        if place and place not in job.get("location", "").lower():
            continue

        job_type = job.get("employment_type", "").lower()
        if selected_type in {"internship", "intern"} and "intern" not in job_type:
            continue
        if selected_type in {"full-time", "full time", "fulltime"} and "full" not in job_type:
            continue

        results.append({**job, "source": "Local demo dataset", "is_demo": True})

    return {
        "count": len(results[:limit]),
        "total": len(results),
        "jobs": results[:limit],
        "is_demo": True,
        "notice": "Sample listings are shown because no live provider is configured. Add provider credentials or board IDs to backend/.env to load live listings.",
    }


@app.get("/")
def health_check():
    return {"status": "ok", "service": "InternHunt API"}


@app.get("/api/providers")
def list_providers():
    return {"providers": provider_configuration()}


@app.get("/api/jobs")
async def list_jobs(
    q: str = "",
    location: str = "",
    type: str = "all",
    source: str = "all",
    limit: int = Query(default=30, ge=1, le=50),
    days: int = Query(default=30, ge=1, le=365),
):
   
    try:
        result = await search_all_providers(
            q=q,
            location=location,
            selected_type=type,
            limit=limit,
            days=days,
            source=source,
        )
    except JobProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Keep a clearly-labelled sample feed for local UI development when no source
    # has been configured at all. Selecting a specific unconfigured source returns
    # an empty list and an actionable provider status rather than demo jobs.
    any_configured = any(item["configured"] for item in provider_configuration())
    if not any_configured and source.strip().lower() == "all":
        demo = search_demo_jobs(q, location, type.strip().lower(), min(limit, 10))
        demo["provider_status"] = result["provider_status"]
        demo["notice"] = (
            "Showing sample data because no live providers are configured. "
            "Add one or more API keys or career-board IDs to backend/.env."
        )
        return demo

    return result


@app.post("/api/resumes/analyze")
async def analyze_resume(
    file: UploadFile = File(...),
    source: str = Form(default="all"),
    location: str = Form(default=""),
    selected_type: str = Form(default="all"),
):
    filename = Path(file.filename or "resume").name
    suffix = Path(filename).suffix.lower()

    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail="Upload a PDF or DOCX resume.")

    try:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
    finally:
        await file.close()

    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="The resume must be 5 MB or smaller.")

    if suffix == ".pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="The file does not look like a valid PDF.")
    if suffix == ".docx" and not content.startswith(b"PK"):
        raise HTTPException(status_code=400, detail="The file does not look like a valid DOCX.")

    try:
        resume_text = extract_resume_text(filename, content)
    except Exception as exc:
        message = str(exc) if isinstance(exc, ValueError) else "Could not read this document. Try another PDF or DOCX."
        raise HTTPException(status_code=422, detail=message) from exc

    if len(resume_text.strip()) < 40:
        raise HTTPException(
            status_code=422,
            detail="Very little text was found. This may be a scanned PDF; try a text-based PDF or DOCX.",
        )

    skills = extract_skills(resume_text)
    configured_providers = provider_configuration()
    has_configured_provider = any(item["configured"] for item in configured_providers)

    selected_source = source.strip().lower() or "all"
    if has_configured_provider or selected_source != "all":
        # Reuse the same live-provider aggregation layer as /api/jobs. This keeps
        # resume recommendations consistent with the listings visible on find.html.
        try:
            job_feed = await search_all_providers(
                q="",
                location=location.strip(),
                selected_type=selected_type.strip().lower() or "all",
                limit=50,
                days=30,
                source=selected_source,
            )
        except JobProviderError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        candidate_jobs = job_feed.get("jobs", [])
        matches = match_jobs(resume_text, candidate_jobs, limit=15)
        if candidate_jobs:
            match_source = "live API listings"
            notice = (
                f"Your resume was compared with {len(candidate_jobs)} live job listings "
                "returned by the connected providers. Similarity scores are ranking signals, "
                "not probabilities of getting hired."
            )
        else:
            match_source = "no live listings available"
            notice = (
                "No live jobs were available for comparison. Check provider status below, "
                "configure a provider key/board ID, or try a broader location/job-type filter. "
                "The system did not silently substitute demo jobs."
            )
        provider_status = job_feed.get("provider_status", [])
        jobs_considered = len(candidate_jobs)
        active_providers = job_feed.get("active_providers", [])
    else:
        # Keep the project testable before the user has obtained provider keys.
        # Demo jobs are only used for the default all-sources view, not for a
        # specific provider that has not been configured.
        demo_feed = search_demo_jobs(
            q="",
            location=location.strip(),
            selected_type=selected_type.strip().lower() or "all",
            limit=10,
        )
        candidate_jobs = demo_feed["jobs"]
        matches = match_jobs(resume_text, candidate_jobs, limit=15)
        match_source = "local demo dataset"
        jobs_considered = len(candidate_jobs)
        provider_status = configured_providers
        active_providers = []
        notice = (
            "No external job provider is configured yet, so these recommendations use "
            "clearly labelled local demo jobs. Add API credentials or company board IDs "
            "to backend/.env to compare your resume with live listings. Similarity scores "
            "are ranking signals, not probabilities of getting hired."
        )

    return {
        "message": "Resume analysis complete.",
        "filename": filename,
        "extracted_characters": len(resume_text),
        "skills": skills,
        "matches": matches,
        "match_source": match_source,
        "jobs_considered": jobs_considered,
        "active_providers": active_providers,
        "provider_status": provider_status,
        "notice": notice,
    }
