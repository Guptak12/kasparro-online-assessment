# Product Requirements Document: AI Resume Screening and Ranking System

| Field | Value |
|---|---|
| Product | AI Resume Screening and Ranking System |
| Document version | 1.0 |
| Status | Implementation-ready draft |
| Primary interface | Python CLI |
| Intended workload | Approximately 50 resumes per batch |
| Primary language | Python 3.11+ |
| Canonical output | JSON |
| Time-box | 2–3 hours for MVP implementation |

## 1. Executive summary

The product is a backend application that screens a directory of candidate resumes for an SDE internship requiring Python proficiency and practical AI or agentic-system exposure. It must parse every supported resume without allowing one malformed file to stop the batch, apply hard eligibility rules, assess and score only eligible candidates, optionally use an LLM for structured project-depth judgment, enrich eligible profiles with public GitHub activity, and generate an explainable ranked result.

The system will be delivered as a CLI-first modular monolith. Deterministic code will own hard eligibility, score weights, caps, penalties, ranking, and error handling. An optional LLM adapter may extract structured project details and assess implementation depth, but its output must be schema-validated and must never directly determine final eligibility or the final score. GitHub enrichment is a positive, non-blocking signal and is not required for eligibility.

The design prioritizes correctness, transparency, graceful degradation, and reviewer usability over interface polish or infrastructure complexity.

## 2. Background and problem statement

Manual screening of approximately 50 heterogeneous resumes is slow and inconsistent. Keyword-only ranking is also unreliable: it may over-rank polished but irrelevant resumes, fail to distinguish real AI systems from thin API wrappers, or penalize otherwise qualified candidates for having additional JavaScript, Java, React, or Next.js experience.

The system must solve four related problems:

1. Extract useful information from resumes with inconsistent layouts and section names.
2. Reject candidates without genuine Python evidence or meaningful AI/LLM/RAG/agentic evidence.
3. Rank eligible candidates using evidence-backed, explainable engineering criteria.
4. Remain useful when files are malformed or when GitHub or LLM services fail.

## 3. Product vision

Provide a reviewer with a reproducible first-pass shortlist that explains what evidence was found, why each candidate passed or failed, how each score was calculated, and which parts of the assessment were unavailable or uncertain.

The product is decision support, not an autonomous hiring authority. A human reviewer remains responsible for final hiring decisions.

## 4. Goals

### 4.1 Primary goals

- Process an entire resume directory in one command.
- Support PDF as a required format and DOCX/TXT as bonus formats.
- Prevent one invalid resume or external-service failure from failing the batch.
- Enforce Python and AI evidence as hard eligibility requirements.
- Rank eligible candidates using the specified 100-point baseline.
- Apply explicit penalties for thin LLM wrappers and tutorial-style projects.
- Preserve short source evidence for important decisions.
- Enrich candidates with public GitHub signals when a profile is present.
- Generate a machine-readable result containing every candidate and a batch summary.
- Keep configuration, business logic, parsing, and integrations separated.
- Include focused tests for the highest-risk logic.

### 4.2 Success metrics

The MVP is successful when:

- 100% of discovered supported files receive a terminal status: eligible, rejected, duplicate, or failed.
- One malformed file does not stop processing of any other file.
- All eligible candidates have both Python evidence and AI evidence.
- All rejected candidates have at least one explicit rejection reason.
- Every eligible candidate has a score breakdown whose arithmetic reproduces the final score.
- No category exceeds its configured cap and no final score falls outside 0–100.
- Missing, private, invalid, or rate-limited GitHub profiles do not affect eligibility or fail the batch.
- Invalid or unavailable LLM responses trigger a documented fallback.
- Given the same validated assessment inputs, eligibility and score calculations are deterministic; model-derived assessments may vary only within validated schema boundaries.
- The output includes counts for total discovered, parsed, eligible, rejected, duplicate, and failed resumes.

## 5. Non-goals

The MVP will not include:

- A frontend or visual dashboard.
- Authentication or user management.
- A persistent database.
- Deployment infrastructure.
- A vector database, embeddings index, or RAG knowledge base.
- Resume OCR for scanned-image PDFs unless time remains.
- Fine-tuning or model training.
- Automated candidate outreach or rejection messages.
- Final hiring recommendations without human review.
- Scraping private GitHub information or bypassing GitHub API restrictions.
- Demographic inference or scoring based on protected or sensitive attributes.

## 6. Users and stakeholders

### 6.1 Primary user: technical recruiter or hiring engineer

Needs to run one command, receive a ranked shortlist, inspect evidence and score breakdowns, and understand failures without reading application logs.

### 6.2 Secondary user: evaluator or code reviewer

Needs to understand the architecture, run the system locally, inspect implementation trade-offs, validate scoring behavior, and execute tests.

### 6.3 Indirect stakeholder: candidate

Needs a process that uses job-relevant evidence, avoids protected attributes, and does not silently convert weak or unavailable external signals into rejection.

## 7. Assumptions and constraints

- A typical batch contains approximately 50 resumes.
- Most PDFs contain selectable text; scanned-image PDFs may fail gracefully.
- Resume layouts and section titles are inconsistent.
- Internet access may be unavailable or restricted during execution.
- GitHub API credentials may be absent.
- An LLM API key may be absent.
- Candidate resumes contain personally identifiable information.
- The application must be operable without a database or external queue.
- The CLI and all deterministic screening logic must remain usable when optional integrations are disabled.
- The time-box favors a focused modular monolith over distributed services.

## 8. User journeys

### 8.1 Standard batch screening

