"""Admin dashboard — platform stats, user management, audit log."""

from datetime import datetime

import streamlit as st

import config
from database import get_all_users, get_audit_log, get_platform_stats, update_user_plan
from ui.auth_guard import init_session, is_admin, require_auth, sidebar_user_menu
from ui.theme import ENTERPRISE_CSS

st.set_page_config(page_title="Admin | LeadAgent.io", layout="wide")
init_session()
require_auth()

if not is_admin():
    st.error("Admin access required. Set your email in ADMIN_EMAILS in .env")
    st.stop()

st.markdown(ENTERPRISE_CSS, unsafe_allow_html=True)
st.sidebar.title("Admin")
sidebar_user_menu()

stats = get_platform_stats()

st.markdown("# 👑 Admin Console")
st.markdown("Platform-wide metrics and user management.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Users", stats["total_users"])
c2.metric("Pipeline Runs", stats["total_runs"])
c3.metric("Leads Processed", stats["total_leads"])
qual_rate = (stats["qualified_leads"] / stats["total_leads"] * 100) if stats["total_leads"] else 0
c4.metric("Platform Qual Rate", f"{qual_rate:.1f}%")

st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    st.markdown("### Users by Plan")
    for plan, count in stats.get("users_by_plan", {}).items():
        plan_name = config.PLANS.get(plan, {}).get("name", plan)
        st.markdown(f"- **{plan_name}**: {count} users")

with col2:
    st.markdown("### Revenue Potential (MRR)")
    mrr = 0
    for plan, count in stats.get("users_by_plan", {}).items():
        if plan in config.PLANS:
            mrr += config.PLANS[plan]["price_monthly"] * count
    st.metric("Estimated MRR", f"${mrr:,}")
    st.caption("Based on plan assignments, not actual Stripe billing.")

st.markdown("---")
st.markdown("### User Management")
users = get_all_users()
if users:
    for u in users:
        with st.expander(f"{u['email']} — {u.get('plan', 'free')}"):
            new_plan = st.selectbox(
                "Change plan",
                ["free", "pro", "enterprise"],
                index=["free", "pro", "enterprise"].index(u.get("plan", "free")),
                key=f"plan_sel_{u['id']}",
            )
            if st.button("Update Plan", key=f"upd_{u['id']}"):
                update_user_plan(u["id"], new_plan)
                st.success(f"Updated {u['email']} to {new_plan}")
                st.rerun()
            created = datetime.fromtimestamp(u["created_at"]).strftime("%Y-%m-%d")
            st.caption(f"Joined: {created}")

st.markdown("---")
st.markdown("### Audit Log")
logs = get_audit_log(limit=50)
if logs:
    st.dataframe(
        [{
            "Time": datetime.fromtimestamp(l["created_at"]).strftime("%Y-%m-%d %H:%M"),
            "User": l.get("email") or "—",
            "Action": l["action"],
            "Details": (l.get("details") or "")[:80],
        } for l in logs],
        use_container_width=True,
        hide_index=True,
    )
