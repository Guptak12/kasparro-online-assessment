from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CandidateStatus(StrEnum):
    ELIGIBLE = "eligible"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    FAILED = "failed"


class EvidenceStrength(StrEnum):
    INCIDENTAL = "incidental"
    SKILL = "skill"
    APPLIED = "applied"
    ADVANCED = "advanced"


class IntegrationStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limited"
    FAILED = "failed"


Depth = Literal["none", "basic", "applied", "advanced"]


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=300)
    section: str | None = None
    page: int | None = Field(default=None, ge=1)
    strength: EvidenceStrength = EvidenceStrength.SKILL
    terms: list[str] = Field(default_factory=list)


class ResumeFile(BaseModel):
    file_id: str
    path: Path = Field(exclude=True)
    source_file: str
    extension: str
    sha256: str
    size_bytes: int = Field(ge=0)


class ParsedResume(BaseModel):
    file: ResumeFile
    raw_text: str
    pages: list[str] = Field(default_factory=list)
    parser_name: str
    metadata: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    candidate_id: str
    source_file: str
    candidate_name: str
    name_source: Literal["resume_header", "pdf_metadata", "linkedin", "email", "filename"] = "filename"
    name_confidence: Literal["high", "medium", "low"] = "low"
    email: str | None = None
    github_url: str | None = None
    github_username: str | None = None
    raw_text: str = Field(exclude=True)
    skills: list[str] = Field(default_factory=list)
    python_evidence: list[Evidence] = Field(default_factory=list)
    ai_evidence: list[Evidence] = Field(default_factory=list)
    engineering_evidence: list[Evidence] = Field(default_factory=list)
    evidence_by_category: dict[str, list[Evidence]] = Field(default_factory=dict)
    extraction_warnings: list[str] = Field(default_factory=list)


class EligibilityDecision(BaseModel):
    eligible: bool
    python_evidence: list[Evidence] = Field(default_factory=list)
    ai_evidence: list[Evidence] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)
    method_version: str = "eligibility-v1"


class ProjectAssessment(BaseModel):
    project_depth: Depth = "none"
    retrieval_depth: Depth = "none"
    agent_depth: Depth = "none"
    data_workflow_depth: Depth = "none"
    evaluation_depth: Depth = "none"
    ownership_depth: Depth = "none"
    thin_wrapper_severity: Literal["none", "low", "medium", "high"] = "none"
    tutorial_severity: Literal["none", "low", "high"] = "none"
    project_summary: str = "No reliable project assessment available."
    evidence: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    provider_status: IntegrationStatus = IntegrationStatus.SKIPPED
    method: str = "deterministic_fallback"
    model: str | None = None
    prompt_version: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None


class SecurityFinding(BaseModel):
    rule_id: str
    severity: Literal["warning", "high", "critical"]
    confidence: Literal["low", "medium", "high"]
    repository: str
    file_path: str
    secret_type: str
    fingerprint: str | None = None
    reason: str


class SecurityHygiene(BaseModel):
    status: Literal["checked", "partial", "not_checked"] = "not_checked"
    repositories_checked: int = 0
    penalty: int = Field(default=0, ge=0, le=5)
    findings: list[SecurityFinding] = Field(default_factory=list)
    reason: str | None = None


class GitHubAssessment(BaseModel):
    status: IntegrationStatus = IntegrationStatus.SKIPPED
    username: str | None = None
    activity_points: int = Field(default=0, ge=0, le=5)
    repository_points: int = Field(default=0, ge=0, le=5)
    final_points: int = Field(default=0, ge=0, le=10)
    summary: str = "GitHub enrichment not run."
    relevant_repositories: list[str] = Field(default_factory=list)
    security_hygiene: SecurityHygiene = Field(default_factory=SecurityHygiene)
    error: str | None = None

    @model_validator(mode="after")
    def validate_score(self) -> "GitHubAssessment":
        expected = max(
            0,
            min(10, self.activity_points + self.repository_points)
            - self.security_hygiene.penalty,
        )
        if self.final_points != expected:
            raise ValueError("GitHub final_points does not match its components")
        return self


