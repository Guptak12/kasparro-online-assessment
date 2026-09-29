from __future__ import annotations

from dataclasses import dataclass

from .models import EvidenceStrength


@dataclass(frozen=True, slots=True)
class ScoringPolicy:
    version: str = "scoring-v2"

    ai_project_max: int = 40
    python_backend_max: int = 30
    cloud_fullstack_max: int = 15
    github_max: int = 10
    engineering_max: int = 5

    ai_components: tuple[tuple[str, int], ...] = (
        ("project_depth", 8),
        ("retrieval_depth", 8),
        ("agent_depth", 8),
        ("data_workflow_depth", 6),
        ("evaluation_depth", 5),
        ("ownership_depth", 5),
    )
    python_components: tuple[tuple[str, int], ...] = (
        ("python", 10),
        ("backend", 8),
        ("database", 5),
        ("async_queues", 4),
    )
    cloud_components: tuple[tuple[str, int], ...] = (
        ("cloud", 5),
        ("containers", 4),
        ("cicd", 3),
        ("frontend", 3),
    )
    engineering_categories: tuple[str, ...] = (
        "testing",
        "observability",
        "security",
        "performance",
        "documentation",
    )

    evidence_multipliers: tuple[tuple[EvidenceStrength, float], ...] = (
        (EvidenceStrength.INCIDENTAL, 0.0),
        (EvidenceStrength.SKILL, 0.45),
        (EvidenceStrength.APPLIED, 0.75),
        (EvidenceStrength.ADVANCED, 1.0),
    )
    depth_multipliers: tuple[tuple[str, float], ...] = (
        ("none", 0.0),
        ("basic", 0.25),
        ("applied", 0.65),
        ("advanced", 1.0),
    )

    ownership_max: int = 3
    thin_wrapper_penalties: tuple[tuple[str, int], ...] = (
        ("none", 0),
        ("low", 5),
        ("medium", 10),
        ("high", 15),
    )
    tutorial_penalties: tuple[tuple[str, int], ...] = (
        ("none", 0),
        ("low", 5),
        ("high", 10),
    )
    project_quality_penalty_cap: int = 20

    def validate(self) -> None:
        positive_total = (
            self.ai_project_max
            + self.python_backend_max
            + self.cloud_fullstack_max
            + self.github_max
            + self.engineering_max
        )
        if positive_total != 100:
            raise ValueError("Positive scoring category maxima must total 100")
        if sum(maximum for _, maximum in self.ai_components) != self.ai_project_max:
            raise ValueError("AI component maxima do not match the AI category maximum")
        if (
            sum(maximum for _, maximum in self.python_components) + self.ownership_max
            != self.python_backend_max
        ):
            raise ValueError("Python component maxima do not match the category maximum")
        if sum(maximum for _, maximum in self.cloud_components) != self.cloud_fullstack_max:
            raise ValueError("Cloud component maxima do not match the category maximum")
        if len(self.engineering_categories) != self.engineering_max:
            raise ValueError("Engineering categories do not match the category maximum")

    @property
    def evidence_multiplier(self) -> dict[EvidenceStrength, float]:
        return dict(self.evidence_multipliers)

    @property
    def depth_multiplier(self) -> dict[str, float]:
        return dict(self.depth_multipliers)


DEFAULT_SCORING_POLICY = ScoringPolicy()
DEFAULT_SCORING_POLICY.validate()
