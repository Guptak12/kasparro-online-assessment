from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path


def load_dotenv(path: Path = Path(".env")) -> None:
    """Load a small, dependency-free subset of dotenv syntax.

    Existing process environment variables always win. This intentionally avoids
    interpolation and shell evaluation.
    """

    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


@dataclass(frozen=True, slots=True)
class Settings:
    llm_enabled: bool = True
    llm_provider: str = "gemini"
    llm_model: str = "gemini-3.5-flash-lite"
    gemini_api_key: str | None = None
    llm_timeout_seconds: int = 45
    llm_max_concurrency: int = 2
    llm_max_input_characters: int = 30_000

    github_enabled: bool = True
    github_token: str | None = None
    github_api_version: str = "2022-11-28"
    github_timeout_seconds: int = 10
    github_max_concurrency: int = 5
    github_security_scan_enabled: bool = True
    github_security_max_repositories: int = 3
    github_security_max_files_per_repository: int = 10
    github_security_max_file_bytes: int = 200_000
    github_security_request_reserve: int = 200

    max_resume_bytes: int = 10_000_000
    max_resume_characters: int = 50_000
    recursive_discovery: bool = False
    log_level: str = "INFO"

    @classmethod
    def from_environment(cls, dotenv_path: Path | None = Path(".env")) -> "Settings":
        if dotenv_path is not None:
            load_dotenv(dotenv_path)
        settings = cls(
            llm_enabled=_bool("LLM_ENABLED", True),
            llm_provider=os.getenv("LLM_PROVIDER", "gemini").strip().lower(),
            llm_model=os.getenv("LLM_MODEL", "gemini-3.5-flash-lite").strip(),
            gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
            llm_timeout_seconds=_int("LLM_TIMEOUT_SECONDS", 45),
            llm_max_concurrency=_int("LLM_MAX_CONCURRENCY", 2),
            llm_max_input_characters=_int("LLM_MAX_INPUT_CHARACTERS", 30_000),
            github_enabled=_bool("GITHUB_ENABLED", True),
            github_token=os.getenv("GITHUB_TOKEN") or None,
            github_api_version=os.getenv("GITHUB_API_VERSION", "2022-11-28").strip(),
            github_timeout_seconds=_int("GITHUB_TIMEOUT_SECONDS", 10),
            github_max_concurrency=_int("GITHUB_MAX_CONCURRENCY", 5),
            github_security_scan_enabled=_bool("GITHUB_SECURITY_SCAN_ENABLED", True),
            github_security_max_repositories=_int("GITHUB_SECURITY_MAX_REPOSITORIES", 3),
            github_security_max_files_per_repository=_int(
                "GITHUB_SECURITY_MAX_FILES_PER_REPOSITORY", 10
            ),
            github_security_max_file_bytes=_int(
                "GITHUB_SECURITY_MAX_FILE_BYTES", 200_000
            ),
            github_security_request_reserve=_int(
                "GITHUB_SECURITY_REQUEST_RESERVE", 200
            ),
            max_resume_bytes=_int("MAX_RESUME_BYTES", 10_000_000),
            max_resume_characters=_int("MAX_RESUME_CHARACTERS", 50_000),
            recursive_discovery=_bool("RECURSIVE_DISCOVERY", False),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        positive_fields = {
            "LLM_TIMEOUT_SECONDS": self.llm_timeout_seconds,
            "LLM_MAX_CONCURRENCY": self.llm_max_concurrency,
            "LLM_MAX_INPUT_CHARACTERS": self.llm_max_input_characters,
            "GITHUB_TIMEOUT_SECONDS": self.github_timeout_seconds,
            "GITHUB_MAX_CONCURRENCY": self.github_max_concurrency,
            "GITHUB_SECURITY_MAX_REPOSITORIES": self.github_security_max_repositories,
            "GITHUB_SECURITY_MAX_FILES_PER_REPOSITORY": (
                self.github_security_max_files_per_repository
            ),
            "GITHUB_SECURITY_MAX_FILE_BYTES": self.github_security_max_file_bytes,
            "MAX_RESUME_BYTES": self.max_resume_bytes,
            "MAX_RESUME_CHARACTERS": self.max_resume_characters,
        }
        for name, value in positive_fields.items():
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if self.llm_enabled and self.llm_provider != "gemini":
            raise ValueError("Only the gemini LLM provider is implemented")
        if not self.llm_model:
            raise ValueError("LLM_MODEL cannot be empty")

    def with_overrides(self, **changes: object) -> "Settings":
        updated = replace(self, **changes)
        updated.validate()
        return updated

    def public_summary(self) -> dict[str, object]:
        return {
            "llm_enabled": self.llm_enabled and bool(self.gemini_api_key),
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "github_enabled": self.github_enabled,
            "github_authenticated": bool(self.github_token),
            "github_security_scan_enabled": self.github_security_scan_enabled,
            "recursive_discovery": self.recursive_discovery,
        }
