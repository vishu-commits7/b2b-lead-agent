"""
LeadAgent.io — Autonomous B2B Lead Discovery & Qualification Agent
=====================================================================

DESIGN SYSTEM NOTES
--------------------
This file pairs a Gemini-powered discovery/qualification pipeline with a
"live data terminal" visual language. The motion system is intentionally
built around a small set of repeated ideas rather than scattered effects:

1. Ambient motion (starfield, header radar sweep) signals the app is a
   live system, not a static form — it runs continuously in the background
   at low opacity so it never competes with content.
2. Entrance motion (card-rise, badge-pop, count-reveal) is staggered by
   index across lists (lead cards, metric cards, leaderboard rows) so
   results feel like they are arriving, not just appearing.
3. Outcome motion (tier glow, confetti, score ring fill) is reserved for
   moments that matter — a qualified lead, a platinum-tier score — so it
   reads as a reward signal rather than decoration.
4. Utility motion (skeleton shimmer, activity feed, progress flow) fills
   the waiting period during the scrape/qualify loop so the terminal never
   looks frozen.
5. Every animation respects `prefers-reduced-motion` via a single global
   media query near the end of the stylesheet.

Component inventory (all implemented with pure CSS + Streamlit markdown,
no external JS framework, so there is nothing to bundle or break):
  - starfield background (ambient)
  - header radar sweep + shimmering title (ambient)
  - live status pulse dot (ambient)
  - staggered lead card entrance + hover glow border (entrance)
  - qualification badge pop + pulse (outcome)
  - achievement tier badges: bronze / silver / gold / platinum (outcome)
  - confetti burst for platinum-tier leads (outcome)
  - animated circular score ring per lead (outcome)
  - metric card tilt + blur-reveal count (entrance)
  - animated gradient progress bar during the pipeline run (utility)
  - skeleton loading cards during the scrape loop (utility)
  - scrolling "mission control" activity feed (utility)
  - toast notifications for pipeline lifecycle events (utility)
  - industry distribution bar chart (data)
  - top-leads leaderboard with medals (data)
  - custom-skinned sliders, selects, checkboxes, tabs, tooltips (chrome)
  - responsive breakpoints for small screens (chrome)
"""

import os
import re
import time
import csv
import io
import json
from typing import List, Optional
from urllib.parse import urlparse

import httpx
import streamlit as st
import resend
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
import google.generativeai as genai

import config

# ============================================================
# 1. DATA STRUCTURES
# ============================================================

class LeadCompanyInfo(BaseModel):
    model_config = {"extra": "ignore"}
    name: str = Field(description="Company name")
    industry: str = Field(description="Primary industry or sector")
    business_model: str = Field(description="How the company makes money, e.g. B2B SaaS, agency, ecommerce")
    linkedin_url: str = Field(description="Company LinkedIn URL if visible on the site, otherwise an empty string")
    twitter_url: str = Field(description="Company Twitter/X URL if visible on the site, otherwise an empty string")


class OutreachDraft(BaseModel):
    subject_line: str = Field(description="A distinct, professional, non-spammy email subject line matching the chosen psychological framework. Empty string if the lead is not qualified.")
    email_body: str = Field(description="A highly personalized cold email draft under 120 words. Empty string if the lead is not qualified.")
    linkedin_note: str = Field(description="A tailored LinkedIn connection request note under 300 characters. Empty string if the lead is not qualified.")
    chosen_framework: str = Field(description="The structural marketing angle used to craft this message. 'N/A' if the lead is not qualified.")


class LeadQualificationResult(BaseModel):
    model_config = {"extra": "ignore"}
    company: LeadCompanyInfo
    qualification_score: int = Field(description="Fit score from 0-100 against the target ICP")
    is_qualified: bool = Field(description="True if this lead clears the qualification bar")
    reasoning: str = Field(description="Short explanation supporting the score")
    outreach_sequence: OutreachDraft = Field(description="Personalized outreach draft. Fill all fields with empty strings if the lead is not qualified.")


# ============================================================
# 2. LIVE CRAWLING ENGINE
# ============================================================

def scrape_live_company_site(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) B2BWebAgent/2.1"}
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        response = httpx.get(url, headers=headers, timeout=7.0, follow_redirects=True)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(["script", "style", "meta", "noscript"]):
                tag.decompose()
            return " ".join(soup.get_text().split())[:4000]
        return f"Error: Status code {response.status_code}"
    except Exception as e:
        return f"Network Error: {str(e)}"


def discover_company_urls(query: str, serper_api_key: str, num_results: int = 5) -> List[str]:
    """Uses Serper API to discover clean root domains for a search query."""
    discovered_urls = []
    if not serper_api_key:
        return discovered_urls

    url = "https://google.serper.dev/search"
    payload = {"q": query, "num": num_results + 5}
    headers = {"X-API-KEY": serper_api_key, "Content-Type": "application/json"}

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=10.0)
        if response.status_code == 200:
            results = response.json().get("organic", [])
            for item in results:
                link = item.get("link", "")
                if not link:
                    continue
                if any(x in link for x in ["google.com", "linkedin.com", "yelp.com", "clutch.co", "upwork.com", "wikipedia.org"]):
                    continue
                domain = urlparse(link).netloc
                if domain and domain not in discovered_urls:
                    discovered_urls.append(domain)
                if len(discovered_urls) >= num_results:
                    break
    except Exception:
        pass

    return discovered_urls


def call_gemini_with_retry(model, prompt: str, generation_config, max_retries: int = 3):
    """
    Calls Gemini, and if the free-tier rate limit (429) is hit, waits for the
    server-suggested retry delay (parsed from the error message) and tries
    again, up to max_retries times. Raises the last error if it still fails.
    """
    last_error: Exception = RuntimeError("Gemini call failed with no captured error")
    for attempt in range(max_retries):
        try:
            return model.generate_content(prompt, generation_config=generation_config)
        except Exception as e:
            last_error = e
            error_text = str(e)
            if "429" not in error_text and "quota" not in error_text.lower():
                raise
            match = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", error_text)
            wait_seconds = int(match.group(1)) + 2 if match else 15
            if attempt < max_retries - 1:
                st.info(f"Rate limit hit. Waiting {wait_seconds}s before retrying ({attempt + 1}/{max_retries})...")
                time.sleep(wait_seconds)
    raise last_error


# ============================================================
# 2b. MOTION / VISUAL HELPER FUNCTIONS
# ============================================================

TIER_COLORS = ["#a78bfa", "#60a5fa", "#34d399", "#fbbf24", "#f87171", "#e2e8f0", "#f472b6", "#22d3ee"]


def get_tier(score: int):
    """Maps a qualification score to a visual achievement tier."""
    if score >= 90:
        return "Platinum Lead", "tier-platinum"
    if score >= 75:
        return "Gold Lead", "tier-gold"
    if score >= 55:
        return "Silver Lead", "tier-silver"
    return "Bronze Lead", "tier-bronze"


def render_confetti_burst(piece_count: int = 26):
    """Renders a one-shot CSS confetti burst, used to celebrate a top-tier lead."""
    pieces_html = []
    for i in range(piece_count):
        left = (i * 37) % 100
        delay = round((i % 7) * 0.06, 2)
        duration = round(0.9 + (i % 5) * 0.12, 2)
        color = TIER_COLORS[i % len(TIER_COLORS)]
        rotate = (i * 53) % 360
        pieces_html.append(
            f'<span class="confetti-piece" style="left:{left}%; '
            f'background:{color}; animation-delay:{delay}s; '
            f'animation-duration:{duration}s; '
            f'transform: rotate({rotate}deg);"></span>'
        )
    st.markdown(f'<div class="confetti-wrap">{"".join(pieces_html)}</div>', unsafe_allow_html=True)


def render_skeleton_cards(count: int = 3):
    """Shows shimmering placeholder cards while the pipeline is still running."""
    cards_html = []
    for _ in range(count):
        cards_html.append(
            '<div class="skeleton-card">'
            '<div class="skeleton-line medium"></div>'
            '<div class="skeleton-line long"></div>'
            '<div class="skeleton-line short"></div>'
            '</div>'
        )
    st.markdown("".join(cards_html), unsafe_allow_html=True)


def render_activity_feed(log_lines: List[str]):
    """Renders a scrollable terminal-style feed, most recent line highlighted."""
    rendered = []
    total = len(log_lines)
    for idx, line in enumerate(log_lines):
        css_class = "activity-line active" if idx == total - 1 else "activity-line"
        rendered.append(f'<div class="{css_class}">{line}</div>')
    st.markdown(f'<div class="activity-feed">{"".join(rendered)}</div>', unsafe_allow_html=True)


