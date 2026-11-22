from __future__ import annotations

import re
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DEMO_JOBS: list[dict[str, Any]] = [
    {
        "id": "demo-001",
        "title": "Python Developer Intern",
        "company": "Sample employer",
        "location": "Bengaluru, India",
        "employment_type": "Internship",
        "work_model": "Hybrid",
        "description": "Build backend services and REST APIs using Python and FastAPI. Work with SQL databases, Git and testing.",
        "skills": ["Python", "FastAPI", "REST APIs", "SQL", "Git"],
        "apply_url": None,
    },
    {
        "id": "demo-002",
        "title": "Data Analyst Intern",
        "company": "Sample employer",
        "location": "Hyderabad, India",
        "employment_type": "Internship",
        "work_model": "On-site",
        "description": "Analyse datasets, write SQL queries, use Python, Excel and data visualization tools to communicate findings.",
        "skills": ["Python", "SQL", "Excel", "Data Analysis", "Power BI"],
        "apply_url": None,
    },
    {
        "id": "demo-003",
        "title": "Frontend Developer Intern",
        "company": "Sample employer",
        "location": "Remote, India",
        "employment_type": "Internship",
        "work_model": "Remote",
        "description": "Create responsive web interfaces using HTML, CSS, JavaScript and React. Collaborate using Git.",
        "skills": ["HTML", "CSS", "JavaScript", "React", "Git"],
        "apply_url": None,
    },
    {
        "id": "demo-004",
        "title": "Junior Machine Learning Engineer",
        "company": "Sample employer",
        "location": "Pune, India",
        "employment_type": "Full-time",
        "work_model": "On-site",
        "description": "Develop machine learning workflows using Python, scikit-learn, pandas, statistics and model evaluation techniques.",
        "skills": ["Python", "Machine Learning", "scikit-learn", "Statistics", "Pandas"],
        "apply_url": None,
    },
    {
            "id": "demo-005",
            "title": "Devops Engineer",
            "company": "salesforce",
            "location": "Bangalore, India",
            "employment_type": "Full-time",
            "work_model": "On-site",
            "description": "Develop and maintain CI/CD pipelines, manage cloud infrastructure, and ensure system reliability using tools like Docker, AWS, Azure, and Linux.",
            "skills": ["Python", "Machine Learning", "scikit-learn", "Statistics", "Pandas","git","Docker","AWS","Azure","Linux","SQL","PostgreSQL","MySQL","MongoDB"],
            "apply_url": None,
        },
]

# A transparent starter vocabulary. Expand it as new job categories are added.
SKILL_VOCABULARY = [
    "Python", "C++", "Java", "JavaScript", "TypeScript", "HTML", "CSS",
    "React", "Next.js", "Node.js", "FastAPI", "Django", "Flask", "REST APIs",
    "SQL", "PostgreSQL", "MySQL", "MongoDB", "Git", "Linux", "Docker",
    "AWS", "Azure", "Machine Learning", "Deep Learning", "TensorFlow",
    "PyTorch", "scikit-learn", "Pandas", "NumPy", "Data Analysis",
    "Statistics", "Excel", "Power BI", "Tableau", "Communication",
    "C", "C#", ".NET", "Spring Boot", "Figma", "Kubernetes", "Redis",
    "GraphQL", "Angular", "Vue.js", "PHP", "Ruby", "Go", "Rust",
    "Data Structures", "Algorithms", "Computer Vision", "NLP", "Selenium",
]


def _contains_phrase(text: str, phrase: str) -> bool:
    pattern = r"(?<![a-z0-9])" + re.escape(phrase.lower()) + r"(?![a-z0-9])"
    return re.search(pattern, text.lower()) is not None


def extract_skills(text: str) -> list[str]:
    return [skill for skill in SKILL_VOCABULARY if _contains_phrase(text, skill)]


def _job_text(job: dict[str, Any]) -> str:
    explicit_skills = job.get("skills") or []
    if not isinstance(explicit_skills, list):
        explicit_skills = [str(explicit_skills)]
    return " ".join(
        str(part)
        for part in [
            job.get("title", ""),
            job.get("description", ""),
            job.get("employment_type", ""),
            job.get("experience_level", ""),
            *explicit_skills,
        ]
        if part
    )


def _canonical_skill_set(skills: list[str]) -> dict[str, str]:
    return {skill.strip().casefold(): skill.strip() for skill in skills if skill.strip()}


def match_jobs(
    resume_text: str,
    jobs: list[dict[str, Any]] | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    
    if not resume_text.strip():
        return []

    candidate_jobs = list(DEMO_JOBS if jobs is None else jobs)
    if not candidate_jobs:
        return []

    job_documents = [_job_text(job) for job in candidate_jobs]

    try:
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        matrix = vectorizer.fit_transform([resume_text, *job_documents])
        scores = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
    except ValueError:
        # Empty vocabulary can occur with very short resumes or empty descriptions.
        scores = [0.0] * len(candidate_jobs)

    resume_skill_map = _canonical_skill_set(extract_skills(resume_text))
    results: list[dict[str, Any]] = []

    for job, score in zip(candidate_jobs, scores):
        explicit = job.get("skills") or []
        if not isinstance(explicit, list):
            explicit = [str(explicit)]
        # Also infer skills from the title and description, so providers that do not
        # return a separate skills array can still participate in skill comparison.
        inferred = extract_skills(_job_text(job))
        required_map = _canonical_skill_set([str(skill) for skill in explicit] + inferred)
        matched_keys = sorted(set(required_map) & set(resume_skill_map))
        missing_keys = sorted(set(required_map) - set(resume_skill_map))
        required_count = len(required_map)
        skill_score = (len(matched_keys) / required_count * 100) if required_count else 0.0

        results.append({
            **job,
            "match_score": round(float(score) * 100, 1),
            "text_similarity": round(float(score) * 100, 1),
            "skill_match_score": round(skill_score, 1),
            "matched_skills": [required_map[key] for key in matched_keys],
            "missing_skills": [required_map[key] for key in missing_keys],
            "source": job.get("source") or "External provider",
            "is_demo": bool(job.get("is_demo", False)),
        })

    results.sort(key=lambda item: (item["match_score"], item["skill_match_score"]), reverse=True)
    return results[:max(1, min(limit, 50))]
