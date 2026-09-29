from __future__ import annotations

import unittest

from resume_screener.eligibility import assess_eligibility
from resume_screener.models import CandidateProfile, Evidence, EvidenceStrength


def profile(python: list[Evidence], ai: list[Evidence]) -> CandidateProfile:
    return CandidateProfile(
        candidate_id="candidate",
        source_file="resume.txt",
        candidate_name="Candidate",
        raw_text="resume",
        python_evidence=python,
        ai_evidence=ai,
    )


class EligibilityTests(unittest.TestCase):
    def test_requires_both_python_and_ai(self) -> None:
        result = assess_eligibility(
            profile(
                [Evidence(text="Built a Python API", strength=EvidenceStrength.APPLIED)],
                [],
            )
        )
        self.assertFalse(result.eligible)
        self.assertEqual(
            result.rejection_reasons,
            ["No applied AI/ML project or implementation evidence was found."],
        )

    def test_incidental_coursework_does_not_pass(self) -> None:
        result = assess_eligibility(
            profile(
                [Evidence(text="Python course", strength=EvidenceStrength.INCIDENTAL)],
                [Evidence(text="ML tutorial", strength=EvidenceStrength.INCIDENTAL)],
            )
        )
        self.assertFalse(result.eligible)
        self.assertEqual(len(result.rejection_reasons), 2)

    def test_applied_evidence_passes(self) -> None:
        result = assess_eligibility(
            profile(
                [Evidence(text="Implemented FastAPI", strength=EvidenceStrength.APPLIED)],
                [Evidence(text="Trained a classifier", strength=EvidenceStrength.APPLIED)],
            )
        )
        self.assertTrue(result.eligible)

    def test_skill_only_ai_mention_does_not_pass(self) -> None:
        result = assess_eligibility(
            profile(
                [Evidence(text="Built a Python API", strength=EvidenceStrength.APPLIED)],
                [Evidence(text="Skills: machine learning", strength=EvidenceStrength.SKILL)],
            )
        )
        self.assertFalse(result.eligible)
        self.assertEqual(result.ai_evidence, [])


if __name__ == "__main__":
    unittest.main()
