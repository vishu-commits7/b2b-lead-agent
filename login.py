import re
import streamlit as st

st.set_page_config(page_title="LeadAgent AI - Login", layout="wide", initial_sidebar_state="collapsed")

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# If this session already passed the gate, skip straight to the app.
if st.session_state.get("authenticated"):
    try:
        st.switch_page("main.py")
    except Exception:
        st.success("You're already signed in.")
        st.info("Open main.py directly, or clear this session to log in again.")
    st.stop()

# ============================================================
# BACKGROUND — animated CSS blob mesh (replaces the old broken
# JS canvas, which was invisible because it rendered inside a
# 0-height iframe and never actually appeared on screen)
# ============================================================
st.markdown("""
<style>
    .stApp {
        background: radial-gradient(circle at 15% 20%, #1f1240 0%, #0a0b10 55%);
        overflow: hidden;
    }

    .blob-field {
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        z-index: 0;
        pointer-events: none;
        overflow: hidden;
    }
    .blob {
        position: absolute;
        border-radius: 50%;
        filter: blur(60px);
        opacity: 0.45;
    }
    .blob-1 {
        width: 480px; height: 480px;
        top: -10%; left: -5%;
        background: radial-gradient(circle, #3d1a5b, transparent 70%);
        animation: drift-a 22s ease-in-out infinite;
    }
    .blob-2 {
        width: 420px; height: 420px;
        bottom: -12%; right: -8%;
        background: radial-gradient(circle, #0f3459, transparent 70%);
        animation: drift-b 26s ease-in-out infinite;
    }
    .blob-3 {
        width: 320px; height: 320px;
        top: 40%; left: 55%;
        background: radial-gradient(circle, #00e5ff, transparent 70%);
        opacity: 0.15;
        animation: drift-c 18s ease-in-out infinite;
    }
    @keyframes drift-a {
        0%, 100% { transform: translate(0, 0) scale(1); }
        50% { transform: translate(60px, 40px) scale(1.1); }
    }
    @keyframes drift-b {
        0%, 100% { transform: translate(0, 0) scale(1); }
        50% { transform: translate(-50px, -30px) scale(1.08); }
    }
    @keyframes drift-c {
        0%, 100% { transform: translate(0, 0) scale(1); }
        50% { transform: translate(-40px, 50px) scale(0.9); }
    }

    /* ============================================================
       LOGIN CARD
       ============================================================ */
    .login-container {
        position: relative;
        z-index: 1;
        background: rgba(255, 255, 255, 0.04);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 24px;
        padding: 40px;
        max-width: 480px;
        margin: 80px auto 0 auto;
        text-align: center;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
        animation: card-in 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
    }
    @keyframes card-in {
        0% { opacity: 0; transform: translateY(16px); }
        100% { opacity: 1; transform: translateY(0); }
    }

    h1 {
        color: #ffffff !important;
        font-weight: 800 !important;
        letter-spacing: -1px;
    }
    p { color: #a0a5c1 !important; }

    .badge-row {
        color: #505570;
        display: block;
        margin-top: 20px;
        font-size: 0.85rem;
    }
</style>

<div class="blob-field">
    <div class="blob blob-1"></div>
    <div class="blob blob-2"></div>
    <div class="blob blob-3"></div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# LOGIN CARD CONTENT
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

    user_email = st.text_input("Enter your work email address", placeholder="you@company.com")

    if st.button("🚀 Get Started", use_container_width=True, type="primary"):
        if not user_email:
            st.error("Please enter your email address.")
        elif not EMAIL_PATTERN.match(user_email.strip()):
            st.error("That doesn't look like a valid email address.")
        else:
            st.session_state["authenticated"] = True
            st.session_state["user_email"] = user_email.strip()
            st.success("Access granted. Loading your lead workspace...")
            try:
                st.switch_page("main.py")
            except Exception:
                st.warning(
                    "Couldn't switch pages automatically (this needs Streamlit 1.36+). "
                    "Update Streamlit, or open main.py directly for now."
                )

    st.button(
        "🔑 Corporate SSO",
        use_container_width=True,
        disabled=True,
        help="Not available yet — coming in a future release.",
    )

    st.markdown(
        '<small class="badge-row">✓ Free Forever &nbsp; • &nbsp; ✓ No Credit Card &nbsp; • &nbsp; ✓ 60s Setup</small>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)