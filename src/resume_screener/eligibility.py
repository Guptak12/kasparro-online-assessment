from __future__ import annotations

from .models import CandidateProfile, EligibilityDecision, Evidence, EvidenceStrength


def _qualifying(items: list[Evidence]) -> list[Evidence]:
    return [item for item in items if item.strength != EvidenceStrength.INCIDENTAL]


def _applied_ai(items: list[Evidence]) -> list[Evidence]:
    return [
        item
        for item in items
        if item.strength in {EvidenceStrength.APPLIED, EvidenceStrength.ADVANCED}
    ]


def assess_eligibility(profile: CandidateProfile) -> EligibilityDecision:
    python_evidence = _qualifying(profile.python_evidence)
    ai_evidence = _applied_ai(profile.ai_evidence)
    reasons: list[str] = []
    if not python_evidence:
        reasons.append("No reliable Python evidence was found.")
    if not ai_evidence:
        reasons.append("No applied AI/ML project or implementation evidence was found.")
    return EligibilityDecision(
        eligible=not reasons,
        python_evidence=python_evidence,
        ai_evidence=ai_evidence,
        rejection_reasons=reasons,
    )
