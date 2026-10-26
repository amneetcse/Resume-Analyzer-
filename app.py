"""Four-page ResumeAI application with local SQLite accounts and resume analysis."""

from __future__ import annotations

import io
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from collections import Counter
from functools import wraps
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

try:
    import docx2txt
except ImportError:
    docx2txt = None

try:
    import fitz
except ImportError:
    fitz = None

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    MAX_CONTENT_LENGTH=10 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true",
)
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", str(INSTANCE_DIR / "resumeai.sqlite3")))
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}


def csrf_token() -> str:
    token = session.get("_csrf_token")
    if token is None:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def protect_forms_from_csrf() -> None:
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    supplied = request.form.get("csrf_token") or request.headers.get("X-CSRFToken", "")
    expected = session.get("_csrf_token", "")
    if not supplied or not expected or not secrets.compare_digest(supplied, expected):
        abort(400, description="The form security token is missing or expired. Reload the page and try again.")

SKILL_TERMS = [
    "python", "java", "javascript", "typescript", "sql", "html", "css", "react",
    "node.js", "flask", "django", "fastapi", "machine learning", "deep learning",
    "natural language processing", "nlp", "data analysis", "pandas", "numpy", "excel",
    "power bi", "tableau", "aws", "azure", "gcp", "docker", "kubernetes", "git",
    "rest api", "postgresql", "mongodb", "communication", "leadership", "project management",
    "problem solving", "agile", "linux", "tensorflow", "pytorch", "scikit-learn", "statistics",
]
SECTIONS = {
    "Contact details": ["email", "phone", "linkedin", "github", "portfolio"],
    "Experience": ["experience", "employment", "work history", "professional background"],
    "Education": ["education", "academic", "university", "degree", "coursework"],
    "Skills": ["skills", "technical skills", "core competencies", "expertise"],
    "Projects": ["projects", "selected work", "portfolio"],
}
STOP_WORDS = set("a an and are as at be by for from has have in into is it its of on or our that the their this to was were will with your you we i they he she how what when where why who which about across using use used able role candidate team work working experience skills looking required preferred responsible including strong excellent".split())


def get_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def database():
    connection = get_db()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with database() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


initialize_database()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Sign in or create an account to continue.", "info")
            return redirect(url_for("auth"))
        return view(*args, **kwargs)
    return wrapped


