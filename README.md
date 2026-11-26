# InternHunt
##This is a interactive website which gives a matching score comparing the resume and the information in job listing. Job seekers can find jobs and their skill ##gap while applying to jobs.

### Indian API Jobs API

- Docs: https://indianapi.in/documentation/jobs-api
- Endpoint: `GET https://jobs.indianapi.in/jobs?limit=...`
- Authentication: `X-Api-Key: <key>`
- Configure: `INDIANAPI_API_KEY`


## 2. Configure backend/.env

Copy the example file:

```powershell
cd backend
Copy-Item .env.example .env
```

Open `backend/.env` and paste only the credentials you have. Leave the others blank. Example:

```env
FRONTEND_ORIGINS=http://127.0.0.1:5500,http://localhost:5500
INDIANAPI_API_KEY=your_indianapi_key
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
