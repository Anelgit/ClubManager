"""SQLite layer for the Club Manager app.

Stores a single file ``club.db`` next to the executable / script.
Schema is intentionally simple; future migrations can be added in
``_migrate`` by checking ``user_version``.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from typing import Iterator, Optional


SCHEMA_VERSION = 2


def _app_dir() -> str:
    """Return the folder where the DB should live.

    When frozen with PyInstaller the script lives inside a temp folder,
    but we want the DB next to the .exe so the user can back it up.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


DB_PATH = os.path.join(_app_dir(), "club.db")


@dataclass
class Member:
    id: Optional[int]
    name: str
    email: str
    paid_date: str            # ISO YYYY-MM-DD
    next_payment_date: str    # ISO YYYY-MM-DD
    reminder_months: int      # 1, 2 or 3
    notes: str = ""
    last_reminder_sent_for: Optional[str] = None   # ISO date of the cycle we already emailed for


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    cur = conn.execute("PRAGMA user_version;")
    version = cur.fetchone()[0]
    if version < 1:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                paid_date TEXT NOT NULL,
                next_payment_date TEXT NOT NULL,
                reminder_months INTEGER NOT NULL DEFAULT 1,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_members_next_payment
                ON members(next_payment_date);
            """
        )
        conn.execute("PRAGMA user_version = 1;")
    if version < 2:
        conn.executescript(
            """
            ALTER TABLE members ADD COLUMN last_reminder_sent_for TEXT;
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        conn.execute("PRAGMA user_version = 2;")
    conn.commit()


def init_db() -> None:
    with _connect() as conn:
        _migrate(conn)


@contextmanager
def _cursor() -> Iterator[sqlite3.Cursor]:
    conn = _connect()
    try:
        yield conn.cursor()
        conn.commit()
    finally:
        conn.close()


def _row_to_member(row: sqlite3.Row) -> Member:
    keys = row.keys()
    return Member(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        paid_date=row["paid_date"],
        next_payment_date=row["next_payment_date"],
        reminder_months=row["reminder_months"],
        notes=row["notes"] or "",
        last_reminder_sent_for=(row["last_reminder_sent_for"]
                                if "last_reminder_sent_for" in keys else None),
    )


def list_members(search: str = "") -> list[Member]:
    with _cursor() as cur:
        if search:
            like = f"%{search}%"
            cur.execute(
                "SELECT * FROM members "
                "WHERE name LIKE ? OR email LIKE ? "
                "ORDER BY name COLLATE NOCASE;",
                (like, like),
            )
        else:
            cur.execute("SELECT * FROM members ORDER BY name COLLATE NOCASE;")
        return [_row_to_member(r) for r in cur.fetchall()]


def get_member(member_id: int) -> Optional[Member]:
    with _cursor() as cur:
        cur.execute("SELECT * FROM members WHERE id = ?;", (member_id,))
        row = cur.fetchone()
        return _row_to_member(row) if row else None


def add_member(m: Member) -> int:
    with _cursor() as cur:
        cur.execute(
            """INSERT INTO members
               (name, email, paid_date, next_payment_date, reminder_months, notes)
               VALUES (?, ?, ?, ?, ?, ?);""",
            (m.name, m.email, m.paid_date, m.next_payment_date,
             m.reminder_months, m.notes),
        )
        return int(cur.lastrowid)


def update_member(m: Member) -> None:
    if m.id is None:
        raise ValueError("Cannot update member without id")
    with _cursor() as cur:
        cur.execute("SELECT next_payment_date FROM members WHERE id = ?;", (m.id,))
        row = cur.fetchone()
        # If the next-payment date moved to a new cycle, allow a fresh reminder.
        new_last_sent = m.last_reminder_sent_for
        if row and row["next_payment_date"] != m.next_payment_date:
            new_last_sent = None
        cur.execute(
            """UPDATE members
               SET name = ?, email = ?, paid_date = ?, next_payment_date = ?,
                   reminder_months = ?, notes = ?, last_reminder_sent_for = ?
               WHERE id = ?;""",
            (m.name, m.email, m.paid_date, m.next_payment_date,
             m.reminder_months, m.notes, new_last_sent, m.id),
        )


def mark_reminder_sent(member_id: int, for_date: str) -> None:
    with _cursor() as cur:
        cur.execute(
            "UPDATE members SET last_reminder_sent_for = ? WHERE id = ?;",
            (for_date, member_id),
        )


# ---------- Settings (key/value) -----------------------------------------

def get_setting(key: str, default: str = "") -> str:
    with _cursor() as cur:
        cur.execute("SELECT value FROM settings WHERE key = ?;", (key,))
        row = cur.fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with _cursor() as cur:
        cur.execute(
            """INSERT INTO settings(key, value) VALUES(?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value;""",
            (key, value),
        )


def get_all_settings() -> dict[str, str]:
    with _cursor() as cur:
        cur.execute("SELECT key, value FROM settings;")
        return {r["key"]: r["value"] for r in cur.fetchall()}


def delete_member(member_id: int) -> None:
    with _cursor() as cur:
        cur.execute("DELETE FROM members WHERE id = ?;", (member_id,))


def members_due_soon(today: Optional[date] = None) -> list[Member]:
    """Members whose next-payment date falls inside their reminder window
    (or has already passed).
    """
    today = today or date.today()
    out: list[Member] = []
    for m in list_members():
        try:
            due = date.fromisoformat(m.next_payment_date)
        except ValueError:
            continue
        delta_days = (due - today).days
        window_days = m.reminder_months * 31
        if delta_days <= window_days:
            out.append(m)
    return out
