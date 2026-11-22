const API_BASE_URL = "http://127.0.0.1:8000";
const MAX_FILE_BYTES = 5 * 1024 * 1024;

const form = document.getElementById("resumeForm");
const fileInput = document.getElementById("resumeFile");
const dropZone = document.getElementById("dropZone");
const fileInfo = document.getElementById("fileInfo");
const fileName = document.getElementById("fileName");
const fileSize = document.getElementById("fileSize");
const analyzeButton = document.getElementById("analyzeButton");
const removeFileButton = document.getElementById("removeFileButton");
const uploadStatus = document.getElementById("uploadStatus");
const analysisResults = document.getElementById("analysisResults");
const analysisSummary = document.getElementById("analysisSummary");
const detectedSkills = document.getElementById("detectedSkills");
const jobMatches = document.getElementById("jobMatches");
const demoNotice = document.getElementById("demoNotice");
const resumeSource = document.getElementById("resumeSource");
const resumeLocation = document.getElementById("resumeLocation");
const resumeType = document.getElementById("resumeType");

let selectedFile = null;

function setStatus(message, kind = "") {
  uploadStatus.textContent = message;
  uploadStatus.className = `status-message ${kind}`.trim();
}

function formatBytes(bytes) {
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function validateFile(file) {
  if (!file) return "Choose a resume first.";

  const extension = file.name.split(".").pop().toLowerCase();
  if (!["pdf", "docx"].includes(extension)) {
    return "Only PDF and DOCX files are supported.";
  }
  if (file.size === 0) return "The selected file is empty.";
  if (file.size > MAX_FILE_BYTES) return "The resume must be 5 MB or smaller.";
  return "";
}

function setSelectedFile(file) {
  const error = validateFile(file);
  if (error) {
    selectedFile = null;
    fileInput.value = "";
    fileInfo.hidden = true;
    analyzeButton.disabled = true;
    removeFileButton.disabled = true;
    setStatus(error, "error");
    return;
  }

  selectedFile = file;
  fileName.textContent = file.name;
  fileSize.textContent = formatBytes(file.size);
  fileInfo.hidden = false;
  analyzeButton.disabled = false;
  removeFileButton.disabled = false;
  setStatus("Resume ready to analyse.");
  analysisResults.hidden = true;
}

fileInput.addEventListener("change", () => {
  setSelectedFile(fileInput.files[0]);
});

removeFileButton.addEventListener("click", () => {
  selectedFile = null;
  fileInput.value = "";
  fileInfo.hidden = true;
  analyzeButton.disabled = true;
  removeFileButton.disabled = true;
  analysisResults.hidden = true;
  setStatus("Resume removed.");
});

["dragenter", "dragover"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("drag-over");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("drag-over");
  });
});

dropZone.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files[0];
  if (!file) return;

  // Keep the input and selectedFile in sync for the form UI.
  try {
    const transfer = new DataTransfer();
    transfer.items.add(file);
    fileInput.files = transfer.files;
  } catch {
    // setSelectedFile still works in browsers without DataTransfer assignment.
  }
  setSelectedFile(file);
});

function addSkillChip(container, skill, className = "") {
  const chip = document.createElement("span");
  chip.className = `skill-chip ${className}`.trim();
  chip.textContent = skill;
  container.appendChild(chip);
}

function renderSkills(skills) {
  detectedSkills.replaceChildren();
  if (!skills || skills.length === 0) {
    const empty = document.createElement("span");
    empty.className = "skill-empty";
    empty.textContent = "No skills from the starter vocabulary were detected. You can expand the skill list in the Python backend.";
    detectedSkills.appendChild(empty);
    return;
  }
  skills.forEach((skill) => addSkillChip(detectedSkills, skill));
}

