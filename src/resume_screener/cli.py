from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import Settings
from .pipeline import screen_directory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resume-screen",
        description="Screen and rank SDE intern resumes using explainable Python, AI, and GitHub evidence.",
    )
    parser.add_argument("input_directory", type=Path, nargs="?", help="Directory containing resumes")
    parser.add_argument("--input", dest="input_option", type=Path, help="Directory containing PDF, DOCX, or TXT resumes")
    parser.add_argument("--output", type=Path, default=Path("output/results.json"), help="JSON output path")
    parser.add_argument("--env-file", type=Path, default=Path(".env"), help="Environment file path")
    parser.add_argument("--no-llm", action="store_true", help="Use deterministic project assessment only")
    parser.add_argument("--no-github", action="store_true", help="Disable GitHub enrichment")
    parser.add_argument("--no-security-scan", action="store_true", help="Disable public-repository secret hygiene checks")
    parser.add_argument("--recursive", action="store_true", help="Discover resumes recursively")
    parser.add_argument("--compact", action="store_true", help="Write compact rather than indented JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_directory = args.input_option or args.input_directory
    if input_directory is None:
        build_parser().error("an input directory is required (use --input <directory>)")
    try:
        base_settings = Settings.from_environment(args.env_file)
        settings = base_settings.with_overrides(
            llm_enabled=base_settings.llm_enabled and not args.no_llm,
            github_enabled=base_settings.github_enabled and not args.no_github,
            github_security_scan_enabled=(
                base_settings.github_security_scan_enabled and not args.no_security_scan
            ),
            recursive_discovery=base_settings.recursive_discovery or args.recursive,
        )
        logging.basicConfig(
            level=getattr(logging, settings.log_level, logging.INFO),
            format="%(levelname)s: %(message)s",
        )
        result = screen_directory(input_directory, args.output, settings, pretty=not args.compact)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    summary = result.batch_summary
    print(
        f"Completed: {summary.eligible} eligible, {summary.rejected} rejected, "
        f"{summary.duplicates} duplicates, {summary.failed} failed."
    )
    print(f"Results: {args.output.expanduser().resolve()}")
    if summary.eligible:
        print("Top candidates:")
        for candidate in result.candidates[: min(5, summary.eligible)]:
            print(f"  {candidate.rank}. {candidate.candidate_name} — {candidate.score_breakdown.total_score}/100")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
