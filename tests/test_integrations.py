from __future__ import annotations

import unittest
import urllib.error
from unittest.mock import patch

from resume_screener.config import Settings
from resume_screener.github import GitHubAPIError, GitHubAnalyzer
from resume_screener.extraction import minimise_for_llm
from resume_screener.llm import GeminiAssessor
from resume_screener.models import (
    CandidateProfile,
    Evidence,
    EvidenceStrength,
    IntegrationStatus,
)
from resume_screener.pipeline import _assess_github


def profile(candidate_id: str = "candidate", username: str | None = "octocat") -> CandidateProfile:
    evidence = Evidence(text="Built a Python machine learning model", strength=EvidenceStrength.APPLIED)
    return CandidateProfile(
        candidate_id=candidate_id,
        source_file=f"{candidate_id}.txt",
        candidate_name="Candidate Name",
        github_username=username,
        raw_text="Candidate Name\nBuilt a Python machine learning model",
        python_evidence=[evidence],
        ai_evidence=[evidence],
    )


class FailingGitHubClient:
    remaining = None

    def __init__(self, code: str) -> None:
        self.code = code

    def get(self, path: str) -> object:
        status = 404 if self.code == "not_found" else 429
        raise GitHubAPIError(self.code, "expected failure", status)


class IntegrationTests(unittest.TestCase):
    def test_llm_input_removes_direct_contact_fields(self) -> None:
        candidate = profile()
        candidate.candidate_name = "Candidate Name"
        candidate.raw_text = (
            "Candidate Name\n"
            "candidate@example.com | +91 98765 43210\n"
            "https://github.com/candidate\n"
            "Built a Python machine learning model"
        )
        sanitized = minimise_for_llm(candidate, 30_000)
        self.assertNotIn("Candidate Name", sanitized)
        self.assertNotIn("candidate@example.com", sanitized)
        self.assertNotIn("98765", sanitized)
        self.assertNotIn("github.com/candidate", sanitized)
        self.assertIn("Built a Python machine learning model", sanitized)

    def test_github_not_found_is_nonfatal(self) -> None:
        assessment = GitHubAnalyzer(
            Settings(), client=FailingGitHubClient("not_found")
        ).assess("missing-user")
        self.assertEqual(assessment.status, IntegrationStatus.NOT_FOUND)
        self.assertEqual(assessment.final_points, 0)

    def test_github_rate_limit_is_nonfatal(self) -> None:
        assessment = GitHubAnalyzer(
            Settings(), client=FailingGitHubClient("rate_limited")
        ).assess("limited-user")
        self.assertEqual(assessment.status, IntegrationStatus.RATE_LIMITED)
        self.assertEqual(assessment.final_points, 0)

    def test_gemini_network_failure_uses_deterministic_fallback(self) -> None:
        settings = Settings(gemini_api_key="test-key")
        with (
            patch(
                "resume_screener.llm.urllib.request.urlopen",
                side_effect=urllib.error.URLError("offline"),
            ),
            patch("resume_screener.llm.time.sleep"),
        ):
            assessment = GeminiAssessor(settings).assess(profile())
        self.assertEqual(assessment.provider_status, IntegrationStatus.FAILED)
        self.assertEqual(
            assessment.method, "deterministic_fallback_after_gemini_failure"
        )
        self.assertTrue(assessment.concerns)

    def test_github_assessment_is_reused_for_same_username(self) -> None:
        calls: list[str] = []

        class FakeAnalyzer:
            def __init__(self, settings: Settings) -> None:
                pass

            def assess(self, username: str):
                calls.append(username)
                return GitHubAnalyzer(Settings(github_enabled=False)).assess(username)

        profiles = [profile("one", "SameUser"), profile("two", "sameuser")]
        with patch("resume_screener.pipeline.GitHubAnalyzer", FakeAnalyzer):
            assessments = _assess_github(profiles, Settings())
        self.assertEqual(calls, ["sameuser"])
        self.assertEqual(list(assessments), ["sameuser"])


if __name__ == "__main__":
    unittest.main()
