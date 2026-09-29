from __future__ import annotations

import unittest
from pathlib import Path

from resume_screener.extraction import extract_profile
from resume_screener.models import ParsedResume, ResumeFile


def parsed(text: str, *, metadata: dict[str, str] | None = None) -> ParsedResume:
    return ParsedResume(
        file=ResumeFile(
            file_id="candidate",
            path=Path("candidate.pdf"),
            source_file="candidate.pdf",
            extension=".pdf",
            sha256="0" * 64,
            size_bytes=len(text),
        ),
        raw_text=text,
        parser_name="test",
        metadata=metadata or {},
    )


class ExtractionTests(unittest.TestCase):
    def test_name_is_trimmed_before_inline_heading(self) -> None:
        profile = extract_profile(
            parsed("ANNISHA S CAREER ASPIRATION\nannisha@example.com\nBuilt a Python API")
        )
        self.assertEqual(profile.candidate_name, "ANNISHA S")
        self.assertEqual(profile.name_source, "resume_header")

    def test_company_after_section_is_not_used_as_name(self) -> None:
        profile = extract_profile(
            parsed(
                "LinkedIn: linkedin.com/in/harsha-arun-4893732a5\n"
                "WORK EXPERIENCE\nMindstack Solutions Pvt. Ltd.\nBuilt a Python model"
            )
        )
        self.assertEqual(profile.candidate_name, "Harsha Arun")
        self.assertEqual(profile.name_source, "linkedin")

    def test_character_spaced_language_is_not_used_as_name(self) -> None:
        profile = extract_profile(
            parsed(
                "M o t i v a t e d g r a d u a t e\nE n g l i s h\n"
                "B u i l t a P y t h o n m a c h i n e l e a r n i n g m o d e l",
                metadata={"Author": "priya r"},
            )
        )
        self.assertEqual(profile.candidate_name, "Priya R")
        self.assertEqual(profile.name_source, "pdf_metadata")

    def test_linkedin_slug_strips_trailing_digits(self) -> None:
        profile = extract_profile(parsed("linkedin.com/in/nidhi-km11\nProfessional Summary"))
        self.assertEqual(profile.candidate_name, "Nidhi Km")

    def test_character_spaced_applied_evidence_is_detected(self) -> None:
        profile = extract_profile(
            parsed("Priya R\nP R O J E C T S\nB u i l t a P y t h o n m a c h i n e l e a r n i n g m o d e l")
        )
        self.assertTrue(profile.python_evidence)
        self.assertTrue(profile.ai_evidence)
        self.assertEqual(profile.ai_evidence[0].strength, "applied")


if __name__ == "__main__":
    unittest.main()
