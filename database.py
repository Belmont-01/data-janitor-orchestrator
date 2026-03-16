"""
database.py — Database setup and helpers.
Uses PostgreSQL on Render (DATABASE_URL env var) and SQLite locally.
Passwords hashed with bcrypt (strong) instead of SHA-256 (weak).
"""
import os
import json
import secrets
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")

# -------------------------------------------------------------------
# Password hashing — bcrypt with fallback to sha256 if bcrypt missing
# -------------------------------------------------------------------

def _hash_bcrypt(password: str):
    import bcrypt
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))
    return hashed.decode(), "bcrypt"

def _verify_bcrypt(password: str, hashed: str) -> bool:
    import bcrypt
    return bcrypt.checkpw(password.encode(), hashed.encode())

def hash_password(password: str, salt: str = None):
    """
    Hash password with bcrypt. Returns (hashed, salt).
    Salt is kept for legacy SHA-256 compatibility but bcrypt embeds its own salt.
    """
    try:
        hashed, _ = _hash_bcrypt(password)
        legacy_salt = salt or secrets.token_hex(4)  # short dummy salt for schema compat
        return hashed, legacy_salt
    except ImportError:
        # Fallback: sha256 if bcrypt not installed yet
        import hashlib
        if salt is None:
            salt = secrets.token_hex(32)
        hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return hashed, salt

def verify_password(password: str, hashed: str, salt: str) -> bool:
    """Verify password — handles both bcrypt and legacy sha256 hashes."""
    if hashed.startswith("$2b$") or hashed.startswith("$2a$"):
        # bcrypt hash
        try:
            return _verify_bcrypt(password, hashed)
        except ImportError:
            return False
    else:
        # Legacy SHA-256
        import hashlib
        check = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return check == hashed


# -------------------------------------------------------------------
# Connection — PostgreSQL on Render, SQLite locally
# -------------------------------------------------------------------

def get_db():
    if DATABASE_URL:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        return conn, "postgres"
    else:
        import sqlite3
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "app.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn, "sqlite"


def fetchall(cursor):
    rows = cursor.fetchall()
    if not rows:
        return []
    if hasattr(rows[0], 'keys'):
        return [dict(r) for r in rows]
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


def fetchone(cursor):
    row = cursor.fetchone()
    if not row:
        return None
    if hasattr(row, 'keys'):
        return dict(row)
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


def placeholder(db_type):
    return "%s" if db_type == "postgres" else "?"


# -------------------------------------------------------------------
# Init — create tables if they don't exist
# -------------------------------------------------------------------

def init_db():
    conn, db_type = get_db()
    cur = conn.cursor()

    if db_type == "postgres":
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id       SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                salt     TEXT NOT NULL,
                created  TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER NOT NULL REFERENCES users(id),
                filename   TEXT NOT NULL,
                status     TEXT NOT NULL,
                clean_json TEXT,
                report     TEXT,
                error      TEXT,
                created    TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id     TEXT PRIMARY KEY,
                filename   TEXT NOT NULL,
                user_id    INTEGER NOT NULL,
                status     TEXT NOT NULL,
                clean_json TEXT,
                report     TEXT,
                error      TEXT,
                created    TEXT NOT NULL
            )
        """)
    else:
        cur.executescript("""
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
            CREATE TABLE IF NOT EXISTS jobs (
                job_id     TEXT PRIMARY KEY,
                filename   TEXT NOT NULL,
                user_id    INTEGER NOT NULL,
                status     TEXT NOT NULL,
                clean_json TEXT,
                report     TEXT,
                error      TEXT,
                created    TEXT NOT NULL
            );
        """)

    conn.commit()
    conn.close()


# -------------------------------------------------------------------
# User helpers
# -------------------------------------------------------------------

def create_user(username: str, password: str) -> dict:
    if len(username) < 3:
        return {"success": False, "error": "Username must be at least 3 characters."}
    if len(password) < 6:
        return {"success": False, "error": "Password must be at least 6 characters."}

    hashed, salt = hash_password(password)
    conn, db_type = get_db()
    p = placeholder(db_type)
    try:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO users (username, password, salt, created) VALUES ({p}, {p}, {p}, {p})",
            (username.lower().strip(), hashed, salt, datetime.utcnow().isoformat())
        )
        conn.commit()
        return {"success": True}
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return {"success": False, "error": "Username already taken. Please choose another."}
        return {"success": False, "error": f"Could not create account: {e}"}
    finally:
        conn.close()


def get_user(username: str) -> dict:
    conn, db_type = get_db()
    p = placeholder(db_type)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE username = {p}", (username.lower().strip(),))
    row = fetchone(cur)
    conn.close()
    return row


def authenticate_user(username: str, password: str) -> dict:
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
    conn, db_type = get_db()
    p = placeholder(db_type)
    cur = conn.cursor()
    cur.execute(
        f"""INSERT INTO runs
            (user_id, filename, status, clean_json, report, error, created)
            VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})""",
        (
            user_id, filename, status,
            json.dumps(clean_json) if clean_json else None,
            report, error,
            datetime.utcnow().isoformat()
        )
    )
    conn.commit()
    conn.close()


def get_user_runs(user_id: int) -> list:
    conn, db_type = get_db()
    p = placeholder(db_type)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM runs WHERE user_id = {p} ORDER BY created DESC", (user_id,))
    rows = fetchall(cur)
    conn.close()
    for r in rows:
        if r.get("clean_json"):
            try:
                r["clean_json"] = json.loads(r["clean_json"])
            except Exception:
                pass
    return rows


def get_run(run_id: int, user_id: int) -> dict:
    conn, db_type = get_db()
    p = placeholder(db_type)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM runs WHERE id = {p} AND user_id = {p}", (run_id, user_id))
    row = fetchone(cur)
    conn.close()
    if not row:
        return None
    if row.get("clean_json"):
        try:
            row["clean_json"] = json.loads(row["clean_json"])
        except Exception:
            pass
    return row

# -------------------------------------------------------------------
# Job store — persisted in DB so all workers can read results
# -------------------------------------------------------------------

def create_job(job_id: str, filename: str, user_id: int):
    conn, db_type = get_db()
    p = placeholder(db_type)
    cur = conn.cursor()
    cur.execute(
        f"INSERT INTO jobs (job_id, filename, user_id, status, created) VALUES ({p},{p},{p},{p},{p})",
        (job_id, filename, user_id, "running", datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


def finish_job(job_id: str, clean_json=None, report=None, error=None):
    conn, db_type = get_db()
    p = placeholder(db_type)
    cur = conn.cursor()
    status = "error" if error else "done"
    cur.execute(
        f"UPDATE jobs SET status={p}, clean_json={p}, report={p}, error={p} WHERE job_id={p}",
        (
            status,
            json.dumps(clean_json) if clean_json else None,
            report,
            error,
            job_id
        )
    )
    conn.commit()
    conn.close()


def get_job(job_id: str) -> dict:
    conn, db_type = get_db()
    p = placeholder(db_type)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM jobs WHERE job_id = {p}", (job_id,))
    row = fetchone(cur)
    conn.close()
    if not row:
        return None
    if row.get("clean_json"):
        try:
            row["clean_json"] = json.loads(row["clean_json"])
        except Exception:
            pass
    return row


def delete_job(job_id: str):
    conn, db_type = get_db()
    p = placeholder(db_type)
    cur = conn.cursor()
    cur.execute(f"DELETE FROM jobs WHERE job_id = {p}", (job_id,))
    conn.commit()
    conn.close()
