from __future__ import annotations

import re
from collections import defaultdict

from .models import CandidateProfile, Evidence, EvidenceStrength, ParsedResume


EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
GITHUB_RE = re.compile(r"(?i)(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9-]{1,39})(?:/[^\s),;]*)?")
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d ().-]{7,}\d)(?!\w)")
URL_RE = re.compile(r"(?i)\bhttps?://\S+")
HEADING_RE = re.compile(
    r"^(summary|profile|skills?|technical skills?|experience|employment|projects?|education|certifications?)\s*:?.*$",
    re.I,
)

SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "Python": ("python", "django", "flask", "fastapi"),
    "FastAPI": ("fastapi",),
    "Django": ("django",),
    "Flask": ("flask",),
    "REST APIs": ("rest api", "restful", "api development"),
    "SQL": ("sql", "postgres", "mysql", "sqlite"),
    "NoSQL": ("mongodb", "dynamodb", "redis", "nosql"),
    "Async/Queues": ("asyncio", "celery", "kafka", "rabbitmq", "message queue"),
    "Machine Learning": ("machine learning", "scikit-learn", "sklearn", "xgboost"),
    "Deep Learning": ("deep learning", "pytorch", "tensorflow", "keras"),
    "NLP": ("nlp", "natural language processing", "transformer", "bert"),
    "LLMs": ("llm", "large language model", "gemini", "openai", "anthropic"),
    "RAG": ("rag", "retrieval augmented", "vector database", "pinecone", "faiss", "chroma"),
    "Agents": ("agentic", "ai agent", "langgraph", "crewai", "autogen"),
    "Evaluation": ("evaluation", "evals", "benchmark", "precision", "recall", "f1 score"),
    "AWS": ("aws", "lambda", "s3", "ec2"),
    "GCP": ("gcp", "google cloud", "cloud run", "vertex ai"),
    "Azure": ("azure",),
    "Docker": ("docker", "container"),
    "CI/CD": ("ci/cd", "github actions", "jenkins"),
    "Frontend": ("react", "next.js", "typescript", "javascript", "frontend"),
    "Testing": ("pytest", "unit test", "integration test", "test coverage"),
    "Observability": ("logging", "monitoring", "prometheus", "grafana", "opentelemetry"),
}

PYTHON_TERMS = SKILL_ALIASES["Python"]
AI_TERMS = tuple(
    term
    for key in ("Machine Learning", "Deep Learning", "NLP", "LLMs", "RAG", "Agents", "Evaluation")
    for term in SKILL_ALIASES[key]
)
ENGINEERING_TERMS = tuple(
    term
    for key in ("REST APIs", "SQL", "NoSQL", "Async/Queues", "Docker", "CI/CD", "Testing", "Observability")
    for term in SKILL_ALIASES[key]
)
ACTION_RE = re.compile(
    r"\b(built|developed|implemented|designed|deployed|created|trained|fine[- ]?tuned|optimized|integrated|led|owned|scaled|evaluated)\b",
    re.I,
)
METRIC_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|ms|x|users?|requests?|records?|accuracy|f1)\b", re.I)
NEGATION_RE = re.compile(r"\b(no|not|without)\b.{0,18}\b", re.I)
COURSE_RE = re.compile(
    r"\b(course|coursework|class|tutorial|currently learning|familiar with|exposure to)\b",
    re.I,
)


def _contains(line: str, terms: tuple[str, ...]) -> list[str]:
    lowered = line.lower()
    return sorted({term for term in terms if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", lowered)})


def _strength(line: str, section: str) -> EvidenceStrength:
    if NEGATION_RE.search(line) or COURSE_RE.search(line):
        return EvidenceStrength.INCIDENTAL
    if ACTION_RE.search(line):
        if METRIC_RE.search(line) or section in {"experience", "employment"}:
            return EvidenceStrength.ADVANCED
        return EvidenceStrength.APPLIED
    if section in {"projects", "project", "experience", "employment"}:
        return EvidenceStrength.APPLIED
    return EvidenceStrength.SKILL


def _candidate_name(lines: list[str], source_file: str) -> str:
    for line in lines[:8]:
        candidate = line.strip(" |-•\t")
        if not candidate or EMAIL_RE.search(candidate) or GITHUB_RE.search(candidate) or PHONE_RE.search(candidate):
            continue
        if HEADING_RE.match(candidate) or len(candidate) > 80 or len(candidate.split()) > 6:
            continue
        if any(char.isdigit() for char in candidate):
            continue
        return candidate
    return source_file.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip()


def extract_profile(parsed: ParsedResume) -> CandidateProfile:
    lines = [line.strip() for line in parsed.raw_text.splitlines() if line.strip()]
    email_match = EMAIL_RE.search(parsed.raw_text)
    github_match = GITHUB_RE.search(parsed.raw_text)
    github_username = github_match.group(1) if github_match else None
    github_url = f"https://github.com/{github_username}" if github_username else None

    skill_hits: set[str] = set()
    lowered = parsed.raw_text.lower()
    for canonical, aliases in SKILL_ALIASES.items():
        if any(re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", lowered) for alias in aliases):
            skill_hits.add(canonical)

    evidence: dict[str, list[Evidence]] = defaultdict(list)
    section = "profile"
    for line in lines:
        heading = HEADING_RE.match(line)
        if heading:
            section = heading.group(1).lower().rstrip("s")
            continue
        for category, terms in (
            ("python", PYTHON_TERMS),
            ("ai", AI_TERMS),
            ("engineering", ENGINEERING_TERMS),
        ):
            matched = _contains(line, terms)
            if matched and len(evidence[category]) < 12:
                evidence[category].append(
                    Evidence(
                        text=line[:300],
                        section=section,
                        strength=_strength(line, section),
                        terms=matched,
                    )
                )

    return CandidateProfile(
        candidate_id=parsed.file.file_id,
        source_file=parsed.file.source_file,
        candidate_name=_candidate_name(lines, parsed.file.source_file),
        email=email_match.group(0) if email_match else None,
        github_url=github_url,
        github_username=github_username,
        raw_text=parsed.raw_text,
        skills=sorted(skill_hits),
        python_evidence=evidence["python"],
        ai_evidence=evidence["ai"],
        engineering_evidence=evidence["engineering"],
        extraction_warnings=parsed.warnings,
    )


def minimise_for_llm(profile: CandidateProfile, character_limit: int) -> str:
    """Remove direct contact fields and retain only professionally relevant text."""

    text = profile.raw_text
    text = EMAIL_RE.sub("[email removed]", text)
    text = PHONE_RE.sub("[phone removed]", text)
    text = URL_RE.sub("[url removed]", text)
    if profile.candidate_name:
        text = re.sub(re.escape(profile.candidate_name), "[name removed]", text, flags=re.I)
    return text[:character_limit]