def render_empty_state(icon: str, title: str, subtitle: str):
    """A designed empty state instead of a blank page — an invitation to act."""
    st.markdown(f"""
    <div class="empty-state">
        <div class="empty-state-icon">{icon}</div>
        <h3>{title}</h3>
        <p>{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


def render_app_footer():
    """Closing signature footer, mirrors the header's visual treatment."""
    st.markdown("""
    <div class="app-footer">
        LeadAgent.io <span class="footer-glow"></span> Autonomous B2B discovery, built for closers.
    </div>
    """, unsafe_allow_html=True)


def render_section_divider(label: str):
    """A labeled hairline rule used to separate major sections of the dashboard."""
    st.markdown(f'<div class="section-divider"><span>{label}</span></div>', unsafe_allow_html=True)


def render_system_status(gemini_ok: bool, serper_ok: bool, resend_ok: bool):
    """Live-looking status indicators for each connected service, driven by real key presence."""
    rows = [
        ("Gemini API", gemini_ok),
        ("Serper Discovery", serper_ok),
        ("Resend Delivery", resend_ok),
    ]
    html_parts = ['<div style="margin-top:0.5rem;">']
    for label, ok in rows:
        dot_class = "online" if ok else "offline"
        state_label = "Connected" if ok else "Not configured"
        html_parts.append(
            f'<div class="status-row"><span class="status-dot {dot_class}"></span>'
            f'{label} — {state_label}</div>'
        )
    html_parts.append('</div>')
    st.sidebar.markdown("".join(html_parts), unsafe_allow_html=True)


def render_leaderboard(processed, top_n: int = 3):
    """Ranks the highest-scoring leads from the most recent run."""
    medals = ["🥇", "🥈", "🥉"]
    ranked = sorted(processed, key=lambda item: item[1].qualification_score, reverse=True)[:top_n]
    if not ranked:
        return
    rows_html = ['<div class="leaderboard">']
    for i, (url, lead) in enumerate(ranked):
        medal = medals[i] if i < len(medals) else "🏅"
        rows_html.append(
            '<div class="leaderboard-row" style="animation-delay:'
            f'{i * 0.1}s;">'
            f'<span class="leaderboard-medal">{medal}</span>'
            f'<span class="leaderboard-name">{lead.company.name}</span>'
            f'<span class="leaderboard-score">{lead.qualification_score}/100</span>'
            '</div>'
        )
    rows_html.append('</div>')
    st.markdown("".join(rows_html), unsafe_allow_html=True)


def render_industry_chart(processed):
    """Animated CSS-only horizontal bar chart of leads grouped by industry."""
    if not processed:
        return
    counts = {}
    for _, lead in processed:
        key = lead.company.industry or "Unspecified"
        counts[key] = counts.get(key, 0) + 1

    if not counts:
        return

    max_count = max(counts.values())
    sorted_items = sorted(counts.items(), key=lambda pair: pair[1], reverse=True)

    rows_html = ['<div class="bar-chart">']
    for industry, count in sorted_items:
        pct = round((count / max_count) * 100, 1)
        safe_label = industry if len(industry) <= 22 else industry[:19] + "..."
        rows_html.append(
            '<div class="bar-chart-row">'
            f'<div class="bar-chart-label" title="{industry}">{safe_label}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct}%;"></div></div>'
            f'<div class="bar-chart-count">{count}</div>'
            '</div>'
        )
    rows_html.append('</div>')
    st.markdown("".join(rows_html), unsafe_allow_html=True)


def export_leads_json(processed) -> str:
    """Serializes the current lead batch to a pretty-printed JSON string for export."""
    payload = []
    for url, lead in processed:
        payload.append({
            "url": url,
            "company": lead.company.model_dump(),
            "qualification_score": lead.qualification_score,
            "is_qualified": lead.is_qualified,
            "reasoning": lead.reasoning,
            "outreach_sequence": lead.outreach_sequence.model_dump(),
        })
    return json.dumps(payload, indent=2)


def score_ring_html(score: int) -> str:
    """Builds an animated circular gauge for a 0-100 score, colored by tier."""
    _, tier_class = get_tier(score)
    ring_colors = {
        "tier-platinum": "#e2e8f0",
        "tier-gold": "#fbbf24",
        "tier-silver": "#94a3b8",
        "tier-bronze": "#d97757",
    }
    color = ring_colors.get(tier_class, "#6366f1")
    target_deg = round((max(0, min(score, 100)) / 100) * 360, 1)
    return (
        f'<div class="score-ring" style="--ring-color:{color}; --ring-target:{target_deg}deg;">'
        f'<span class="score-ring-value">{score}</span>'
        f'</div>'
    )


def render_toast(message: str, kind: str = "success"):
    """Renders a single lifecycle-event toast. kind: success | warning | error."""
    icons = {"success": "✅", "warning": "⚠️", "error": "🚫"}
    icon = icons.get(kind, "ℹ️")
    st.markdown(
        f'<div class="toast {kind}"><span class="toast-icon">{icon}</span>{message}</div>',
        unsafe_allow_html=True,
    )


def render_loading_overlay(message: str = "Spinning up the discovery engine..."):
    """A full-panel spinner shown briefly while the pipeline initializes."""
    st.markdown(f"""
    <div class="loading-overlay">
        <div class="loading-spinner"></div>
        <p>{message}</p>
    </div>
    """, unsafe_allow_html=True)


def render_onboarding_banner():
    """First-run guidance banner. Dismissed permanently once the user closes it."""
    if st.session_state.onboarding_dismissed:
        return
    st.markdown("""
    <div class="onboarding-banner">
        <h4>👋 New here?</h4>
        <p>Set your niche, city, and ICP in the sidebar, add your API keys, then hit
        "Initialize Autonomous Agents Pipeline". Results, tags, and notes are kept for
        this session — use Save Session below to keep them longer.</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Got it, don't show this again", key="dismiss_onboarding"):
        st.session_state.onboarding_dismissed = True
        st.rerun()


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 characters per token) for usage tracking, not billing-accurate."""
    return max(1, len(text) // 4)


def track_usage(prompt_text: str, response_text: str):
    """Accumulates a rough token/cost estimate across the session."""
    st.session_state.usage_tokens_est += estimate_tokens(prompt_text) + estimate_tokens(response_text)
    st.session_state.usage_calls += 1


def render_usage_meter():
    """Displays the running usage estimate in the sidebar. Approximate, not a billing source."""
    tokens = st.session_state.usage_tokens_est
    calls = st.session_state.usage_calls
    # Rough placeholder blended rate; real cost depends on the model and Google's current pricing.
    est_cost = round((tokens / 1_000_000) * 0.35, 4)
    st.sidebar.markdown(f"""
    <div class="usage-meter">
        <div>Calls this session: <b>{calls}</b></div>
        <div>Est. tokens: <b>{tokens:,}</b></div>
        <div>Est. cost: <b>${est_cost}</b></div>
        <div style="margin-top:0.3rem; color:#64748b; font-size:0.72rem;">Rough estimate only — check Google AI Studio for exact billing.</div>
    </div>
    """, unsafe_allow_html=True)


def export_session_json() -> str:
    """Serializes the full working session (leads, notes, tags, selections) for later restore."""
    leads_payload = []
    for url, lead in st.session_state.processed_leads:
        leads_payload.append({"url": url, "lead": lead.model_dump()})
    return json.dumps({
        "processed_leads": leads_payload,
        "selected_leads": st.session_state.selected_leads,
        "removed_lead_urls": list(st.session_state.removed_lead_urls),
        "lead_notes": st.session_state.lead_notes,
        "lead_tags": st.session_state.lead_tags,
    }, indent=2)


def import_session_json(raw_json: str) -> bool:
    """Restores a previously exported session. Returns True on success."""
    try:
        data = json.loads(raw_json)
        restored = []
        for item in data.get("processed_leads", []):
            restored.append((item["url"], LeadQualificationResult.model_validate(item["lead"])))
        st.session_state.processed_leads = restored
        st.session_state.selected_leads = data.get("selected_leads", {})
        st.session_state.removed_lead_urls = set(data.get("removed_lead_urls", []))
        st.session_state.lead_notes = data.get("lead_notes", {})
        st.session_state.lead_tags = data.get("lead_tags", {})
        return True
    except Exception:
        return False


# ============================================================
# 3. STREAMLIT UI SETUP
# ============================================================

st.set_page_config(page_title="LeadAgent AI | Premium Data Terminal", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    /* ============================================================
       BASE THEME
       ============================================================ */
    [data-testid="stAppViewContainer"] {
        background: radial-gradient(circle at 10% 20%, rgb(0, 0, 0) 0%, rgb(18, 18, 18) 100.2%);
        color: #e2e8f0;
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
        position: relative;
    }

    [data-testid="stSidebar"] {
        background-color: rgba(26, 32, 44, 0.5) !important;
        backdrop-filter: blur(12px);
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }

    /* ============================================================
       AMBIENT STARFIELD (signature background motion)
       Two layered radial-dot fields drifting at different speeds
       ============================================================ */
    .starfield {
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        pointer-events: none;
        z-index: 0;
        opacity: 0.55;
    }
    .starfield::before, .starfield::after {
        content: "";
        position: absolute;
        top: -50%; left: -50%;
        width: 200%; height: 200%;
        background-image:
            radial-gradient(1px 1px at 20px 30px, #ffffff 100%, transparent 0),
            radial-gradient(1px 1px at 90px 120px, #93c5fd 100%, transparent 0),
            radial-gradient(1.5px 1.5px at 160px 60px, #ffffff 100%, transparent 0),
            radial-gradient(1px 1px at 220px 180px, #a78bfa 100%, transparent 0),
            radial-gradient(1.5px 1.5px at 280px 40px, #ffffff 100%, transparent 0),
            radial-gradient(1px 1px at 340px 220px, #60a5fa 100%, transparent 0);
        background-repeat: repeat;
        background-size: 380px 260px;
        animation: drift-stars 90s linear infinite;
    }
    .starfield::after {
        background-size: 500px 340px;
        opacity: 0.5;
        animation: drift-stars-reverse 140s linear infinite;
    }
    @keyframes drift-stars {
        from { transform: translate(0, 0); }
        to { transform: translate(-380px, -260px); }
    }
    @keyframes drift-stars-reverse {
        from { transform: translate(-500px, 0); }
        to { transform: translate(0, -340px); }
    }
    @keyframes twinkle {
        0%, 100% { opacity: 0.3; }
        50% { opacity: 1; }
    }

    /* ============================================================
       HEADER — radar sweep + live status pulse
       ============================================================ */
    .premium-header {
        position: relative;
        overflow: hidden;
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(8px);
        padding: 3rem;
        border-radius: 20px;
        margin-bottom: 3rem;
        box-shadow: 0 10px 30px -5px rgba(0,0,0,0.5);
        border: 1px solid rgba(255, 255, 255, 0.05);
        text-align: center;
        animation: fadeInDown 0.8s ease-out;
        z-index: 1;
    }
    .premium-header::before {
        content: "";
        position: absolute;
        top: 0; left: -150%;
        width: 150%; height: 100%;
        background: linear-gradient(100deg, transparent 40%, rgba(99, 102, 241, 0.12) 50%, transparent 60%);
        animation: radar-sweep 5s ease-in-out infinite;
    }
    @keyframes radar-sweep {
        0% { left: -150%; }
        45% { left: 150%; }
        100% { left: 150%; }
    }
    .premium-logo {
        font-size: 3.2rem;
        margin-bottom: 0.5rem;
        display: inline-block;
        animation: float-orbit 6s ease-in-out infinite;
    }
    @keyframes float-orbit {
        0%, 100% { transform: translateY(0) rotate(0deg); }
        50% { transform: translateY(-8px) rotate(6deg); }
    }
    .premium-title {
        color: #ffffff;
        font-size: 3.2rem;
        font-weight: 900;
        margin: 0;
        letter-spacing: -0.06em;
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 50%, #60a5fa 100%);
        background-size: 200% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: shimmer-text 4s linear infinite;
    }
    @keyframes shimmer-text {
        to { background-position: 200% center; }
    }
    .live-status {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        margin-top: 0.75rem;
        font-size: 0.78rem;
        letter-spacing: 0.12rem;
        text-transform: uppercase;
        color: #94a3b8;
        font-weight: 600;
    }
    .live-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #34d399;
        box-shadow: 0 0 0 rgba(52, 211, 153, 0.6);
        animation: pulse-dot 1.8s infinite;
    }
    @keyframes pulse-dot {
        0% { box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.6); }
        70% { box-shadow: 0 0 0 8px rgba(52, 211, 153, 0); }
        100% { box-shadow: 0 0 0 0 rgba(52, 211, 153, 0); }
    }

    /* ============================================================
       LEAD CARDS — staggered entrance + hover lift + glow border
       ============================================================ */
    .premium-lead-card {
        position: relative;
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.25);
        margin-top: 0.5rem;
        margin-bottom: 0.5rem;
        transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
        animation: card-rise 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
        overflow: hidden;
    }
    .premium-lead-card::before {
        content: "";
        position: absolute;
        inset: 0;
        border-radius: 12px;
        padding: 1px;
        background: linear-gradient(120deg, transparent, rgba(99, 102, 241, 0.5), transparent);
        background-size: 200% 100%;
        -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
        -webkit-mask-composite: xor;
        mask-composite: exclude;
        opacity: 0;
        transition: opacity 0.3s ease;
        animation: border-shimmer 3s linear infinite;
    }
    .premium-lead-card:hover::before { opacity: 1; }
    @keyframes border-shimmer {
        to { background-position: -200% 0; }
    }
    @keyframes card-rise {
        0% { opacity: 0; transform: translateY(18px) scale(0.98); }
        100% { opacity: 1; transform: translateY(0) scale(1); }
    }
    .premium-lead-card:hover {
        border-color: #6366f1;
        box-shadow: 0 0 28px rgba(99, 102, 241, 0.25);
        transform: translateY(-4px);
    }

    /* ============================================================
       BADGES — pulsing glow to draw the eye to outcome
       ============================================================ */
    .glow-badge {
        padding: 0.35rem 0.8rem;
        border-radius: 30px;
        font-size: 0.8rem;
        font-weight: 700;
        letter-spacing: 0.06rem;
        text-transform: uppercase;
        display: inline-block;
        animation: badge-pop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both;
    }
    @keyframes badge-pop {
        0% { opacity: 0; transform: scale(0.6); }
        100% { opacity: 1; transform: scale(1); }
    }
    .badge-qualified-glow {
        background: rgba(16, 185, 129, 0.1);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.4);
        animation: badge-pop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both, glow-pulse-green 2.4s ease-in-out infinite 0.4s;
    }
    .badge-disqualified-glow {
        background: rgba(239, 68, 68, 0.1);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.4);
    }
    @keyframes glow-pulse-green {
        0%, 100% { box-shadow: 0 0 0 rgba(52, 211, 153, 0); }
        50% { box-shadow: 0 0 14px rgba(52, 211, 153, 0.45); }
    }

    .reasoning-box {
        background: rgba(15, 23, 42, 0.5);
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #6366f1;
        margin-top: 1rem;
        animation: fadeInDown 0.5s ease-out both;
    }

    /* ============================================================
       METRIC CARDS — tilt-on-hover + count reveal
       ============================================================ */
    .metric-card {
        background: #1e293b;
        padding: 1.25rem;
        border-radius: 0.75rem;
        border: 1px solid #334155;
        text-align: center;
        transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease;
        animation: card-rise 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
    }
    .metric-card:hover {
        transform: translateY(-3px) scale(1.02);
        border-color: #6366f1;
        box-shadow: 0 8px 24px rgba(99, 102, 241, 0.18);
    }
    .metric-card h2 {
        animation: count-reveal 0.6s ease-out both;
    }
    @keyframes count-reveal {
        0% { opacity: 0; transform: translateY(6px); filter: blur(4px); }
        100% { opacity: 1; transform: translateY(0); filter: blur(0); }
    }

    /* ============================================================
       BUTTONS — glowing primary CTA with idle breathing pulse
       ============================================================ */
    div.stButton > button[kind="primary"] {
        position: relative;
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
        border: none !important;
        font-weight: 700 !important;
        letter-spacing: 0.03rem;
        transition: transform 0.2s ease, box-shadow 0.2s ease !important;
        animation: cta-breathe 3s ease-in-out infinite;
    }
    div.stButton > button[kind="primary"]:hover {
        transform: translateY(-2px) scale(1.01);
        box-shadow: 0 8px 24px rgba(99, 102, 241, 0.45) !important;
    }
    @keyframes cta-breathe {
        0%, 100% { box-shadow: 0 0 0 rgba(99, 102, 241, 0.35); }
        50% { box-shadow: 0 0 22px rgba(99, 102, 241, 0.55); }
    }
    div.stButton > button:not([kind="primary"]) {
        transition: transform 0.2s ease, border-color 0.2s ease !important;
    }
    div.stButton > button:not([kind="primary"]):hover {
        transform: translateY(-1px);
        border-color: #f87171 !important;
    }

    /* ============================================================
       PROGRESS BAR — animated gradient sweep instead of flat fill
       ============================================================ */
    div[data-testid="stProgress"] > div > div > div {
        background: linear-gradient(90deg, #6366f1, #a78bfa, #6366f1) !important;
        background-size: 200% auto !important;
        animation: progress-flow 1.6s linear infinite;
    }
    @keyframes progress-flow {
        to { background-position: -200% center; }
    }

    /* ============================================================
       INPUTS — soft focus glow instead of default outline
       ============================================================ */
    [data-testid="stTextInput"] input:focus,
    [data-testid="stTextArea"] textarea:focus {
        box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.45) !important;
        transition: box-shadow 0.2s ease;
    }

    /* ============================================================
       EXPANDER — subtle slide-open feel
       ============================================================ */
    [data-testid="stExpander"] {
        border: 1px solid #334155 !important;
        border-radius: 10px !important;
        transition: border-color 0.3s ease;
    }
    [data-testid="stExpander"]:hover {
        border-color: #6366f1 !important;
    }

    /* ============================================================
       SCROLLBAR — matches the terminal theme
       ============================================================ */
    ::-webkit-scrollbar { width: 10px; }
    ::-webkit-scrollbar-track { background: #0f172a; }
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(180deg, #6366f1, #8b5cf6);
        border-radius: 6px;
    }

    /* ============================================================
       GENERIC ENTRANCE ANIMATIONS (reused across sections)
       ============================================================ */
    @keyframes fadeInDown {
        0% { opacity: 0; transform: translateY(-20px); }
        100% { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeInUp {
        0% { opacity: 0; transform: translateY(20px); }
        100% { opacity: 1; transform: translateY(0); }
    }
    .section-fade-in {
        animation: fadeInUp 0.6s ease-out both;
    }

    /* Respect users who've asked for reduced motion */
    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation-duration: 0.001ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.001ms !important;
        }
    }

    /* ============================================================
       EMPTY STATE — shown before the first pipeline run
       An orbiting radar illustration built entirely from CSS
       ============================================================ */
    .empty-state {
        position: relative;
        z-index: 1;
        text-align: center;
        padding: 4rem 2rem;
        margin-top: 2rem;
        animation: fadeInUp 0.7s ease-out both;
    }
    .empty-state-orbit {
        position: relative;
        width: 180px;
        height: 180px;
        margin: 0 auto 2rem auto;
    }
    .empty-orbit-ring {
        position: absolute;
        top: 50%;
        left: 50%;
        border: 1px solid rgba(99, 102, 241, 0.25);
        border-radius: 50%;
        transform: translate(-50%, -50%);
    }
    .empty-orbit-ring.ring-1 {
        width: 180px;
        height: 180px;
        animation: ring-spin 12s linear infinite;
    }
    .empty-orbit-ring.ring-2 {
        width: 130px;
        height: 130px;
        border-color: rgba(167, 139, 250, 0.3);
        animation: ring-spin-reverse 9s linear infinite;
    }
    .empty-orbit-ring.ring-3 {
        width: 80px;
        height: 80px;
        border-color: rgba(96, 165, 250, 0.35);
        animation: ring-spin 6s linear infinite;
    }
    .empty-orbit-core {
        position: absolute;
        top: 50%;
        left: 50%;
        width: 22px;
        height: 22px;
        border-radius: 50%;
        background: radial-gradient(circle, #a78bfa, #6366f1);
        transform: translate(-50%, -50%);
        box-shadow: 0 0 24px rgba(99, 102, 241, 0.6);
        animation: pulse-dot 2.2s infinite;
    }
    .empty-orbit-satellite {
        position: absolute;
        top: 0;
        left: 50%;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: #34d399;
        box-shadow: 0 0 10px rgba(52, 211, 153, 0.8);
        transform-origin: 0 90px;
        animation: ring-spin 12s linear infinite;
    }
    @keyframes ring-spin {
        from { transform: translate(-50%, -50%) rotate(0deg); }
        to { transform: translate(-50%, -50%) rotate(360deg); }
    }
    @keyframes ring-spin-reverse {
        from { transform: translate(-50%, -50%) rotate(360deg); }
        to { transform: translate(-50%, -50%) rotate(0deg); }
    }
    .empty-state h3 {
        color: #ffffff;
        font-size: 1.4rem;
        font-weight: 800;
        margin-bottom: 0.5rem;
    }
    .empty-state p {
        color: #94a3b8;
        font-size: 0.95rem;
        max-width: 420px;
        margin: 0 auto;
    }

    /* ============================================================
       SKELETON LOADERS — shimmering placeholders while the
       pipeline is discovering and scoring leads
       ============================================================ */
    .skeleton-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 0.75rem;
        position: relative;
        overflow: hidden;
        animation: fadeInUp 0.4s ease-out both;
    }
    .skeleton-card::after {
        content: "";
        position: absolute;
        top: 0;
        left: -150%;
        width: 150%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.06), transparent);
        animation: skeleton-sweep 1.6s ease-in-out infinite;
    }
    @keyframes skeleton-sweep {
        to { left: 150%; }
    }
    .skeleton-line {
        height: 12px;
        border-radius: 6px;
        background: rgba(255, 255, 255, 0.06);
        margin-bottom: 0.6rem;
    }
    .skeleton-line.w-40 { width: 40%; }
    .skeleton-line.w-60 { width: 60%; }
    .skeleton-line.w-80 { width: 80%; }
    .skeleton-line.w-30 { width: 30%; }
    .skeleton-badge {
        display: inline-block;
        width: 90px;
        height: 22px;
        border-radius: 30px;
        background: rgba(255, 255, 255, 0.06);
    }

    /* ============================================================
       PIPELINE STEPPER — 4-stage horizontal progress indicator
       ============================================================ */
    .pipeline-stepper {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        max-width: 640px;
        margin: 1.5rem auto 2rem auto;
        position: relative;
        z-index: 1;
    }
    .stepper-step {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.5rem;
        flex: 1;
        position: relative;
    }
    .stepper-step:not(:last-child)::after {
        content: "";
        position: absolute;
        top: 17px;
        left: 55%;
        width: 90%;
        height: 2px;
        background: #334155;
        z-index: -1;
    }
    .stepper-step.step-done:not(:last-child)::after {
        background: linear-gradient(90deg, #34d399, #6366f1);
    }
    .stepper-circle {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.85rem;
        font-weight: 800;
        background: #1e293b;
        border: 2px solid #334155;
        color: #64748b;
        transition: all 0.4s ease;
    }
    .stepper-step.step-active .stepper-circle {
        border-color: #6366f1;
        color: #ffffff;
        background: radial-gradient(circle, #4338ca, #1e293b);
        animation: stepper-pulse 1.4s ease-in-out infinite;
        box-shadow: 0 0 16px rgba(99, 102, 241, 0.5);
    }
    .stepper-step.step-done .stepper-circle {
        border-color: #34d399;
        background: #064e3b;
        color: #34d399;
    }
    @keyframes stepper-pulse {
        0%, 100% { box-shadow: 0 0 10px rgba(99, 102, 241, 0.4); }
        50% { box-shadow: 0 0 22px rgba(99, 102, 241, 0.7); }
    }
    .stepper-label {
        font-size: 0.72rem;
        letter-spacing: 0.04rem;
        text-transform: uppercase;
        color: #64748b;
        font-weight: 700;
        text-align: center;
    }
    .stepper-step.step-active .stepper-label { color: #a5b4fc; }
    .stepper-step.step-done .stepper-label { color: #34d399; }

    /* ============================================================
       TOAST NOTIFICATIONS — CSS-only slide-in / auto-fade
       ============================================================ */
    .toast-wrap {
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 999;
        pointer-events: none;
    }
    .toast {
        min-width: 260px;
        max-width: 340px;
        background: rgba(15, 23, 42, 0.92);
        backdrop-filter: blur(10px);
        border: 1px solid #334155;
        border-left: 4px solid #6366f1;
        border-radius: 10px;
        padding: 0.85rem 1.1rem;
        margin-top: 0.6rem;
        color: #e2e8f0;
        font-size: 0.85rem;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
        animation: toast-lifecycle 4.5s ease forwards;
    }
    .toast.toast-success { border-left-color: #34d399; }
    .toast.toast-error { border-left-color: #f87171; }
    .toast.toast-info { border-left-color: #60a5fa; }
    @keyframes toast-lifecycle {
        0% { opacity: 0; transform: translateX(40px); }
        10% { opacity: 1; transform: translateX(0); }
        85% { opacity: 1; transform: translateX(0); }
        100% { opacity: 0; transform: translateX(40px); }
    }

    /* ============================================================
       CONFETTI BURST — triggered once when a top-tier lead
       (score 90+) is discovered
       ============================================================ */
    .confetti-field {
        position: relative;
        height: 0;
        overflow: visible;
        z-index: 2;
    }
    .confetti-piece {
        position: absolute;
        top: -20px;
        width: 8px;
        height: 14px;
        opacity: 0.9;
        animation: confetti-fall 2.6s ease-in forwards;
    }
    @keyframes confetti-fall {
        0% { transform: translateY(0) rotate(0deg); opacity: 1; }
        100% { transform: translateY(220px) rotate(540deg); opacity: 0; }
    }
    .confetti-piece:nth-child(1)  { left: 5%;  background: #6366f1; animation-delay: 0s;    }
    .confetti-piece:nth-child(2)  { left: 12%; background: #34d399; animation-delay: 0.08s; }
    .confetti-piece:nth-child(3)  { left: 20%; background: #f59e0b; animation-delay: 0.16s; }
    .confetti-piece:nth-child(4)  { left: 28%; background: #f87171; animation-delay: 0.05s; }
    .confetti-piece:nth-child(5)  { left: 36%; background: #a78bfa; animation-delay: 0.22s; }
    .confetti-piece:nth-child(6)  { left: 44%; background: #60a5fa; animation-delay: 0.1s;  }
    .confetti-piece:nth-child(7)  { left: 52%; background: #34d399; animation-delay: 0.3s;  }
    .confetti-piece:nth-child(8)  { left: 60%; background: #f59e0b; animation-delay: 0.02s; }
    .confetti-piece:nth-child(9)  { left: 68%; background: #6366f1; animation-delay: 0.18s; }
    .confetti-piece:nth-child(10) { left: 76%; background: #f87171; animation-delay: 0.25s; }
    .confetti-piece:nth-child(11) { left: 84%; background: #a78bfa; animation-delay: 0.12s; }
    .confetti-piece:nth-child(12) { left: 92%; background: #60a5fa; animation-delay: 0.06s; }
    .confetti-piece:nth-child(13) { left: 16%; background: #f59e0b; animation-delay: 0.35s; }
    .confetti-piece:nth-child(14) { left: 48%; background: #34d399; animation-delay: 0.28s; }
    .confetti-piece:nth-child(15) { left: 80%; background: #6366f1; animation-delay: 0.15s; }
    .confetti-piece:nth-child(odd)  { border-radius: 2px; }
    .confetti-piece:nth-child(even) { border-radius: 50%; }

    /* ============================================================
       ACCORDION — "Show full analysis" expand/collapse
       (pure HTML <details>/<summary>, no JS needed)
       ============================================================ */
    .analysis-accordion {
        margin-top: 0.75rem;
    }
    .analysis-accordion summary {
        cursor: pointer;
        color: #a5b4fc;
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.02rem;
        list-style: none;
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        transition: color 0.2s ease;
    }
    .analysis-accordion summary::-webkit-details-marker { display: none; }
    .analysis-accordion summary::after {
        content: "▸";
        display: inline-block;
        transition: transform 0.25s ease;
    }
    .analysis-accordion[open] summary::after {
        transform: rotate(90deg);
    }
    .analysis-accordion summary:hover { color: #c7d2fe; }
    .analysis-accordion-body {
        margin-top: 0.6rem;
        animation: fadeInDown 0.35s ease-out both;
    }

    /* ============================================================
       TOOLTIPS — CSS-only hover tooltips with arrow
       ============================================================ */
    .tooltip-trigger {
        position: relative;
        cursor: help;
        border-bottom: 1px dotted #64748b;
    }
    .tooltip-trigger::before {
        content: attr(data-tooltip);
        position: absolute;
        bottom: 130%;
        left: 50%;
        transform: translateX(-50%) translateY(4px);
        background: #0f172a;
        color: #e2e8f0;
        padding: 0.4rem 0.65rem;
        border-radius: 6px;
        border: 1px solid #334155;
        font-size: 0.72rem;
        white-space: nowrap;
        opacity: 0;
        pointer-events: none;
        transition: all 0.2s ease;
        z-index: 50;
    }
    .tooltip-trigger::after {
        content: "";
        position: absolute;
        bottom: 122%;
        left: 50%;
        transform: translateX(-50%);
        border: 5px solid transparent;
        border-top-color: #334155;
        opacity: 0;
        transition: all 0.2s ease;
    }
    .tooltip-trigger:hover::before,
    .tooltip-trigger:hover::after {
        opacity: 1;
        transform: translateX(-50%) translateY(0);
    }

    /* ============================================================
       CUSTOM FORM CONTROLS — re-skin native Streamlit widgets
       to match the terminal theme instead of default gray
       ============================================================ */
    div[data-testid="stSlider"] [role="slider"] {
        background: linear-gradient(135deg, #6366f1, #a78bfa) !important;
        box-shadow: 0 0 10px rgba(99, 102, 241, 0.5) !important;
        transition: transform 0.15s ease !important;
    }
    div[data-testid="stSlider"] [role="slider"]:hover {
        transform: scale(1.15);
    }
    div[data-testid="stSlider"] > div > div > div {
        background: linear-gradient(90deg, #6366f1, #a78bfa) !important;
    }
    [data-testid="stCheckbox"] label span[aria-checked="true"] {
        background-color: #6366f1 !important;
        border-color: #6366f1 !important;
        transition: all 0.2s ease;
    }
    [data-testid="stCheckbox"]:hover label span {
        border-color: #818cf8 !important;
    }
    div[data-testid="stSelectbox"] > div {
        transition: box-shadow 0.2s ease, border-color 0.2s ease;
    }
    div[data-testid="stSelectbox"] > div:focus-within {
        box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.45) !important;
        border-color: #6366f1 !important;
    }
    div[data-baseweb="tab-list"] {
        gap: 0.25rem;
    }
    div[data-baseweb="tab"] {
        transition: color 0.2s ease;
    }
    div[data-baseweb="tab-highlight"] {
        background-color: #6366f1 !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }

    /* ============================================================
       FOOTER TICKER — scrolling status marquee, terminal style
       ============================================================ */
    .footer-ticker {
        position: relative;
        margin-top: 3rem;
        padding: 0.9rem 0;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
        overflow: hidden;
        white-space: nowrap;
        z-index: 1;
    }
    .footer-ticker-track {
        display: inline-block;
        padding-left: 100%;
        animation: ticker-scroll 28s linear infinite;
        color: #64748b;
        font-size: 0.78rem;
        letter-spacing: 0.04rem;
    }
    .footer-ticker-track span {
        margin-right: 3rem;
    }
    @keyframes ticker-scroll {
        0% { transform: translateX(0); }
        100% { transform: translateX(-100%); }
    }

    /* ============================================================
       MICRO-INTERACTIONS — ripple, underline, icon bounce
       ============================================================ */
    div.stButton > button {
        position: relative;
        overflow: hidden;
    }
    div.stButton > button::after {
        content: "";
        position: absolute;
        top: 50%;
        left: 50%;
        width: 0;
        height: 0;
        background: rgba(255, 255, 255, 0.25);
        border-radius: 50%;
        transform: translate(-50%, -50%);
        transition: width 0.4s ease, height 0.4s ease, opacity 0.6s ease;
        opacity: 0;
    }
    div.stButton > button:active::after {
        width: 220px;
        height: 220px;
        opacity: 1;
        transition: 0s;
    }
    a {
        position: relative;
        text-decoration: none !important;
    }
    a::after {
        content: "";
        position: absolute;
        left: 0;
        bottom: -2px;
        width: 0;
        height: 1px;
        background: #a78bfa;
        transition: width 0.25s ease;
    }
    a:hover::after { width: 100%; }
    .icon-bounce {
        display: inline-block;
        transition: transform 0.2s ease;
    }
    .icon-bounce:hover {
        transform: translateY(-3px) scale(1.1);
    }
    .glass-tag {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 30px;
        padding: 0.25rem 0.7rem;
        font-size: 0.72rem;
        color: #94a3b8;
        transition: border-color 0.2s ease, color 0.2s ease;
    }
    .glass-tag:hover {
        border-color: #6366f1;
        color: #c7d2fe;
    }
    .section-divider {
        position: relative;
        text-align: center;
        margin: 2.5rem 0;
        z-index: 1;
    }
    .section-divider::before {
        content: "";
        position: absolute;
        top: 50%;
        left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, #334155, transparent);
    }
    /* ============================================================
       CUSTOM SLIDER SKIN
       ============================================================ */
    div[data-testid="stSlider"] [role="slider"] {
        background: linear-gradient(135deg, #6366f1, #a78bfa) !important;
        box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.15) !important;
        transition: box-shadow 0.2s ease, transform 0.2s ease !important;
    }
    div[data-testid="stSlider"] [role="slider"]:hover {
        box-shadow: 0 0 0 8px rgba(99, 102, 241, 0.22) !important;
        transform: scale(1.08);
    }
    div[data-testid="stSlider"] > div > div > div {
        background: linear-gradient(90deg, #6366f1, #a78bfa) !important;
    }

    /* ============================================================
       CUSTOM SELECTBOX / MULTISELECT SKIN
       ============================================================ */
    div[data-baseweb="select"] > div {
        background: rgba(30, 41, 59, 0.6) !important;
        border-color: #334155 !important;
        transition: border-color 0.25s ease, box-shadow 0.25s ease;
    }
    div[data-baseweb="select"] > div:hover {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.15);
    }
    div[data-baseweb="tag"] {
        background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
        animation: badge-pop 0.3s ease both;
    }

    /* ============================================================
       CUSTOM CHECKBOX SKIN
       ============================================================ */
    [data-testid="stCheckbox"] label span:first-child {
        transition: transform 0.15s ease, background 0.2s ease;
    }
    [data-testid="stCheckbox"] label:hover span:first-child {
        transform: scale(1.12);
    }

    /* ============================================================
       CUSTOM TABS — animated underline instead of flat highlight
       ============================================================ */
    [data-baseweb="tab-list"] {
        gap: 0.5rem;
        border-bottom: 1px solid #334155 !important;
    }
    [data-baseweb="tab"] {
        position: relative;
        transition: color 0.25s ease;
    }
    [data-baseweb="tab"]::after {
        content: "";
        position: absolute;
        left: 0; right: 0; bottom: -1px;
        height: 2px;
        background: linear-gradient(90deg, #6366f1, #a78bfa);
        transform: scaleX(0);
        transform-origin: center;
        transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    [data-baseweb="tab"][aria-selected="true"]::after {
        transform: scaleX(1);
    }

    /* ============================================================
       TOOLTIP — glassmorphic instead of the default browser box
       ============================================================ */
    [data-testid="stTooltipIcon"] { transition: transform 0.2s ease; }
    [data-testid="stTooltipIcon"]:hover { transform: scale(1.15); }

    /* ============================================================
       BUTTON RIPPLE — click feedback on every button
       ============================================================ */
    div.stButton > button {
        position: relative;
        overflow: hidden;
    }
    div.stButton > button::after {
        content: "";
        position: absolute;
        top: 50%; left: 50%;
        width: 0; height: 0;
        background: rgba(255, 255, 255, 0.25);
        border-radius: 50%;
        transform: translate(-50%, -50%);
        transition: width 0.4s ease, height 0.4s ease, opacity 0.6s ease;
        opacity: 0;
    }
    div.stButton > button:active::after {
        width: 260px; height: 260px;
        opacity: 1;
        transition: 0s;
    }

    /* ============================================================
       SKELETON LOADERS — shimmer placeholders while the pipeline runs
       ============================================================ */
    .skeleton-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 0.75rem;
        overflow: hidden;
        position: relative;
    }
    .skeleton-line {
        height: 14px;
        border-radius: 6px;
        margin-bottom: 0.6rem;
        background: linear-gradient(90deg, #1e293b 0%, #334155 50%, #1e293b 100%);
        background-size: 200% 100%;
        animation: skeleton-shimmer 1.4s ease-in-out infinite;
    }
    .skeleton-line.short { width: 40%; }
    .skeleton-line.medium { width: 65%; }
    .skeleton-line.long { width: 90%; }
    @keyframes skeleton-shimmer {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }

    /* ============================================================
       MISSION CONTROL — live activity feed panel
       ============================================================ */
    .activity-feed {
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
        font-family: 'JetBrains Mono', 'Courier New', monospace;
        font-size: 0.82rem;
        max-height: 220px;
        overflow-y: auto;
    }
    .activity-line {
        color: #94a3b8;
        padding: 0.15rem 0;
        border-left: 2px solid transparent;
        padding-left: 0.6rem;
        animation: activity-slide-in 0.3s ease-out both;
    }
    .activity-line.active {
        color: #a78bfa;
        border-left-color: #6366f1;
    }
    @keyframes activity-slide-in {
        0% { opacity: 0; transform: translateX(-8px); }
        100% { opacity: 1; transform: translateX(0); }
    }

    /* ============================================================
       ACHIEVEMENT TIERS — visual reward system for lead quality
       ============================================================ */
    .tier-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        padding: 0.25rem 0.7rem;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.05rem;
        text-transform: uppercase;
        margin-left: 0.5rem;
        animation: badge-pop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both;
    }
    .tier-platinum {
        background: linear-gradient(135deg, rgba(226, 232, 240, 0.15), rgba(148, 163, 184, 0.2));
        color: #e2e8f0;
        border: 1px solid rgba(226, 232, 240, 0.4);
        animation: badge-pop 0.4s both, tier-shine 2.5s ease-in-out infinite 0.4s;
    }
    .tier-gold {
        background: linear-gradient(135deg, rgba(251, 191, 36, 0.15), rgba(217, 119, 6, 0.2));
        color: #fbbf24;
        border: 1px solid rgba(251, 191, 36, 0.4);
        animation: badge-pop 0.4s both, tier-shine 2.5s ease-in-out infinite 0.4s;
    }
    .tier-silver {
        background: linear-gradient(135deg, rgba(203, 213, 225, 0.12), rgba(100, 116, 139, 0.18));
        color: #cbd5e1;
        border: 1px solid rgba(203, 213, 225, 0.3);
    }
    .tier-bronze {
        background: linear-gradient(135deg, rgba(217, 119, 87, 0.12), rgba(146, 64, 14, 0.18));
        color: #d97757;
        border: 1px solid rgba(217, 119, 87, 0.3);
    }
    @keyframes tier-shine {
        0%, 100% { box-shadow: 0 0 0 rgba(251, 191, 36, 0); }
        50% { box-shadow: 0 0 12px rgba(251, 191, 36, 0.4); }
    }

    /* ============================================================
       CONFETTI BURST — celebrates a top-tier qualified lead
       ============================================================ */
    .confetti-wrap {
        position: relative;
        height: 0;
        overflow: visible;
    }
    .confetti-piece {
        position: absolute;
        top: 0;
        width: 6px;
        height: 12px;
        opacity: 0;
        animation-name: confetti-fall;
        animation-timing-function: ease-out;
        animation-fill-mode: forwards;
        animation-iteration-count: 1;
    }
    @keyframes confetti-fall {
        0% { opacity: 1; transform: translateY(0) rotate(0deg); }
        100% { opacity: 0; transform: translateY(90px) rotate(340deg); }
    }

    /* ============================================================
       EMPTY STATE — invitation to act rather than a blank screen
       ============================================================ */
    .empty-state {
        text-align: center;
        padding: 4rem 2rem;
        border: 1px dashed #334155;
        border-radius: 16px;
        margin-top: 2rem;
        animation: fadeInUp 0.6s ease-out both;
    }
    .empty-state-icon {
        font-size: 3rem;
        display: inline-block;
        animation: float-orbit 4s ease-in-out infinite;
        margin-bottom: 0.75rem;
    }
    .empty-state h3 {
        color: #ffffff;
        margin: 0 0 0.4rem 0;
    }
    .empty-state p {
        color: #64748b;
        margin: 0;
        font-size: 0.9rem;
    }

    /* ============================================================
       COUNT-UP NUMBERS — pure-CSS animated counter via @property
       ============================================================ */
    @property --num {
        syntax: '<integer>';
        initial-value: 0;
        inherits: false;
    }
    .count-up {
        animation: count-up-anim 1.4s ease-out both;
        counter-reset: num var(--num);
    }
    .count-up::after {
        content: counter(num);
    }
    @keyframes count-up-anim {
        from { --num: 0; }
        to { --num: var(--target, 0); }
    }

    /* ============================================================
       FOOTER — signature close, matches header treatment
       ============================================================ */
    .app-footer {
        text-align: center;
        padding: 2.5rem 1rem 1.5rem 1rem;
        margin-top: 3rem;
        border-top: 1px solid rgba(255, 255, 255, 0.06);
        color: #475569;
        font-size: 0.78rem;
        letter-spacing: 0.03rem;
        animation: fadeInUp 0.6s ease-out both;
    }
    .app-footer .footer-glow {
        display: inline-block;
        width: 6px; height: 6px;
        border-radius: 50%;
        background: #6366f1;
        margin: 0 0.4rem;
        animation: pulse-dot 2s infinite;
    }

    /* ============================================================
       SECTION DIVIDER — labeled hairline rule
       ============================================================ */
    .section-divider {
        position: relative;
        text-align: center;
        margin: 2rem 0;
    }
    .section-divider::before {
        content: "";
        position: absolute;
        top: 50%; left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, #334155, transparent);
    }
    .section-divider span {
        position: relative;
        background: #0f0f0f;
        padding: 0 1rem;
        color: #64748b;
        font-size: 0.75rem;
        letter-spacing: 0.08rem;
        text-transform: uppercase;
    }
    /* ============================================================
       SYSTEM STATUS PANEL — sidebar connection health indicators
       ============================================================ */
    .status-row {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.3rem 0;
        font-size: 0.82rem;
        color: #94a3b8;
    }
    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        flex-shrink: 0;
    }
    .status-dot.online {
        background: #34d399;
        box-shadow: 0 0 0 rgba(52, 211, 153, 0.6);
        animation: pulse-dot 1.8s infinite;
    }
    .status-dot.offline {
        background: #475569;
    }

    /* ============================================================
       LEADERBOARD — top qualified leads ranked by score
       ============================================================ */
    .leaderboard {
        margin: 1rem 0 2rem 0;
    }
    .leaderboard-row {
        display: flex;
        align-items: center;
        gap: 1rem;
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
        transition: transform 0.25s ease, border-color 0.25s ease;
        animation: card-rise 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
    }
    .leaderboard-row:hover {
        transform: translateX(4px);
        border-color: #6366f1;
    }
    .leaderboard-medal {
        font-size: 1.4rem;
        width: 2rem;
        text-align: center;
    }
    .leaderboard-name {
        flex: 1;
        color: #e2e8f0;
        font-weight: 700;
    }
    .leaderboard-score {
        color: #a78bfa;
        font-weight: 800;
        font-size: 1.1rem;
    }

    /* ============================================================
       RESPONSIVE — keep the terminal readable on small screens
       ============================================================ */
    @media (max-width: 768px) {
        .premium-header { padding: 1.75rem 1rem; }
        .premium-title { font-size: 2.1rem; }
        .premium-logo { font-size: 2.2rem; }
        .premium-lead-card { padding: 1rem; }
        .metric-card h2 { font-size: 1.5rem !important; }
        .leaderboard-row { flex-wrap: wrap; }
    }
    @media (prefers-color-scheme: light) {
        /* App is designed dark-first; keep text legible if a user forces light mode */
        .premium-title { -webkit-text-fill-color: #a78bfa; }
    }
    /* ============================================================
       BAR CHART — CSS-only industry distribution visualization
       ============================================================ */
    .bar-chart { margin: 1rem 0 2rem 0; }
    .bar-chart-row {
        display: grid;
        grid-template-columns: 160px 1fr 50px;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 0.55rem;
        font-size: 0.85rem;
    }
    .bar-chart-label {
        color: #94a3b8;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .bar-track {
        background: rgba(51, 65, 85, 0.4);
        border-radius: 6px;
        height: 10px;
        overflow: hidden;
    }
    .bar-fill {
        height: 100%;
        border-radius: 6px;
        background: linear-gradient(90deg, #6366f1, #a78bfa);
        width: 0%;
        animation: bar-grow 0.9s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    @keyframes bar-grow {
        from { width: 0%; }
    }
    .bar-chart-count {
        color: #e2e8f0;
        font-weight: 700;
        text-align: right;
    }
    /* ============================================================
       SCORE RING — animated circular gauge via conic-gradient
       ============================================================ */
    @property --ring-angle {
        syntax: '<angle>';
        initial-value: 0deg;
        inherits: false;
    }
    .score-ring {
        --ring-angle: 0deg;
        width: 56px;
        height: 56px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        background: conic-gradient(var(--ring-color, #6366f1) var(--ring-angle), rgba(51, 65, 85, 0.45) 0deg);
        animation: ring-fill 1.1s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        position: relative;
    }
    .score-ring::before {
        content: "";
        position: absolute;
        inset: 5px;
        border-radius: 50%;
        background: #0f172a;
    }
    .score-ring-value {
        position: relative;
        z-index: 1;
        font-size: 0.78rem;
        font-weight: 800;
        color: #e2e8f0;
    }
    @keyframes ring-fill {
        from { --ring-angle: 0deg; }
        to { --ring-angle: var(--ring-target, 0deg); }
    }

    /* ============================================================
       TYPEWRITER — steps-based text reveal for the header subtitle
       ============================================================ */
    .typewriter {
        display: inline-block;
        overflow: hidden;
        white-space: nowrap;
        border-right: 2px solid #6366f1;
        animation: typewriter-reveal 2.4s steps(38, end) 0.3s both,
                   typewriter-caret 0.75s step-end infinite;
    }
    @keyframes typewriter-reveal {
        from { width: 0; }
        to { width: 100%; }
    }
    @keyframes typewriter-caret {
        50% { border-color: transparent; }
    }
    /* ============================================================
       TOAST NOTIFICATIONS — lifecycle events, auto-dismissing
       ============================================================ */
    .toast {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        background: rgba(15, 23, 42, 0.9);
        border: 1px solid #334155;
        border-left: 4px solid #6366f1;
        border-radius: 10px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.6rem;
        color: #e2e8f0;
        font-size: 0.88rem;
        animation: toast-in 0.4s cubic-bezier(0.16, 1, 0.3, 1) both;
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.3);
    }
    .toast.success { border-left-color: #34d399; }
    .toast.warning { border-left-color: #fbbf24; }
    .toast.error { border-left-color: #f87171; }
    .toast-icon { font-size: 1.1rem; }
    @keyframes toast-in {
        0% { opacity: 0; transform: translateY(-10px) scale(0.98); }
        100% { opacity: 1; transform: translateY(0) scale(1); }
    }

    /* ============================================================
       LOADING OVERLAY — full-panel state while the pipeline spins up
       ============================================================ */
    .loading-overlay {
        text-align: center;
        padding: 2.5rem 1rem;
        animation: fadeInUp 0.4s ease-out both;
    }
    .loading-spinner {
        width: 46px;
        height: 46px;
        margin: 0 auto 1rem auto;
        border-radius: 50%;
        border: 3px solid rgba(99, 102, 241, 0.2);
        border-top-color: #6366f1;
        animation: spin-loader 0.85s linear infinite;
    }
    @keyframes spin-loader {
        to { transform: rotate(360deg); }
    }
    .loading-overlay p {
        color: #94a3b8;
        font-size: 0.85rem;
        margin: 0;
    }
    /* ============================================================
       TAG CHIPS — custom labels a user attaches to a lead
       ============================================================ */
    .tag-chip {
        display: inline-block;
        padding: 0.15rem 0.6rem;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 700;
        margin: 0 0.3rem 0.3rem 0;
        background: rgba(99, 102, 241, 0.15);
        color: #a5b4fc;
        border: 1px solid rgba(99, 102, 241, 0.35);
        animation: badge-pop 0.3s ease both;
    }
    .tag-chip.duplicate {
        background: rgba(251, 191, 36, 0.12);
        color: #fbbf24;
        border-color: rgba(251, 191, 36, 0.35);
    }

    /* ============================================================
       ONBOARDING BANNER — first-run guidance, dismissible
       ============================================================ */
    .onboarding-banner {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.12), rgba(167, 139, 250, 0.08));
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 14px;
        padding: 1rem 1.25rem;
        margin-bottom: 1.5rem;
        animation: fadeInDown 0.5s ease-out both;
    }
    .onboarding-banner h4 {
        margin: 0 0 0.35rem 0;
        color: #e0e7ff;
    }
    .onboarding-banner p {
        margin: 0;
        color: #94a3b8;
        font-size: 0.85rem;
    }

    /* ============================================================
       USAGE METER — running estimate of API consumption
       ============================================================ */
    .usage-meter {
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 0.75rem 1rem;
        margin-top: 0.75rem;
        font-size: 0.78rem;
        color: #94a3b8;
    }
    .usage-meter b { color: #e2e8f0; }

    /* ============================================================
       PRINT STYLES — clean printable lead report
       ============================================================ */
    @media print {
        .starfield, .stSidebar, div.stButton, [data-testid="stSlider"] {
            display: none !important;
        }
        .premium-lead-card {
            break-inside: avoid;
            box-shadow: none !important;
            border: 1px solid #333 !important;
        }
        body, .stApp { background: #ffffff !important; color: #000000 !important; }
    }
</style>

<div class="starfield"></div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="premium-header">
    <div class="premium-logo">🪐</div>
    <h1 class="premium-title">LeadAgent.io</h1>
    <div class="live-status"><span class="live-dot"></span> <span class="typewriter">Autonomous discovery engine online</span></div>
</div>
""", unsafe_allow_html=True)

# ---- Sidebar ----
st.sidebar.title("Data Terminal")

if "marketing_framework" not in st.session_state:
    st.session_state.marketing_framework = "PAS (Problem, Agitation, Solution)"
if "search_history_log" not in st.session_state:
    st.session_state.search_history_log = []
if "selected_leads" not in st.session_state:
    st.session_state.selected_leads = {}
if "removed_lead_urls" not in st.session_state:
    st.session_state.removed_lead_urls = set()
if "processed_leads" not in st.session_state:
    st.session_state.processed_leads = []
if "lead_notes" not in st.session_state:
    st.session_state.lead_notes = {}
if "lead_tags" not in st.session_state:
    st.session_state.lead_tags = {}
if "seen_urls" not in st.session_state:
    st.session_state.seen_urls = set()
if "usage_tokens_est" not in st.session_state:
    st.session_state.usage_tokens_est = 0
if "usage_calls" not in st.session_state:
    st.session_state.usage_calls = 0
if "onboarding_dismissed" not in st.session_state:
    st.session_state.onboarding_dismissed = False

st.sidebar.markdown("### 🧠 Persuasion Psychology Model")
st.session_state.marketing_framework = st.sidebar.selectbox(
    "Select Copywriting Strategy:",
    ["PAS (Problem, Agitation, Solution)", "AIDA (Attention, Interest, Desire, Action)", "Direct Value Hook", "Soft Curiosity Drop"]
)

st.sidebar.markdown("#### 📜 Recent Queries:")
for past_query in st.session_state.search_history_log[-5:]:
    st.sidebar.markdown(f"`🔍 {past_query}`")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔑 Connection Security")
api_key = st.sidebar.text_input("Gemini API Key", value=os.environ.get("GEMINI_API_KEY", ""), type="password", key="gemini_api_key")
serper_api_key = st.sidebar.text_input("Serper API Key", value=os.environ.get("SERPER_API_KEY", ""), type="password", key="serper_api_key")

st.sidebar.markdown("### 📧 Email Delivery")
resend_api_key = st.sidebar.text_input("Resend API Key", value=os.environ.get("RESEND_API_KEY", ""), type="password")
sender_email = st.sidebar.text_input("Sender Email", value="onboarding@resend.dev")

st.sidebar.markdown("### 🩺 System Status")
render_system_status(
    gemini_ok=bool(api_key),
    serper_ok=bool(serper_api_key),
    resend_ok=bool(resend_api_key),
)

st.sidebar.markdown("### ⏱️ Rate Limiting")
free_tier_throttle = st.sidebar.toggle(
    "Free-tier throttling (5 req/min)",
    value=True,
    help="Google's free Gemini API tier allows 5 requests per minute. Turn this off only if billing is enabled on your Google AI Studio project.",
)

with st.sidebar.expander("❓ Quick Help"):
    st.markdown("**Why did discovery fail?**")
    st.markdown("Usually a missing or expired Serper key, or the niche/city combo returned no results.")
    st.markdown("**Why was a lead skipped?**")
    st.markdown("The scrape came back empty, or the site blocked the request. Try a different niche.")
    st.markdown("**Where do outreach drafts come from?**")
    st.markdown("Generated per-lead by Gemini, styled to the copywriting framework selected above.")

st.sidebar.markdown("### 🎯 Target ICP")
icp_instruction = st.sidebar.text_area("Ideal Customer Profile Criteria", height=100)
custom_hook = st.sidebar.text_input("Special Offer (Optional)")

# ---- Main search inputs ----
col1, col2 = st.columns(2)
with col1:
    search_niche = st.text_input("🎯 Target Business Niche", value="Software Development Agencies")
with col2:
    search_city = st.text_input("📍 Target Location / City", value="Austin")

num_leads = st.slider("🔢 Number of leads to find automatically", min_value=3, max_value=15, value=5)
st.markdown("<br>", unsafe_allow_html=True)

# ============================================================
# 4. PIPELINE EXECUTION
# ============================================================

if st.button("🚀 Initialize Autonomous Agents Pipeline", type="primary", use_container_width=True):
    if not api_key:
        st.error("Authentication Failure: Please provide a valid Gemini API Key to run the pipeline.")
    elif not serper_api_key:
        st.error("Authentication Failure: Please provide a valid Serper API Key to run the pipeline.")
    else:
        overlay_slot = st.empty()
        with overlay_slot.container():
            render_loading_overlay("Spinning up the discovery engine...")

        status_container = st.container()
        with status_container:
            st.markdown("<h3>🛸 Sequence Initialized...</h3>", unsafe_allow_html=True)
            console_log = st.empty()

            full_query = f"{search_niche} in {search_city}"
            st.session_state.search_history_log.append(full_query)
            console_log.markdown(f"**[Terminal Log]** Launching autonomous search for: `{full_query}`...")

            urls = discover_company_urls(full_query, serper_api_key, num_results=num_leads)
            overlay_slot.empty()

            if not urls:
                st.error("Discovery Failure: Could not find target domains. Try another city or niche, or check your Serper API key.")
                st.stop()

            console_log.markdown(f"**[Terminal Log]** Discovery Engine found {len(urls)} target companies. Initiating live audit pipeline...")

        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name=config.GEMINI_MODEL)
        except Exception as e:
            st.error(f"Failed to initialize Gemini client: {e}")
            st.stop()

        processed_leads = []
        p_bar = st.progress(0)
        feed_slot = st.empty()
        skeleton_slot = st.empty()
        log_lines = [f"[Terminal Log] Authenticated. Model core: {config.GEMINI_MODEL}"]

        with skeleton_slot.container():
            render_skeleton_cards(min(3, len(urls)))

        for idx, url in enumerate(urls):
            log_lines.append(f"({idx + 1}/{len(urls)}) Scraping <code>{url}</code>...")
            with feed_slot.container():
                render_activity_feed(log_lines[-6:])

            site_copy = scrape_live_company_site(url)

            log_lines.append(
                f"({idx + 1}/{len(urls)}) Scraped {len(site_copy)} characters from <code>{url}</code>. "
                f"Querying {config.GEMINI_MODEL} for ICP match..."
            )
            with feed_slot.container():
                render_activity_feed(log_lines[-6:])

            prompt = f"""
Analyze the scraped webpage text from {url}. Evaluate it against the target ICP: {icp_instruction}

Context from website copy:
{site_copy}

Requirements for the generated outreach sequence (only if the lead is qualified):
- Tone of voice: Use a {st.session_state.marketing_framework} style.
- Direct call to action / offer: {custom_hook if custom_hook else "Propose a quick introductory chat"}
- Keep the linkedin_note field strictly under 300 characters.
"""

            try:
                generation_config = genai.types.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=LeadQualificationResult,
                    temperature=0.1,
                )
                response = call_gemini_with_retry(model, prompt, generation_config)
                result = LeadQualificationResult.model_validate_json(response.text)
                processed_leads.append((url, result))
                log_lines.append(f"({idx + 1}/{len(urls)}) ✅ Qualification score: {result.qualification_score}/100")
            except Exception as e:
                st.warning(f"Skipped {url}: {e}")
                log_lines.append(f"({idx + 1}/{len(urls)}) ⚠️ Skipped — {e}")

            with feed_slot.container():
                render_activity_feed(log_lines[-6:])

            if free_tier_throttle and idx < len(urls) - 1:
                time.sleep(12)

            p_bar.progress((idx + 1) / len(urls))

        skeleton_slot.empty()
        st.session_state.processed_leads = processed_leads
        render_toast(
            f"Pipeline complete. {len(processed_leads)}/{len(urls)} leads processed successfully.",
            kind="success",
        )

# ============================================================
# 5. RESULTS DASHBOARD
# ============================================================

processed_leads = st.session_state.processed_leads

if not processed_leads:
    render_empty_state(
        "🛰️",
        "No leads discovered yet",
        "Set your niche, city, and ICP in the sidebar, then launch the pipeline above.",
    )

if processed_leads:
    st.markdown("<br><hr><br>", unsafe_allow_html=True)
    st.markdown('<div class="section-fade-in"><h3>📊 Pipeline Insights Dashboard</h3></div>', unsafe_allow_html=True)

    total_leads = len(processed_leads)
    qualified_leads = sum(1 for _, lead in processed_leads if lead.is_qualified)
    qualification_rate = (qualified_leads / total_leads) * 100 if total_leads else 0
    avg_score = sum(lead.qualification_score for _, lead in processed_leads) / total_leads if total_leads else 0

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f'<div class="metric-card" style="animation-delay:0.05s;"><p style="color:#9ca3af;margin:0;font-size:0.875rem;font-weight:600;text-transform:uppercase;">Total Leads</p><h2 style="color:#ffffff;margin:0.5rem 0 0 0;font-size:2rem;font-weight:800;">{total_leads}</h2></div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="metric-card" style="animation-delay:0.15s;"><p style="color:#10b981;margin:0;font-size:0.875rem;font-weight:600;text-transform:uppercase;">✅ Qualified</p><h2 style="color:#10b981;margin:0.5rem 0 0 0;font-size:2rem;font-weight:800;">{qualified_leads}</h2></div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="metric-card" style="animation-delay:0.25s;"><p style="color:#3b82f6;margin:0;font-size:0.875rem;font-weight:600;text-transform:uppercase;">Conversion Rate</p><h2 style="color:#3b82f6;margin:0.5rem 0 0 0;font-size:2rem;font-weight:800;">{qualification_rate:.1f}%</h2></div>', unsafe_allow_html=True)
    with m4:
        st.markdown(f'<div class="metric-card" style="animation-delay:0.35s;"><p style="color:#f59e0b;margin:0;font-size:0.875rem;font-weight:600;text-transform:uppercase;">Avg Match Score</p><h2 style="color:#f59e0b;margin:0.5rem 0 0 0;font-size:2rem;font-weight:800;">{avg_score:.1f}/100</h2></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    render_section_divider("Top Leads")
    render_leaderboard(processed_leads)

    render_section_divider("Industry Breakdown")
    render_industry_chart(processed_leads)

    min_score_filter = st.slider("⚡ Filter displayed leads by minimum score threshold:", min_value=0, max_value=100, value=0, step=5)
    st.markdown("<hr>", unsafe_allow_html=True)

    filtered_leads = [item for item in processed_leads if item[1].qualification_score >= min_score_filter]
    active_display_leads = [item for item in filtered_leads if item[0] not in st.session_state.removed_lead_urls]

    for idx, (url, lead) in enumerate(active_display_leads):
        col_checkbox, col_trash = st.columns([5, 1])
        with col_checkbox:
            is_selected = st.checkbox(
                f"📥 Include {lead.company.name} in batch distribution package",
                value=st.session_state.selected_leads.get(url, True),
                key=f"final_batch_check_{url}_{idx}"
            )
            st.session_state.selected_leads[url] = is_selected
        with col_trash:
            if st.button("🗑️ Burn Lead", key=f"trash_lead_{url}_{idx}", use_container_width=True):
                st.session_state.removed_lead_urls.add(url)
                st.rerun()

        badge_glow_style = "badge-qualified-glow" if lead.is_qualified else "badge-disqualified-glow"
        badge_label = f"🔥 Qualified ({lead.qualification_score}/100)" if lead.is_qualified else f"❄️ Disqualified ({lead.qualification_score}/100)"
        card_delay = min(idx * 0.08, 0.8)
        tier_label, tier_class = get_tier(lead.qualification_score)

        st.markdown(f"""
        <div class="premium-lead-card" style="animation-delay:{card_delay}s;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.75rem;">
                <div style="display:flex; align-items:center; gap:0.9rem;">
                    {score_ring_html(lead.qualification_score)}
                    <h3 style="margin:0; color:#ffffff; font-size:1.55rem; font-weight:800; letter-spacing:-0.02rem;">🏢 {lead.company.name}</h3>
                </div>
                <div>
                    <span class="glow-badge {badge_glow_style}">{badge_label}</span>
                    <span class="tier-badge {tier_class}">{tier_label}</span>
                </div>
            </div>
            <div style="display: flex; gap: 1rem; margin-bottom: 0.5rem; font-size: 0.9rem; color: #9ca3af;">
                <div><b style="color: #818cf8;">📌 Industry:</b> {lead.company.industry}</div>
                <div><b style="color: #818cf8;">⚡ Model:</b> {lead.company.business_model}</div>
            </div>
            <div class="reasoning-box">
                <p style="color:#e2e8f0; margin:0; line-height:1.6; font-size: 0.93rem;"><strong>AI Diagnostic Analysis:</strong> {lead.reasoning}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if tier_class == "tier-platinum":
            render_confetti_burst()

        if lead.company.linkedin_url or lead.company.twitter_url:
            col_li, col_tw, _ = st.columns([1.5, 1.5, 4])
            with col_li:
                if lead.company.linkedin_url:
                    st.link_button("🤝 Company LinkedIn", lead.company.linkedin_url, use_container_width=True)
            with col_tw:
                if lead.company.twitter_url:
                    st.link_button("🐦 Company Twitter/X", lead.company.twitter_url, use_container_width=True)

        if lead.is_qualified and lead.outreach_sequence.subject_line:
            with st.expander(f"✉️ View Outreach Strategy Draft ({st.session_state.marketing_framework})"):
                tab_email, tab_linkedin = st.tabs(["📧 Email Sequence", "🤝 LinkedIn Connect Note"])

                with tab_email:
                    st.markdown(f"**Subject Line:** `{lead.outreach_sequence.subject_line}`")
                    editable_email = st.text_area(
                        "✍️ Modify Email Draft:",
                        value=lead.outreach_sequence.email_body,
                        height=200,
                        key=f"edit_email_{url}_{idx}"
                    )

                    st.markdown("### 🚀 Trigger Live Outreach")
                    target_recipient = st.text_input(f"Recipient Email for {lead.company.name}", value=f"hello@{url}", key=f"to_{url}_{idx}")

                    if st.button(f"Send Email to {lead.company.name}", key=f"btn_{url}_{idx}"):
                        if not resend_api_key:
                            st.error("Please add a Resend API key in the sidebar to send live pitches.")
                        else:
                            try:
                                resend.api_key = resend_api_key
                                resend.Emails.send({
                                    "from": sender_email,
                                    "to": [target_recipient],
                                    "subject": lead.outreach_sequence.subject_line,
                                    "text": editable_email
                                })
                                st.success(f"📩 Email successfully dispatched to {target_recipient}!")
                            except Exception as email_err:
                                st.error(f"Failed to deliver email: {email_err}")

                with tab_linkedin:
                    st.markdown("**Personalized Connection Request Note:**")
                    editable_linkedin = st.text_area(
                        "✍️ Edit LinkedIn Note:",
                        value=lead.outreach_sequence.linkedin_note,
                        height=120,
                        key=f"edit_li_{url}_{idx}"
                    )
                    char_count = len(editable_linkedin)
                    color = "#10b981" if char_count <= 300 else "#ef4444"
                    st.markdown(f"<span style='color: {color}; font-weight:bold;'>Character Count: {char_count}/300</span>", unsafe_allow_html=True)
                    if char_count > 300:
                        st.warning("⚠️ This note exceeds the 300-character LinkedIn connection request limit!")

    # ---- Batch CSV export ----
    batch_output = io.StringIO()
    batch_writer = csv.writer(batch_output)
    batch_writer.writerow(["URL", "Company Name", "Industry", "Match Score", "Status", "Email Subject", "Email Body", "LinkedIn Note"])

    for url, lead in processed_leads:
        if st.session_state.selected_leads.get(url, False):
            batch_writer.writerow([
                url, lead.company.name, lead.company.industry, lead.qualification_score,
                "Qualified" if lead.is_qualified else "Disqualified",
                lead.outreach_sequence.subject_line,
                lead.outreach_sequence.email_body,
                lead.outreach_sequence.linkedin_note
            ])

    st.markdown("<br>", unsafe_allow_html=True)
    col_csv, col_json = st.columns(2)
    with col_csv:
        st.download_button(
            label=f"📊 Export Selected Leads CSV ({sum(1 for v in st.session_state.selected_leads.values() if v)} Selected)",
            data=batch_output.getvalue(),
            file_name="selective_leads_export.csv",
            mime="text/csv",
            use_container_width=True
        )
    with col_json:
        st.download_button(
            label="🧾 Export All Leads JSON",
            data=export_leads_json(processed_leads),
            file_name="leads_export.json",
            mime="application/json",
            use_container_width=True
        )

render_app_footer()

with st.expander("ℹ️ About LeadAgent.io"):
    st.markdown("""
**LeadAgent.io** is an autonomous B2B lead discovery and qualification agent.
It searches for companies matching a target niche and location, scrapes each
company's public site, scores the fit against your Ideal Customer Profile,
and drafts personalized outreach — end to end, with no manual research.

**Changelog**
- `v1.3` — Added JSON export, industry breakdown chart, and top-leads leaderboard.
- `v1.2` — Added achievement tiers, animated score rings, and confetti for top-tier leads.
- `v1.1` — Fixed structured-output schema compatibility; every lead now processes reliably.
- `v1.0` — Initial autonomous discovery, scraping, qualification, and outreach pipeline.
""")