1. The user places resumes in an input directory.
2. The user configures optional environment variables.
3. The user runs the CLI with input and output paths.
4. The application discovers, parses, evaluates, enriches, and ranks the resumes.
5. The application writes `results.json` and prints a concise batch summary.
6. The user reviews top-ranked eligible candidates and rejected-candidate reasons.

### 8.2 Screening without external services

1. The user runs the CLI without an LLM key or GitHub token.
2. The deterministic extraction, eligibility, and scoring pipeline still runs.
3. Optional enrichment statuses state why those features were skipped or limited.
4. The output remains valid and complete.

### 8.3 Partial failure

1. A resume is malformed, an LLM call times out, or GitHub is rate-limited.
2. The failure is captured at the narrowest relevant boundary.
3. Other resumes continue processing.
4. The affected candidate contains a structured failure or fallback status.
5. The batch summary accurately records the outcome.

## 9. Functional requirements

### 9.1 File discovery and ingestion

| ID | Requirement | Priority |
|---|---|---|
| FR-ING-001 | The system shall accept an input directory and output file path through the CLI. | Must |
| FR-ING-002 | The system shall discover supported files recursively or non-recursively according to a configurable setting; non-recursive is the MVP default. | Must |
| FR-ING-003 | PDF shall be supported. DOCX and TXT should be supported as bonus formats. | Must/Should |
| FR-ING-004 | Unsupported files shall be skipped and reported without failing the batch. | Must |
| FR-ING-005 | Every discovered supported file shall receive a unique internal ID and content hash. | Must |
| FR-ING-006 | Exact duplicate files shall be detected by SHA-256 hash and reported without being scored twice. | Must |
| FR-ING-007 | An empty, encrypted, corrupt, or unreadable file shall produce a per-file failure record. | Must |
| FR-ING-008 | The application shall preserve the source filename in the result for auditability. | Must |

### 9.2 Text parsing and normalization

| ID | Requirement | Priority |
|---|---|---|
| FR-PAR-001 | PDF text shall be extracted page by page where possible. | Must |
| FR-PAR-002 | Text normalization shall repair common whitespace and Unicode issues without changing substantive content. | Must |
| FR-PAR-003 | Page boundaries should be retained when available to improve evidence traceability. | Should |
| FR-PAR-004 | A resume with partially extractable content shall continue if sufficient non-empty text remains. | Must |
| FR-PAR-005 | The system shall impose a configurable maximum text length before any LLM call. | Must |
| FR-PAR-006 | Parser implementations shall conform to a common interface so formats can be added independently. | Must |

### 9.3 Candidate information extraction

| ID | Requirement | Priority |
|---|---|---|
| FR-EXT-001 | The system shall attempt to extract candidate name, email, GitHub profile, skills, projects, education, and work/internship evidence. | Must |
| FR-EXT-002 | Email and GitHub URLs shall use deterministic extraction before any model-assisted extraction. | Must |
| FR-EXT-003 | GitHub URLs shall be normalized to a canonical profile URL and username where possible. | Must |
| FR-EXT-004 | Extracted skills shall be normalized for case and common aliases while preserving the original evidence. | Must |
| FR-EXT-005 | The system shall retain short evidence snippets and an optional source section/page for material claims. | Must |
| FR-EXT-006 | Missing candidate fields shall not fail processing. | Must |
| FR-EXT-007 | Unknown candidate names shall fall back to a stable filename-derived display value. | Must |

### 9.4 Hard eligibility

| ID | Requirement | Priority |
|---|---|---|
| FR-ELG-001 | A candidate shall be eligible only if both contextual Python evidence and contextual AI evidence are present. | Must |
| FR-ELG-002 | Python evidence may come from skills, projects, internships, work, backend implementation, or implementation-language statements. | Must |
| FR-ELG-003 | AI evidence may include LLMs, RAG, embeddings/vector search, agents, tool calling, orchestration, evaluation, LangChain, LangGraph, LlamaIndex, Google ADK, or equivalent custom implementations. | Must |
| FR-ELG-004 | Java, JavaScript, React, or Next.js shall not be negative eligibility signals when Python and AI requirements are met. | Must |
| FR-ELG-005 | Keyword occurrences in unrelated contexts shall not count as genuine evidence. | Must |
| FR-ELG-006 | The final eligibility decision shall be made by deterministic code using validated extracted evidence. | Must |
| FR-ELG-007 | Rejected candidates shall list one or both canonical reasons: no Python evidence; no AI/agentic evidence. | Must |
| FR-ELG-008 | Rejected candidates shall retain matched skills and available evidence for reviewer inspection. | Must |
| FR-ELG-009 | Eligibility shall not depend on GitHub availability or score. | Must |

### 9.5 Candidate scoring

| ID | Requirement | Priority |
|---|---|---|
| FR-SCR-001 | Only eligible candidates shall receive a ranking score. | Must |
| FR-SCR-002 | The baseline category weights shall total 100 points before penalties. | Must |
| FR-SCR-003 | Each category score shall be capped at its configured maximum. | Must |
| FR-SCR-004 | Resume evidence shall outweigh skill-section keyword presence. | Must |
| FR-SCR-005 | Thin LLM/API wrappers shall receive a 5–15 point penalty proportional to shallowness. | Must |
| FR-SCR-006 | Tutorial-style projects without implementation detail or ownership evidence shall receive a configurable penalty. | Must |
| FR-SCR-007 | Framework-name mentions alone shall not earn full implementation-depth points. | Must |
| FR-SCR-008 | The final score shall equal the sum of category scores minus explicit penalties, bounded to 0–100. | Must |
| FR-SCR-009 | Each score component shall include concise evidence or a reason. | Must |
| FR-SCR-010 | All score weights and thresholds shall live in configuration rather than integration code. | Must |

