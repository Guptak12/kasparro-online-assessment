from __future__ import annotations

import re

from .models import (
    CandidateProfile,
    Evidence,
    GitHubAssessment,
    ProjectAssessment,
    ScoreBreakdown,
    ScoreCalculation,
)
from .policy import DEFAULT_SCORING_POLICY, ScoringPolicy


def _unique_text(items: list[Evidence]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.text.lower()
        if key not in seen:
            result.append(item.text)
            seen.add(key)
    return result


def _category_points(
    profile: CandidateProfile,
    category: str,
    maximum: int,
    policy: ScoringPolicy,
) -> tuple[int, list[str]]:
    relevant = profile.evidence_by_category.get(category, [])
    if not relevant:
        return 0, []
    multiplier = max(policy.evidence_multiplier[item.strength] for item in relevant)
    return round(maximum * multiplier), _unique_text(relevant)


def calculate_score(
    profile: CandidateProfile,
    assessment: ProjectAssessment,
    github: GitHubAssessment,
    policy: ScoringPolicy = DEFAULT_SCORING_POLICY,
) -> ScoreCalculation:
    policy.validate()
    depth_multiplier = policy.depth_multiplier
    ai_score = round(
        sum(
            depth_multiplier[getattr(assessment, attribute)] * maximum
            for attribute, maximum in policy.ai_components
        )
    )

    python_backend = 0
    python_evidence: list[str] = []
    for category, maximum in policy.python_components:
        points, evidence = _category_points(profile, category, maximum, policy)
        python_backend += points
        python_evidence.extend(evidence)
    ownership_score = round(
        policy.ownership_max * depth_multiplier[assessment.ownership_depth]
    )
    python_backend = min(
        policy.python_backend_max, python_backend + ownership_score
    )

    cloud_fullstack = 0
    cloud_evidence: list[str] = []
    for category, maximum in policy.cloud_components:
        points, evidence = _category_points(profile, category, maximum, policy)
        cloud_fullstack += points
        cloud_evidence.extend(evidence)
    cloud_fullstack = min(policy.cloud_fullstack_max, cloud_fullstack)

    engineering_evidence: list[str] = []
    engineering_depth = 0
    for category in policy.engineering_categories:
        category_items = profile.evidence_by_category.get(category, [])
        if category_items:
            engineering_depth += 1
            engineering_evidence.extend(_unique_text(category_items))

    thin_penalties = dict(policy.thin_wrapper_penalties)
    tutorial_penalties = dict(policy.tutorial_penalties)
    penalties: list[tuple[int, str]] = []
    wrapper_points = thin_penalties[assessment.thin_wrapper_severity]
    tutorial_points = tutorial_penalties[assessment.tutorial_severity]
    if wrapper_points:
        penalties.append((wrapper_points, "Thin API-wrapper project evidence."))
    if tutorial_points:
        penalties.append(
            (tutorial_points, "Tutorial-only or minimally original project evidence.")
        )
    penalty = min(
        policy.project_quality_penalty_cap,
        sum(points for points, _ in penalties),
    )
    total = max(
        0,
        min(
            100,
            ai_score
            + python_backend
            + cloud_fullstack
            + github.final_points
            + engineering_depth
            - penalty,
        ),
    )
    breakdown = ScoreBreakdown(
        ai_project_depth=ai_score,
        python_backend=python_backend,
        cloud_fullstack=cloud_fullstack,
        github=github.final_points,
        engineering_depth=engineering_depth,
        project_quality_penalty=penalty,
        penalty_reasons=[reason for _, reason in penalties],
        total_score=total,
    )
    github_evidence = [github.summary, *github.relevant_repositories]
    return ScoreCalculation(
        breakdown=breakdown,
        evidence={
            "ai_project_depth": list(assessment.evidence),
            "python_backend": list(dict.fromkeys(python_evidence)),
            "cloud_fullstack": list(dict.fromkeys(cloud_evidence)),
            "github": list(dict.fromkeys(item for item in github_evidence if item)),
            "engineering_depth": list(dict.fromkeys(engineering_evidence)),
            "project_quality_penalty": [reason for _, reason in penalties],
        },
        policy_version=policy.version,
    )


def ranking_key(name: str, score: ScoreBreakdown) -> tuple[int, int, int, str]:
    return (
        -score.total_score,
        -score.ai_project_depth,
        -score.python_backend,
        re.sub(r"\s+", " ", name.lower()),
    )
