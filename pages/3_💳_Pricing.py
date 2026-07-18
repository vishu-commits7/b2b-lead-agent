"""Pricing and subscription upgrade page."""

import streamlit as st

import config
from database import get_user_by_id
from services.billing import create_billing_portal, create_checkout_session, stripe_configured
from ui.auth_guard import init_session, require_auth, sidebar_user_menu
from ui.theme import ENTERPRISE_CSS

st.set_page_config(page_title="Pricing | LeadAgent.io", layout="wide")
init_session()
require_auth()

st.markdown(ENTERPRISE_CSS, unsafe_allow_html=True)
st.sidebar.title("Pricing")
sidebar_user_menu()

user_id = st.session_state.user_id
current_plan = st.session_state.user_plan
user = get_user_by_id(user_id) or {}

st.markdown("# 💳 Plans & Pricing")
st.markdown("Choose the plan that matches your outbound volume. All plans include core discovery and ICP scoring.")

if not stripe_configured():
    st.warning("Stripe is not configured yet. Set `STRIPE_SECRET_KEY`, `STRIPE_PRICE_PRO`, and `STRIPE_PRICE_ENTERPRISE` in `.env` to enable live billing.")

st.markdown(f"**Your current plan:** {config.PLANS.get(current_plan, {}).get('name', current_plan)}")

cols = st.columns(3)
plan_keys = ["free", "pro", "enterprise"]

for i, plan_key in enumerate(plan_keys):
    plan = config.PLANS[plan_key]
    with cols[i]:
        featured = plan_key == "pro"
        st.markdown(f"""
        <div class="plan-card {'featured' if featured else ''}">
            <h3>{plan['name']}</h3>
            <div style="font-size:2rem;font-weight:900;color:#fff;">
                ${plan['price_monthly']:,}<span style="font-size:0.9rem;color:#64748b;">/mo</span>
            </div>
            <p style="color:#64748b;font-size:0.85rem;">or ${plan['price_annual']:,}/year (2 months free)</p>
        </div>
        """, unsafe_allow_html=True)

        runs = "Unlimited" if plan["runs_per_month"] < 0 else f"{plan['runs_per_month']}/month"
        st.markdown(f"""
        - **{runs}** pipeline runs
        - **{plan['leads_per_run']}** leads per run
        - Contact enrichment: {'✅' if plan['contact_enrichment'] else '❌'}
        - Email sequences: {'✅' if plan['email_sequences'] else '❌'}
        - REST API: {'✅' if plan['api_access'] else '❌'}
        - Team seats: **{plan['team_seats']}**
        - Priority support: {'✅' if plan['priority_support'] else '❌'}
        - White-label: {'✅' if plan['white_label'] else '❌'}
        """)

        if plan_key == current_plan:
            st.button("Current Plan", disabled=True, key=f"plan_{plan_key}", use_container_width=True)
        elif plan_key == "free":
            st.button("Downgrade via Portal", disabled=not stripe_configured(), key=f"plan_{plan_key}", use_container_width=True)
        else:
            if st.button(f"Upgrade to {plan['name']}", key=f"upgrade_{plan_key}", type="primary" if featured else "secondary", use_container_width=True):
                ok, msg, url = create_checkout_session(user_id, st.session_state.user_email, plan_key)
                if ok and url:
                    st.markdown(f"[Complete checkout →]({url})")
                    st.info("Click the link above to complete payment via Stripe.")
                else:
                    st.error(msg)

st.markdown("---")
st.markdown("### Enterprise Custom Deployment")
st.markdown("""
For agencies and teams needing **white-label deployment**, **custom integrations**, or **on-premise hosting**:
- Dedicated instance with your branding
- Custom CRM integrations (HubSpot, Salesforce, Pipedrive)
- SLA-backed uptime and priority support
- Typical engagement: **$25,000 – $75,000** one-time + monthly support

Contact: **enterprise@leadagent.io** (replace with your email)
""")

if stripe_configured() and user.get("stripe_customer_id"):
    if st.button("Manage Billing & Invoices"):
        ok, msg, url = create_billing_portal(user["stripe_customer_id"])
        if url:
            st.markdown(f"[Open billing portal →]({url})")
        else:
            st.error(msg)
