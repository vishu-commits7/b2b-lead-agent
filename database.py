"""
database.py — Enterprise persistence for LeadAgent.io
SQLite by default; swap DATABASE_PATH for Postgres in production.
"""

import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

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
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                plan TEXT NOT NULL DEFAULT 'free',
                company_name TEXT DEFAULT '',
                stripe_customer_id TEXT DEFAULT '',
                stripe_subscription_id TEXT DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                gemini_api_key TEXT DEFAULT '',
                serper_api_key TEXT DEFAULT '',
                resend_api_key TEXT DEFAULT '',
                sender_email TEXT DEFAULT 'onboarding@resend.dev',
                default_icp TEXT DEFAULT '',
                default_niche TEXT DEFAULT 'Software Development Agencies',
                default_city TEXT DEFAULT 'Austin',
                marketing_framework TEXT DEFAULT 'PAS (Problem, Agitation, Solution)',
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                key_hash TEXT NOT NULL,
                key_prefix TEXT NOT NULL,
                label TEXT DEFAULT 'Default',
                last_used_at REAL,
                created_at REAL NOT NULL,
                revoked INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                niche TEXT,
                city TEXT,
                icp_snapshot TEXT,
                total_leads INTEGER DEFAULT 0,
                qualified_leads INTEGER DEFAULT 0,
                avg_score REAL DEFAULT 0,
                status TEXT DEFAULT 'completed',
                created_at REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                company_name TEXT,
                industry TEXT,
                business_model TEXT,
                linkedin_url TEXT,
                twitter_url TEXT,
                employee_estimate TEXT,
                tech_stack_json TEXT,
                qualification_score INTEGER,
                is_qualified INTEGER,
                reasoning TEXT,
                pain_points_json TEXT,
                buying_signals_json TEXT,
                outreach_json TEXT,
                contact_json TEXT,
                sequence_json TEXT,
                email_sent INTEGER DEFAULT 0,
                crm_exported INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                tags_json TEXT DEFAULT '[]',
                created_at REAL NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                details TEXT,
                ip_address TEXT DEFAULT '',
                created_at REAL NOT NULL
            )
        """)


# ------------------------------------------------------------------
# Users & settings
# ------------------------------------------------------------------

def create_user_settings(user_id: int):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)",
            (user_id,),
        )


def get_user_settings(user_id: int) -> Dict[str, Any]:
    create_user_settings(user_id)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM user_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else {}


def update_user_settings(user_id: int, **fields):
    create_user_settings(user_id)
    allowed = {
        "gemini_api_key", "serper_api_key", "resend_api_key", "sender_email",
        "default_icp", "default_niche", "default_city", "marketing_framework",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    cols = ", ".join(f"{k} = ?" for k in updates)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE user_settings SET {cols} WHERE user_id = ?",
            (*updates.values(), user_id),
        )


def update_user_plan(user_id: int, plan: str, stripe_customer_id: str = "", stripe_subscription_id: str = ""):
    with get_connection() as conn:
        conn.execute(
            """UPDATE users SET plan = ?, stripe_customer_id = COALESCE(NULLIF(?, ''), stripe_customer_id),
               stripe_subscription_id = COALESCE(NULLIF(?, ''), stripe_subscription_id),
               updated_at = ? WHERE id = ?""",
            (plan, stripe_customer_id, stripe_subscription_id, time.time(), user_id),
        )


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
        return dict(row) if row else None


def get_all_users(limit: int = 200) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, email, plan, company_name, created_at FROM users ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_platform_stats() -> Dict[str, Any]:
    with get_connection() as conn:
        users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
        runs = conn.execute("SELECT COUNT(*) as c FROM runs").fetchone()["c"]
        leads = conn.execute("SELECT COUNT(*) as c FROM leads").fetchone()["c"]
        qualified = conn.execute("SELECT COUNT(*) as c FROM leads WHERE is_qualified = 1").fetchone()["c"]
        by_plan = conn.execute(
            "SELECT plan, COUNT(*) as c FROM users GROUP BY plan"
        ).fetchall()
        return {
            "total_users": users,
            "total_runs": runs,
            "total_leads": leads,
            "qualified_leads": qualified,
            "users_by_plan": {r["plan"]: r["c"] for r in by_plan},
        }


# ------------------------------------------------------------------
# API keys
# ------------------------------------------------------------------

def _hash_api_key(raw_key: str) -> str:
    import hashlib
    return hashlib.sha256(raw_key.encode()).hexdigest()


def create_api_key(user_id: int, label: str = "Default") -> str:
    raw_key = f"la_{secrets.token_urlsafe(32)}"
    prefix = raw_key[:12]
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO api_keys (user_id, key_hash, key_prefix, label, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, _hash_api_key(raw_key), prefix, label, time.time()),
        )
    return raw_key


def verify_api_key(raw_key: str) -> Optional[Dict[str, Any]]:
    if not raw_key or not raw_key.startswith("la_"):
        return None
    key_hash = _hash_api_key(raw_key)
    with get_connection() as conn:
        row = conn.execute(
            """SELECT api_keys.*, users.email, users.plan FROM api_keys
               JOIN users ON api_keys.user_id = users.id
               WHERE api_keys.key_hash = ? AND api_keys.revoked = 0""",
            (key_hash,),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE api_keys SET last_used_at = ? WHERE key_hash = ?",
                (time.time(), key_hash),
            )
            return dict(row)
    return None


def list_api_keys(user_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, key_prefix, label, last_used_at, created_at, revoked FROM api_keys WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def revoke_api_key(user_id: int, key_id: int):
    with get_connection() as conn:
        conn.execute(
            "UPDATE api_keys SET revoked = 1 WHERE id = ? AND user_id = ?",
            (key_id, user_id),
        )


# ------------------------------------------------------------------
# Runs & leads
# ------------------------------------------------------------------

def create_run(user_id: int, niche: str, city: str, icp_snapshot: str = "") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO runs (user_id, niche, city, icp_snapshot, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, niche, city, icp_snapshot, time.time()),
        )
        return cur.lastrowid


def finalize_run(run_id: int, total_leads: int, qualified_leads: int, avg_score: float = 0):
    with get_connection() as conn:
        conn.execute(
            "UPDATE runs SET total_leads = ?, qualified_leads = ?, avg_score = ?, status = 'completed' WHERE id = ?",
            (total_leads, qualified_leads, avg_score, run_id),
        )


def save_lead(user_id: int, run_id: int, url: str, lead) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO leads (
                run_id, user_id, url, company_name, industry, business_model,
                linkedin_url, twitter_url, employee_estimate, tech_stack_json,
                qualification_score, is_qualified, reasoning, pain_points_json,
                buying_signals_json, outreach_json, contact_json, sequence_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, user_id, url, lead.company.name, lead.company.industry,
                lead.company.business_model, lead.company.linkedin_url, lead.company.twitter_url,
                lead.company.employee_estimate, json.dumps(lead.company.tech_stack_signals),
                lead.qualification_score, 1 if lead.is_qualified else 0, lead.reasoning,
                json.dumps(lead.pain_points), json.dumps(lead.buying_signals),
                json.dumps(lead.outreach_sequence.model_dump()),
                json.dumps(lead.primary_contact.model_dump()) if lead.primary_contact else "",
                json.dumps(lead.email_sequence.model_dump()) if lead.email_sequence else "",
                time.time(),
            ),
        )
        return cur.lastrowid


def get_runs_for_user(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM runs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_leads_for_run(run_id: int, user_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM leads WHERE run_id = ? AND user_id = ? ORDER BY qualification_score DESC",
            (run_id, user_id),
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_leads_for_user(user_id: int, limit: int = 500) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM leads WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_analytics_for_user(user_id: int) -> Dict[str, Any]:
    with get_connection() as conn:
        runs = conn.execute(
            "SELECT COUNT(*) as c, AVG(avg_score) as avg_score, SUM(qualified_leads) as qualified, SUM(total_leads) as total FROM runs WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        industries = conn.execute(
            """SELECT industry, COUNT(*) as c FROM leads WHERE user_id = ? AND industry IS NOT NULL
               GROUP BY industry ORDER BY c DESC LIMIT 10""",
            (user_id,),
        ).fetchall()
        recent = conn.execute(
            "SELECT * FROM runs WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
            (user_id,),
        ).fetchall()
        return {
            "total_runs": runs["c"] or 0,
            "avg_score": round(runs["avg_score"] or 0, 1),
            "total_leads": runs["total"] or 0,
            "qualified_leads": runs["qualified"] or 0,
            "industries": {r["industry"]: r["c"] for r in industries},
            "recent_runs": [dict(r) for r in recent],
        }


def mark_email_sent(lead_id: int, user_id: int):
    with get_connection() as conn:
        conn.execute(
            "UPDATE leads SET email_sent = 1 WHERE id = ? AND user_id = ?",
            (lead_id, user_id),
        )


# ------------------------------------------------------------------
# Usage & audit
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


def log_audit(user_id: Optional[int], action: str, details: str = "", ip_address: str = ""):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO audit_log (user_id, action, details, ip_address, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, action, details, ip_address, time.time()),
        )


def get_audit_log(limit: int = 100) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT audit_log.*, users.email FROM audit_log
               LEFT JOIN users ON audit_log.user_id = users.id
               ORDER BY audit_log.created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