### 9.6 GitHub enrichment

| ID | Requirement | Priority |
|---|---|---|
| FR-GH-001 | GitHub enrichment shall run when a valid public profile is found. | Must |
| FR-GH-002 | The system shall use public GitHub APIs or equivalent public data only. | Must |
| FR-GH-003 | The GitHub contribution shall be capped at 10 points. | Must |
| FR-GH-004 | Recent activity shall contribute at most 5 points. | Must |
| FR-GH-005 | Maintained and Python/AI-relevant repositories shall contribute at most 5 points. | Must |
| FR-GH-006 | Missing, private, invalid, rate-limited, or unavailable profiles shall not reject a candidate or fail the batch. | Must |
| FR-GH-007 | GitHub failures shall produce a structured status and human-readable summary. | Must |
| FR-GH-008 | API responses shall be cached by username during the batch. | Must |
| FR-GH-009 | An optional token shall be read only from `GITHUB_TOKEN`. | Must |
| FR-GH-010 | The implementation shall use timeouts and bounded concurrency. | Must |
| FR-GH-011 | The system should inspect a bounded set of owned, non-fork public repositories for high-confidence secret-exposure signals. | Should |
| FR-GH-012 | GitHub security-hygiene deductions shall be limited to the GitHub category and shall not make the GitHub score negative. | Must |
| FR-GH-013 | The system shall not test, authenticate with, redeem, or otherwise use any suspected credential. | Must |
| FR-GH-014 | Suspected secret values shall be redacted immediately and shall never appear in output, logs, exceptions, or model prompts. | Must |
| FR-GH-015 | Placeholder files, `.env.example`, documentation samples, test fixtures, environment-variable references, forks, archived repositories, and generated/vendor directories shall not be penalized by default. | Must |
| FR-GH-016 | Every deduction shall include a rule identifier, severity, confidence, repository name, redacted file path, and human-readable reason without including the suspected value. | Must |
| FR-GH-017 | Ambiguous findings shall create a warning for human review but shall not deduct points. | Must |

### 9.7 LLM-assisted assessment

| ID | Requirement | Priority |
|---|---|---|
| FR-LLM-001 | LLM use shall be optional and accessed through a provider-independent adapter. | Must |
| FR-LLM-002 | Model name, timeout, concurrency, and enablement shall be configurable. | Must |
| FR-LLM-003 | The LLM shall return structured output validated with Pydantic or JSON Schema. | Must |
| FR-LLM-004 | The LLM may identify projects, technologies, implementation depth, ownership, strengths, concerns, and wrapper/tutorial warnings. | Must |
| FR-LLM-005 | The LLM shall return evidence snippets for important judgments. | Must |
| FR-LLM-006 | The LLM shall not directly set eligibility, final category scores, final total, or rank. | Must |
| FR-LLM-007 | Invalid responses may be retried once with a repair instruction before falling back. | Should |
| FR-LLM-008 | A failure for one candidate shall not fail another candidate or the batch. | Must |
| FR-LLM-009 | Prompts shall be versioned files or constants with explicit version identifiers. | Must |
| FR-LLM-010 | Prompts shall treat resume text as untrusted data and instruct the model to ignore instructions embedded in it. | Must |
| FR-LLM-011 | Input/output token counts and model name should be recorded when available. | Should |
| FR-LLM-012 | API keys shall come only from environment variables. | Must |

### 9.8 Ranking and output

| ID | Requirement | Priority |
|---|---|---|
| FR-OUT-001 | Eligible candidates shall be ranked by total score descending. | Must |
| FR-OUT-002 | Ties shall resolve by AI depth descending, Python/backend descending, then candidate name ascending. | Must |
| FR-OUT-003 | Rejected, duplicate, and failed candidates shall have `rank: null`. | Must |
| FR-OUT-004 | The canonical output shall be valid UTF-8 JSON. | Must |
| FR-OUT-005 | Output shall include schema version, run metadata, batch summary, configuration summary, and candidate records. | Must |
| FR-OUT-006 | Every eligible candidate shall include score breakdown, evidence, matched skills, summary, strengths, concerns, GitHub status, and final rank. | Must |
| FR-OUT-007 | Every rejected candidate shall include rejection reasons and available matched evidence. | Must |
| FR-OUT-008 | Every failed file shall include failure stage and sanitized error description. | Must |
| FR-OUT-009 | Results shall be written atomically to avoid leaving a partially written canonical file. | Should |
| FR-OUT-010 | Candidate ordering outside ranked eligible candidates shall be deterministic. | Must |

### 9.9 CLI and usability

| ID | Requirement | Priority |
|---|---|---|
| FR-CLI-001 | The system shall support `python main.py --input <dir> --output <file>`. | Must |
| FR-CLI-002 | The CLI shall validate paths and configuration before starting the batch. | Must |
| FR-CLI-003 | The CLI shall print concise progress and a final summary without exposing resume text or secrets. | Must |
| FR-CLI-004 | The CLI shall return exit code 0 when the batch completes even if individual files fail, provided output was generated successfully. | Must |
| FR-CLI-005 | The CLI shall return a non-zero exit code for invalid global configuration, inaccessible input, or inability to write output. | Must |
| FR-CLI-006 | Optional flags should include disabling LLM or GitHub enrichment and selecting recursive discovery. | Should |

