from __future__ import annotations

import re

from .models import CandidateProfile, EvidenceStrength, GitHubAssessment, ProjectAssessment, ScoreBreakdown


DEPTH_POINTS = {"none": 0.0, "basic": 0.25, "applied": 0.65, "advanced": 1.0}
STRENGTH_POINTS = {
    EvidenceStrength.INCIDENTAL: 0.0,
    EvidenceStrength.SKILL: 0.45,
    EvidenceStrength.APPLIED: 0.75,
    EvidenceStrength.ADVANCED: 1.0,
}


def _category_points(profile: CandidateProfile, terms: tuple[str, ...], maximum: int) -> int:
    relevant = [
        evidence
        for evidence in profile.engineering_evidence + profile.python_evidence
        if any(term in evidence.text.lower() for term in terms)
    ]
    if not relevant:
        return 0
    multiplier = max(STRENGTH_POINTS[item.strength] for item in relevant)
    return round(maximum * multiplier)


def calculate_score(
    profile: CandidateProfile,
    assessment: ProjectAssessment,
    github: GitHubAssessment,
) -> ScoreBreakdown:
    ai_parts = (
        (assessment.project_depth, 8),
        (assessment.retrieval_depth, 8),
        (assessment.agent_depth, 8),
        (assessment.data_workflow_depth, 6),
        (assessment.evaluation_depth, 5),
        (assessment.ownership_depth, 5),
    )
    ai_score = round(sum(DEPTH_POINTS[depth] * cap for depth, cap in ai_parts))

    python_score = _category_points(profile, ("python", "django", "flask", "fastapi"), 10)
    backend_score = _category_points(profile, ("api", "backend", "django", "flask", "fastapi"), 8)
    database_score = _category_points(profile, ("sql", "postgres", "mysql", "mongo", "redis", "database"), 5)
    async_score = _category_points(profile, ("async", "celery", "kafka", "rabbit", "queue"), 4)
    ownership_score = round(3 * DEPTH_POINTS[assessment.ownership_depth])
    python_backend = min(30, python_score + backend_score + database_score + async_score + ownership_score)

    cloud_fullstack = sum(
        (
            _category_points(profile, ("aws", "gcp", "azure", "cloud"), 5),
            _category_points(profile, ("docker", "kubernetes", "container"), 4),
            _category_points(profile, ("ci/cd", "github actions", "jenkins", "deployment"), 3),
            _category_points(profile, ("react", "next.js", "typescript", "frontend"), 3),
        )
    )
    engineering_checks = (
        ("test", "pytest"),
        ("monitor", "logging", "observability"),
        ("security", "authentication", "authorization"),
        ("performance", "latency", "scal"),
        ("document", "readme"),
    )
    text = profile.raw_text.lower()
    engineering_depth = sum(any(term in text for term in group) for group in engineering_checks)

    penalties: list[tuple[int, str]] = []
    wrapper_points = {"none": 0, "low": 5, "medium": 10, "high": 15}[assessment.thin_wrapper_severity]
    tutorial_points = {"none": 0, "low": 5, "high": 10}[assessment.tutorial_severity]
    if wrapper_points:
        penalties.append((wrapper_points, "Thin API-wrapper project evidence."))
    if tutorial_points:
        penalties.append((tutorial_points, "Tutorial-only or minimally original project evidence."))
    penalty = min(20, sum(points for points, _ in penalties))
    total = max(0, min(100, ai_score + python_backend + cloud_fullstack + github.final_points + engineering_depth - penalty))
    return ScoreBreakdown(
        ai_project_depth=ai_score,
        python_backend=python_backend,
        cloud_fullstack=cloud_fullstack,
        github=github.final_points,
        engineering_depth=engineering_depth,
        project_quality_penalty=penalty,
        penalty_reasons=[reason for _, reason in penalties],
        total_score=total,
    )


def ranking_key(name: str, score: ScoreBreakdown) -> tuple[int, int, int, str]:
    return (-score.total_score, -score.ai_project_depth, -score.python_backend, re.sub(r"\s+", " ", name.lower()))
