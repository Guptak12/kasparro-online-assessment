from __future__ import annotations

import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from .config import Settings
from .eligibility import assess_eligibility
from .extraction import extract_profile
from .github import GitHubAnalyzer
from .ingestion import ResumeParseError, discover_resumes, parse_resume
from .llm import DeterministicAssessor, build_assessor
from .models import (
    BatchResult,
    BatchSummary,
    CandidateProfile,
    CandidateResult,
    CandidateStatus,
    EligibilityDecision,
    FailureRecord,
    GitHubAssessment,
    IntegrationStatus,
    ProjectAssessment,
    RunMetadata,
)
from .scoring import calculate_score, ranking_key


def _failure(path: Path, code: str, message: str) -> CandidateResult:
    return CandidateResult(
        candidate_id=uuid.uuid5(uuid.NAMESPACE_URL, str(path.resolve())).hex[:16],
        source_file=path.name,
        status=CandidateStatus.FAILED,
        candidate_name=path.stem,
        eligible=False,
        failure=FailureRecord(stage="ingestion", code=code, message=message),
    )


def _rejected(profile: CandidateProfile, decision: EligibilityDecision) -> CandidateResult:
    return CandidateResult(
        candidate_id=profile.candidate_id,
        source_file=profile.source_file,
        status=CandidateStatus.REJECTED,
        candidate_name=profile.candidate_name,
        name_source=profile.name_source,
        name_confidence=profile.name_confidence,
        email=profile.email,
        github_url=profile.github_url,
        eligible=False,
        rejection_reasons=decision.rejection_reasons,
        matched_skills=profile.skills,
        eligibility_evidence={"python": decision.python_evidence, "ai": decision.ai_evidence},
        warnings=profile.extraction_warnings,
    )


def _eligible_result(
    profile: CandidateProfile,
    decision: EligibilityDecision,
    assessment: ProjectAssessment,
    github: GitHubAssessment,
) -> CandidateResult:
    score = calculate_score(profile, assessment, github)
    warnings = list(profile.extraction_warnings)
    if assessment.provider_status.value == "failed":
        warnings.append("Gemini enrichment failed; deterministic project assessment was used.")
    if github.status.value in {"failed", "rate_limited"}:
        warnings.append("GitHub enrichment was unavailable; GitHub contributed zero points.")
    return CandidateResult(
        candidate_id=profile.candidate_id,
        source_file=profile.source_file,
        status=CandidateStatus.ELIGIBLE,
        candidate_name=profile.candidate_name,
        name_source=profile.name_source,
        name_confidence=profile.name_confidence,
        email=profile.email,
        github_url=profile.github_url,
        eligible=True,
        matched_skills=profile.skills,
        eligibility_evidence={"python": decision.python_evidence, "ai": decision.ai_evidence},
        score_breakdown=score.breakdown,
        score_evidence=score.evidence,
        scoring_policy_version=score.policy_version,
        project_summary=assessment.project_summary,
        strengths=assessment.strengths,
        concerns=assessment.concerns,
        github=github,
        assessment=assessment,
        warnings=warnings,
    )


def _assess_projects(
    profiles: list[CandidateProfile], settings: Settings
) -> dict[str, ProjectAssessment]:
    assessor = build_assessor(settings)
    fallback = DeterministicAssessor()
    assessments: dict[str, ProjectAssessment] = {}
    workers = min(settings.llm_max_concurrency, max(1, len(profiles)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="gemini") as executor:
        future_map = {executor.submit(assessor.assess, profile): profile for profile in profiles}
        for future in as_completed(future_map):
            profile = future_map[future]
            try:
                assessments[profile.candidate_id] = future.result()
            except Exception as exc:
                deterministic = fallback.assess(profile)
                assessments[profile.candidate_id] = deterministic.model_copy(
                    update={
                        "provider_status": IntegrationStatus.FAILED,
                        "method": "deterministic_fallback_after_unexpected_error",
                        "concerns": deterministic.concerns
                        + [f"Unexpected assessment error: {type(exc).__name__}"],
                    }
                )
    return assessments


def _assess_github(
    profiles: list[CandidateProfile], settings: Settings
) -> dict[str, GitHubAssessment]:
    usernames = {
        profile.github_username.lower(): profile.github_username
        for profile in profiles
        if profile.github_username
    }
    assessments: dict[str, GitHubAssessment] = {}
    if not usernames:
        return assessments
    workers = min(settings.github_max_concurrency, len(usernames))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="github") as executor:
        future_map = {
            executor.submit(GitHubAnalyzer(settings).assess, username): normalised
            for normalised, username in usernames.items()
        }
        for future in as_completed(future_map):
            normalised = future_map[future]
            try:
                assessments[normalised] = future.result()
            except Exception as exc:
                assessments[normalised] = GitHubAssessment(
                    status=IntegrationStatus.FAILED,
                    username=usernames[normalised],
                    summary="GitHub enrichment failed; no points were awarded or deducted.",
                    error=f"Unexpected GitHub error: {type(exc).__name__}",
                )
    return assessments


