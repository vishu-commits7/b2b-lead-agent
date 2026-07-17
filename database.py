"""
database.py — Persistent storage layer for LeadAgent.io

Replaces in-memory session_state as the source of truth for leads. Uses
SQLite so it works out of the box on Render without needing a separate
database service. If you outgrow SQLite (many concurrent users writing
at once), swap DATABASE_PATH usage for a Postgres connection string —
the function signatures below won't need to change.
"""

import sqlite3
import json
import time
import os
from contextlib import contextmanager
from typing import List, Optional, Dict, Any

DATABASE_PATH = os.environ.get("DATABASE_PATH", "leadagent.db")


@contextmanager
def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Creates all tables if they don't already exist. Safe to call on every app start."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                plan TEXT NOT NULL DEFAULT 'free',
                created_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                niche TEXT,
                city TEXT,
                total_leads INTEGER DEFAULT 0,
                qualified_leads INTEGER DEFAULT 0,
                created_at REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                company_name TEXT,
                industry TEXT,
                business_model TEXT,
                linkedin_url TEXT,
                twitter_url TEXT,
                qualification_score INTEGER,
                is_qualified INTEGER,
                reasoning TEXT,
                outreach_json TEXT,
                email_sent INTEGER DEFAULT 0,
                created_at REAL NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs (id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                metadata TEXT,
                created_at REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)


# ------------------------------------------------------------------
# Runs
# ------------------------------------------------------------------

def create_run(user_id: int, niche: str, city: str) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO runs (user_id, niche, city, created_at) VALUES (?, ?, ?, ?)",
            (user_id, niche, city, time.time()),
        )
        return cur.lastrowid


def finalize_run(run_id: int, total_leads: int, qualified_leads: int):
    with get_connection() as conn:
        conn.execute(
            "UPDATE runs SET total_leads = ?, qualified_leads = ? WHERE id = ?",
            (total_leads, qualified_leads, run_id),
        )


def get_runs_for_user(user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM runs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]


# ------------------------------------------------------------------
# Leads
# ------------------------------------------------------------------

def save_lead(run_id: int, url: str, lead) -> int:
    """Persists a single qualified/disqualified lead result tied to a run."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO leads (
                run_id, url, company_name, industry, business_model,
                linkedin_url, twitter_url, qualification_score, is_qualified,
                reasoning, outreach_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, url, lead.company.name, lead.company.industry, lead.company.business_model,
                lead.company.linkedin_url, lead.company.twitter_url, lead.qualification_score,
                1 if lead.is_qualified else 0, lead.reasoning,
                json.dumps(lead.outreach_sequence.model_dump()), time.time(),
            ),
        )
        return cur.lastrowid


def get_leads_for_run(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM leads WHERE run_id = ? ORDER BY qualification_score DESC",
            (run_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_all_leads_for_user(user_id: int, limit: int = 500) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT leads.* FROM leads
            JOIN runs ON leads.run_id = runs.id
            WHERE runs.user_id = ?
            ORDER BY leads.created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]


def mark_email_sent(lead_id: int):
    with get_connection() as conn:
        conn.execute("UPDATE leads SET email_sent = 1 WHERE id = ?", (lead_id,))


# ------------------------------------------------------------------
# Usage tracking (for the admin dashboard / plan limits)
# ------------------------------------------------------------------

def log_usage_event(user_id: int, event_type: str, metadata: Optional[dict] = None):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO usage_events (user_id, event_type, metadata, created_at) VALUES (?, ?, ?, ?)",
            (user_id, event_type, json.dumps(metadata or {}), time.time()),
        )


def count_usage_this_month(user_id: int, event_type: str) -> int:
    month_start = time.time() - (30 * 24 * 60 * 60)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as c FROM usage_events WHERE user_id = ? AND event_type = ? AND created_at >= ?",
            (user_id, event_type, month_start),
        ).fetchone()
        return row["c"] if row else 0