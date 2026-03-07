"""
database.py — Database setup and helpers.
Uses PostgreSQL on Render (DATABASE_URL env var) and SQLite locally.
"""
import os
import json
import hashlib
import secrets
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")

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
    # Normalize to list of dicts
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
    """Return the right parameter placeholder for each DB."""
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
        """)

    conn.commit()
    conn.close()


# -------------------------------------------------------------------
# Password helpers
# -------------------------------------------------------------------

def hash_password(password: str, salt: str = None):
    if salt is None:
        salt = secrets.token_hex(32)
    hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return hashed, salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    check, _ = hash_password(password, salt)
    return check == hashed


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
    conn, db_type = get_db()
    p = placeholder(db_type)
    cur = conn.cursor()
    cur.execute(
        f"SELECT * FROM runs WHERE user_id = {p} ORDER BY created DESC",
        (user_id,)
    )
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
    cur.execute(
        f"SELECT * FROM runs WHERE id = {p} AND user_id = {p}",
        (run_id, user_id)
    )
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
