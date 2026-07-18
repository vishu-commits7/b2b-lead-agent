"""Account settings — API keys, defaults, password change."""

import streamlit as st

import config
from auth import change_password
from database import get_user_settings, update_user_settings
from ui.auth_guard import init_session, require_auth, sidebar_user_menu
from ui.theme import ENTERPRISE_CSS

st.set_page_config(page_title="Settings | LeadAgent.io", layout="wide")
init_session()
require_auth()

st.markdown(ENTERPRISE_CSS, unsafe_allow_html=True)
st.sidebar.title("Settings")
sidebar_user_menu()

user_id = st.session_state.user_id
settings = get_user_settings(user_id)

st.markdown("# ⚙️ Account Settings")

tab_api, tab_defaults, tab_security = st.tabs(["API Keys", "Pipeline Defaults", "Security"])

with tab_api:
    st.markdown("Store your API keys securely. These are used for your pipeline runs.")
    st.info("Keys are stored in your local database. For production, use environment variables or a secrets manager.")

    gemini = st.text_input("Gemini API Key", value=settings.get("gemini_api_key", ""), type="password")
    serper = st.text_input("Serper API Key", value=settings.get("serper_api_key", ""), type="password")
    resend = st.text_input("Resend API Key", value=settings.get("resend_api_key", ""), type="password")
    sender = st.text_input("Default Sender Email", value=settings.get("sender_email", "onboarding@resend.dev"))

    if st.button("Save API Settings", type="primary"):
        update_user_settings(
            user_id,
            gemini_api_key=gemini,
            serper_api_key=serper,
            resend_api_key=resend,
            sender_email=sender,
        )
        st.success("API settings saved.")

with tab_defaults:
    st.markdown("Default values pre-filled when you launch a new pipeline.")
    niche = st.text_input("Default Niche", value=settings.get("default_niche", ""))
    city = st.text_input("Default City", value=settings.get("default_city", ""))
    icp = st.text_area("Default ICP", value=settings.get("default_icp", ""), height=120)
    framework = st.selectbox(
        "Default Copywriting Framework",
        config.MARKETING_FRAMEWORKS,
        index=config.MARKETING_FRAMEWORKS.index(settings["marketing_framework"])
        if settings.get("marketing_framework") in config.MARKETING_FRAMEWORKS else 0,
    )

    if st.button("Save Defaults", type="primary"):
        update_user_settings(
            user_id,
            default_niche=niche,
            default_city=city,
            default_icp=icp,
            marketing_framework=framework,
        )
        st.session_state.marketing_framework = framework
        st.success("Defaults saved.")

with tab_security:
    st.markdown("### Change Password")
    new_pw = st.text_input("New Password", type="password")
    confirm_pw = st.text_input("Confirm Password", type="password")
    if st.button("Update Password"):
        if new_pw != confirm_pw:
            st.error("Passwords don't match.")
        elif len(new_pw) < 8:
            st.error("Password must be at least 8 characters.")
        else:
            ok, msg = change_password(user_id, new_pw)
            st.success(msg) if ok else st.error(msg)
