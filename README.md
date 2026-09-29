# SDE Intern Resume Screener

Python CLI for screening the supplied 50-resume dataset. It parses PDF, DOCX, and TXT files,
requires evidence of both Python and AI/ML, scores eligible candidates, checks public GitHub
activity, and writes the complete result to `output/results.json`.

## Setup

Requires Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

Set the two credentials in `.env`:

```dotenv
GEMINI_API_KEY=your_gemini_key
GITHUB_TOKEN=your_fine_grained_github_token
```

`.env` is ignored by Git. The GitHub token only needs read access to public resources.

## Run

```bash
python main.py --input ./resumes --output ./output/results.json
```

Run without external services:

```bash
python main.py --input ./resumes --output ./output/results.json --no-llm --no-github
```

Options:

```text
--recursive          Include nested directories
--no-llm             Use deterministic project assessment
--no-github          Disable GitHub enrichment
--no-security-scan   Disable public-repository credential checks
--compact            Write compact JSON
--env-file PATH      Use a different environment file
```

## Eligibility

A candidate must have both:

1. Python evidence; and
2. AI/ML evidence, such as machine learning, deep learning, NLP, LLMs, RAG, agents, or evaluation.

Coursework-only, tutorial-only, negated, or incidental mentions do not satisfy the gate. Rejected
candidates remain in the output with explicit reasons, but receive no score or rank. GitHub does
not affect eligibility.

## Scoring

Only eligible candidates are scored. The five positive categories total 100 points.

| Category | Maximum |
|---|---:|
| AI and project depth | 40 |
| Python and backend | 30 |
| Cloud and full-stack | 15 |
| GitHub | 10 |
| Engineering depth | 5 |

### Evidence strength

Resume evidence uses these multipliers:

| Evidence | Multiplier |
|---|---:|
| Incidental | 0.00 |
| Skill mention | 0.45 |
| Applied implementation | 0.75 |
| Advanced implementation | 1.00 |

For a resume-based subcategory, the strongest matching evidence determines the multiplier. Its
score is `round(maximum × multiplier)`.

### AI and project depth: 40 points

Gemini returns depth labels, not points. The deterministic fallback returns the same labels.

| Subcategory | Maximum |
|---|---:|
| Overall project implementation | 8 |
| Retrieval/RAG | 8 |
| Agent systems | 8 |
| Data workflows | 6 |
| Evaluation | 5 |
| Ownership | 5 |

Depth multipliers are `none = 0`, `basic = 0.25`, `applied = 0.65`, and `advanced = 1.00`.
The six weighted values are summed and rounded once, with a maximum of 40.

### Python and backend: 30 points

| Subcategory | Maximum | Evidence examples |
|---|---:|---|
| Python implementation | 10 | Python, Django, Flask, FastAPI |
| Backend/API work | 8 | APIs, backend services, Django, Flask, FastAPI |
| Databases | 5 | SQL, PostgreSQL, MySQL, MongoDB, Redis |
| Async and queues | 4 | asyncio, Celery, Kafka, RabbitMQ |
| Ownership | 3 | Project ownership depth |

The first four use evidence-strength multipliers. Ownership uses project-depth multipliers. The
category is capped at 30.

### Cloud and full-stack: 15 points

| Subcategory | Maximum |
|---|---:|
| Cloud platforms: AWS, GCP, Azure | 5 |
| Containers: Docker, Kubernetes | 4 |
| CI/CD and deployment | 3 |
| Frontend: React, Next.js, TypeScript | 3 |

Each subcategory uses the strongest matching evidence multiplier. The category is capped at 15.

### GitHub: 10 points

GitHub contributes up to 5 activity points and 5 repository points.

Activity scoring:

```text
signal = public events in the last 90 days + min(repositories pushed in the last 180 days, 5)

signal 12+ → 5 points
signal  7+ → 4 points
signal  4+ → 3 points
signal  2+ → 2 points
signal  1+ → 1 point
otherwise → 0 points
```

Repository scoring uses non-fork, non-archived public repositories. Relevance comes from Python,
backend, API, ML, LLM, RAG, agent, NLP, PyTorch, TensorFlow, Django, Flask, or FastAPI terms in the
repository name, description, language, or topics.

```text
repository_match = 4 × matched terms + min(stars, 5) + min(forks, 3)
relevant repository = repository_match > 0
strong top match = highest repository_match >= 8
```

```text
4+ relevant repositories and a strong top match → 5 points
3+ relevant repositories                        → 4 points
2+ relevant repositories                        → 3 points
1 relevant repository                           → 2 points
other owned public repositories                  → 1 point
no owned public repositories                     → 0 points
```

The bounded security check can deduct GitHub points:

| Finding | Deduction |
|---|---:|
| Private key or GitHub token pattern | 5 |
| Google or OpenAI-style API key pattern | 4 |
| Hard-coded credential pattern | 3 |

Multiple findings use the largest deduction, not their sum. The deduction is capped at 5, cannot
make the GitHub score negative, and is zero when the scan is incomplete.

```text
github = max(0, min(10, activity + repositories) - security_deduction)
```

The scanner stores only the repository, file path, credential type, and an HMAC fingerprint. It
does not store the detected value.

### Engineering depth: 5 points

One point is awarded for each area found in the resume:

- testing;
- monitoring, logging, or observability;
- security, authentication, or authorization;
- performance, latency, or scaling; and
- documentation or README work.

### Project-quality deductions

These deductions apply to the total score, not the GitHub category.

| Finding | Deduction |
|---|---:|
| Thin wrapper: low / medium / high | 5 / 10 / 15 |
| Tutorial-only work: low / high | 5 / 10 |

The combined project-quality deduction is capped at 20.

```text
total = clamp(
    AI + Python/backend + Cloud/full-stack + GitHub + Engineering
    - project-quality deduction,
    0,
    100,
)
```

Candidates are ranked by total score, then AI score, then Python/backend score, then name.

## Gemini usage

The configured model is `gemini-3.5-flash-lite`. Before a request, the application removes detected
names, emails, phone numbers, and URLs. Responses must match a schema, and cited evidence is kept
only when it occurs in the resume. A missing key, timeout, rate limit, or invalid response uses the
deterministic fallback for that candidate.

Use `--no-llm` if resume text must not be sent to an external provider. Review Google's current
[Gemini API pricing and data-use terms](https://ai.google.dev/gemini-api/docs/pricing) before using
real applicant data.

## Output

`output/results.json` contains run metadata, batch totals, every candidate outcome, eligibility
evidence, category scores, deductions, GitHub status, warnings, and ranks. It also contains
candidate email addresses and should be handled as private applicant data.

The committed result contains the completed dataset run: 50 parsed, 38 eligible, 12 rejected, and
0 failed.

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Documentation

- [Product requirements](docs/PRD.md)
- [Technical requirements](docs/TRD.md)
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md)

## Repository layout

```text
docs/                   requirements and implementation plan
output/results.json     generated assessment result
src/resume_screener/    application modules
tests/                  unit and end-to-end tests
main.py                 CLI entry point
```