def _atomic_write(result: BatchResult, output_file: Path, pretty: bool) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_file.with_name(f".{output_file.name}.{uuid.uuid4().hex}.tmp")
    payload = result.model_dump_json(indent=2 if pretty else None, exclude_none=True)
    try:
        temporary.write_text(payload + "\n", encoding="utf-8")
        os.replace(temporary, output_file)
    finally:
        temporary.unlink(missing_ok=True)


def screen_directory(
    input_directory: Path,
    output_file: Path,
    settings: Settings,
    *,
    pretty: bool = True,
) -> BatchResult:
    started_at = datetime.now(UTC)
    started = time.monotonic()
    discovery = discover_resumes(input_directory, settings.recursive_discovery)
    results: list[CandidateResult] = []
    eligible_work: list[tuple[CandidateProfile, EligibilityDecision]] = []
    seen_hashes: dict[str, str] = {}

    for path in discovery.files:
        try:
            parsed = parse_resume(path, settings)
            if parsed.file.sha256 in seen_hashes:
                results.append(
                    CandidateResult(
                        candidate_id=parsed.file.file_id,
                        source_file=path.name,
                        status=CandidateStatus.DUPLICATE,
                        candidate_name=path.stem,
                        eligible=False,
                        duplicate_of=seen_hashes[parsed.file.sha256],
                    )
                )
                continue
            seen_hashes[parsed.file.sha256] = parsed.file.file_id
            profile = extract_profile(parsed)
            decision = assess_eligibility(profile)
            if decision.eligible:
                eligible_work.append((profile, decision))
            else:
                results.append(_rejected(profile, decision))
        except ResumeParseError as exc:
            results.append(_failure(path, exc.code, str(exc)))
        except Exception as exc:
            results.append(_failure(path, "unexpected_parse_error", f"Unexpected parse error: {type(exc).__name__}"))

    if eligible_work:
        profiles = [profile for profile, _ in eligible_work]
        assessments = _assess_projects(profiles, settings)
        github_assessments = _assess_github(profiles, settings)
        for profile, decision in eligible_work:
            github = (
                github_assessments.get(profile.github_username.lower())
                if profile.github_username
                else None
            ) or GitHubAssessment(
                status=IntegrationStatus.SKIPPED,
                summary="No GitHub username was available or GitHub enrichment was disabled.",
            )
            try:
                results.append(
                    _eligible_result(
                        profile,
                        decision,
                        assessments[profile.candidate_id],
                        github,
                    )
                )
            except Exception as exc:
                results.append(
                    CandidateResult(
                        candidate_id=profile.candidate_id,
                        source_file=profile.source_file,
                        status=CandidateStatus.FAILED,
                        candidate_name=profile.candidate_name,
                        name_source=profile.name_source,
                        name_confidence=profile.name_confidence,
                        email=profile.email,
                        github_url=profile.github_url,
                        eligible=False,
                        matched_skills=profile.skills,
                        failure=FailureRecord(
                            stage="scoring",
                            code="unexpected_scoring_error",
                            message=f"Unexpected scoring error: {type(exc).__name__}",
                        ),
                    )
                )

    eligible = [item for item in results if item.status == CandidateStatus.ELIGIBLE]
    eligible.sort(key=lambda item: ranking_key(item.candidate_name, item.score_breakdown))  # type: ignore[arg-type]
    for index, item in enumerate(eligible, start=1):
        item.rank = index
    non_eligible = sorted(
        (item for item in results if item.status != CandidateStatus.ELIGIBLE),
        key=lambda item: (item.status.value, item.candidate_name.lower(), item.source_file.lower()),
    )
    ordered = eligible + non_eligible
    counts = {status: sum(item.status == status for item in ordered) for status in CandidateStatus}
    completed_at = datetime.now(UTC)
    summary = BatchSummary(
        total_discovered=discovery.total_discovered,
        supported=len(discovery.files),
        successfully_parsed=counts[CandidateStatus.ELIGIBLE] + counts[CandidateStatus.REJECTED],
        eligible=counts[CandidateStatus.ELIGIBLE],
        rejected=counts[CandidateStatus.REJECTED],
        duplicates=counts[CandidateStatus.DUPLICATE],
        failed=counts[CandidateStatus.FAILED],
        unsupported=len(discovery.unsupported),
    )
    result = BatchResult(
        run=RunMetadata(
            run_id=uuid.uuid4().hex,
            started_at=started_at,
            completed_at=completed_at,
            input_directory=str(input_directory.expanduser()),
            output_file=str(output_file.expanduser()),
            duration_ms=int((time.monotonic() - started) * 1000),
        ),
        configuration=settings.public_summary(),
        batch_summary=summary,
        candidates=ordered,
    )
    _atomic_write(result, output_file, pretty)
    return result


def load_result(path: Path) -> BatchResult:
    return BatchResult.model_validate(json.loads(path.read_text(encoding="utf-8")))
