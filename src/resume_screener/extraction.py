from __future__ import annotations

import re
from collections import defaultdict

from .models import CandidateProfile, Evidence, EvidenceStrength, ParsedResume


EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
GITHUB_RE = re.compile(
    r"(?i)(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9-]{1,39})(?:/[^\s),;]*)?"
)
LINKEDIN_RE = re.compile(
    r"(?i)(?:https?://)?(?:www\.)?linkedin\.com/in/([A-Za-z0-9-]+)"
)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d ().-]{7,}\d)(?!\w)")
URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
HEADING_RE = re.compile(
    r"^(professional summary|summary|profile|skills?|technical skills?|experience|"
    r"professional experience|work experience|employment|projects?|education|certifications?|"
    r"education qualification|career aspiration|area of interest|contact|links?|achievements?)\s*:?.*$",
    re.I,
)
INLINE_HEADING_RE = re.compile(
    r"\b(?:professional summary|career aspiration|education qualification|technical skills?|"
    r"work experience|professional experience|area of interest|projects?|education|skills?)\b.*$",
    re.I,
)

SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "Python": ("python", "django", "flask", "fastapi"),
    "FastAPI": ("fastapi",),
    "Django": ("django",),
    "Flask": ("flask",),
    "REST APIs": ("rest api", "restful", "api development", "graphql"),
    "SQL": ("sql", "postgres", "mysql", "sqlite"),
    "NoSQL": ("mongodb", "dynamodb", "redis", "nosql"),
    "Async/Queues": ("asyncio", "celery", "kafka", "rabbitmq", "message queue"),
    "Machine Learning": ("machine learning", "scikit-learn", "sklearn", "xgboost"),
    "Deep Learning": ("deep learning", "pytorch", "tensorflow", "keras", "neural network"),
    "NLP": ("nlp", "natural language processing", "transformer", "bert"),
    "LLMs": ("llm", "large language model", "gemini", "openai", "anthropic"),
    "RAG": (
        "rag",
        "retrieval augmented",
        "vector database",
        "vector search",
        "embedding",
        "pinecone",
        "faiss",
        "chroma",
    ),
    "Agents": (
        "agentic",
        "ai agent",
        "tool calling",
        "langchain",
        "langgraph",
        "llamaindex",
        "google adk",
        "crewai",
        "autogen",
    ),
    "Evaluation": ("evaluation", "evals", "benchmark", "precision", "recall", "f1 score"),
    "AWS": ("aws", "lambda", "s3", "ec2"),
    "GCP": ("gcp", "google cloud", "cloud run", "vertex ai"),
    "Azure": ("azure",),
    "Docker": ("docker", "kubernetes", "container"),
    "CI/CD": ("ci/cd", "github actions", "jenkins", "deployment"),
    "Frontend": ("react", "next.js", "typescript", "javascript", "frontend"),
    "Testing": ("pytest", "unit test", "integration test", "test coverage"),
    "Observability": (
        "logging",
        "monitoring",
        "prometheus",
        "grafana",
        "opentelemetry",
        "observability",
    ),
}

PYTHON_TERMS = SKILL_ALIASES["Python"]
AI_TERMS = tuple(
    term
    for key in ("Machine Learning", "Deep Learning", "NLP", "LLMs", "RAG", "Agents")
    for term in SKILL_ALIASES[key]
) + ("computer vision", "classifier", "model training", "model inference")

CATEGORY_TERMS: dict[str, tuple[str, ...]] = {
    "python": PYTHON_TERMS,
    "backend": ("backend", "rest api", "restful", "api development", "fastapi", "django", "flask", "graphql"),
    "database": ("sql", "postgres", "mysql", "sqlite", "mongodb", "dynamodb", "redis", "nosql", "database"),
    "async_queues": ("asyncio", "celery", "kafka", "rabbitmq", "message queue", "background worker"),
    "ai": AI_TERMS,
    "cloud": ("aws", "gcp", "google cloud", "azure", "cloud run", "vertex ai", "lambda", "ec2", "s3"),
    "containers": ("docker", "kubernetes", "container"),
    "cicd": ("ci/cd", "github actions", "jenkins", "deployment", "deployed"),
    "frontend": ("react", "next.js", "typescript", "javascript", "frontend"),
    "testing": ("pytest", "unit test", "integration test", "test coverage", "testing"),
    "observability": ("logging", "monitoring", "prometheus", "grafana", "opentelemetry", "observability"),
    "security": ("security", "authentication", "authorization", "oauth", "rbac"),
    "performance": ("performance", "latency", "scalability", "scaled", "optimization", "optimized"),
    "documentation": ("documentation", "documented", "readme"),
}

