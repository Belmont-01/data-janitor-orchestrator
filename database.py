"""
database.py — SQLite database setup and helper functions.
Handles users and pipeline run history.
"""
import os
import json
import sqlite3
import hashlib
import secrets
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "app.db")


def get_db():
    """Get a database connection."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            username  TEXT UNIQUE NOT NULL,
            password  TEXT NOT NULL,
            salt      TEXT NOT NULL,
            created   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            filename    TEXT NOT NULL,
            status      TEXT NOT NULL,
            clean_json  TEXT,
            report      TEXT,
            error       TEXT,
            created     TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    conn.commit()
    conn.close()


# -------------------------------------------------------------------
# Password helpers
# -------------------------------------------------------------------

def hash_password(password: str, salt: str = None):
    """Hash a password with a salt using SHA-256."""
    if salt is None:
        salt = secrets.token_hex(32)
    hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return hashed, salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    """Verify a password against its hash."""
    check, _ = hash_password(password, salt)
    return check == hashed


# -------------------------------------------------------------------
# User helpers
# -------------------------------------------------------------------

def create_user(username: str, password: str) -> dict:
    """
    Create a new user. Returns dict with success/error.
    """
    if len(username) < 3:
        return {"success": False, "error": "Username must be at least 3 characters."}
    if len(password) < 6:
        return {"success": False, "error": "Password must be at least 6 characters."}

    hashed, salt = hash_password(password)
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, password, salt, created) VALUES (?, ?, ?, ?)",
            (username.lower().strip(), hashed, salt, datetime.utcnow().isoformat())
        )
        conn.commit()
        return {"success": True}
    except sqlite3.IntegrityError:
        return {"success": False, "error": "Username already taken. Please choose another."}
    finally:
        conn.close()


def get_user(username: str) -> dict:
    """Get a user by username."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        (username.lower().strip(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def authenticate_user(username: str, password: str) -> dict:
    """Authenticate a user. Returns user dict or None."""
    user = get_user(username)
    if not user:
        return None
    if verify_password(password, user["password"], user["salt"]):
        return user
    return None


# -------------------------------------------------------------------
# Run history helpers
# -------------------------------------------------------------------

def save_run(user_id: int, filename: str, status: str,
             clean_json=None, report=None, error=None):
    """Save a pipeline run to the database."""
    conn = get_db()
    conn.execute(
        """INSERT INTO runs
           (user_id, filename, status, clean_json, report, error, created)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id,
            filename,
            status,
            json.dumps(clean_json) if clean_json else None,
            report,
            error,
            datetime.utcnow().isoformat()
        )
    )
    conn.commit()
    conn.close()


def get_user_runs(user_id: int) -> list:
    """Get all pipeline runs for a user, newest first."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM runs WHERE user_id = ? ORDER BY created DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    runs = []
    for row in rows:
        r = dict(row)
        if r["clean_json"]:
            try:
                r["clean_json"] = json.loads(r["clean_json"])
            except Exception:
                pass
        runs.append(r)
    return runs


def get_run(run_id: int, user_id: int) -> dict:
    """Get a specific run, only if it belongs to the user."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM runs WHERE id = ? AND user_id = ?",
        (run_id, user_id)
    ).fetchone()
    conn.close()
    if not row:
        return None
    r = dict(row)
    if r["clean_json"]:
        try:
            r["clean_json"] = json.loads(r["clean_json"])
        except Exception:
            pass
    return r
