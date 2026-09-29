from __future__ import annotations

import unittest

from resume_screener.github import scan_text_for_secrets


class GitHubSecurityTests(unittest.TestCase):
    def test_finds_key_without_returning_value(self) -> None:
        raw_value = "gh" + "p_" + "A" * 36
        findings = scan_text_for_secrets(
            f'TOKEN = "{raw_value}"', "repo", "settings.py", b"fixed-test-key"
        )
        self.assertTrue(findings)
        serialized = " ".join(str(item.model_dump()) for item in findings)
        self.assertNotIn(raw_value, serialized)
        self.assertEqual(findings[0].confidence, "high")

    def test_ignores_placeholders(self) -> None:
        findings = scan_text_for_secrets(
            'API_KEY = "your_key_here_placeholder"',
            "repo",
            "settings.py",
            b"fixed-test-key",
        )
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