class ScoreBreakdown(BaseModel):
    ai_project_depth: int = Field(ge=0, le=40)
    python_backend: int = Field(ge=0, le=30)
    cloud_fullstack: int = Field(ge=0, le=15)
    github: int = Field(ge=0, le=10)
    engineering_depth: int = Field(ge=0, le=5)
    project_quality_penalty: int = Field(default=0, ge=0, le=20)
    penalty_reasons: list[str] = Field(default_factory=list)
    total_score: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_total(self) -> "ScoreBreakdown":
        expected = max(
            0,
            min(
                100,
                self.ai_project_depth
                + self.python_backend
                + self.cloud_fullstack
                + self.github
                + self.engineering_depth
                - self.project_quality_penalty,
            ),
        )
        if self.total_score != expected:
            raise ValueError(f"total_score must equal {expected}")
        return self


class ScoreCalculation(BaseModel):
    breakdown: ScoreBreakdown
    evidence: dict[str, list[str]] = Field(default_factory=dict)
    policy_version: str


class FailureRecord(BaseModel):
    stage: str
    code: str
    message: str
    retryable: bool = False


class CandidateResult(BaseModel):
    candidate_id: str
    source_file: str
    status: CandidateStatus
    rank: int | None = Field(default=None, ge=1)
    candidate_name: str
    name_source: Literal["resume_header", "pdf_metadata", "linkedin", "email", "filename"] = "filename"
    name_confidence: Literal["high", "medium", "low"] = "low"
    email: str | None = None
    github_url: str | None = None
    eligible: bool
    rejection_reasons: list[str] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    eligibility_evidence: dict[str, list[Evidence]] = Field(default_factory=dict)
    score_breakdown: ScoreBreakdown | None = None
    score_evidence: dict[str, list[str]] = Field(default_factory=dict)
    scoring_policy_version: str | None = None
    project_summary: str | None = None
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    github: GitHubAssessment = Field(default_factory=GitHubAssessment)
    assessment: ProjectAssessment | None = None
    warnings: list[str] = Field(default_factory=list)
    failure: FailureRecord | None = None
    duplicate_of: str | None = None

    @model_validator(mode="after")
    def validate_state(self) -> "CandidateResult":
        if self.status == CandidateStatus.ELIGIBLE:
            if not self.eligible or self.score_breakdown is None:
                raise ValueError("Eligible results require eligible=true and a score")
        else:
            if self.rank is not None:
                raise ValueError("Only eligible candidates may have a rank")
        if self.status == CandidateStatus.REJECTED and not self.rejection_reasons:
            raise ValueError("Rejected candidates require rejection reasons")
        if self.status == CandidateStatus.FAILED and self.failure is None:
            raise ValueError("Failed candidates require a failure record")
        return self


class BatchSummary(BaseModel):
    total_discovered: int = Field(ge=0)
    supported: int = Field(ge=0)
    successfully_parsed: int = Field(ge=0)
    eligible: int = Field(ge=0)
    rejected: int = Field(ge=0)
    duplicates: int = Field(ge=0)
    failed: int = Field(ge=0)
    unsupported: int = Field(ge=0)


class RunMetadata(BaseModel):
    run_id: str
    started_at: datetime
    completed_at: datetime
    input_directory: str
    output_file: str
    duration_ms: int = Field(ge=0)


class BatchResult(BaseModel):
    schema_version: str = "1.0"
    run: RunMetadata
    configuration: dict[str, object]
    batch_summary: BatchSummary
    candidates: list[CandidateResult]

    @model_validator(mode="after")
    def validate_counts(self) -> "BatchResult":
        counts = {
            CandidateStatus.ELIGIBLE: 0,
            CandidateStatus.REJECTED: 0,
            CandidateStatus.DUPLICATE: 0,
            CandidateStatus.FAILED: 0,
        }
        for candidate in self.candidates:
            counts[candidate.status] += 1
        summary = self.batch_summary
        expected_supported = sum(counts.values())
        if summary.supported != expected_supported:
            raise ValueError("supported count does not match candidate records")
        if summary.eligible != counts[CandidateStatus.ELIGIBLE]:
            raise ValueError("eligible count mismatch")
        if summary.rejected != counts[CandidateStatus.REJECTED]:
            raise ValueError("rejected count mismatch")
        if summary.duplicates != counts[CandidateStatus.DUPLICATE]:
            raise ValueError("duplicate count mismatch")
        if summary.failed != counts[CandidateStatus.FAILED]:
            raise ValueError("failed count mismatch")
        if summary.successfully_parsed != summary.eligible + summary.rejected:
            raise ValueError("successfully_parsed must equal eligible + rejected")
        if summary.total_discovered != summary.supported + summary.unsupported:
            raise ValueError("total_discovered count mismatch")
        return self
