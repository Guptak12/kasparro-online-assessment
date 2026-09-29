from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .config import Settings
from .models import GitHubAssessment, IntegrationStatus, SecurityFinding, SecurityHygiene


RELEVANT_TERMS = (
    "python", "django", "flask", "fastapi", "machine learning", "deep learning",
    "llm", "rag", "agent", "nlp", "pytorch", "tensorflow", "backend", "api",
)
SCANNABLE_SUFFIXES = {".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml", ".env", ".ini", ".cfg"}
SKIP_PATH_PARTS = {"node_modules", "vendor", "dist", "build", "examples", "example", "fixtures", "docs", ".git"}
PLACEHOLDER_RE = re.compile(r"(?i)(example|sample|placeholder|dummy|your[_ -]?key|changeme|xxx|test[_ -]?key)")

SECRET_RULES: tuple[tuple[str, str, str, re.Pattern[str], int], ...] = (
    ("private_key", "Private key", "critical", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), 5),
    ("github_token", "GitHub token", "critical", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b"), 5),
    ("google_api_key", "Google API key", "high", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"), 4),
    ("openai_key", "OpenAI-style API key", "high", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), 4),
    (
        "hardcoded_secret",
        "Hard-coded credential",
        "high",
        re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password)\s*[=:]\s*['\"]([^'\"\s]{12,})['\"]"),
        3,
    ),
)


@dataclass(slots=True)
class GitHubAPIError(RuntimeError):
    code: str
    message: str
    status: int | None = None

    def __str__(self) -> str:
        return self.message


class GitHubClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.remaining: int | None = None
        self.cache: dict[str, object] = {}

    def get(self, path: str) -> object:
        if path in self.cache:
            return self.cache[path]
        request = urllib.request.Request(
            f"https://api.github.com{path}",
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": self.settings.github_api_version,
                "User-Agent": "kasparro-resume-screener/0.1",
                **({"Authorization": f"Bearer {self.settings.github_token}"} if self.settings.github_token else {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.settings.github_timeout_seconds) as response:
                remaining = response.headers.get("X-RateLimit-Remaining")
                if remaining and remaining.isdigit():
                    self.remaining = int(remaining)
                value = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise GitHubAPIError("not_found", "GitHub user or resource was not found", 404) from exc
            if exc.code in {403, 429}:
                raise GitHubAPIError("rate_limited", "GitHub API rate limit was reached", exc.code) from exc
            raise GitHubAPIError("http_error", f"GitHub API returned HTTP {exc.code}", exc.code) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise GitHubAPIError("network_error", f"GitHub request failed: {exc}") from exc
        self.cache[path] = value
        return value


def _parse_date(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _activity_points(events: list[dict[str, object]], repos: list[dict[str, object]]) -> int:
    now = datetime.now(UTC)
    recent_events = sum((_parse_date(item.get("created_at")) or datetime.min.replace(tzinfo=UTC)) >= now - timedelta(days=90) for item in events)
    recently_pushed = sum((_parse_date(item.get("pushed_at")) or datetime.min.replace(tzinfo=UTC)) >= now - timedelta(days=180) for item in repos)
    signal = recent_events + min(recently_pushed, 5)
    if signal >= 12:
        return 5
    if signal >= 7:
        return 4
    if signal >= 4:
        return 3
    if signal >= 2:
        return 2
    if signal:
        return 1
    return 0


def _repo_relevance(repo: dict[str, object]) -> int:
    text = " ".join(
        str(repo.get(key) or "") for key in ("name", "description", "language", "topics")
    ).lower()
    matches = sum(term in text for term in RELEVANT_TERMS)
    return matches * 4 + min(int(repo.get("stargazers_count") or 0), 5) + min(int(repo.get("forks_count") or 0), 3)


def _repository_points(repos: list[dict[str, object]]) -> tuple[int, list[dict[str, object]]]:
    owned = [repo for repo in repos if not repo.get("fork") and not repo.get("archived")]
    ranked = sorted(owned, key=_repo_relevance, reverse=True)
    relevant = [repo for repo in ranked if _repo_relevance(repo) > 0]
    if len(relevant) >= 4 and _repo_relevance(relevant[0]) >= 8:
        points = 5
    elif len(relevant) >= 3:
        points = 4
    elif len(relevant) >= 2:
        points = 3
    elif len(relevant) == 1:
        points = 2
    elif owned:
        points = 1
    else:
        points = 0
    return points, relevant[:5]


def _fingerprint(value: str, run_key: bytes) -> str:
    return hmac.new(run_key, value.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def scan_text_for_secrets(text: str, repository: str, file_path: str, run_key: bytes) -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    seen: set[str] = set()
    for rule_id, secret_type, severity, pattern, _ in SECRET_RULES:
        for match in pattern.finditer(text):
            value = match.group(1) if match.lastindex else match.group(0)
            if PLACEHOLDER_RE.search(value):
                continue
            fingerprint = _fingerprint(value, run_key)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            findings.append(
                SecurityFinding(
                    rule_id=rule_id,
                    severity=severity,
                    confidence="high",
                    repository=repository,
                    file_path=file_path,
                    secret_type=secret_type,
                    fingerprint=fingerprint,
                    reason=f"High-confidence {secret_type.lower()} pattern found in a public file.",
                )
            )
    return findings


def _security_scan(client: GitHubClient, username: str, repos: list[dict[str, object]], settings: Settings) -> SecurityHygiene:
    if not settings.github_security_scan_enabled:
        return SecurityHygiene(reason="Security scan disabled by configuration.")
    if client.remaining is not None and client.remaining < settings.github_security_request_reserve:
        return SecurityHygiene(reason="Skipped to preserve the configured GitHub API request reserve.")
    run_key = secrets.token_bytes(32)
    findings: list[SecurityFinding] = []
    checked = 0
    incomplete = False
    for repo in repos[: settings.github_security_max_repositories]:
        name = str(repo.get("name") or "")
        branch = str(repo.get("default_branch") or "main")
        if not name:
            continue
        try:
            tree = client.get(f"/repos/{urllib.parse.quote(username)}/{urllib.parse.quote(name)}/git/trees/{urllib.parse.quote(branch)}?recursive=1")
            if not isinstance(tree, dict) or tree.get("truncated"):
                incomplete = True
                continue
            entries = tree.get("tree", [])
            paths = []
            if isinstance(entries, list):
                for entry in entries:
                    if not isinstance(entry, dict) or entry.get("type") != "blob":
                        continue
                    path = str(entry.get("path") or "")
                    parts = set(path.lower().split("/"))
                    suffix = ".env" if path.lower().endswith(".env") else "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
                    size = int(entry.get("size") or 0)
                    if suffix in SCANNABLE_SUFFIXES and not (parts & SKIP_PATH_PARTS) and size <= settings.github_security_max_file_bytes:
                        paths.append(path)
            priority = lambda p: (0 if any(token in p.lower() for token in ("config", "settings", ".env")) else 1, p)
            for path in sorted(paths, key=priority)[: settings.github_security_max_files_per_repository]:
                encoded_path = urllib.parse.quote(path, safe="/")
                content = client.get(f"/repos/{urllib.parse.quote(username)}/{urllib.parse.quote(name)}/contents/{encoded_path}?ref={urllib.parse.quote(branch)}")
                if not isinstance(content, dict) or content.get("encoding") != "base64":
                    incomplete = True
                    continue
                try:
                    decoded = base64.b64decode(str(content.get("content") or "")).decode("utf-8", errors="replace")
                except (ValueError, TypeError):
                    incomplete = True
                    continue
                findings.extend(scan_text_for_secrets(decoded, name, path, run_key))
            checked += 1
        except GitHubAPIError:
            incomplete = True
    if incomplete:
        return SecurityHygiene(
            status="partial",
            repositories_checked=checked,
            penalty=0,
            findings=findings,
            reason="The bounded scan was incomplete; findings are advisory and no points were deducted.",
        )
    penalty_map = {rule_id: penalty for rule_id, _, _, _, penalty in SECRET_RULES}
    penalty = min(5, max((penalty_map.get(item.rule_id, 0) for item in findings), default=0))
    return SecurityHygiene(
        status="checked",
        repositories_checked=checked,
        penalty=penalty,
        findings=findings,
        reason="Only public, bounded, high-confidence patterns were checked.",
    )


class GitHubAnalyzer:
    def __init__(self, settings: Settings, client: GitHubClient | None = None) -> None:
        self.settings = settings
        self.client = client or GitHubClient(settings)

    def assess(self, username: str | None) -> GitHubAssessment:
        if not self.settings.github_enabled or not username:
            return GitHubAssessment(
                status=IntegrationStatus.SKIPPED,
                username=username,
                summary="No GitHub username was available or GitHub enrichment was disabled.",
            )
        quoted = urllib.parse.quote(username)
        try:
            self.client.get(f"/users/{quoted}")
            repos_raw = self.client.get(f"/users/{quoted}/repos?per_page=100&sort=updated")
            events_raw = self.client.get(f"/users/{quoted}/events/public?per_page=100")
            repos = [item for item in repos_raw if isinstance(item, dict)] if isinstance(repos_raw, list) else []
            events = [item for item in events_raw if isinstance(item, dict)] if isinstance(events_raw, list) else []
            activity = _activity_points(events, repos)
            repository, relevant = _repository_points(repos)
            hygiene = _security_scan(self.client, username, relevant, self.settings)
            final = max(0, min(10, activity + repository) - hygiene.penalty)
            return GitHubAssessment(
                status=IntegrationStatus.SUCCESS,
                username=username,
                activity_points=activity,
                repository_points=repository,
                final_points=final,
                summary=f"Reviewed {len(repos)} public repositories and {len(events)} recent public events.",
                relevant_repositories=[str(item.get("html_url") or item.get("name")) for item in relevant],
                security_hygiene=hygiene,
            )
        except GitHubAPIError as exc:
            status = IntegrationStatus.NOT_FOUND if exc.code == "not_found" else IntegrationStatus.RATE_LIMITED if exc.code == "rate_limited" else IntegrationStatus.FAILED
            return GitHubAssessment(
                status=status,
                username=username,
                summary="GitHub enrichment could not be completed; no points were awarded or deducted.",
                error=exc.message,
            )
