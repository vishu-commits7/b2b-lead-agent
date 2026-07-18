"""
login.py — Real authentication gate for LeadAgent.io

Replaces the old cosmetic gate (email-format check only, no password,
no verification). This version actually calls auth.py, which checks
credentials against the SQLite `users` table in database.py using
PBKDF2 password hashing.

On success, sets:
    st.session_state["authenticated"] = True
    st.session_state["user_id"]       = int
    st.session_state["user_email"]    = str
    st.session_state["user_plan"]     = str

IMPORTANT — this file only guards the login page itself. It does not
stop someone from typing main.py's URL directly. main.py needs its own
check at the top (see the snippet at the bottom of this file) or this
gate is cosmetic all over again, just with a real backend behind it.
"""

import time

import streamlit as st

from database import init_db
from auth import sign_up, log_in

st.set_page_config(page_title="LeadAgent AI - Login", layout="wide", initial_sidebar_state="collapsed")

init_db()

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 60

if "login_attempts" not in st.session_state:
    st.session_state.login_attempts = 0
if "login_locked_until" not in st.session_state:
    st.session_state.login_locked_until = 0.0

# If this session already passed the gate, skip straight to the app.
if st.session_state.get("authenticated"):
    try:
        st.switch_page("main.py")
    except Exception:
        st.success("You're already signed in.")
        st.info("Open main.py directly, or clear this session to log in again.")
    st.stop()

# ============================================================
# BACKGROUND — animated CSS blob mesh
# ============================================================
st.markdown("""
<style>
    .stApp {
        background: radial-gradient(circle at 15% 20%, #1f1240 0%, #0a0b10 55%);
        overflow: hidden;
    }
    .blob-field {
        position: fixed; top: 0; left: 0; right: 0; bottom: 0;
        z-index: 0; pointer-events: none; overflow: hidden;
    }
    .blob { position: absolute; border-radius: 50%; filter: blur(60px); opacity: 0.45; }
    .blob-1 {
        width: 480px; height: 480px; top: -10%; left: -5%;
        background: radial-gradient(circle, #3d1a5b, transparent 70%);
        animation: drift-a 22s ease-in-out infinite;
    }
    .blob-2 {
        width: 420px; height: 420px; bottom: -12%; right: -8%;
        background: radial-gradient(circle, #0f3459, transparent 70%);
        animation: drift-b 26s ease-in-out infinite;
    }
    .blob-3 {
        width: 320px; height: 320px; top: 40%; left: 55%;
        background: radial-gradient(circle, #00e5ff, transparent 70%);
        opacity: 0.15; animation: drift-c 18s ease-in-out infinite;
    }
    @keyframes drift-a { 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(60px,40px) scale(1.1); } }
    @keyframes drift-b { 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(-50px,-30px) scale(1.08); } }
    @keyframes drift-c { 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(-40px,50px) scale(0.9); } }

    .login-container {
        position: relative; z-index: 1;
        background: rgba(255, 255, 255, 0.04);
        backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 24px; padding: 40px; max-width: 480px;
        margin: 60px auto 0 auto; text-align: center;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
        animation: card-in 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
    }
    @keyframes card-in { 0% { opacity: 0; transform: translateY(16px); } 100% { opacity: 1; transform: translateY(0); } }

    h1 { color: #ffffff !important; font-weight: 800 !important; letter-spacing: -1px; }
    p { color: #a0a5c1 !important; }
    .badge-row { color: #505570; display: block; margin-top: 20px; font-size: 0.85rem; }
    .field-hint { color: #6b7094; font-size: 0.8rem; text-align: left; margin-top: -8px; }
</style>

<div class="blob-field">
    <div class="blob blob-1"></div>
    <div class="blob blob-2"></div>
    <div class="blob blob-3"></div>
</div>
""", unsafe_allow_html=True)


def _locked_out() -> bool:
    return time.time() < st.session_state.login_locked_until


def _seconds_remaining() -> int:
    return max(0, int(st.session_state.login_locked_until - time.time()))


def _register_failed_attempt():
    st.session_state.login_attempts += 1
    if st.session_state.login_attempts >= MAX_LOGIN_ATTEMPTS:
        st.session_state.login_locked_until = time.time() + LOCKOUT_SECONDS
        st.session_state.login_attempts = 0


def _complete_login(user_row: dict):
    from database import log_audit
    st.session_state["authenticated"] = True
    st.session_state["user_id"] = user_row["id"]
    st.session_state["user_email"] = user_row["email"]
    st.session_state["user_plan"] = user_row.get("plan", "free")
    st.session_state.login_attempts = 0
    log_audit(user_row["id"], "login", user_row["email"])
    st.success("Access granted. Loading your lead workspace...")
    try:
        st.switch_page("main.py")
    except Exception:
        st.warning(
            "Couldn't switch pages automatically (this needs Streamlit 1.36+). "
            "Update Streamlit, or open main.py directly for now."
        )


# ============================================================
# CARD CONTENT
# ============================================================
_, center_col, _ = st.columns([1, 1.8, 1])

with center_col:
    st.markdown('<div class="login-container">', unsafe_allow_html=True)

    st.markdown("⚡ **LEADAGENT AI**")
    st.markdown("<h1>Your next 10 enterprise clients are ready.</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p>Analyze domains, verify contact vectors, and draft high-intent outreach instantly.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    if _locked_out():
        st.error(f"Too many failed attempts. Try again in {_seconds_remaining()}s.")
    else:
        tab_login, tab_signup = st.tabs(["Log In", "Create Account"])

        # ---------------- LOG IN ----------------
        with tab_login:
            login_email = st.text_input("Email", placeholder="you@company.com", key="login_email")
            login_password = st.text_input("Password", type="password", key="login_password")

            if st.button("🚀 Log In", use_container_width=True, type="primary", key="login_btn"):
                if not login_email or not login_password:
                    st.error("Enter both email and password.")
                else:
                    success, user_row, message = log_in(login_email, login_password)
                    if success:
                        _complete_login(user_row)
                    else:
                        _register_failed_attempt()
                        st.error(message)

        # ---------------- SIGN UP ----------------
        with tab_signup:
            signup_email = st.text_input("Email", placeholder="you@company.com", key="signup_email")
            signup_password = st.text_input("Password", type="password", key="signup_password")
            st.markdown('<p class="field-hint">Minimum 8 characters.</p>', unsafe_allow_html=True)
            signup_password_confirm = st.text_input("Confirm password", type="password", key="signup_password_confirm")

            if st.button("✨ Create Account", use_container_width=True, type="primary", key="signup_btn"):
                if not signup_email or not signup_password:
                    st.error("Enter an email and password.")
                elif signup_password != signup_password_confirm:
                    st.error("Passwords don't match.")
                else:
                    success, message = sign_up(signup_email, signup_password)
                    if success:
                        # log in immediately after account creation
                        _, user_row, _ = log_in(signup_email, signup_password)
                        _complete_login(user_row)
                    else:
                        st.error(message)

    st.button(
        "🔑 Corporate SSO",
        use_container_width=True,
        disabled=True,
        help="Not available yet — real email/password auth only for now.",
    )

    st.markdown(
        '<small class="badge-row">✓ Real password auth &nbsp; • &nbsp; ✓ No Credit Card &nbsp; • &nbsp; ✓ 60s Setup</small>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# REQUIRED: paste this at the very top of main.py, right after
# st.set_page_config(), or this login page protects nothing —
# main.py's URL is still open to anyone who types it directly.
# ============================================================
#
#   if not st.session_state.get("authenticated"):
#       st.warning("Please log in first.")
#       st.stop()