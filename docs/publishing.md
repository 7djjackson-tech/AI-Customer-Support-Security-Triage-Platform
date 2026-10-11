# Publishing source to GitHub

The project is intended for the existing repository:
https://github.com/7djjackson-tech/AI-Customer-Support-Security-Triage-Platform

Source publication is separate from application deployment. No Azure deployment is included. Git ignores virtual environments, local databases, `.env`, Python caches, and generated runtime files. Review staged files before every future push; never commit credentials or real customer data.

For future changes from your local clone:

```bash
python -m pytest -q
python evaluate.py
git status --short
git add app.py triage.py evaluate.py templates static data tests docs .github README.md requirements.txt .gitignore .env.example LICENSE
git diff --cached --stat
git diff --cached
git commit -m "Describe your SupportShield change"
git push origin main
```

Use a feature branch and pull request if you prefer review. Keep your existing origin; never embed a token in its URL. The included GitHub Actions workflow runs tests, an isolated local HTTP smoke check, and demo evaluation on pushes and pull requests. CI execution and results must be checked on GitHub; local passing checks do not prove a remote run passed.

For the first run on Windows, follow the README PowerShell instructions. You can also choose GitHub **Code → Download ZIP**, extract the archive, and open a terminal in the folder containing `app.py` and `requirements.txt`.