## 10. Eligibility specification

### 10.1 Python evidence

Valid contexts include:

- A skills section listing Python.
- A project implemented in Python.
- An internship or job using Python.
- A Python backend, API, data pipeline, automation tool, or ML implementation.

Non-qualifying examples by themselves include:

- A course title containing Python with no applied work.
- A negative statement such as “no Python experience.”
- A keyword embedded in a URL or unrelated reference.
- A technology comparison that does not claim candidate usage.

### 10.2 AI or agentic evidence

Valid contexts include:

- An AI, ML, LLM, RAG, embedding, vector-search, or agent project.
- Use of an agent/RAG framework in skills, work, or projects.
- A custom retrieval, tool-calling, multi-agent, evaluation, or orchestration implementation.

Eligibility is intentionally a minimum bar. A credible framework or implementation mention may pass the filter, while scoring determines whether the work is shallow or substantial.

### 10.3 Decision record

The eligibility result shall contain:

- `eligible`
- `python_evidence`
- `ai_evidence`
- `rejection_reasons`
- `matched_skills`
- `decision_method`

## 11. Scoring specification

### 11.1 AI / Agentic / RAG project depth: 40 points

| Signal | Maximum | Guidance |
|---|---:|---|
| Meaningful AI problem and implementation | 8 | AI is central to the project, not decorative. |
| Retrieval, embeddings, vector search, or grounding | 8 | Reward implemented data flow and retrieval details. |
| Agents, tools, state, or orchestration | 8 | Reward functional workflows over framework mentions. |
| Data processing and application logic | 6 | Reward ingestion, transformation, routing, or domain logic. |
| Evaluation, reliability, or guardrails | 5 | Reward tests, evals, tracing, retries, safety, or quality measurement. |
| Ownership, complexity, and measurable impact | 5 | Reward clear implementation ownership and meaningful outcomes. |

### 11.2 Python and backend engineering: 30 points

| Signal | Maximum | Guidance |
|---|---:|---|
| Python implementation depth | 10 | Applied Python in projects or work outweighs keyword-only evidence. |
| APIs and backend frameworks | 8 | FastAPI, Flask, Django, API design, validation, or service logic. |
| Data persistence | 5 | PostgreSQL, SQL, Redis, ORM usage, schema or data-model design. |
| Async or concurrency | 4 | Async I/O, workers, concurrency control, or parallel processing. |
| Ownership and implementation detail | 3 | Clear responsibility and non-trivial technical detail. |

### 11.3 Cloud, deployment, and full stack: 15 points

| Signal | Maximum | Guidance |
|---|---:|---|
| Cloud platform use | 5 | GCP is preferred by the assignment; equivalent deployment evidence is useful. |
| Docker/containerization | 4 | Reward applied containerization over a skill mention. |
| Deployment or CI/CD | 3 | Hosting, pipelines, infrastructure, or release evidence. |
| End-to-end/full-stack integration | 3 | React/Next.js or equivalent connected to a meaningful backend. |

### 11.4 GitHub activity: 10 points

| Signal | Maximum | Guidance |
|---|---:|---|
| Recent public activity | 5 | Score recency and consistency, not raw event volume alone. |
| Maintained and relevant repositories | 5 | Reward non-fork Python/AI repositories with recent maintenance. |

Default recent-activity guidance:

- 5 points: meaningful public activity within approximately 30 days.
- 4 points: activity within approximately 90 days.
- 2–3 points: activity within approximately 180 days.
- 1 point: older but still visible activity.
- 0 points: no public activity or enrichment unavailable.

GitHub points must not be negative.

#### 11.4.1 Repository security-hygiene adjustment

After calculating the 0–10 positive GitHub score, the system may deduct up to 5 GitHub points for high-confidence evidence that a candidate-owned, non-fork public repository exposes credentials or private key material.

```text
github_score = max(
    0,
    recent_activity_points
    + relevant_repository_points
    - github_security_penalty
)
```

| Finding | Suggested deduction | Minimum confidence |
|---|---:|---|
| Public private-key material or high-confidence provider credential pattern in application configuration/source | 4–5 | High |
| Tracked `.env`-style file containing one or more non-placeholder secrets | 3–4 | High |
| Single probable hard-coded credential with strong assignment/context evidence | 1–2 | High |
| Ambiguous token-like string, documentation sample, test fixture, or placeholder | 0; warning only | Any |

Rules for this adjustment:

- Inspect only a bounded set of recently maintained or otherwise relevant candidate-owned public repositories; default maximum: 5.
- Inspect the default branch only in the MVP. Do not scan full Git history.
- Exclude forks, archived repositories, dependency/vendor trees, generated files, build output, and binary files.
- Prefer high-confidence patterns supported by filename and assignment context rather than entropy alone.
- Treat `.env.example`, placeholder values, redacted strings, and environment-variable lookups such as `os.getenv(...)` as safe unless separate high-confidence evidence shows a real embedded credential.
- Never call a provider to determine whether a suspected key is active.
- Redact suspected values in memory immediately after classification and retain only safe metadata.
- A medium- or low-confidence finding may create a concern for manual review but must not reduce points.
- The maximum deduction is 5 points regardless of the number of findings, preventing this lightweight check from dominating the overall candidate score.

The `score_breakdown.github` value is the post-adjustment score. `github.security_hygiene.penalty` exposes the deduction separately so the arithmetic remains auditable. This adjustment is distinct from project-quality penalties.

### 11.5 Engineering depth: 5 points

