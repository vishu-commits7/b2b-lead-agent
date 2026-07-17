import os
import csv
import io
from typing import List, Optional
from urllib.parse import urlparse

import httpx
import streamlit as st
import resend
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
import google.generativeai as genai

import config
from dotenv import load_dotenv
load_dotenv()

# ============================================================
# 1. DATA STRUCTURES
# ============================================================

class LeadCompanyInfo(BaseModel):
    model_config = {"extra": "ignore"}
    name: str = Field(description="Company name")
    industry: str = Field(description="Primary industry or sector")
    business_model: str = Field(description="How the company makes money, e.g. B2B SaaS, agency, ecommerce")
    linkedin_url: Optional[str] = Field(default=None, description="Company LinkedIn URL if visible on the site")
    twitter_url: Optional[str] = Field(default=None, description="Company Twitter/X URL if visible on the site")


class OutreachDraft(BaseModel):
    subject_line: str = Field(description="A distinct, professional, non-spammy email subject line matching the chosen psychological framework")
    email_body: str = Field(description="A highly personalized cold email draft under 120 words")
    linkedin_note: str = Field(description="A tailored LinkedIn connection request note under 300 characters")
    chosen_framework: str = Field(description="The structural marketing angle used to craft this message")


class LeadQualificationResult(BaseModel):
    model_config = {"extra": "ignore"}
    company: LeadCompanyInfo
    qualification_score: int = Field(description="Fit score from 0-100 against the target ICP")
    is_qualified: bool = Field(description="True if this lead clears the qualification bar")
    reasoning: str = Field(description="Short explanation supporting the score")
    outreach_sequence: Optional[OutreachDraft] = Field(default=None, description="Personalized outreach draft, present only if qualified")


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
</style>

<div class="starfield"></div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="premium-header">
    <div class="premium-logo">🪐</div>
    <h1 class="premium-title">LeadAgent.io</h1>
    <div class="live-status"><span class="live-dot"></span> Autonomous discovery engine online</div>
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
        status_container = st.container()
        with status_container:
            st.markdown("<h3>🛸 Sequence Initialized...</h3>", unsafe_allow_html=True)
            console_log = st.empty()

            full_query = f"{search_niche} in {search_city}"
            st.session_state.search_history_log.append(full_query)
            console_log.markdown(f"**[Terminal Log]** Launching autonomous search for: `{full_query}`...")

            urls = discover_company_urls(full_query, serper_api_key, num_results=num_leads)

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
        console_log2 = st.empty()

        for idx, url in enumerate(urls):
            console_log2.markdown(f"**[Terminal Log]** ({idx + 1}/{len(urls)}) Scraping `{url}`...")
            site_copy = scrape_live_company_site(url)

            console_log2.markdown(
                f"**[Terminal Log]** ({idx + 1}/{len(urls)}) Scraped {len(site_copy)} characters from `{url}`. "
                f"Querying {config.GEMINI_MODEL} for ICP match..."
            )

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
                response = model.generate_content(prompt, generation_config=generation_config)
                result = LeadQualificationResult.model_validate_json(response.text)
                processed_leads.append((url, result))
            except Exception as e:
                st.warning(f"Skipped {url}: {e}")

            p_bar.progress((idx + 1) / len(urls))

        st.session_state.processed_leads = processed_leads
        st.success(f"Pipeline complete. {len(processed_leads)}/{len(urls)} leads processed successfully.")

# ============================================================
# 5. RESULTS DASHBOARD
# ============================================================

processed_leads = st.session_state.processed_leads

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

        st.markdown(f"""
        <div class="premium-lead-card" style="animation-delay:{card_delay}s;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem;">
                <h3 style="margin:0; color:#ffffff; font-size:1.55rem; font-weight:800; letter-spacing:-0.02rem;">🏢 {lead.company.name}</h3>
                <span class="glow-badge {badge_glow_style}">{badge_label}</span>
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

        if lead.company.linkedin_url or lead.company.twitter_url:
            col_li, col_tw, _ = st.columns([1.5, 1.5, 4])
            with col_li:
                if lead.company.linkedin_url:
                    st.link_button("🤝 Company LinkedIn", lead.company.linkedin_url, use_container_width=True)
            with col_tw:
                if lead.company.twitter_url:
                    st.link_button("🐦 Company Twitter/X", lead.company.twitter_url, use_container_width=True)

        if lead.outreach_sequence:
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
                lead.outreach_sequence.subject_line if lead.outreach_sequence else "",
                lead.outreach_sequence.email_body if lead.outreach_sequence else "",
                lead.outreach_sequence.linkedin_note if lead.outreach_sequence else ""
            ])

    st.markdown("<br>", unsafe_allow_html=True)
    st.download_button(
        label=f"📊 Export Selected Leads CSV ({sum(1 for v in st.session_state.selected_leads.values() if v)} Selected)",
        data=batch_output.getvalue(),
        file_name="selective_leads_export.csv",
        mime="text/csv",
        use_container_width=True
    )