const JOBS_API_URL = "http://127.0.0.1:8000/api/jobs";

const searchForm = document.getElementById("jobSearchForm");
const jobsGrid = document.getElementById("jobsGrid");
const resultCount = document.getElementById("resultCount");
const searchStatus = document.getElementById("searchStatus");
const feedNotice = document.getElementById("feedNotice");

function createBadge(text) {
  const badge = document.createElement("span");
  badge.className = "job-badge";
  badge.textContent = text;
  return badge;
}

function renderJob(job) {
  const card = document.createElement("article");
  card.className = "job-card";

  const title = document.createElement("h2");
  title.textContent = job.title || "Untitled role";

  const company = document.createElement("p");
  company.className = "job-company";
  company.textContent = [job.company, job.location].filter(Boolean).join(" · ");

  const badges = document.createElement("div");
  badges.className = "job-badges";
  [job.employment_type, job.work_model].filter(Boolean).forEach((item) => badges.appendChild(createBadge(item)));

  const description = document.createElement("p");
  description.className = "job-description";
  const text = job.description || "No description provided.";
  description.textContent = text.length > 210 ? `${text.slice(0, 207)}...` : text;

  const skills = document.createElement("div");
  skills.className = "job-skills";
  (job.skills || []).forEach((skill) => {
    const chip = document.createElement("span");
    chip.className = "job-skill";
    chip.textContent = skill;
    skills.appendChild(chip);
  });

  const footer = document.createElement("div");
  footer.className = "job-card-footer";
  if (job.is_demo) {
    const source = document.createElement("small");
    source.textContent = "Sample listing";
    footer.appendChild(source);
  } else if (job.source === "Adzuna") {
    // Adzuna's API terms require a visible Adzuna attribution link on each advert.
    const credit = document.createElement("a");
    credit.href = "https://www.adzuna.in/";
    credit.target = "_blank";
    credit.rel = "noopener noreferrer";
    credit.textContent = "Adzuna";
    credit.title = "Jobs data provided by Adzuna";
    credit.style.display = "inline-flex";
    credit.style.alignItems = "center";
    credit.style.justifyContent = "center";
    credit.style.minWidth = "116px";
    credit.style.minHeight = "23px";
    credit.style.padding = "3px 8px";
    credit.style.border = "1px solid var(--border)";
    credit.style.borderRadius = "5px";
    credit.style.fontSize = "12px";
    credit.style.fontWeight = "700";
    footer.appendChild(credit);
  } else {
    const source = document.createElement("small");
    source.textContent = `Source: ${job.source || "Job provider"}`;
    footer.appendChild(source);
  }

  if (job.apply_url) {
    const apply = document.createElement("a");
    apply.className = "btn";
    apply.href = job.apply_url;
    apply.target = "_blank";
    apply.rel = "noopener noreferrer";
    apply.textContent = "View & apply →";
    footer.appendChild(apply);
  } else {
    const placeholder = document.createElement("small");
    placeholder.textContent = "No live apply link";
    footer.appendChild(placeholder);
  }

  card.append(title, company, badges, description, skills, footer);
  return card;
}

async function loadJobs(formValues = new FormData(searchForm)) {
  const params = new URLSearchParams();
  for (const key of ["q", "location", "type", "source"]) {
    const value = String(formValues.get(key) || "").trim();
    if (value) params.set(key, value);
  }

  searchStatus.textContent = "Searching...";
  resultCount.textContent = "";
  jobsGrid.replaceChildren();

  try {
    const response = await fetch(`${JOBS_API_URL}?${params.toString()}`);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);

    const jobs = data.jobs || [];
    resultCount.textContent = `${data.count ?? jobs.length} opportunities found`;
    searchStatus.textContent = "";
    const providerSummary = (data.provider_status || [])
      .map((item) => `${item.provider}: ${item.status === "ok" ? `${item.count} found` : item.status === "not_configured" ? "not configured" : "error"}`)
      .join(" · ");
    feedNotice.textContent = [data.notice, providerSummary ? `Provider status: ${providerSummary}` : ""]
      .filter(Boolean).join(" ");

    if (!jobs.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "No matching opportunities in this dataset. Try a different keyword or city.";
      jobsGrid.appendChild(empty);
      return;
    }

    jobs.forEach((job) => jobsGrid.appendChild(renderJob(job)));
  } catch (error) {
    searchStatus.textContent = error.message || "Could not connect to the job service.";
    resultCount.textContent = "";
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "Start the FastAPI backend, then refresh this page. The API should be available at 127.0.0.1:8000.";
    jobsGrid.appendChild(empty);
  }
}

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  loadJobs();
});

loadJobs();
