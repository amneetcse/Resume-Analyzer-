# ResumeAI

A four-page Flask resume analyzer:

1. **Home** — introduction, features, and Get Started links.
2. **Login / sign up** — account creation and sign-in with hashed passwords and session-token CSRF protection.
3. **Resume analyzer** — PDF, DOCX, or TXT upload plus a required job description.
4. **Results** — job-match percentage, a separate ATS-readiness score with its factors, matched and missing skills, resume sections, keywords, and improvement suggestions.

The uploaded resume is read in memory and is not saved. The analysis uses a small built-in skills vocabulary and transparent heuristics; it does not call an external AI service. The ATS score estimates section structure, resume length, measurable outcomes, and recognized job-skill overlap. It is a guide, not a real ATS vendor score.

## Run on Windows

Open PowerShell in this folder and run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Then open http://127.0.0.1:5000. The SQLite account database is created in `instance/resumeai.sqlite3`.

## Deploy with Render

The included `render.yaml` sets up Gunicorn, a generated Flask secret, and secure session cookies. To deploy, put the files from this folder at the root of a GitHub repository, then create a Render Blueprint from that repository. Render will read the configuration and create the service.

**Database note:** the included SQLite database is suitable for local learning. Render's default filesystem is temporary, so accounts may be lost when the service is redeployed or restarted. For real users, connect a persistent managed PostgreSQL database before publishing broadly. Use a strong secret key, HTTPS, and a persistent database in production.

## Files

- `app.py` — routes, account handling, resume extraction, and analysis.
- `templates/` — the four pages.
- `static/styles.css` — responsive visual design.
- `static/app.js` — upload interactions and analyzer page theme toggle.
- `requirements.txt` — Python dependencies.
- `render.yaml` — Render deployment configuration.