function renderJobCard(job) {
  const card = document.createElement("article");
  card.className = "job-match-card";

  const top = document.createElement("div");
  top.className = "job-match-top";

  const info = document.createElement("div");
  const title = document.createElement("h3");
  title.textContent = job.title || "Untitled role";
  const meta = document.createElement("p");
  meta.className = "job-meta";
  meta.textContent = [job.company, job.location, job.employment_type, job.work_model]
    .filter(Boolean).join(" · ");
  info.append(title, meta);

  const score = document.createElement("span");
  score.className = "score-pill";
  score.textContent = `${Number(job.match_score || 0).toFixed(1)}% text match`;
  top.append(info, score);
  card.appendChild(top);

  const track = document.createElement("div");
  track.className = "score-track";
  const fill = document.createElement("span");
  fill.className = "score-fill";
  fill.style.width = `${Math.max(0, Math.min(100, Number(job.match_score || 0)))}%`;
  track.appendChild(fill);
  card.appendChild(track);

  const skillColumns = document.createElement("div");
  skillColumns.className = "match-skills";

  const matchedBox = document.createElement("div");
  const matchedHeading = document.createElement("h4");
  matchedHeading.textContent = "Skills found in your resume";
  matchedBox.appendChild(matchedHeading);
  if (job.matched_skills && job.matched_skills.length) {
    job.matched_skills.forEach((skill) => addSkillChip(matchedBox, skill));
  } else {
    const none = document.createElement("p");
    none.className = "skill-empty";
    none.textContent = "No direct skill overlap detected.";
    matchedBox.appendChild(none);
  }

  const missingBox = document.createElement("div");
  const missingHeading = document.createElement("h4");
  missingHeading.textContent = "Other skills this listing mentions";
  missingBox.appendChild(missingHeading);
  if (job.missing_skills && job.missing_skills.length) {
    job.missing_skills.forEach((skill) => addSkillChip(missingBox, skill, "missing"));
  } else {
    const allFound = document.createElement("p");
    allFound.className = "skill-empty";
    allFound.textContent = "All listed skills were detected.";
    missingBox.appendChild(allFound);
  }

  skillColumns.append(matchedBox, missingBox);
  card.appendChild(skillColumns);

  const source = document.createElement("p");
  source.className = "job-meta";
  source.style.marginTop = "14px";
  source.textContent = job.is_demo
    ? "Demo listing · No real application link is available."
    : `Source: ${job.source || "External provider"}`;
  card.appendChild(source);

  if (job.apply_url) {
    const link = document.createElement("a");
    link.className = "btn";
    link.href = job.apply_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "View application →";
    link.style.marginTop = "12px";
    card.appendChild(link);
  }

  return card;
}

function renderResults(data) {
  const matchSource = data.match_source || "current job dataset";
  const jobsConsidered = Number(data.jobs_considered || 0);
  analysisSummary.textContent = `${data.filename} · ${data.extracted_characters} characters extracted · Compared against ${jobsConsidered} jobs from ${matchSource}.`;
  renderSkills(data.skills || []);
  jobMatches.replaceChildren();

  if (!data.matches || data.matches.length === 0) {
    const empty = document.createElement("p");
    empty.className = "skill-empty";
    empty.textContent = "No job matches were returned. Try a resume with selectable text.";
    jobMatches.appendChild(empty);
  } else {
    data.matches.forEach((job) => jobMatches.appendChild(renderJobCard(job)));
  }

  const providerSummary = (data.provider_status || [])
    .map((item) => `${item.provider}: ${item.status === "ok" ? `${item.count} found` : item.status === "not_configured" ? "not configured" : "error"}`)
    .join(" · ");
  demoNotice.textContent = [data.notice, providerSummary ? `Provider status: ${providerSummary}` : ""]
    .filter(Boolean).join(" ");
  analysisResults.hidden = false;
  analysisResults.scrollIntoView({ behavior: "smooth", block: "start" });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const validationError = validateFile(selectedFile);
  if (validationError) {
    setStatus(validationError, "error");
    return;
  }

  const formData = new FormData();
  formData.append("file", selectedFile, selectedFile.name);
  formData.append("source", resumeSource?.value || "all");
  formData.append("location", resumeLocation?.value.trim() || "");
  formData.append("selected_type", resumeType?.value || "all");

  analyzeButton.disabled = true;
  removeFileButton.disabled = true;
  analyzeButton.textContent = "Analysing...";
  setStatus("Uploading and analysing your resume. This may take a moment.");

  try {
    const response = await fetch(`${API_BASE_URL}/api/resumes/analyze`, {
      method: "POST",
      body: formData,
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || `Request failed (${response.status}). Is the Python backend running?`);
    }

    renderResults(data);
    setStatus("Analysis complete.", "success");
  } catch (error) {
    setStatus(error.message || "Could not connect to the backend.", "error");
  } finally {
    analyzeButton.disabled = !selectedFile;
    removeFileButton.disabled = !selectedFile;
    analyzeButton.textContent = "Analyse resume →";
  }
});