Award up to one point each for demonstrated:

- Testing or quality automation.
- Caching or performance optimization.
- Queues, workers, or concurrency architecture.
- Observability, resilience, or failure handling.
- Clear architecture, security, or scalability decisions.

### 11.6 Penalties

| Condition | Deduction |
|---|---:|
| Thin LLM/API wrapper with little supporting logic | 5–15 |
| Tutorial or clone project with little ownership evidence | 5–10 |
| Unverifiable or internally inconsistent implementation claims | 0–5 |

Penalties must include a reason and evidence. The total is calculated as:

```text
total_score = clamp(
    ai_project_depth
    + python_backend
    + cloud_fullstack
    + github
    + engineering_depth
    - total_penalties,
    0,
    100
)
```

The same factual signal should not be counted repeatedly across categories unless it independently demonstrates different competencies.

## 12. Backend architecture

### 12.1 Architectural style

Use a CLI-first modular monolith with four layers:

1. **Interface layer:** CLI argument parsing and user-facing summary.
2. **Application layer:** batch orchestration and use-case coordination.
3. **Domain layer:** eligibility, scoring, penalties, and ranking.
4. **Adapter layer:** resume parsers, LLM provider, GitHub client, and JSON writer.

The domain layer must not import provider SDKs or perform network calls.

### 12.2 Component diagram

```text
CLI
 │
 ▼
PipelineService
 ├── FileDiscovery ──► DuplicateDetector
 ├── ParserRegistry ─► PDF / DOCX / TXT parsers
 ├── CandidateExtractor
 ├── EligibilityEngine
 │     ├── rejected ─────────────────────────┐
 │     └── eligible                          │
 ├── ProjectAssessor (optional LLM)          │
 ├── GitHubEnricher (optional)               │
 ├── ScoringEngine                           │
 ├── RankingService                          │
 └── ResultWriter ◄──────────────────────────┘
```

### 12.3 Proposed package layout

```text
resume-screener/
├── main.py
├── src/resume_screener/
│   ├── config.py
│   ├── models.py
│   ├── application/pipeline.py
│   ├── ingestion/
│   │   ├── discovery.py
│   │   ├── base.py
│   │   ├── pdf_parser.py
│   │   ├── docx_parser.py
│   │   └── txt_parser.py
│   ├── extraction/
│   │   ├── normalizer.py
│   │   ├── contact.py
│   │   ├── skills.py
│   │   └── projects.py
│   ├── domain/
│   │   ├── eligibility.py
│   │   ├── scoring.py
│   │   ├── penalties.py
│   │   └── ranking.py
│   ├── integrations/
│   │   ├── llm/base.py
│   │   ├── llm/provider.py
│   │   └── github/client.py
│   └── output/json_writer.py
├── tests/
├── pyproject.toml
├── .env.example
└── README.md
```

### 12.4 Runtime data flow

```text
ResumeFile
  → ParsedResume
  → CandidateProfile
  → EligibilityDecision
  → CandidateAssessment
  → CandidateResult
  → RankedBatchResult
```

Each transition uses a typed Pydantic model. Failures become data records rather than uncaught batch-level exceptions.

### 12.5 Concurrency

- File parsing may run sequentially or in a small bounded worker pool.
- LLM calls use asynchronous bounded concurrency; default maximum: 3.
- GitHub calls use asynchronous bounded concurrency; default maximum: 5.
- Concurrency limits must be configurable.
- No unbounded task creation is permitted.

### 12.6 Caching

The MVP uses in-memory per-run caches:

- GitHub response keyed by normalized username.
- LLM assessment keyed by resume content hash, model, and prompt version.

Persistent caching is a future enhancement and is not required.

## 13. Data model and output contract

### 13.1 Top-level result

```json
{
  "schema_version": "1.0",
  "run": {
    "run_id": "uuid",
    "started_at": "ISO-8601 timestamp",
    "completed_at": "ISO-8601 timestamp",
    "input_directory": "./resumes",
    "llm_enabled": true,
    "github_enabled": true
  },
  "batch_summary": {
    "total_discovered": 50,
    "supported": 50,
    "successfully_parsed": 48,
    "eligible": 18,
    "rejected": 30,
    "duplicates": 0,
    "failed": 2
  },
  "candidates": []
}
```

### 13.2 Candidate result

```json
{
  "candidate_id": "stable-id",
  "source_file": "candidate_01.pdf",
  "status": "eligible",
  "rank": 1,
  "candidate_name": "Asha Rao",
  "email": "asha@example.com",
  "github_url": "https://github.com/example",
  "eligible": true,
  "rejection_reasons": [],
  "matched_skills": ["Python", "FastAPI", "LangGraph"],
  "eligibility_evidence": {
    "python": ["Built an asynchronous FastAPI service in Python"],
    "ai": ["Implemented a stateful retrieval agent using LangGraph"]
  },
  "score_breakdown": {
    "ai_project_depth": 35,
    "python_backend": 27,
    "cloud_fullstack": 12,
    "github": 8,
    "engineering_depth": 4,
    "penalties": 0,
    "total": 86
  },
  "score_evidence": [],
  "project_summary": "Built a stateful agentic workflow with retrieval and tool calling.",
  "github": {
    "status": "success",
    "summary": "Recently active with maintained Python repositories.",
    "security_hygiene": {
      "status": "checked",
      "repositories_checked": 3,
      "penalty": 0,
      "findings": []
    }
  },
  "strengths": ["Strong agentic project", "Async backend experience"],
  "concerns": ["Limited Redis evidence"],
  "warnings": []
}
```

