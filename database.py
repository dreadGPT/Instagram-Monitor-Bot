import sqlite3
import time

DB_PATH = "monitor.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS monitors (
                username    TEXT PRIMARY KEY,
                mode        TEXT NOT NULL,
                channel_id  INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                start_time  REAL NOT NULL,
                checks      INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS proxy (
                id      INTEGER PRIMARY KEY CHECK (id = 1),
                host    TEXT,
                port    TEXT,
                user    TEXT,
                pass    TEXT
            );

            CREATE TABLE IF NOT EXISTS history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT NOT NULL,
                mode        TEXT NOT NULL,
                result      TEXT NOT NULL,
                followers   INTEGER,
                elapsed     INTEGER,
                timestamp   REAL NOT NULL
            );
        """)


# ââ Monitors ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def save_monitor(username: str, mode: str, channel_id: int, user_id: int, start_time: float):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO monitors (username, mode, channel_id, user_id, start_time, checks)
            VALUES (?, ?, ?, ?, ?, 0)
        """, (username, mode, channel_id, user_id, start_time))


def remove_monitor(username: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM monitors WHERE username = ?", (username,))


def update_checks(username: str, checks: int):
    with get_conn() as conn:
        conn.execute("UPDATE monitors SET checks = ? WHERE username = ?", (checks, username))


def load_all_monitors() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM monitors").fetchall()
    return [dict(r) for r in rows]


# ââ Proxy âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def save_proxy(host: str, port: str, user: str, passwd: str):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO proxy (id, host, port, user, pass)
            VALUES (1, ?, ?, ?, ?)
        """, (host, port, user, passwd))


def load_proxy() -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM proxy WHERE id = 1").fetchone()
    return dict(row) if row else None


# ââ History âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def save_history(username: str, mode: str, result: str, followers: int | None, elapsed: int):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO history (username, mode, result, followers, elapsed, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (username, mode, result, followers, elapsed, time.time()))