ENGINEERING_CATEGORIES = (
    "backend",
    "database",
    "async_queues",
    "containers",
    "cicd",
    "testing",
    "observability",
    "security",
    "performance",
    "documentation",
)
ACTION_TERMS = (
    "built",
    "developed",
    "implemented",
    "designed",
    "deployed",
    "created",
    "trained",
    "fine-tuned",
    "finetuned",
    "optimized",
    "integrated",
    "led",
    "owned",
    "scaled",
    "evaluated",
    "architected",
)
ACTION_RE = re.compile(rf"\b({'|'.join(re.escape(term) for term in ACTION_TERMS)})\b", re.I)
METRIC_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:%|ms|x|users?|requests?|records?|accuracy|f1)\b",
    re.I,
)
NEGATION_RE = re.compile(r"\b(no|not|without)\b", re.I)
COURSE_RE = re.compile(
    r"\b(course|coursework|class|tutorial|currently learning|familiar with|exposure to)\b",
    re.I,
)

NAME_STOP_WORDS = {
    "summary",
    "profile",
    "skills",
    "github",
    "linkedin",
    "leetcode",
    "education",
    "experience",
    "automated",
    "deterministic",
    "percentage",
    "developer",
    "engineer",
    "engineering",
    "resume",
    "curriculum",
    "vitae",
    "solutions",
    "private",
    "limited",
    "pvt",
    "ltd",
}
LOCATION_TERMS = (
    "Bangalore",
    "Bengaluru",
    "Hyderabad",
    "Dehradun",
    "Ghaziabad",
    "Delhi",
    "Mumbai",
    "Pune",
    "Chennai",
    "Kolkata",
    "India",
)


def _is_character_spaced(text: str) -> bool:
    tokens = [re.sub(r"[^A-Za-z]", "", token) for token in text.split()]
    tokens = [token for token in tokens if token]
    return len(tokens) >= 5 and sum(len(token) == 1 for token in tokens) / len(tokens) >= 0.6


def _matching_text(text: str) -> str:
    lowered = text.lower()
    if _is_character_spaced(text):
        return re.sub(r"\s+", "", lowered)
    return lowered


def _contains(line: str, terms: tuple[str, ...]) -> list[str]:
    lowered = line.lower()
    compacted = _matching_text(line)
    spaced = compacted != lowered
    matched: set[str] = set()
    for term in terms:
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", lowered):
            matched.add(term)
        elif spaced and len(re.sub(r"\W", "", term)) >= 5:
            if re.sub(r"\W", "", term.lower()) in re.sub(r"\W", "", compacted):
                matched.add(term)
    return sorted(matched)


def _strength(line: str, section: str) -> EvidenceStrength:
    lowered = line.lower()
    compacted = _matching_text(line)
    if NEGATION_RE.search(lowered) or COURSE_RE.search(lowered):
        return EvidenceStrength.INCIDENTAL
    action = bool(ACTION_RE.search(lowered))
    if compacted != lowered:
        action = action or any(term.replace("-", "") in compacted for term in ACTION_TERMS)
    if action:
        if METRIC_RE.search(lowered) or section in {"experience", "employment"}:
            return EvidenceStrength.ADVANCED
        return EvidenceStrength.APPLIED
    if section in {"project", "experience", "employment"}:
        return EvidenceStrength.APPLIED
    return EvidenceStrength.SKILL


def _normalise_name_candidate(line: str) -> str:
    candidate = re.sub(r"([a-z])([A-Z])", r"\1 \2", line.strip(" |-•\t"))
    candidate = re.sub(r"(?i)^name\s*:\s*", "", candidate)
    cut_positions = []
    for pattern in (EMAIL_RE, PHONE_RE, URL_RE):
        match = pattern.search(candidate)
        if match:
            cut_positions.append(match.start())
    separator = re.search(r"\s(?:\||—|–|•)\s", candidate)
    if separator:
        cut_positions.append(separator.start())
    label = re.search(r"(?i)\b(?:email|mobile|phone|linkedin|github)\s*:", candidate)
    if label:
        cut_positions.append(label.start())
    heading = INLINE_HEADING_RE.search(candidate)
    if heading:
        cut_positions.append(heading.start())
    for location in LOCATION_TERMS:
        match = re.search(rf"(?i)\b{re.escape(location)}\b", candidate)
        if match:
            cut_positions.append(match.start())
    if cut_positions:
        candidate = candidate[: min(cut_positions)]
    candidate = re.sub(r"\s+", " ", candidate).strip(" ,:;|-/")
    return candidate


def _valid_name(candidate: str) -> bool:
    if not candidate or HEADING_RE.match(_matching_text(candidate)):
        return False
    words = candidate.split()
    if not 2 <= len(words) <= 5 or len(candidate) > 60:
        return False
    if any(word.lower().strip(".:") in NAME_STOP_WORDS for word in words):
        return False
    if any(char.isdigit() for char in candidate):
        return False
    if not all(re.fullmatch(r"[A-Za-z][A-Za-z.'-]*", word) for word in words):
        return False
    return True