### 13.3 Candidate statuses

- `eligible`
- `rejected`
- `duplicate`
- `failed`

The `status` value is authoritative. The `eligible` field remains for convenient filtering.

## 14. External integration contracts

### 14.1 LLM adapter

```python
class ProjectAssessor(Protocol):
    async def assess(
        self,
        profile: CandidateProfile,
    ) -> ProjectAssessment:
        ...
```

The adapter is responsible for provider calls, timeout handling, token accounting, response parsing, and schema validation. It is not responsible for score calculation.

### 14.2 GitHub adapter

```python
class GitHubEnricher(Protocol):
    async def enrich(self, username: str) -> GitHubAssessment:
        ...
```

The client should inspect only the minimum public endpoints required for profile, repository, and recent-activity signals. It must identify rate-limit responses distinctly from missing profiles.

The GitHub adapter may also expose a bounded repository-security hygiene scan. The scanner shall return safe metadata only:

```python
class RepositorySecurityFinding(BaseModel):
    rule_id: str
    severity: Literal["warning", "high", "critical"]
    confidence: Literal["low", "medium", "high"]
    repository: str
    file_path: str
    secret_type: str
    redacted_fingerprint: str | None
    reason: str
```

The scanner must never return the matched credential value. A `redacted_fingerprint`, if used for deduplication, must be a short non-reversible hash rather than a masked prefix that reveals secret characters.

## 15. Configuration

Configuration shall be read from environment variables and CLI flags, validated once at startup, and passed into services explicitly.

Suggested `.env.example`:

```dotenv
LLM_ENABLED=true
LLM_PROVIDER=gemini
LLM_MODEL=gemini-3.5-flash-lite
GEMINI_API_KEY=
LLM_TIMEOUT_SECONDS=45
LLM_MAX_CONCURRENCY=2

GITHUB_ENABLED=true
GITHUB_TOKEN=
GITHUB_TIMEOUT_SECONDS=10
GITHUB_MAX_CONCURRENCY=5
GITHUB_SECURITY_SCAN_ENABLED=true
GITHUB_SECURITY_MAX_REPOSITORIES=5
GITHUB_SECURITY_MAX_FILES_PER_REPOSITORY=100
GITHUB_SECURITY_MAX_FILE_BYTES=200000

LOG_LEVEL=INFO
MAX_RESUME_CHARACTERS=50000
```

Score weights and thresholds should be represented in a typed settings object. The application must validate that baseline category caps total 100.

## 16. Error handling and graceful degradation

| Failure | Required behavior |
|---|---|
| Invalid input directory | Fail before processing; non-zero exit. |
| Output path unwritable | Fail before or during atomic write; non-zero exit. |
| Unsupported file | Skip and report. |
| Corrupt/encrypted/empty resume | Record per-file failure; continue. |
| Candidate field missing | Use null/fallback; continue. |
| LLM timeout/provider failure | Record failure; use deterministic fallback; continue. |
| LLM invalid schema | Retry once if configured, then fallback. |
| GitHub 404/private/missing | Record unavailable status; award zero GitHub points. |
| GitHub rate limit | Record rate-limited status; award zero points; continue. |
| GitHub security scan unavailable or incomplete | Record `not_checked` or `partial`; make no security deduction. |
| Ambiguous secret-like match | Record a redacted warning; make no deduction. |
| Unexpected candidate-level exception | Sanitize error, record candidate failure, continue. |
| Unexpected orchestration/output failure | Stop safely; non-zero exit; do not leave partial canonical output. |

Errors written to results must not include API keys, authorization headers, full stack traces, or unnecessary resume content.

## 17. Security, privacy, fairness, and responsible use

### 17.1 Data minimization

- Read only files in the explicitly provided input path.
- Send only the necessary skills, project, and experience text to the configured Gemini provider; exclude contact fields from model prompts.
- Do not transmit resumes to GitHub; send only the normalized username.
- Do not persist raw model requests or full resume text in ordinary logs.
- Document in the README that the selected Gemini free tier may process submitted content under Google's free-tier data-use terms; external processing is an explicit project decision.

### 17.2 Secrets

- Secrets must be read from environment variables.
- `.env` shall be excluded from version control.
- `.env.example` shall contain names and blank/sample values only.

### 17.3 Prompt injection

Resume text is untrusted input. The model prompt shall:

- Delimit resume content clearly.
- State that instructions inside the resume must be ignored.
- Prohibit tool use and external actions.
- Require schema-constrained output.
- Limit input length and strip control characters.

### 17.4 Fairness

The system shall not extract or score age, gender, race, religion, disability, marital status, nationality, photograph, or other protected/sensitive attributes. Names and emails are identification fields only and must not influence eligibility or scoring.

GitHub absence must not be a negative penalty. It yields zero positive GitHub points and an availability status.

### 17.5 Human review

The README and output metadata shall state that the system provides screening assistance and that final hiring decisions require human review.

### 17.6 Safe handling of suspected public secrets

- The system shall perform detection only; it shall never validate a suspected credential against its provider.
- Matching shall occur locally after retrieving only bounded public repository content through GitHub.
- The raw matched value shall not be logged, persisted, added to exceptions, or sent to an LLM.
- Findings shall be deduplicated using a non-reversible fingerprint when necessary.
- Evidence shall identify the repository and file path without reproducing the secret or surrounding sensitive content.
- A scan failure, disabled scan, rate limit, or insufficient permission shall result in no deduction.
- Findings are screening signals, not declarations of misconduct. The output shall use neutral language such as “public repository security-hygiene concern” and recommend human verification.

