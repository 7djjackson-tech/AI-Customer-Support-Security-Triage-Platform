# Completed project validation — October 11, 2026

Environment: Linux, Python 3.12.14, Flask 3.1.2, Flask-WTF 1.2.2, Werkzeug 3.1.9, Gunicorn 23.0.0, SQLite, pytest 8.4.2.

## Tests

Command: `.venv/bin/python -m pytest -q`

Actual result: **41 passed in 8.88 seconds**, zero failed or skipped.

Tests cover imports, malformed CSV/atomic rejection, persistence, duplicate IDs, upload/field/row limits, text escaping, parameterized literal search, CSRF on authentication and all mutations, scrypt password hashing, failed-login throttling, logout, ordinary/security direct URL authorization, role changes affecting active sessions, last-admin protection, staff creation, review actions/audits, manual operation without AI, status changes, security handoffs, stale review versions, separate recommendation history, invalid structured responses, mocked API failures, prompt-injection demo behavior, and reproducible evaluation.

Live-provider tests mock HTTPS responses and failures; **no real API request** was made. A test run using isolated temporary SQLite databases is separate from runtime sample data.

## Running-service checks

Command (Linux): `.venv/bin/python tests/http_smoke.py`

Actual result: **passed**. The test creates an isolated temporary database and private runtime credentials, starts Gunicorn on an available local port, and verifies CLI bootstrap, staff login, administrator staff creation, session/CSRF-protected CSV upload, eight-ticket intake, role-restricted queues, a forbidden direct URL (403), demo generation, saved approval, audit history, status change, security evidence, and the evaluation dashboard. It restarts the owned server and verifies persistent database state and the session with a stable key. It stops its server and removes temporary data.

`pip check`: no broken requirements. `git diff --check`: passed.

## Evaluation

Command: `.venv/bin/python evaluate.py`

Source: deterministic rules-based **demo**, not live AI. Dataset: `data/evaluation.csv`, separate from `data/development.csv`.

| Metric | Actual result |
| --- | --- |
| Scored examples | 24/24 |
| Correct categories | 21/24 (87.5%) |
| False security alerts | 0/16 ordinary cases (0%) |
| Missed security incidents | 1/8 incident cases (12.5%) |
| Service failures | 0 (demo makes no API calls) |

Errors are retained in `docs/evaluation-demo.json`: a double charge, an indirect account misuse report, and a refund-related embedded instruction. The missed indirect incident demonstrates the limits of rules. Customer commands are not executed. This small author-created dataset is not an independent production benchmark. Live AI metrics and time-saving claims are absent.

## Unverified

No visual browser/accessibility audit, Windows runtime execution, live-provider integration, remote GitHub Actions run, or Azure deployment was verified in this cloud environment. Windows commands avoid activation-policy issues but require a compatible installed Python. Azure preparation is documentation only.