def _metadata_name(parsed: ParsedResume) -> str | None:
    ignored = {"canva", "microsoft", "pypdf", "resume", "curriculum vitae"}
    for key in ("Author", "Title"):
        value = parsed.metadata.get(key, "").strip()
        value = re.sub(r"(?i)[_-]?resume.*$", "", value).replace("_", " ").strip()
        candidate = _normalise_name_candidate(value)
        if candidate.lower() not in ignored and _valid_name(candidate):
            return candidate.title() if candidate.islower() else candidate
    return None


def _linkedin_name(text: str) -> str | None:
    match = LINKEDIN_RE.search(text)
    if not match:
        return None
    parts = [re.sub(r"\d+$", "", part) for part in match.group(1).split("-")]
    parts = [part for part in parts if part and not any(ch.isdigit() for ch in part)]
    candidate = " ".join(parts[:4]).title()
    return candidate if _valid_name(candidate) else None


def _email_name(email: str | None) -> str | None:
    if not email:
        return None
    local = email.split("@", 1)[0]
    if not re.search(r"[._-]", local):
        return None
    candidate = re.sub(r"\d+", "", local)
    candidate = re.sub(r"[._-]+", " ", candidate).strip().title()
    return candidate if _valid_name(candidate) else None


def _candidate_name(
    parsed: ParsedResume, lines: list[str], email: str | None
) -> tuple[str, str, str]:
    for line in lines[:15]:
        if HEADING_RE.match(_matching_text(line)):
            break
        if _is_character_spaced(line):
            continue
        candidate = _normalise_name_candidate(line)
        if _valid_name(candidate):
            return candidate, "resume_header", "high"
    metadata = _metadata_name(parsed)
    if metadata:
        return metadata, "pdf_metadata", "medium"
    linkedin = _linkedin_name(parsed.raw_text)
    if linkedin:
        return linkedin, "linkedin", "medium"
    email_name = _email_name(email)
    if email_name:
        return email_name, "email", "low"
    fallback = parsed.file.source_file.rsplit(".", 1)[0].replace("_", " ").replace("-", " ")
    return fallback.strip(), "filename", "low"


def _deduplicate_evidence(items: list[Evidence]) -> list[Evidence]:
    unique: list[Evidence] = []
    seen: set[tuple[str, str | None]] = set()
    for item in items:
        key = (item.text.lower(), item.section)
        if key not in seen:
            unique.append(item)
            seen.add(key)
    return unique


def extract_profile(parsed: ParsedResume) -> CandidateProfile:
    lines = [line.strip() for line in parsed.raw_text.splitlines() if line.strip()]
    email_match = EMAIL_RE.search(parsed.raw_text)
    email = email_match.group(0) if email_match else None
    github_match = GITHUB_RE.search(parsed.raw_text)
    github_username = github_match.group(1) if github_match else None
    github_url = f"https://github.com/{github_username}" if github_username else None
    candidate_name, name_source, name_confidence = _candidate_name(parsed, lines, email)

    skill_hits: set[str] = set()
    for canonical, aliases in SKILL_ALIASES.items():
        if any(_contains(line, aliases) for line in lines):
            skill_hits.add(canonical)

    evidence: dict[str, list[Evidence]] = defaultdict(list)
    section = "profile"
    for line in lines:
        heading_text = _matching_text(line)
        heading = HEADING_RE.match(heading_text)
        if heading:
            section = heading.group(1).lower().replace("professional ", "").replace("work ", "")
            section = section.rstrip("s")
            continue
        for category, terms in CATEGORY_TERMS.items():
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

    category_evidence = {
        category: _deduplicate_evidence(items) for category, items in evidence.items()
    }
    engineering = _deduplicate_evidence(
        [item for category in ENGINEERING_CATEGORIES for item in category_evidence.get(category, [])]
    )
    return CandidateProfile(
        candidate_id=parsed.file.file_id,
        source_file=parsed.file.source_file,
        candidate_name=candidate_name,
        name_source=name_source,
        name_confidence=name_confidence,
        email=email,
        github_url=github_url,
        github_username=github_username,
        raw_text=parsed.raw_text,
        skills=sorted(skill_hits),
        python_evidence=category_evidence.get("python", []),
        ai_evidence=category_evidence.get("ai", []),
        engineering_evidence=engineering,
        evidence_by_category=category_evidence,
        extraction_warnings=parsed.warnings,
    )


def minimise_for_llm(profile: CandidateProfile, character_limit: int) -> str:
    """Remove direct contact fields and retain only professionally relevant text."""

    text = EMAIL_RE.sub("[email removed]", profile.raw_text)
    text = PHONE_RE.sub("[phone removed]", text)
    text = URL_RE.sub("[url removed]", text)
    if profile.candidate_name:
        text = re.sub(re.escape(profile.candidate_name), "[name removed]", text, flags=re.I)
    return text[:character_limit]