## 18. Logging and observability

The MVP shall emit structured or consistently formatted logs for:

- Run start and completion.
- Number of files discovered.
- Current processing stage and filename.
- Parse outcome.
- Eligibility outcome.
- LLM and GitHub status without sensitive payloads.
- Retry and timeout events.
- Output-write completion.

Recommended run-level metrics:

- Total duration.
- Per-stage duration.
- Parsed/rejected/eligible/failed counts.
- LLM request count, validation failures, token usage, and fallback count.
- GitHub success, unavailable, and rate-limit counts.
- Repository-security scan coverage, redacted finding counts by rule/severity, and total GitHub deductions; never matched values.

## 19. Performance requirements

- The system shall process approximately 50 text-based resumes in a single run on a typical development machine.
- Deterministic parsing and scoring should complete in under two minutes for 50 ordinary resumes, excluding external service latency.
- With network enrichment enabled, the target total batch duration is under ten minutes under normal provider conditions.
- External requests shall use explicit timeouts.
- Duplicate resumes shall not trigger duplicate LLM or GitHub requests.
- Memory use should remain proportional to the batch size and extracted text; loading 50 ordinary resumes in memory is acceptable.

These are engineering targets, not hard guarantees across all PDF layouts and providers.

## 20. Testing strategy

### 20.1 Unit tests

Required cases:

- Python + AI candidate passes eligibility.
- Python-only candidate fails with missing AI reason.
- AI-only candidate fails with missing Python reason.
- JavaScript/Java/React alongside Python + AI does not cause rejection.
- Negated or unrelated Python mentions do not count.
- AI framework mention passes the minimum bar but does not earn full depth points.
- Thin LLM wrapper receives a penalty.
- Tutorial-style project receives an appropriate penalty.
- Category and total caps are enforced.
- Ranking and tie-breaking are deterministic.
- GitHub unavailability returns zero points without affecting eligibility.
- A high-confidence private-key or provider-token fixture produces the configured GitHub deduction and redacted evidence.
- `.env.example`, placeholders, environment-variable lookups, documentation samples, forks, and ambiguous token-like strings produce no deduction.
- GitHub security penalties cannot exceed 5 and cannot make the GitHub score negative.
- Suspected credential values never appear in serialized results or captured logs.
- Duplicate hashes are detected.

### 20.2 Integration tests

- A synthetic directory containing valid, rejected, duplicate, malformed, and unsupported files produces the correct batch summary.
- Fake LLM and GitHub adapters generate a complete valid output.
- LLM schema failure triggers fallback.
- GitHub rate-limit response is represented correctly.
- Output JSON validates against the expected model/schema.

### 20.3 Prompt regression tests

Maintain a small synthetic set covering:

- Substantial RAG project.
- Tool-calling agent.
- Thin API wrapper.
- Framework-name-only resume.
- Resume containing prompt-injection instructions.

Assertions should focus on schema validity, required evidence, wrapper warnings, and bounded enum values—not exact natural-language wording.

### 20.4 Manual acceptance test

Run the CLI on a mixed sample batch, inspect the top candidates, verify at least two rejected candidates and one integration failure, and manually recompute one final score from its breakdown.

## 21. Acceptance criteria

The MVP is accepted when all of the following are true:

1. The documented CLI command runs against a resume directory.
2. PDF resumes are supported.
3. The batch does not stop because one file is invalid.
4. Exact duplicates are detected.
5. Eligibility requires both Python and AI evidence.
6. Rejection reasons are explicit and evidence-backed where possible.
7. Only eligible candidates receive scores and ranks.
8. The five scoring categories use caps of 40, 30, 15, 10, and 5.
9. Thin-wrapper and tutorial penalties are explicit.
10. GitHub enrichment is capped at 10 and fails gracefully.
11. High-confidence public secret exposure may deduct at most 5 GitHub points; ambiguous or incomplete scans deduct nothing.
12. Suspected secret values are never validated, logged, persisted, or sent to an LLM.
13. LLM output is structured, validated, provider-isolated, and optional.
14. API keys are not hard-coded.
15. Final JSON includes every candidate and the batch summary.
16. Ranking is deterministic given identical validated assessments.
17. Focused eligibility, scoring, ranking, security-hygiene, and failure tests pass.
18. README includes setup, execution, output explanation, Design Decisions, and If I Had More Time.
19. `.env.example` contains no secrets.

## 22. Evaluation-rubric traceability

| Evaluation area | Product coverage |
|---|---|
| Ingestion + hard filtering correctness | Parser registry, per-file failures, duplicate detection, contextual Python + AI hard filter. |
| Ranking & project-quality logic | Explicit sub-score rules, source evidence, wrapper/tutorial penalties, deterministic calculation. |
| AI/LLM implementation | Provider adapter, structured output, validation, prompt versioning, injection resistance, fallback. |
| Code quality & architecture | Modular monolith, typed contracts, pure domain logic, dependency inversion. |
| GitHub enrichment | Public lightweight signals, 10-point cap, bounded security-hygiene adjustment, caching, timeout/rate-limit handling. |
| Reliability & tests | Failure isolation, bounded concurrency, unit/integration/prompt tests. |
| README & usability | CLI-first workflow, `.env.example`, design decisions, future improvements. |

## 23. Delivery plan for the 2–3 hour time-box

### Phase 1: foundation and ingestion

- Create project structure, settings, models, and CLI.
- Implement file discovery, hashing, PDF parsing, and text normalization.
- Add initial ingestion tests.

