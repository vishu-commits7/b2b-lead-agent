"""Analytics dashboard — run history, conversion trends, industry breakdown."""

import json
from datetime import datetime

import streamlit as st

from database import get_analytics_for_user, get_leads_for_run, get_runs_for_user
from ui.auth_guard import init_session, require_auth, sidebar_user_menu
from ui.theme import ENTERPRISE_CSS

st.set_page_config(page_title="Analytics | LeadAgent.io", layout="wide")
init_session()
require_auth()

st.markdown(ENTERPRISE_CSS, unsafe_allow_html=True)
st.sidebar.title("Analytics")
sidebar_user_menu()

user_id = st.session_state.user_id
analytics = get_analytics_for_user(user_id)

st.markdown("# 📊 Analytics Dashboard")
st.markdown("Track pipeline performance, qualification rates, and lead intelligence over time.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Runs", analytics["total_runs"])
c2.metric("Leads Discovered", analytics["total_leads"])
c3.metric("Qualified Leads", analytics["qualified_leads"])
conv = (analytics["qualified_leads"] / analytics["total_leads"] * 100) if analytics["total_leads"] else 0
c4.metric("Qualification Rate", f"{conv:.1f}%")

st.markdown("---")

col_left, col_right = st.columns(2)

with col_left:
    st.markdown("### Recent Pipeline Runs")
    runs = analytics["recent_runs"]
    if not runs:
        st.info("No runs yet. Launch your first pipeline from the home page.")
    else:
        for run in runs:
            ts = datetime.fromtimestamp(run["created_at"]).strftime("%Y-%m-%d %H:%M")
            qual_rate = (run["qualified_leads"] / run["total_leads"] * 100) if run["total_leads"] else 0
            with st.expander(f"**{run['niche']}** in {run['city']} — {ts}"):
                st.markdown(f"- Leads: **{run['total_leads']}** · Qualified: **{run['qualified_leads']}** ({qual_rate:.0f}%)")
                st.markdown(f"- Avg score: **{run.get('avg_score', 0):.1f}**")
                if st.button("Load leads from this run", key=f"load_{run['id']}"):
                    from models.schemas import LeadQualificationResult, LeadCompanyInfo, OutreachDraft
                    db_leads = get_leads_for_run(run["id"], user_id)
                    restored = []
                    for row in db_leads:
                        outreach = json.loads(row["outreach_json"]) if row["outreach_json"] else {}
                        contact = json.loads(row["contact_json"]) if row.get("contact_json") else None
                        sequence = json.loads(row["sequence_json"]) if row.get("sequence_json") else None
                        lead = LeadQualificationResult(
                            company=LeadCompanyInfo(
                                name=row["company_name"] or "",
                                industry=row["industry"] or "",
                                business_model=row["business_model"] or "",
                                linkedin_url=row["linkedin_url"] or "",
                                twitter_url=row["twitter_url"] or "",
                                employee_estimate=row.get("employee_estimate") or "Unknown",
                                tech_stack_signals=json.loads(row.get("tech_stack_json") or "[]"),
                            ),
                            qualification_score=row["qualification_score"] or 0,
                            is_qualified=bool(row["is_qualified"]),
                            reasoning=row["reasoning"] or "",
                            pain_points=json.loads(row.get("pain_points_json") or "[]"),
                            buying_signals=json.loads(row.get("buying_signals_json") or "[]"),
                            outreach_sequence=OutreachDraft(**outreach) if outreach else OutreachDraft(
                                subject_line="", email_body="", linkedin_note="", chosen_framework="N/A"
                            ),
                        )
                        if contact:
                            from models.schemas import ContactEnrichment
                            lead.primary_contact = ContactEnrichment(**contact)
                        if sequence:
                            from models.schemas import EmailSequence
                            lead.email_sequence = EmailSequence(**sequence)
                        restored.append((row["url"], lead))
                    st.session_state.processed_leads = restored
                    st.session_state.selected_leads = {url: True for url, _ in restored}
                    st.success(f"Loaded {len(restored)} leads. Go to Home to view them.")
                    st.page_link("main.py", label="→ Open Home Dashboard")

with col_right:
    st.markdown("### Industry Distribution")
    industries = analytics.get("industries", {})
    if industries:
        for industry, count in industries.items():
            pct = count / max(analytics["total_leads"], 1) * 100
            st.progress(min(pct / 100, 1.0), text=f"{industry} ({count})")
    else:
        st.info("Industry data appears after your first pipeline run.")

st.markdown("---")
st.markdown("### All Runs")
all_runs = get_runs_for_user(user_id, limit=50)
if all_runs:
    st.dataframe(
        [{
            "Date": datetime.fromtimestamp(r["created_at"]).strftime("%Y-%m-%d"),
            "Niche": r["niche"],
            "City": r["city"],
            "Leads": r["total_leads"],
            "Qualified": r["qualified_leads"],
            "Avg Score": round(r.get("avg_score") or 0, 1),
        } for r in all_runs],
        use_container_width=True,
        hide_index=True,
    )
