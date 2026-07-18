"""
auth.py — Real authentication for LeadAgent.io

This replaces the old login.py gate, which accepted any non-empty email
with no password and no verification. This module does actual password
hashing (PBKDF2-HMAC-SHA256 with a random per-user salt, no external
dependency needed) and checks credentials against the users table in
database.py.

This is NOT enterprise SSO — it's real, but simple, single-project auth.
If you sell this to a company that requires SSO/SAML, that's a separate,
larger integration (Auth0, WorkOS, etc.) — say so honestly rather than
implying this covers it.
"""

import hashlib
import hmac
import os
import time
from typing import Optional, Tuple

from database import get_connection, create_user_settings, log_audit

PBKDF2_ITERATIONS = 260_000


def _hash_password(password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
    """Returns (hash_hex, salt_hex). Generates a new random salt if none given."""
    if salt is None:
        salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return digest.hex(), salt.hex()


def _verify_password(password: str, stored_hash_hex: str, salt_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    candidate_hash, _ = _hash_password(password, salt)
    # constant-time comparison to avoid timing attacks
    return hmac.compare_digest(candidate_hash, stored_hash_hex)


def sign_up(email: str, password: str) -> Tuple[bool, str]:
    """Creates a new user. Returns (success, message)."""
    email = email.strip().lower()
    if len(password) < 8:
        return False, "Password must be at least 8 characters."

    password_hash, salt = _hash_password(password)
    try:
        now = time.time()
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO users (email, password_hash, salt, plan, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (email, password_hash, salt, "free", now, now),
            )
            user_id = cur.lastrowid
        create_user_settings(user_id)
        log_audit(user_id, "signup", email)
        return True, "Account created."
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            return False, "An account with this email already exists."
        return False, f"Could not create account: {e}"


def log_in(email: str, password: str) -> Tuple[bool, Optional[dict], str]:
    """Verifies credentials. Returns (success, user_dict_or_None, message)."""
    email = email.strip().lower()
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    if row is None:
        return False, None, "No account found with that email."

    if not _verify_password(password, row["password_hash"], row["salt"]):
        return False, None, "Incorrect password."

    return True, dict(row), "Welcome back."


def change_password(user_id: int, new_password: str) -> Tuple[bool, str]:
    if len(new_password) < 8:
        return False, "Password must be at least 8 characters."
    password_hash, salt = _hash_password(new_password)
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
            (password_hash, salt, user_id),
        )
    return True, "Password updated."