def extract_text(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".txt":
        return data.decode("utf-8-sig", errors="replace")
    if ext == ".pdf":
        if fitz is None:
            raise ValueError("PDF support is unavailable. Install the packages in requirements.txt and restart.")
        with fitz.open(stream=data, filetype="pdf") as document:
            return "\n".join(page.get_text() for page in document)
    if ext == ".docx":
        if docx2txt is None:
            raise ValueError("DOCX support is unavailable. Install the packages in requirements.txt and restart.")
        return docx2txt.process(io.BytesIO(data))
    raise ValueError("Please upload a PDF, DOCX, or TXT file.")


def find_skills(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text.lower())
    return [skill for skill in SKILL_TERMS if re.search(r"(?<![\w+#.])" + re.escape(skill) + r"(?![\w+#.])", normalized)]


def extract_keywords(text: str, limit: int = 8) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z+#.-]{2,}", text.lower())
    counts = Counter(w.strip(".-") for w in words if w not in STOP_WORDS and len(w.strip(".-")) > 2)
    return [word for word, _ in counts.most_common(limit)]


def analyze(text: str, job_description: str) -> dict:
    clean = re.sub(r"\s+", " ", text).strip()
    words = re.findall(r"\b[\w+#.-]+\b", clean)
    lower = clean.lower()
    found_skills = find_skills(clean)
    job_skills = find_skills(job_description)
    matched = [skill for skill in job_skills if skill in found_skills]
    missing = [skill for skill in job_skills if skill not in found_skills]
    match_score = round(100 * len(matched) / len(job_skills)) if job_skills else 0
    sections = {name: any(term in lower for term in terms) for name, terms in SECTIONS.items()}
    section_weights = {"Contact details": 8, "Experience": 13, "Education": 8, "Skills": 12, "Projects": 4}
    section_points = sum(section_weights[name] for name, present in sections.items() if present)
    if 300 <= len(words) <= 800:
        length_points = 15
        length_label = "Good length"
    elif 200 <= len(words) <= 1000:
        length_points = 10
        length_label = "Acceptable length"
    elif 100 <= len(words) <= 1200:
        length_points = 5
        length_label = "Could be more concise or detailed"
    else:
        length_points = 0
        length_label = "Outside the suggested range"
    metric_count = len(re.findall(r"\b\d+(?:\.\d+)?\s*%?\b", clean))
    impact_points = min(metric_count, 3) * 10 // 3
    keyword_points = round(30 * len(matched) / len(job_skills)) if job_skills else 0
    ats_score = min(100, section_points + length_points + impact_points + keyword_points)

    tips = []
    if not sections["Experience"]:
        tips.append("Add a clearly labeled Experience section so recruiters can find your work history.")
    if not sections["Education"]:
        tips.append("Add an Education section with relevant degrees, training, or certifications.")
    if not sections["Skills"]:
        tips.append("Add a Skills section with tools and capabilities relevant to your target role.")
    if len(re.findall(r"\b\d+(?:\.\d+)?\s*%?\b", clean)) < 3:
        tips.append("Add measurable outcomes where possible, such as time saved, revenue, or users served.")
    if len(words) < 250:
        tips.append("Your resume is quite short. Add relevant achievements and context where useful.")
    elif len(words) > 900:
        tips.append("Consider trimming less relevant details so recruiters can scan your resume quickly.")
    if missing:
        tips.append("If accurate, add evidence of these job-description skills: " + ", ".join(missing[:5]) + ".")
    if not tips:
        tips.append("Good foundation. Tailor your most prominent achievements to the specific role.")

    return {
        "score": match_score,
        "ats_score": ats_score,
        "ats_factors": {
            "section_points": section_points,
            "section_max": sum(section_weights.values()),
            "length_points": length_points,
            "length_max": 15,
            "length_label": length_label,
            "impact_points": impact_points,
            "impact_max": 10,
            "metric_count": metric_count,
            "keyword_points": keyword_points,
            "keyword_max": 30,
            "job_skill_count": len(job_skills),
        },
        "job_skill_count": len(job_skills),
        "word_count": len(words),
        "skills": found_skills,
        "matched_skills": matched,
        "missing_skills": missing,
        "sections": sections,
        "keywords": extract_keywords(clean),
        "tips": tips,
    }


@app.get("/")
def home():
    return render_template("index.html")


@app.route("/auth", methods=["GET"])
def auth():
    return render_template("auth.html", mode=request.args.get("mode", "signup"))


@app.post("/signup")
def signup():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    if not name or len(name) > 80:
        flash("Enter your name (up to 80 characters).", "error")
        return redirect(url_for("auth", mode="signup"))
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        flash("Enter a valid email address.", "error")
        return redirect(url_for("auth", mode="signup"))
    if len(password) < 8:
        flash("Use a password with at least 8 characters.", "error")
        return redirect(url_for("auth", mode="signup"))
    try:
        with database() as connection:
            cursor = connection.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        flash("An account with that email already exists. Sign in instead.", "error")
        return redirect(url_for("auth", mode="login"))
    session.clear()
    session["user_id"] = user_id
    session["user_name"] = name
    flash("Your account is ready. Let's review your resume.", "success")
    return redirect(url_for("analyzer"))


@app.post("/login")
def login():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    with database() as connection:
        user = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        flash("Email or password is incorrect.", "error")
        return redirect(url_for("auth", mode="login"))
    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("analyzer"))


@app.post("/logout")
def logout():
    session.clear()
    flash("You have signed out.", "info")
    return redirect(url_for("home"))


@app.get("/analyzer")
@login_required
def analyzer():
    return render_template("analyzer.html")


@app.post("/analyze")
@login_required
def analyze_resume():
    uploaded = request.files.get("resume")
    job_description = request.form.get("job_description", "").strip()
    if uploaded is None or not uploaded.filename:
        flash("Choose a resume file to analyze.", "error")
        return redirect(url_for("analyzer"))
    if not job_description:
        flash("Paste the job description so we can calculate your match.", "error")
        return redirect(url_for("analyzer"))
    filename = secure_filename(uploaded.filename)
    if Path(filename).suffix.lower().lstrip(".") not in ALLOWED_EXTENSIONS:
        flash("Supported formats are PDF, DOCX, and TXT.", "error")
        return redirect(url_for("analyzer"))
    try:
        text = extract_text(filename, uploaded.read())
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("analyzer"))
    except Exception:
        flash("We couldn't read that file. Try exporting it again as a text-based PDF, DOCX, or TXT file.", "error")
        return redirect(url_for("analyzer"))
    if len(text.strip()) < 40:
        flash("I couldn't find enough readable text. Try a text-based PDF, DOCX, or TXT file.", "error")
        return redirect(url_for("analyzer"))
    report = analyze(text, job_description)
    session["report"] = report
    session["resume_filename"] = filename
    return redirect(url_for("results"))


@app.get("/results")
@login_required
def results():
    report = session.get("report")
    if not report:
        return redirect(url_for("analyzer"))
    return render_template("results.html", report=report, filename=session.get("resume_filename", "Resume"))


@app.errorhandler(413)
def too_large(_error):
    flash("That file is too large. The maximum size is 10 MB.", "error")
    return redirect(url_for("analyzer"))


if __name__ == "__main__":
    app.run(debug=True)
