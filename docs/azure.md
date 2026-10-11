# Azure for Students — preparation only

No Azure resources have been created and nothing has been deployed. Complete the local README walkthrough first. Before a later deployment, confirm your Azure for Students subscription is active, check your remaining credit and spending controls in the Azure portal, and verify current eligibility and prices. Student offers and available SKUs vary; do not assume App Service or OpenAI is free.

## Small demonstration target

Use **Linux Azure App Service with Python 3.12**, one instance, and a persistent SQLite file. This keeps the portfolio architecture understandable. Evaluate the lowest eligible App Service tier against memory limits and scrypt hashing; do not select a paid tier until reviewing estimated costs. Use the provider's App Service quickstart for currently supported runtimes and deployment steps: https://learn.microsoft.com/azure/app-service/quickstart-python

The repository includes Gunicorn on non-Windows systems. Proposed startup command (run from the deployed project root):

```bash
gunicorn --bind 0.0.0.0:8000 --workers 1 --threads 2 --timeout 60 'app:create_app()'
```

One worker is deliberate for this small SQLite demonstration. Do not scale to multiple instances with SQLite. Linux `/home` must be persistent for your chosen hosting mode; confirm persistence, writable permissions, and backup behavior before accepting any deployment. A future scaled system should use a managed database.

## Hosting configuration checklist

Set these privately in App Service environment settings, not in Git:

- `SECRET_KEY`: strong stable private key shared by every restart.
- `DATABASE_PATH=/home/supportshield/supportshield.sqlite3`.
- `COOKIE_SECURE=true`; enable HTTPS-only on the App Service.
- `LIVE_AI_ENABLED=false` initially. No provider credential is needed for demo.
- Build-on-deploy settings required by your chosen supported App Service deployment method (e.g. Oryx), so `requirements.txt` is installed. Do not upload your local Windows `.venv`.

Do not expose the empty application publicly before creating the administrator. Use the App Service SSH console to run `flask --app app:create_app create-staff --username admin --role admin` with a prompted private password. Do not include the password in a startup command or deployment log. Use temporary access restrictions while bootstrapping. There is no default or public signup account.

## Acceptance checks for the later deployment

1. Run tests locally and ensure the release includes only fictional source/data, no local database or secrets.
2. Confirm `/health` succeeds and login cookies are Secure/HTTP-only over HTTPS.
3. Import the eight examples; test role-specific list/detail/recommend/review/status routes and forbidden URLs.
4. Restart App Service and confirm staff accounts, tickets, audit records, and sessions survive as intended with stable configuration.
5. Back up the SQLite database with a SQLite-supported backup operation, avoiding inconsistent copies during writes. Restore to a separate test instance and verify it.
6. Check logs contain no credentials or full message bodies, inspect resource usage, and confirm budget/spending limits.
7. Delete unused resources when the demo is finished to avoid ongoing charges.

Azure authentication, runtime compatibility, filesystem persistence, public HTTPS behavior, and student-service eligibility have **not** been validated here. The local Linux Gunicorn smoke check is recorded in the validation report. Do not treat this document as evidence of a completed Azure deployment.
