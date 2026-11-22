# InternHunt

## What's included
## 1. Providers and credentials
Only providers configured in `backend/.env` are queried. Choose **All connected sources** in `find.html` to aggregate all configured providers, or choose one source from the dropdown.

### Indian API Jobs API

- Docs: https://indianapi.in/documentation/jobs-api
- Endpoint: `GET https://jobs.indianapi.in/jobs?limit=...`
- Authentication: `X-Api-Key: <key>`
- Configure: `INDIANAPI_API_KEY`
- The published docs say a free subscription/API key is available. They explicitly say that location/title/company/experience/job_type query filters are potential parameters that must be confirmed with the provider. Therefore this connector only requests the documented `limit` parameter, then filters jobs inside InternHunt. The docs do not publish a precise free request quota.
### Providers not included

Jooble is left out of the automatic configuration because its current API documentation says each country needs its own key, but the current documentation available here does not confirm an India registration endpoint/key. Remotive is also omitted: its public API is for remote jobs, its terms require direct attribution/linking and have restrictions on republishing jobs to third-party job sites.

## 2. Configure backend/.env

Copy the example file:

```powershell
cd backend
Copy-Item .env.example .env
```

Open `backend/.env` and paste only the credentials you have. Leave the others blank. Example:

```env
FRONTEND_ORIGINS=http://127.0.0.1:5500,http://localhost:5500
JOBVETTA_API_KEY=your_jobvetta_key
INDIANAPI_API_KEY=your_indianapi_key
ADZUNA_APP_ID=your_adzuna_app_id
ADZUNA_APP_KEY=your_adzuna_app_key
GREENHOUSE_BOARDS=
LEVER_SITES=
JOB_CACHE_TTL_SECONDS=1800
```

Do not put credentials in frontend JavaScript and do not upload `.env` to GitHub.

## 3. Start the backend on Windows

From the project root:

```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Keep this terminal open. Test:

- Health check: http://127.0.0.1:8000/
- API documentation: http://127.0.0.1:8000/docs
- Provider configuration (no secrets shown): http://127.0.0.1:8000/api/providers

## 4. Start the frontend

Open `frontend/index.html` or `frontend/find.html` with VS Code Live Server. The usual address is `http://127.0.0.1:5500`. Do not open the page using `file://`.

- Homepage: http://127.0.0.1:5500/index.html
- Job search: http://127.0.0.1:5500/find.html
- Resume checker: http://127.0.0.1:5500/check.html

## 5. Test job sources

Check configured sources first:

```text
http://127.0.0.1:8000/api/providers
```

Search across all connected sources:

```text
http://127.0.0.1:8000/api/jobs?q=python&location=Bengaluru&type=all
```

Search one provider only:

```text
http://127.0.0.1:8000/api/jobs?q=python&location=Bengaluru&source=adzuna
```

Supported `source` values: `all`, `jobvetta`, `indianapi`, `adzuna`, `greenhouse`, `lever`.

The backend queries configured providers concurrently, normalizes results to one InternHunt job shape, filters to India and removes obvious duplicates. If one provider fails, results from other providers can still be returned and its status appears in the response. Results are cached in memory for the configured duration (default 30 minutes).

If no external provider is configured, the API returns the clearly labelled local demo jobs. Selecting a specific provider that is not configured returns no fake listings and reports that the provider needs credentials/configuration.

## 6. Resume matching against connected job APIs

The resume endpoint now uses the same `search_all_providers()` function as `/api/jobs`:

```http
POST http://127.0.0.1:8000/api/resumes/analyze
Content-Type: multipart/form-data

file=<resume.pdf>
source=all
location=Bengaluru
selected_type=internship
```

`source` can be `all`, `jobvetta`, `indianapi`, `adzuna`, `greenhouse` or `lever`. `location` is optional. `selected_type` can be `all`, `internship` or `full-time`. The frontend adds these fields automatically from the Check Resume form.

The backend fetches normalized provider listings (using the existing provider cache), extracts skills from the resume and job title/description/skill fields, then ranks the jobs using TF-IDF cosine similarity. Results include the provider name, application URL, matched skills and missing skills where those skills are in the starter vocabulary. If no API provider is configured at all, the endpoint uses clearly labelled demo jobs. If a provider is configured but returns no jobs or errors, it returns no matches and reports provider status instead of presenting demo jobs as live.

The similarity score is a text-ranking signal, not a probability of being hired. TF-IDF is a lightweight baseline; it is not a full semantic understanding model. Providers may return brief descriptions or omit skill fields, which affects ranking quality.

## 7. Important data and API limitations

- The free usage limits are controlled by each provider and can change. Indian API's documentation does not state a numeric free quota. Adzuna's no-cost key is specifically for evaluation and has additional licensing/attribution terms for published adverts.
- Internship filtering is based on each provider's available employment-type/title/description fields. Some providers do not expose a dedicated internship filter, so result counts can be lower.
- Greenhouse and Lever are employer-specific feeds. You must supply board tokens/site slugs for companies you want to include; these do not search every company automatically.
- The India-only check uses provider market/country data and a location allow-list for ATS feeds. Unknown location labels may be excluded; inspect results before public release.
- Some feeds provide short descriptions or only a link. Always open the original employer/provider page to confirm the vacancy is active and review eligibility.
- `find.html` job search and `check.html` resume analysis now use the same provider data and normalized job records. When at least one provider is configured, resume analysis fetches a cached batch of current listings from the selected source(s), then ranks those jobs against the uploaded resume. It does not silently fall back to demo records if a configured provider returns no results.
- Resume analysis accepts optional `source`, `location` and `selected_type` form fields. The Check Resume page exposes these filters so a user can compare against all connected sources, one provider, a city, internships, full-time jobs or both.
- When no external provider is configured at all, resume analysis explicitly uses the local demo dataset so the feature can still be tested before API keys are available.
- No PostgreSQL persistence, user accounts, permanent resume storage or scheduled ingestion worker is included yet.

## 8. Next production steps

1. Store imported jobs in PostgreSQL and deduplicate them across provider IDs/URLs.
2. Run scheduled syncs rather than calling external APIs on every user search.
3. Add authentication and private resume storage before retaining uploads.
4. Add stale-job verification, provider attribution and source-specific terms checks.
5. Restrict CORS to the deployed domain and use HTTPS.

## 9. Merge with your original project

This ZIP contains the provided `index.html`, `check.html` and `find.html` pages plus new JavaScript and backend files. Copy your original `assets/` folder and `about.html` into `frontend/` if they are not present.
