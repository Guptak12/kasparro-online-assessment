# AI Resume Screening & Ranking

A CLI-first Python application for screening roughly 50 SDE intern resumes. It extracts candidate
evidence, applies the required Python + AI eligibility gate, scores only eligible candidates,
optionally enriches them with Gemini and public GitHub signals, and writes one auditable JSON file.

The application is deliberately a modular monolith: it is easy to run and review, but its parsing,
eligibility, assessment, GitHub, scoring, and output boundaries remain independently testable.

## What it does

- Parses PDF, DOCX, and TXT resumes; one malformed file cannot stop the batch.
- Extracts name, email, GitHub URL, skills, and contextual evidence.
- Requires both reliable Python evidence and reliable AI/ML evidence.
- Scores eligible candidates with the assessment weights:
  - AI/project depth: 40
  - Python/backend: 30
  - Cloud/full-stack: 15
  - GitHub: 10
  - Engineering depth: 5
- Applies explicit thin-wrapper/tutorial penalties, capped at 20 points.
- Uses Gemini structured output for project-depth classification when configured, with a local
  deterministic fallback.
- Assesses public GitHub activity and repository relevance. A bounded, high-confidence public-file
  scan can deduct at most 5 GitHub points for exposed credentials; incomplete scans never deduct.
- Produces ranked eligible candidates followed by rejected, duplicate, and failed records.

Gemini does **not** decide eligibility, numeric scores, or rank. GitHub does **not** affect
eligibility. Those decisions remain deterministic and inspectable in Python.

## Quick start

Requires Python 3.11 or later.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

Add keys to `.env` if you want the optional integrations:

```dotenv
GEMINI_API_KEY=your_key
GITHUB_TOKEN=your_fine_grained_token
```

Never commit `.env`. A GitHub token is strongly recommended for a 50-resume run: authenticated
requests normally receive a much larger primary rate-limit budget than anonymous requests. The
scanner only requests public candidate repositories and needs no write permission.

Run the batch:

```bash
python main.py --input ./resumes --output ./output/results.json
```

Run fully offline/deterministically:

```bash
python main.py --input ./resumes --output ./output/results.json --no-llm --no-github
```

Other useful switches:

```text
--recursive          Search nested directories
--no-security-scan   Keep GitHub scoring but disable secret-hygiene checks
--compact            Write compact JSON
--env-file PATH      Read a different environment file
```

The input path may also be supplied positionally: `python main.py ./resumes`.

## Output

`results.json` contains:

- `schema_version`, run timestamps, input/output locations, and non-secret configuration summary;
- reconciled totals for discovered, supported, parsed, eligible, rejected, duplicate, and failed
  files;
- every supported candidate outcome;
- private local contact email, matched skills, eligibility evidence, project assessment, score
  breakdown, GitHub status, warnings/failures, and final rank where applicable.

Only eligible candidates have a score and rank. Rank ordering is total score, AI score,
Python/backend score, then normalized candidate name. Output is validated with Pydantic before an
atomic file replacement, so a partially written result is not left behind.

## Scoring and evidence

The 100-point baseline is calculated from bounded sub-signals. Project-depth labels map to fixed
multipliers (`none`, `basic`, `applied`, `advanced`); resume evidence is classified as incidental,
skill-only, applied, or advanced. Keyword-only or coursework-only claims do not satisfy the hard
gate. The output preserves the evidence used for the gate and the structured assessment used for
scoring.

The optional project-quality deduction is separate from GitHub security hygiene:

```text
total = clamp(AI + Python/backend + Cloud/full-stack + GitHub + Engineering - quality_penalty, 0, 100)
github = max(0, min(10, activity + repository_relevance) - security_penalty)
```

## GitHub analysis

For each eligible candidate with a GitHub URL, the application retrieves public profile,
repository, and recent public-event metadata. It assigns up to 5 activity points and 5 repository
relevance points. Stars and forks are small supporting signals rather than popularity gates.

The optional hygiene scan is intentionally conservative:

- scans at most 3 relevant, candidate-owned public repositories;
- inspects at most 10 small text/config files per repository;
- skips dependencies, build output, documentation, fixtures, examples, and binary/large files;
- records secret type, repository, path, and a run-scoped HMAC fingerprint—never the raw value;
- does not validate, use, or transmit a discovered credential;
- makes findings advisory with zero deduction if the bounded scan is incomplete or ambiguous.

This is a screening signal, not a security audit.

## Gemini and privacy

The configured model is `gemini-3.5-flash-lite`. Calls use Gemini's schema-constrained Interactions
API with `store: false`. Before sending text, the application removes detected names, emails,
phone numbers, and URLs and caps the payload size. Model responses are validated, and quoted
evidence is retained only when it occurs in the original resume. A timeout, rate limit, invalid
response, or missing key causes a per-candidate deterministic fallback.

Resume text is still processed by an external provider when Gemini is enabled. Review Google's
current [API data-use and pricing terms](https://ai.google.dev/gemini-api/docs/pricing) before
processing real applicants. Use `--no-llm` if external processing is not approved. Email is retained
only in the local JSON and never affects scoring, logs, GitHub calls, or model prompts. Protected
personal characteristics are not extracted or scored.

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Tests cover the hard gate, score caps and penalties, secret redaction, duplicate handling, batch
count reconciliation, ranking, and schema-valid end-to-end output.

## Project layout

```text
src/resume_screener/
  cli.py          command-line interface
  config.py       validated environment configuration
  ingestion.py    discovery and PDF/DOCX/TXT parsing
  extraction.py   candidate fields and contextual evidence
  eligibility.py  deterministic Python + AI gate
  llm.py          Gemini structured output and fallback
  github.py       public GitHub scoring and bounded hygiene scan
  scoring.py      category arithmetic, penalties, and rank key
  pipeline.py     batch orchestration and atomic output
tests/            unit and end-to-end tests
outputs/          PRD, TRD, and implementation plan
```

## Design decisions and limitations

- No database, queue, web UI, embeddings, or framework is required for this assessment-sized batch.
- Native/digital PDFs work best. OCR for scanned PDFs is not included.
- Resume formats are highly variable; extracted evidence should support recruiter review, not replace
  it.
- GitHub public events are a limited recent window and private work is invisible, so GitHub remains
  only 10% of the score.
- The deterministic fallback is intentionally conservative and less nuanced than Gemini.

With more time, I would add OCR, golden-set calibration with recruiter labels, configurable scoring
rules in a versioned file, richer mocked integration tests, resume-format benchmarks, and a small
HTML review report generated from the same validated JSON.

## Product and technical documents

- [`outputs/AI_Resume_Screening_PRD.md`](outputs/AI_Resume_Screening_PRD.md)
- [`outputs/AI_Resume_Screening_TRD.md`](outputs/AI_Resume_Screening_TRD.md)
- [`outputs/AI_Resume_Screening_Implementation_Plan.md`](outputs/AI_Resume_Screening_Implementation_Plan.md)
