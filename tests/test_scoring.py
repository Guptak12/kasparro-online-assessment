from __future__ import annotations

import unittest

from resume_screener.models import (
    CandidateProfile,
    Evidence,
    EvidenceStrength,
    GitHubAssessment,
    IntegrationStatus,
    ProjectAssessment,
)
from resume_screener.scoring import calculate_score


class ScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = CandidateProfile(
            candidate_id="candidate",
            source_file="resume.txt",
            candidate_name="Candidate",
            raw_text="testing monitoring security performance documentation",
            python_evidence=[
                Evidence(
                    text="Built a Python FastAPI backend with PostgreSQL and Celery",
                    strength=EvidenceStrength.ADVANCED,
                )
            ],
            engineering_evidence=[
                Evidence(
                    text="Deployed Docker on AWS with GitHub Actions and React",
                    strength=EvidenceStrength.ADVANCED,
                )
            ],
            evidence_by_category={
                "python": [
                    Evidence(
                        text="Built a Python FastAPI backend",
                        strength=EvidenceStrength.ADVANCED,
                    )
                ],
                "backend": [
                    Evidence(
                        text="Built a Python FastAPI backend",
                        strength=EvidenceStrength.ADVANCED,
                    )
                ],
                "database": [
                    Evidence(text="Used PostgreSQL", strength=EvidenceStrength.ADVANCED)
                ],
                "async_queues": [
                    Evidence(text="Used Celery", strength=EvidenceStrength.ADVANCED)
                ],
                "cloud": [Evidence(text="Deployed to GCP", strength=EvidenceStrength.ADVANCED)],
                "containers": [Evidence(text="Used Docker", strength=EvidenceStrength.ADVANCED)],
                "cicd": [
                    Evidence(text="Used GitHub Actions", strength=EvidenceStrength.ADVANCED)
                ],
                "frontend": [Evidence(text="Built React UI", strength=EvidenceStrength.ADVANCED)],
                "testing": [Evidence(text="Added pytest", strength=EvidenceStrength.APPLIED)],
                "observability": [
                    Evidence(text="Added monitoring", strength=EvidenceStrength.APPLIED)
                ],
                "security": [Evidence(text="Added OAuth", strength=EvidenceStrength.APPLIED)],
                "performance": [
                    Evidence(text="Reduced latency", strength=EvidenceStrength.APPLIED)
                ],
                "documentation": [
                    Evidence(text="Documented APIs", strength=EvidenceStrength.APPLIED)
                ],
            },
        )

    def test_maximum_categories_remain_bounded(self) -> None:
        assessment = ProjectAssessment(
            project_depth="advanced",
            retrieval_depth="advanced",
            agent_depth="advanced",
            data_workflow_depth="advanced",
            evaluation_depth="advanced",
            ownership_depth="advanced",
        )
        github = GitHubAssessment(
            status=IntegrationStatus.SUCCESS,
            activity_points=5,
            repository_points=5,
            final_points=10,
        )
        score = calculate_score(self.profile, assessment, github)
        self.assertLessEqual(score.breakdown.total_score, 100)
        self.assertEqual(score.breakdown.github, 10)
        self.assertEqual(score.breakdown.ai_project_depth, 40)
        self.assertEqual(score.breakdown.cloud_fullstack, 15)
        self.assertEqual(score.breakdown.engineering_depth, 5)
        self.assertTrue(score.evidence["cloud_fullstack"])

    def test_penalty_is_explainable_and_capped(self) -> None:
        assessment = ProjectAssessment(
            project_depth="applied",
            thin_wrapper_severity="high",
            tutorial_severity="high",
        )
        score = calculate_score(self.profile, assessment, GitHubAssessment())
        self.assertEqual(score.breakdown.project_quality_penalty, 20)
        self.assertEqual(len(score.breakdown.penalty_reasons), 2)
        self.assertEqual(len(score.evidence["project_quality_penalty"]), 2)


if __name__ == "__main__":
    unittest.main()
