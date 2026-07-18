"""Shared Streamlit auth guard and session helpers."""

import streamlit as st

import config
from database import init_db, log_audit


def init_session():
    init_db()
    defaults = {
        "authenticated": False,
        "user_id": None,
        "user_email": "",
        "user_plan": "free",
        "processed_leads": [],
        "selected_leads": {},
        "removed_lead_urls": set(),
        "lead_notes": {},
        "lead_tags": {},
        "search_history_log": [],
        "marketing_framework": "PAS (Problem, Agitation, Solution)",
        "current_run_id": None,
        "usage_tokens_est": 0,
        "usage_calls": 0,
        "onboarding_dismissed": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def require_auth(redirect_to_login: bool = True):
    init_session()
    if not st.session_state.get("authenticated"):
        if redirect_to_login:
            st.warning("Please sign in to access LeadAgent.io")
            if st.button("Go to Login"):
                try:
                    st.switch_page("login.py")
                except Exception:
                    st.info("Run `streamlit run login.py` to sign in.")
            st.stop()
        return False
    return True


def is_admin() -> bool:
    email = st.session_state.get("user_email", "").lower()
    if not email:
        return False
    if config.ADMIN_EMAILS and email in config.ADMIN_EMAILS:
        return True
    return False


def logout():
    log_audit(st.session_state.get("user_id"), "logout", st.session_state.get("user_email", ""))
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    try:
        st.switch_page("login.py")
    except Exception:
        st.rerun()


def sidebar_user_menu():
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**{st.session_state.get('user_email', '')}**")
    plan = st.session_state.get("user_plan", "free")
    plan_name = config.PLANS.get(plan, config.PLANS["free"])["name"]
    st.sidebar.caption(f"Plan: **{plan_name}**")
    if st.sidebar.button("Sign Out", use_container_width=True):
        logout()
