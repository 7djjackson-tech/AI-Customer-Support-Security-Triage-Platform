# SupportShield

**AI Customer Support & Security Triage Platform** — a manageable portfolio project using Python, Flask, SQLite, and simple HTML/CSS. Fictional retailer **Northstar Goods** receives returns, missing-order, account-access, and suspicious-activity requests. Staff review recommendations and retain control over every decision.

Demo mode works without an API key. It is a **deterministic rules-based simulation, not a trained AI model**. The optional OpenAI adapter is disabled by default and has not been evaluated against a live provider. No emails are sent and no account changes are performed.

## What is implemented

- Validated fictional CSV imports, persistent tickets, search, responsive dashboard, detail pages.
- Staff login with Werkzeug scrypt password hashes, CSRF protection, eight-hour sessions, and basic login throttling.
- Server-enforced queues and direct URL permissions: customer-service staff see ordinary tickets; security staff see security tickets; administrators see both and manage staff roles.
- Categories, priority, routing, short summaries, policy-grounded drafts, quoted security evidence, and uncertainty statements.
- Approve the saved recommendation, edit/manual review, or reject; update status; retain reviewer actions and separate source-labeled recommendation history.
- Mandatory security escalation rules, safe text rendering, parameterized queries, constrained uploads, and usable demo fallback if live AI fails or returns invalid output.
- Separate development and labeled evaluation datasets, reproducible metrics, meaningful tests, MIT license, demo walkthrough, case study, and Azure preparation notes.

## Windows PowerShell: download and run

Install Python 3.11+ (tested on Python 3.12) and Git first. Open PowerShell in a folder where you want to keep the project. If you have already cloned it, use `git pull` from that folder instead of cloning again; preserve any local changes first.

```powershell
git clone https://github.com/7djjackson-tech/AI-Customer-Support-Security-Triage-Platform.git
cd AI-Customer-Support-Security-Triage-Platform
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:SECRET_KEY = .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
.\.venv\Scripts\python.exe -m flask --app app:create_app create-staff --username admin --role admin
```

The last command prompts for a password twice. Choose a private password of at least 12 characters. There is **no default password**. Then run:

```powershell
.\.venv\Scripts\python.exe -m flask --app app:create_app run --host 127.0.0.1 --port 5000
```

Open **http://127.0.0.1:5000** in your local browser. Sign in as `admin`, import `data/development.csv`, and use **Staff access** to create customer-service and security users. Review tickets from their assigned queues. Ctrl+C stops the app.

Tests and demo evaluation (stop the server or use another terminal in the project folder):

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe evaluate.py
```

These commands do not require PowerShell virtual-environment activation or execution-policy changes. If downloading a ZIP from GitHub instead, extract it and open a terminal **inside the folder containing `app.py` and `requirements.txt`**; skip the clone command. `/workspace` is a cloud-only path.

## macOS/Linux/cloud

```bash
cd AI-Customer-Support-Security-Triage-Platform
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
flask --app app:create_app create-staff --username admin --role admin
flask --app app:create_app run --host 127.0.0.1 --port 5000
# In another terminal with the environment activated:
python -m pytest -q
python evaluate.py
```

## Configuration

`.env.example` documents variable names. This app does **not** load `.env` automatically: set variables in your shell or hosting configuration. Never commit credentials. No AI key is needed for demo mode.

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Private Flask session/CSRF signing key. Keep stable across restarts. Unset: random in-memory local key, invalidating sessions on restart. |
| `DATABASE_PATH` | Optional SQLite path; defaults to ignored `instance/supportshield.sqlite3`. Parent directory is created automatically. |
| `COOKIE_SECURE` | Set `true` when serving over HTTPS; leave unset for local HTTP. |
| `LIVE_AI_ENABLED` | Explicit opt-in `true`; otherwise no live requests. |
| `SUPPORTSHIELD_AI_KEY` | Private OpenAI credential, used only for the fixed OpenAI HTTPS endpoint. |
| `AI_MODEL` | Optional model selection; adapter default `gpt-4o-mini`, availability subject to provider. |

Read [provider options and cost estimates](docs/live-ai.md) **before enabling live AI**. There is no Azure OpenAI adapter in this version. Live requests require both configuration and a per-request fictional-data consent checkbox. Provider errors never surface raw bodies to staff. The app shows an explicitly labeled `demo_fallback` and manual review remains available.

## CSV contract

Exact headers: `external_id,customer_name,subject,message`. UTF-8 with optional BOM; quoted multiline fields supported. Maximum 200 rows and 1 MB request size including upload overhead. Fields must be nonempty, contain no null bytes, and stay within lengths 80, 100, 160, and 5,000 respectively. All rows are validated before a write transaction. Duplicate IDs within a file reject the batch; IDs already stored are skipped without overwriting originals. Only administrators import. The fictional-data checkbox is an attestation, not a personal-data detector. `data/evaluation.csv` has additional labels and is deliberately **not an import file**.

## Architecture

```text
Browser → Flask routes + CSRF + role checks → SQLite
                   ↓
           triage.py: rules-based demo
                   or
           optional OpenAI structured response
                   ↓
           schema/evidence validation + mandatory escalation
                   ↓
           source-labeled recommendation → staff review → audit
```

`app.py` is a single application factory with routes, small database helpers, schema initialization/migration, and a staff bootstrap command. `triage.py` holds documented demo behavior, provider integration, and validation. Jinja templates escape customer text. No frontend framework or JavaScript is required. `evaluate.py` scores a separate dataset. Five SQLite tables store tickets, staff, audit events, recommendation versions, and login-attempt counters. Source values are `demo`, `live`, and `demo_fallback`; old outputs remain separate records. Database files are ignored by Git.

Imports run the demo routing guard to keep recognized security concerns out of the ordinary queue. Account-takeover patterns are applied again after AI, so a valid but incorrect AI category cannot suppress explicit-rule escalation. A security flag is sticky in this prototype. Reviews cannot downgrade it. Recommendations are final once reviewed; statuses can still change. Stale review forms are rejected using recommendation version IDs. Writes use transactions; audit records commit with the relevant ticket change.

## Actual results and limitations

The committed demo evaluation: **21/24 category predictions correct (87.5%)**, **0/16 false security alerts**, **1/8 missed incidents (12.5%)**. The missed indirect takeover report illustrates limits of keyword rules. The small author-labeled dataset is not independent external validation and does not establish real-world accuracy. No time savings are claimed. Live provider behavior and cost have not been measured. See [validation results](docs/validation.md) and [per-example output](docs/evaluation-demo.json).

This is a fictional-data portfolio prototype, not a production support system. A real deployment would need broader threat review, stronger rate limiting/MFA, secure account recovery, pagination, tested backups, retention controls, monitoring, and more representative evaluation. The audit log is append-only through app routes, not tamper-proof against database administrators. Structural validation and prompt isolation do not guarantee factual correctness; staff must verify live drafts against policy. Rules can over-escalate negated reports and miss unfamiliar wording. Roles are mutually exclusive except administrators. CLI account creation requires trusted machine access. Avoid putting full customer messages or secrets in review rationales.

## Portfolio and Azure preparation

- [Five-minute demo](docs/demo.md)
- [Business case study and design decisions](docs/case-study.md)
- [Security model and escalation rules](docs/security.md)
- [Live AI options, estimated costs, and evaluation](docs/live-ai.md)
- [Publishing source to GitHub](docs/publishing.md)
- [Azure for Students deployment preparation](docs/azure.md)

**Nothing has been deployed to Azure.** The Azure guide is preparation only; deploying requires a later explicit decision and review of student credits and service pricing.