### Phase 2: extraction, eligibility, and scoring

- Implement deterministic extraction.
- Implement contextual hard filters.
- Implement score categories, caps, evidence, penalties, and ranking.
- Add core domain tests.

### Phase 3: integrations

- Add GitHub client with cache, timeout, and failure statuses.
- Add one structured LLM adapter and deterministic fallback.
- Add fake adapters for tests.

### Phase 4: output and hardening

- Generate canonical JSON and batch summary.
- Add integration tests and sample synthetic resumes.
- Complete README, `.env.example`, Design Decisions, and If I Had More Time.
- Run an end-to-end verification.

If time becomes constrained, DOCX/TXT parsing, persistent caching, FastAPI, and richer terminal reporting are deferred before any core requirement.

## 24. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| PDF layout causes poor extraction | Incorrect evidence or missing fields | Normalize conservatively, preserve raw text, fail visibly when content is insufficient. |
| Keyword rules produce false positives | Irrelevant candidates pass | Require contextual evidence and down-weight keyword-only claims. |
| LLM output is inconsistent | Unstable assessment | Structured schema, low-variance prompt, validation, one repair attempt, deterministic scoring. |
| Resume prompt injection | Model behavior hijacked | Treat resume as data, explicit delimiters, no tools, schema validation. |
| GitHub API rate limit | Missing enrichment | Optional token, cache, bounded concurrency, zero-point graceful fallback. |
| GitHub disadvantages private contributors | Unfair ranking | Positive-only signal, no eligibility impact, explicit unavailable status. |
| Secret detection produces false positives | Unfair GitHub deduction | High-confidence threshold, context-aware exclusions, deduction cap, redacted evidence, and warning-only treatment for ambiguity. |
| Suspected secret is accidentally propagated | Security/privacy incident | Never validate credentials; redact on detection; exclude raw matches from logs, output, errors, and LLM prompts. |
| Duplicate evidence inflates scores | Misleading rank | Evidence deduplication and rules against repeated counting. |
| Time-box encourages overengineering | Incomplete core pipeline | CLI-first modular monolith; defer API/UI/database/vector store. |
| PII leaks through logs or provider calls | Privacy issue | Minimize payloads, redact logs, document external-model behavior. |

## 25. Design decisions

### 25.1 Modular monolith over microservices

The workload is a small local batch. A modular monolith gives clear boundaries and testability without queues, service discovery, deployments, or distributed failure modes.

### 25.2 Hybrid rules plus LLM

Rules are best for hard requirements, arithmetic, caps, and stable ranking. An LLM is useful for interpreting inconsistent project descriptions and judging implementation depth. The hybrid design uses each approach where it is strongest.

### 25.3 Evidence-first assessment

Every material decision carries source evidence. This makes the system debuggable and lets reviewers challenge an assessment without reverse-engineering hidden model reasoning.

### 25.4 GitHub as positive-only enrichment

Public GitHub activity can provide useful engineering signals but is incomplete and socially uneven. It adds at most 10 points and never controls eligibility. A bounded security-hygiene adjustment may reduce only points earned within that GitHub category when high-confidence public credential exposure is found. It does not create a negative overall GitHub contribution, and unavailable or ambiguous scans never deduct points.

### 25.5 JSON over CSV

JSON naturally represents nested evidence, category breakdowns, errors, and enrichment statuses. CSV may be added later as a secondary export.

## 26. If I Had More Time

- Add OCR and layout-aware extraction for scanned or complex PDFs.
- Add persistent, content-addressed caching for model and GitHub responses.
- Build an evaluation dataset with labeled eligibility and ranking judgments, then measure precision, recall, and ranking agreement.
- Add a small FastAPI job interface and human-review workflow using the same application service.

## 27. Future enhancements

- Configurable job descriptions and reusable scoring profiles.
- Human overrides with an audit trail.
- Secondary CSV or HTML report.
- Local-model support for privacy-sensitive environments.
- Calibrated confidence and “needs review” routing for ambiguous cases.
- Bias and outcome monitoring using approved, aggregate evaluation processes.
- Persistent run history and result comparison.
- CI pipeline with linting, type checking, tests, and JSON-schema validation.

## 28. Resolved implementation inputs

The following implementation decisions are confirmed:

- Use the external Gemini API with the stable `gemini-3.5-flash-lite` model.
- External processing of relevant resume text is permitted for this assignment. Apply data minimization by excluding names, emails, phone numbers, addresses, and unrelated sections from model prompts where practical.
- Use schema-constrained structured output, a 45-second timeout, a maximum concurrency of 2, rate-limit-aware retries, and deterministic per-candidate fallback.
- The target dataset of approximately 50 resumes is available; its filesystem path will be supplied when implementation begins.
- Use the user's GitHub token through `GITHUB_TOKEN`, with least-privileged public read access, adaptive request budgeting, and no token logging.
- Preserve the complete extracted email address only in the private local `results.json` output.
- Never use email as a scoring signal, print it in logs, send it to GitHub, or include it in a model prompt.
- A redacted export may mask emails for sharing or demonstration purposes.

The deterministic fallback remains available if Gemini is unavailable, rate-limited, returns invalid output, or fails for an individual candidate.

## 29. Definition of done

The work is complete when source code, tests, README, dependency manifest, `.env.example`, and a generated `results.json` are present; the documented command succeeds on the supplied resume set; acceptance criteria pass; and a reviewer can trace every eligibility and scoring decision to explicit evidence or a clearly recorded failure/fallback state.
