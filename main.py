"""
LeadAgent.io — Enterprise B2B Lead Intelligence Platform
Autonomous discovery, ICP scoring, contact enrichment, and multi-touch outreach.
"""

import csv
import io
import os
import time

import resend
import streamlit as st

import config
from database import (
    create_run,
    finalize_run,
    get_user_settings,
    log_audit,
    save_lead,
    update_user_settings,
)
from models.schemas import LeadQualificationResult
from services.billing import create_checkout_session, stripe_configured
from services.crm_export import export_hubspot_csv, export_json, export_salesforce_csv, export_standard_csv
from services.pipeline import discover_company_urls, run_pipeline
from services.plans import check_can_run_pipeline, feature_enabled, get_plan_limits, record_pipeline_run
from ui.auth_guard import init_session, require_auth, sidebar_user_menu
from ui.theme import ENTERPRISE_CSS, get_tier, score_ring_html

st.set_page_config(
    page_title="LeadAgent.io | Enterprise Lead Intelligence",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session()
require_auth()

user_id = st.session_state.user_id
user_plan = st.session_state.user_plan
plan_limits = get_plan_limits(user_plan)
user_settings = get_user_settings(user_id)

st.markdown(ENTERPRISE_CSS, unsafe_allow_html=True)

# Load persisted settings into session defaults
if not st.session_state.get("_settings_loaded"):
    st.session_state.marketing_framework = user_settings.get("marketing_framework") or st.session_state.marketing_framework
    st.session_state._settings_loaded = True

# Handle Stripe upgrade redirect
if st.query_params.get("upgrade") == "success":
    st.success(f"Upgrade initiated! Your plan will update once Stripe confirms payment.")
if st.query_params.get("upgrade") == "cancelled":
    st.info("Upgrade cancelled. You can upgrade anytime from Pricing.")

st.markdown("""
<div class="premium-header">
    <div style="font-size:2.5rem;">🪐</div>
    <h1 class="premium-title">LeadAgent.io</h1>
    <p style="color:#94a3b8;margin:0.5rem 0 0 0;">Enterprise B2B Lead Intelligence · Discovery · Enrichment · Outreach</p>
</div>
""", unsafe_allow_html=True)

# ---- Sidebar ----
st.sidebar.title("Command Center")
sidebar_user_menu()

runs_used = 0
try:
    from database import count_usage_this_month
    runs_used = count_usage_this_month(user_id, "pipeline_run")
except Exception:
    pass

max_runs = plan_limits["runs_per_month"]
runs_label = f"{runs_used}/{max_runs}" if max_runs >= 0 else f"{runs_used}/∞"
st.sidebar.markdown(f"**Runs this month:** {runs_label}")
st.sidebar.markdown(f"**Leads per run:** up to {plan_limits['leads_per_run']}")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🧠 Copywriting Framework")
st.session_state.marketing_framework = st.sidebar.selectbox(
    "Outreach style",
    config.MARKETING_FRAMEWORKS,
    index=config.MARKETING_FRAMEWORKS.index(st.session_state.marketing_framework)
    if st.session_state.marketing_framework in config.MARKETING_FRAMEWORKS else 0,
    label_visibility="collapsed",
)

st.sidebar.markdown("### 🔑 API Connections")
gemini_key = st.sidebar.text_input(
    "Gemini API Key",
    value=user_settings.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY", ""),
    type="password",
)
serper_key = st.sidebar.text_input(
    "Serper API Key",
    value=user_settings.get("serper_api_key") or os.environ.get("SERPER_API_KEY", ""),
    type="password",
)
resend_key = st.sidebar.text_input(
    "Resend API Key",
    value=user_settings.get("resend_api_key") or os.environ.get("RESEND_API_KEY", ""),
    type="password",
)
sender_email = st.sidebar.text_input(
    "Sender Email",
    value=user_settings.get("sender_email") or "onboarding@resend.dev",
)

if st.sidebar.button("💾 Save Settings", use_container_width=True):
    update_user_settings(
        user_id,
        gemini_api_key=gemini_key,
        serper_api_key=serper_key,
        resend_api_key=resend_key,
        sender_email=sender_email,
        marketing_framework=st.session_state.marketing_framework,
    )
    st.sidebar.success("Settings saved.")

st.sidebar.markdown("### 🎯 Ideal Customer Profile")
icp_instruction = st.sidebar.text_area(
    "ICP Criteria",
    value=user_settings.get("default_icp") or "",
    height=100,
    placeholder="e.g. B2B SaaS, 20-100 employees, US-based, uses HubSpot...",
)
custom_hook = st.sidebar.text_input("Special Offer (optional)", value="")

# Enterprise feature flags
include_enrichment = feature_enabled(user_plan, "contact_enrichment")
include_sequence = feature_enabled(user_plan, "email_sequences")

if not include_enrichment or not include_sequence:
    st.sidebar.markdown("""
    <div class="upgrade-banner">
        <small>🔒 <b>Pro features locked:</b> Contact enrichment & 3-touch email sequences.
        <a href="#" style="color:#a5b4fc;">Upgrade →</a></small>
    </div>
    """, unsafe_allow_html=True)

# ---- Main inputs ----
col1, col2 = st.columns(2)
with col1:
    search_niche = st.text_input("🎯 Target Niche", value=user_settings.get("default_niche") or "Software Development Agencies")
with col2:
    search_city = st.text_input("📍 Location", value=user_settings.get("default_city") or "Austin")

max_leads_slider = plan_limits["leads_per_run"]
num_leads = st.slider("🔢 Leads to discover", min_value=3, max_value=max_leads_slider, value=min(5, max_leads_slider))

# ============================================================
# PIPELINE
# ============================================================

if st.button("🚀 Launch Discovery Pipeline", type="primary", use_container_width=True):
    if not gemini_key:
        st.error("Add your Gemini API key in the sidebar.")
    elif not serper_key:
        st.error("Add your Serper API key in the sidebar.")
    else:
        allowed, msg = check_can_run_pipeline(user_id, user_plan, num_leads)
        if not allowed:
            st.error(msg)
        else:
            full_query = f"{search_niche} in {search_city}"
            st.session_state.search_history_log.append(full_query)
            log_audit(user_id, "pipeline_start", full_query)

            with st.spinner("Discovering target companies..."):
                urls = discover_company_urls(full_query, serper_key, num_results=num_leads)

            if not urls:
                st.error("No companies found. Try a different niche or location.")
            else:
                run_id = create_run(user_id, search_niche, search_city, icp_instruction)
                st.session_state.current_run_id = run_id

                progress = st.progress(0)
                feed = st.empty()
                log_lines = [f"[LOG] Found {len(urls)} targets. Starting qualification..."]

                def on_log(line):
                    log_lines.append(line)
                    feed.markdown(f'<div class="activity-feed">{"<br>".join(log_lines[-8:])}</div>', unsafe_allow_html=True)

                def on_progress(done, total):
                    progress.progress(done / total)

                processed = run_pipeline(
                    urls=urls,
                    api_key=gemini_key,
                    icp_instruction=icp_instruction,
                    marketing_framework=st.session_state.marketing_framework,
                    custom_hook=custom_hook,
                    include_enrichment=include_enrichment,
                    include_sequence=include_sequence,
                    free_tier_throttle=True,
                    progress_callback=on_progress,
                    log_callback=on_log,
                    on_rate_limit=lambda w, a, m: st.info(f"Rate limit — waiting {w}s ({a}/{m})"),
                )

                for url, lead in processed:
                    save_lead(user_id, run_id, url, lead)

                qualified = sum(1 for _, l in processed if l.is_qualified)
                avg = sum(l.qualification_score for _, l in processed) / len(processed) if processed else 0
                finalize_run(run_id, len(processed), qualified, avg)
                record_pipeline_run(user_id, {"run_id": run_id, "leads": len(processed), "qualified": qualified})

                update_user_settings(
                    user_id,
                    default_icp=icp_instruction,
                    default_niche=search_niche,
                    default_city=search_city,
                )

                st.session_state.processed_leads = processed
                st.session_state.selected_leads = {url: True for url, _ in processed}
                st.success(f"Pipeline complete — {qualified}/{len(processed)} qualified leads.")
                log_audit(user_id, "pipeline_complete", f"run={run_id} qualified={qualified}")

# ============================================================
# RESULTS DASHBOARD
# ============================================================

processed_leads = st.session_state.processed_leads

if not processed_leads:
    st.markdown("""
    <div class="empty-state">
        <div style="font-size:3rem;">🛰️</div>
        <h3>No leads yet</h3>
        <p>Configure your ICP, set your niche and location, then launch the discovery pipeline.</p>
    </div>
    """, unsafe_allow_html=True)
else:
    total = len(processed_leads)
    qualified = sum(1 for _, l in processed_leads if l.is_qualified)
    rate = (qualified / total * 100) if total else 0
    avg_score = sum(l.qualification_score for _, l in processed_leads) / total

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Leads", total)
    m2.metric("Qualified", qualified)
    m3.metric("Conversion Rate", f"{rate:.1f}%")
    m4.metric("Avg Score", f"{avg_score:.1f}")

    min_score = st.slider("Minimum score filter", 0, 100, 0, 5)
    active = [
        (url, lead) for url, lead in processed_leads
        if lead.qualification_score >= min_score and url not in st.session_state.removed_lead_urls
    ]

    for idx, (url, lead) in enumerate(active):
        tier_label, tier_class = get_tier(lead.qualification_score)
        badge = "badge-qualified-glow" if lead.is_qualified else "badge-disqualified-glow"
        status = f"{'Qualified' if lead.is_qualified else 'Disqualified'} ({lead.qualification_score}/100)"

        pain_html = "".join(f'<span class="signal-chip pain-chip">{p}</span>' for p in lead.pain_points)
        signal_html = "".join(f'<span class="signal-chip">{s}</span>' for s in lead.buying_signals)

        st.markdown(f"""
        <div class="premium-lead-card">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.75rem;">
                <div style="display:flex;align-items:center;gap:0.9rem;">
                    {score_ring_html(lead.qualification_score)}
                    <div>
                        <h3 style="margin:0;color:#fff;">🏢 {lead.company.name}</h3>
                        <small style="color:#64748b;">{url}</small>
                    </div>
                </div>
                <div>
                    <span class="glow-badge {badge}">{status}</span>
                    <span class="tier-badge {tier_class}">{tier_label}</span>
                </div>
            </div>
            <div style="margin:0.75rem 0;color:#94a3b8;font-size:0.9rem;">
                <b style="color:#818cf8;">Industry:</b> {lead.company.industry} ·
                <b style="color:#818cf8;">Model:</b> {lead.company.business_model} ·
                <b style="color:#818cf8;">Size:</b> {lead.company.employee_estimate}
            </div>
            <div class="reasoning-box"><strong>AI Analysis:</strong> {lead.reasoning}</div>
            {f'<div style="margin-top:0.75rem;"><b style="color:#f87171;">Pain Points:</b> {pain_html}</div>' if pain_html else ''}
            {f'<div style="margin-top:0.5rem;"><b style="color:#34d399;">Buying Signals:</b> {signal_html}</div>' if signal_html else ''}
        </div>
        """, unsafe_allow_html=True)

        c1, c2 = st.columns([5, 1])
        with c1:
            st.session_state.selected_leads[url] = st.checkbox(
                f"Include in export batch — {lead.company.name}",
                value=st.session_state.selected_leads.get(url, True),
                key=f"sel_{url}_{idx}",
            )
        with c2:
            if st.button("🗑️", key=f"rm_{url}_{idx}"):
                st.session_state.removed_lead_urls.add(url)
                st.rerun()

        if lead.primary_contact and include_enrichment:
            c = lead.primary_contact
            st.info(f"👤 **{c.full_name}** · {c.title} · Email pattern: `{c.email_pattern}` · Confidence: {c.confidence}%")

        if lead.company.linkedin_url:
            st.link_button("LinkedIn", lead.company.linkedin_url, use_container_width=False)

        if lead.is_qualified and lead.outreach_sequence.subject_line:
            with st.expander(f"✉️ Outreach — {st.session_state.marketing_framework}"):
                tab1, tab2, tab3 = st.tabs(["Email", "LinkedIn", "Sequence"])

                with tab1:
                    st.markdown(f"**Subject:** `{lead.outreach_sequence.subject_line}`")
                    email_body = st.text_area("Email body", value=lead.outreach_sequence.email_body, height=180, key=f"em_{url}_{idx}")
                    recipient = st.text_input("Recipient", value=f"hello@{url}", key=f"to_{url}_{idx}")
                    if st.button(f"Send via Resend", key=f"send_{url}_{idx}"):
                        if not resend_key:
                            st.error("Add Resend API key in sidebar.")
                        else:
                            try:
                                resend.api_key = resend_key
                                resend.Emails.send({
                                    "from": sender_email,
                                    "to": [recipient],
                                    "subject": lead.outreach_sequence.subject_line,
                                    "text": email_body,
                                })
                                st.success(f"Sent to {recipient}")
                            except Exception as e:
                                st.error(str(e))

                with tab2:
                    li_note = st.text_area("LinkedIn note", value=lead.outreach_sequence.linkedin_note, height=100, key=f"li_{url}_{idx}")
                    color = "#10b981" if len(li_note) <= 300 else "#ef4444"
                    st.markdown(f"<span style='color:{color};font-weight:bold;'>{len(li_note)}/300 chars</span>", unsafe_allow_html=True)

                with tab3:
                    if lead.email_sequence and include_sequence:
                        for touch in lead.email_sequence.touches:
                            st.markdown(f"**Touch {touch.touch_number}** — Day +{touch.delay_days} · _{touch.purpose}_")
                            st.markdown(f"Subject: `{touch.subject_line}`")
                            st.text(touch.email_body[:500])
                            st.markdown("---")
                    else:
                        st.caption("3-touch sequences available on Pro and Enterprise plans.")

    # ---- Exports ----
    st.markdown("---")
    st.markdown("### 📤 Export & CRM Sync")
    sel = st.session_state.selected_leads
    sel_count = sum(1 for v in sel.values() if v)

    e1, e2, e3, e4 = st.columns(4)
    with e1:
        st.download_button("📊 Standard CSV", export_standard_csv(processed_leads, sel), f"leads_{int(time.time())}.csv", "text/csv", use_container_width=True)
    with e2:
        st.download_button("🟠 HubSpot CSV", export_hubspot_csv(processed_leads, sel), "hubspot_import.csv", "text/csv", use_container_width=True)
    with e3:
        st.download_button("☁️ Salesforce CSV", export_salesforce_csv(processed_leads, sel), "salesforce_import.csv", "text/csv", use_container_width=True)
    with e4:
        st.download_button("🧾 Full JSON", export_json(processed_leads), "leads.json", "application/json", use_container_width=True)

    st.caption(f"{sel_count} leads selected for CRM export")

st.markdown("<br><center style='color:#475569;font-size:0.78rem;'>LeadAgent.io · Enterprise B2B Lead Intelligence</center>", unsafe_allow_html=True)
