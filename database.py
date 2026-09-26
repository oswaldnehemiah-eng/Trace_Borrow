"""SQLite setup for TraceBorrow.

The database is stored inside the project folder and is never deleted when the
server starts. This keeps registered users, transfers, and return requests
across server restarts and computer shutdowns.
"""

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_DIR = os.path.join(BASE_DIR, "database")
DATABASE_PATH = os.path.join(DATABASE_DIR, "traceborrow.db")


def get_connection():
    os.makedirs(DATABASE_DIR, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _columns(conn, table_name):
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def init_db():
    """Create the database/tables if needed without deleting existing data."""
    os.makedirs(DATABASE_DIR, exist_ok=True)
    conn = get_connection()

    # IMPORTANT: Never DROP users/transfers on startup. The old version could
    # erase all login accounts if the schema was slightly different.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user_id INTEGER NOT NULL,
            to_user_id INTEGER NOT NULL,
            item_description TEXT NOT NULL,
            transferred_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (from_user_id) REFERENCES users(id),
            FOREIGN KEY (to_user_id) REFERENCES users(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS return_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_description TEXT NOT NULL,
            requester_id INTEGER NOT NULL,
            target_user_id INTEGER NOT NULL,
            requested_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            status TEXT NOT NULL DEFAULT 'PENDING'
                CHECK(status IN ('PENDING', 'FULFILLED')),
            FOREIGN KEY (requester_id) REFERENCES users(id),
            FOREIGN KEY (target_user_id) REFERENCES users(id)
        )
    """)

    # Safe migration for databases created by an older TraceBorrow version.
    # Only missing tables/columns are added; existing rows are preserved.
    user_columns = _columns(conn, "users")
    transfer_columns = _columns(conn, "transfers")
    request_columns = _columns(conn, "return_requests")

    if "created_at" not in user_columns:
        conn.execute(
            "ALTER TABLE users ADD COLUMN created_at TEXT DEFAULT (datetime('now', 'localtime'))"
        )

    if "transferred_at" not in transfer_columns:
        conn.execute(
            "ALTER TABLE transfers ADD COLUMN transferred_at TEXT"
        )
        conn.execute(
            "UPDATE transfers SET transferred_at = datetime('now', 'localtime') "
            "WHERE transferred_at IS NULL"
        )

    if "requested_at" not in request_columns:
        conn.execute(
            "ALTER TABLE return_requests ADD COLUMN requested_at TEXT"
        )
        conn.execute(
            "UPDATE return_requests SET requested_at = datetime('now', 'localtime') "
            "WHERE requested_at IS NULL"
        )

    if "status" not in request_columns:
        conn.execute(
            "ALTER TABLE return_requests ADD COLUMN status TEXT DEFAULT 'PENDING'"
        )
        conn.execute(
            "UPDATE return_requests SET status = 'PENDING' WHERE status IS NULL"
        )

    conn.execute("CREATE INDEX IF NOT EXISTS idx_transfers_description ON transfers(item_description)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_transfers_from_user ON transfers(from_user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_transfers_to_user ON transfers(to_user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_target ON return_requests(target_user_id, status)")

    conn.commit()
    conn.close()
