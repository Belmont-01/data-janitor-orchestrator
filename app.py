import os
import json
import uuid
import tempfile
import threading
from datetime import timedelta
from flask import (
    Flask, request, jsonify, render_template,
    redirect, url_for, session
)
from functools import wraps
from dotenv import load_dotenv, find_dotenv
from errors import (
    PipelineError, FileIngestionError, APIError,
    InvalidOutputError, AgentTimeoutError
)
from database import init_db, create_user, authenticate_user, save_run, get_user_runs, get_run

load_dotenv(find_dotenv())

os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.makedirs("data/clean", exist_ok=True)
os.makedirs("data/raw", exist_ok=True)
os.makedirs("data/jobs", exist_ok=True)

init_db()

from orchestrator.boss import run_pipeline

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-in-production")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("RENDER") is not None
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024

ALLOWED_EXTENSIONS = {".csv", ".pdf", ".xlsx", ".xls", ".txt", ".json", ".docx"}

jobs = {}
jobs_lock = threading.Lock()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            if request.is_json or request.path.startswith("/upload") or request.path.startswith("/status"):
                return jsonify({"success": False, "error": "Session expired. Please refresh the page and sign in again."}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def allowed_file(filename: str) -> bool:
    return os.path.splitext(filename)[-1].lower() in ALLOWED_EXTENSIONS


@app.errorhandler(413)
def too_large(e):
    return jsonify({"success": False, "error": "File too large. Maximum upload size is 32MB."}), 413


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("logged_in"):
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm  = request.form.get("confirm", "").strip()
        if password != confirm:
            error = "Passwords do not match."
        else:
            result = create_user(username, password)
            if result["success"]:
                return redirect(url_for("login", registered="1"))
            else:
                error = result["error"]
    return render_template("register.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("index"))
    error = None
    registered = request.args.get("registered")
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = authenticate_user(username, password)
        if user:
            session.permanent = True
            session["logged_in"] = True
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("index"))
        else:
            error = "Invalid username or password."
    return render_template("login.html", error=error, registered=registered)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html", username=session.get("username"))


@app.route("/history")
@login_required
def history():
    runs = get_user_runs(session["user_id"])
    return render_template("history.html", runs=runs, username=session.get("username"))


@app.route("/history/<int:run_id>")
@login_required
def run_detail(run_id):
    run = get_run(run_id, session["user_id"])
    if not run:
        return redirect(url_for("history"))
    return render_template("run_detail.html", run=run, username=session.get("username"))


def _run_pipeline_job(job_id, tmp_path, filename, output_dir, user_id):
    import shutil
    try:
        run_pipeline(tmp_path, output_dir)

        clean_json = None
        report_text = None

        json_path = os.path.join(output_dir, "output.json")
        report_path = os.path.join(output_dir, "report.md")

        if os.path.exists(json_path):
            with open(json_path, "r") as f:
                clean_json = json.load(f)

        if os.path.exists(report_path):
            with open(report_path, "r") as f:
                report_text = f.read()

        save_run(user_id=user_id, filename=filename, status="success",
                 clean_json=clean_json, report=report_text)

        with jobs_lock:
            jobs[job_id] = {
                "status": "done",
                "filename": filename,
                "result": {"clean_json": clean_json, "report": report_text}
            }

    except (FileIngestionError, APIError, InvalidOutputError,
            AgentTimeoutError, PipelineError) as e:
        save_run(user_id=user_id, filename=filename, status="error", error=str(e))
        with jobs_lock:
            jobs[job_id] = {"status": "error", "filename": filename, "error": str(e)}

    except Exception as e:
        save_run(user_id=user_id, filename=filename, status="error", error=str(e))
        with jobs_lock:
            jobs[job_id] = {"status": "error", "filename": filename, "error": f"Unexpected error: {e}"}

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)


@app.route("/upload", methods=["POST"])
@login_required
def upload():
    files = request.files.getlist("file")

    if not files or all(f.filename == "" for f in files):
        return jsonify({"success": False, "error": "No files provided."}), 400

    job_ids = []

    for file in files:
        if not file.filename:
            continue

        if not allowed_file(file.filename):
            ext = os.path.splitext(file.filename)[-1].lower()
            job_ids.append({"filename": file.filename, "error": f"Unsupported file type: '{ext}'"})
            continue

        suffix = os.path.splitext(file.filename)[-1].lower()
        tmp_path = None

        try:
            job_id = str(uuid.uuid4())
            output_dir = os.path.join("data", "jobs", job_id)
            os.makedirs(output_dir, exist_ok=True)

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                file.save(tmp.name)
                tmp_path = tmp.name

            with jobs_lock:
                jobs[job_id] = {"status": "running", "filename": file.filename}

            user_id = session["user_id"]
            t = threading.Thread(
                target=_run_pipeline_job,
                args=(job_id, tmp_path, file.filename, output_dir, user_id),
                daemon=True
            )
            t.start()

            job_ids.append({"filename": file.filename, "job_id": job_id})

        except Exception as e:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
            job_ids.append({"filename": file.filename, "error": str(e)})

    return jsonify({"success": True, "jobs": job_ids})


@app.route("/status/<job_id>")
@login_required
def job_status(job_id):
    with jobs_lock:
        job = jobs.get(job_id)

    if not job:
        return jsonify({"status": "not_found"}), 404

    if job["status"] == "done":
        with jobs_lock:
            jobs.pop(job_id, None)
        return jsonify({"status": "done", "filename": job["filename"], "result": job["result"]})

    if job["status"] == "error":
        with jobs_lock:
            jobs.pop(job_id, None)
        return jsonify({"status": "error", "filename": job["filename"], "error": job.get("error", "Unknown error")})

    return jsonify({"status": "running", "filename": job.get("filename", "")})


if __name__ == "__main__":
    app.run(debug=False, port=int(os.getenv("PORT", 5000)))
