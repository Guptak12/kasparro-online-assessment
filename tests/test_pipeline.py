from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from resume_screener.config import Settings
from resume_screener.models import BatchResult, CandidateStatus
from resume_screener.pipeline import screen_directory


ELIGIBLE = """Alex Candidate
alex@example.com
Skills: Python, FastAPI, PostgreSQL, Machine Learning, Docker
Projects
Built and deployed a Python FastAPI backend for a machine learning classifier with 92% accuracy.
Implemented evaluation using precision and recall, pytest tests, logging, and Docker on AWS.
"""

REJECTED = """Taylor Candidate
taylor@example.com
Skills: Java, React, SQL
Built a React dashboard and Java REST service.
"""


class PipelineTests(unittest.TestCase):
    def test_batch_is_valid_and_ranked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "alex.txt").write_text(ELIGIBLE, encoding="utf-8")
            (root / "taylor.txt").write_text(REJECTED, encoding="utf-8")
            (root / "notes.csv").write_text("unsupported", encoding="utf-8")
            output = root / "results.json"
            settings = Settings(llm_enabled=False, github_enabled=False)
            result = screen_directory(root, output, settings)

            self.assertEqual(result.batch_summary.eligible, 1)
            self.assertEqual(result.batch_summary.rejected, 1)
            self.assertEqual(result.batch_summary.unsupported, 1)
            self.assertEqual(result.candidates[0].status, CandidateStatus.ELIGIBLE)
            self.assertEqual(result.candidates[0].rank, 1)
            BatchResult.model_validate(json.loads(output.read_text(encoding="utf-8")))

    def test_duplicate_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "one.txt").write_text(ELIGIBLE, encoding="utf-8")
            (root / "two.txt").write_text(ELIGIBLE, encoding="utf-8")
            result = screen_directory(
                root,
                root / "results.json",
                Settings(llm_enabled=False, github_enabled=False),
            )
            self.assertEqual(result.batch_summary.duplicates, 1)
            self.assertTrue(any(item.status == CandidateStatus.DUPLICATE for item in result.candidates))


if __name__ == "__main__":
    unittest.main()
