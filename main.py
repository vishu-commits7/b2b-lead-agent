import os
import sys
import csv
import io
import time
import httpx
from bs4 import BeautifulSoup
from typing import List, Optional
from pydantic import BaseModel, Field
import streamlit as st
import google.generativeai as genai
from google.generativeai import types
import resend

# --- 1. DATA STRUCTURES ---
class LeadCompanyInfo(BaseModel):
    model_config = {"extra": "ignore"}  # <--- MUST ADD THIS
    name: str = Field(description="...")
    industry: str = Field(description="...")
    # ... your other fields ...



class OutreachDraft(BaseModel):
    subject_line: str = Field(description="A distinct, professional, non-spammy email subject line matching the chosen psychological framework")
    email_body: str = Field(description="A highly personalized cold email draft under 120 words engineered specifically using the template framework rules")
    linkedin_note: str = Field(description="A highly tailored, contextual LinkedIn connection request note under 300 characters total")
    chosen_framework: str = Field(description="The structural marketing angle used to craft this message")


class LeadQualificationResult(BaseModel):
    model_config = {"extra": "ignore"}  # <--- MUST ADD THIS
    company: LeadCompanyInfo
    qualification_score: int
    # ... your other fields ...
# --- 2. LIVE CRAWLING ENGINE ---
def scrape_live_company_site(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) B2BWebAgent/2.1"}
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        response = httpx.get(url, headers=headers, timeout=7.0, follow_redirects=True)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            for script in soup(["script", "style", "meta", "noscript"]):
                script.decompose()
            return " ".join(soup.get_text().split())[:4000]
        return f"Error: Status code {response.status_code}"
    except Exception as e:
        return f"Network Error: {str(e)}"

def discover_company_urls(query: str, num_results: int = 5) -> List[str]:
    """Uses Serper API to bypass Google blocks and discover clean root domains."""
    discovered_urls = []
    # Replace the text below with your actual API key from serper.dev
    SERPER_API_KEY = "38ac0bd933f5c7593dc9b43e57cc2601ddb87450" 
    
    url = "https://google.serper.dev/search"
    payload = {"q": query, "num": num_results + 5}
    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }
    
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=10.0)
        if response.status_code == 200:
            results = response.json().get("organic", [])
            for item in results:
                link = item.get("link", "")
                if link:
                    if any(x in link for x in ["google.com", "linkedin.com", "yelp.com", "clutch.co", "upwork.com", "wikipedia.org"]):
                        continue
                    from urllib.parse import urlparse
                    domain = urlparse(link).netloc
                    if domain and domain not in discovered_urls:
                        discovered_urls.append(domain)
                if len(discovered_urls) >= num_results:
                    break
    except Exception as e:
        pass
    
    return discovered_urls
# --- 3. STREAMLIT WEB UI SETUP ---
st.set_page_config(page_title="LeadAgent AI | Premium Data Terminal", layout="wide", initial_sidebar_state="expanded")

# --- 🧠 CUSTOM PREMIUM GLASSMORPHISM CSS ---
st.markdown("""
<style>
    /* 1. Global Immersive Gradient Background */
    [data-testid="stAppViewContainer"] {
        background: radial-gradient(circle at 10% 20%, rgb(0, 0, 0) 0%, rgb(18, 18, 18) 100.2%);
        color: #e2e8f0;
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
    }
    
    /* 2. Frosted Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: rgba(26, 32, 44, 0.5) !important;
        backdrop-filter: blur(12px);
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }
    
    /* 3. Immersive Header Card */
    .premium-header {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(8px);
        padding: 3rem;
        border-radius: 20px;
        margin-bottom: 3rem;
        box-shadow: 0 10px 30px -5px rgba(0,0,0,0.5);
        border: 1px solid rgba(255, 255, 255, 0.05);
        text-align: center;
        animation: fadeInDown 0.8s ease-out;
    }
    .premium-logo { font-size: 3.2rem; margin-bottom: 0.5rem; }
    .premium-title {
        color: #ffffff;
        font-size: 3.2rem;
        font-weight: 900;
        margin: 0;
        letter-spacing: -0.06em;
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    /* 4. Result Card styling (Glass + Slide Animation) */
    .result-card {
        background: rgba(255, 255, 255, 0.02);
        backdrop-filter: blur(10px);
        padding: 2.2rem;
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.05);
        margin-bottom: 2rem;
        transition: transform 0.3s, border-color 0.3s;
        animation: slideInRight 0.6s ease-out;
    }
    .result-card:hover {
        transform: translateY(-4px) scale(1.005);
        border-color: rgba(167, 139, 250, 0.4);
    }
    
    /* 5. Dynamic Score Badge (Gradient & Głow) */
    .badge-qualified {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(5, 150, 105, 0.3) 100%);
        color: #34d399;
        padding: 0.5rem 1.2rem;
        border-radius: 30px;
        font-weight: 800;
        border: 1px solid rgba(16, 185, 129, 0.4);
        box-shadow: 0 0 15px rgba(16, 185, 129, 0.2);
    }
    .badge-unqualified {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.2) 0%, rgba(185, 28, 28, 0.3) 100%);
        color: #f87171;
        padding: 0.5rem 1.2rem;
        border-radius: 30px;
        font-weight: 800;
        border: 1px solid rgba(239, 68, 68, 0.4);
    }
    
    /* 6. Claude-style Code Editor */
    textarea {
        background-color: rgba(0,0,0,0.2) !important;
        color: #e2e8f0 !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
    }

    /* 7. Keyframe Animations */
    @keyframes fadeInDown {
        0% { opacity: 0; transform: translateY(-20px); }
        100% { opacity: 1; transform: translateY(0); }
    }
    @keyframes slideInRight {
        0% { opacity: 0; transform: translateX(30px); }
        100% { opacity: 1; transform: translateX(0); }
    }
</style>
""", unsafe_allow_html=True)

# Main Title Section
st.markdown("""
<div class="premium-header">
    <div class="premium-logo">🪐</div>
    <h1 class="premium-title">LeadAgent.io</h1>
</div>
""", unsafe_allow_html=True)

# Sidebar UI
# --- SIDEBAR UI ---
st.sidebar.title("Data Terminal")

# Define the framework variable globally
if "marketing_framework" not in st.session_state:
    st.session_state.marketing_framework = "PAS (Problem, Agitation, Solution)"

st.sidebar.markdown("### 🧠 Persuasion Psychology Model")
st.session_state.marketing_framework = st.sidebar.selectbox(
    "Select Copywriting Strategy:",
    ["PAS (Problem, Agitation, Solution)", "AIDA (Attention, Interest, Desire, Action)", "Direct Value Hook", "Soft Curiosity Drop"]
)

# Search History Tracker
if "search_history_log" not in st.session_state:
    st.session_state.search_history_log = []

st.sidebar.markdown("#### 📜 Recent Queries:")
for past_query in st.session_state.search_history_log[-5:]:
    st.sidebar.markdown(f"`🔍 {past_query}`")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔑 Connection Security")
# Change line 213 to this:
api_key = st.sidebar.text_input("Gemini API Key", value=os.environ.get("GEMINI_API_KEY", ""), type="password", key="gemini_api_key")

st.sidebar.markdown("### 📧 Email Delivery")
resend_api_key = st.sidebar.text_input("Resend API Key", value=os.environ.get("RESEND_API_KEY", ""), type="password")
sender_email = st.sidebar.text_input("Sender Email", value="onboarding@resend.dev")

st.sidebar.markdown("### 🎯 Target ICP")
icp_instruction = st.sidebar.text_area("Ideal Customer Profile Criteria", height=100)
custom_hook = st.sidebar.text_input("Special Offer (Optional)")
if "selected_leads" not in st.session_state:
    st.session_state.selected_leads = {}
# --- NEW AUTOMATED SEARCH INPUTS ---
col1, col2 = st.columns(2)
with col1:
    search_niche = st.text_input("🎯 Target Business Niche", value="Software Development Agencies")
with col2:
    search_city = st.text_input("📍 Target Location / City", value="Austin")

# Number of targets to scrape automatically
num_leads = st.slider("🔢 Number of leads to find automatically", min_value=3, max_value=15, value=5)
st.markdown("<br>", unsafe_allow_html=True)

if st.button("🚀 Initialize Autonomous Agents Pipeline", type="primary", use_container_width=True):
    if not api_key:
        st.error("Authentication Failure: Please provide a valid Gemini API Key to run the pipeline.")
    else:
       # --- NEW CONSOLE LOG FOR DISCOVERY PHASE ---
        status_container = st.container()
        
        with status_container:
            st.markdown("<h3>🛸 Sequence Initialized...</h3>", unsafe_allow_html=True)
            console_log = st.empty()
            
            # Combine niche and city into a solid search query
            full_query = f"{search_niche} in {search_city}"
            console_log.markdown(f"**[Terminal Log]** Launching background autonomous search for: `{full_query}`...")
            
            # Automatically find the URLs!
            urls = discover_company_urls(full_query, num_results=num_leads)
            
            if not urls:
                st.error("Discovery Failure: Could not scrape root search domains. Try another city or niche.")
                st.stop()
                
            console_log.markdown(f"**[Terminal Log]** Discovery Engine found {len(urls)} target agencies. Initiating live audit pipeline...")
            time.sleep(1.5)
            
            p_bar = st.progress(0)
            # The rest of your loop (for idx, url in enumerate(urls):) stays exactly the same!
        
        try:
            # Replace 'client = genai.Client(...)' with this:
            genai.configure(api_key=st.session_state.gemini_api_key)
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
        except Exception as e:
            st.error(f"Failed to initialize client: {e}")
            st.stop()
            
        processed_leads = []
        
        # --- 🎬 DYNAMIC CONSOLE LOG SEQUENCE ---
        status_container = st.container()
        
        with status_container:
            st.markdown("<h3>🛸 Sequence Initialized...</h3>", unsafe_allow_html=True)
            console_log = st.empty()  # This empty slot is where we dynamically swap log text
            p_bar = st.progress(0)
            
            for idx, url in enumerate(urls):
                # Update 1: Show connection & start crawling
                log_text = f"[Terminal Log] Authenticating... SUCCESS. Model Core: Gemini 1.5 Flash..."
                console_log.markdown(log_text)
                
                site_copy = scrape_live_company_site(url)
                
                # Update 2: Show successful scrape size
                log_text += f"\n\n**[Terminal Log]** Web Scraping: COMPLETE ({len(site_copy)} characters found)"
                console_log.markdown(log_text)
                
                # Update 3: Evaluating AI matching rules
                log_text += f"\n\n[Terminal Log] Querying Gemini 1.5 Flash engine for ICP Match..."
                console_log.markdown(log_text)
                
                prompt = f"""
        Analyze the scraped webpage text from {url}. Evaluate against the target ICP: {icp_instruction}
        
        Context from website copy:
        {site_copy}
        
        Requirements for the generated outreach sequence:
        - Tone of voice: Use a {st.session_state.marketing_framework} style.
        - Direct Call to Action/Offer: {custom_hook if custom_hook else "Propose a quick introductory chat"}
        - Ensure the linkedin_note field is completely filled out contextually and strictly under 300 characters total.
        """
    genai.configure(api_key=st.session_state.gemini_api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    
        # ... rest of your code ...
    # ... inside your loop ...
   # Ensure this is inside your loop: for idx, url in enumerate(urls):
    try:
            # 1. Configuration
            generation_config = genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=LeadQualificationResult,
                temperature=0.1,
            )
            
            # 2. API Call
            response = model.generate_content(prompt, generation_config=generation_config)
            
            # 3. Validation
            result = LeadQualificationResult.model_validate_json(response.text)
            processed_leads.append((url, result))
            
    except Exception as e:
            # 4. Error Handling
            st.error(f"Error evaluating {url}: {e}")

# Everything after this point is back at the indentation level of the 'try'
        
    st.markdown("<br><hr><br>", unsafe_allow_html=True)
        
    # Display Dynamic, Claude-style Results  
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Target URL", "Company Name", "Industry", "Score", "Qualified", "Reasoning", "Subject Line", "Email Body"])
    if 'processed_leads' in locals() and processed_leads:
        # --- PIPELINE METRICS CONTAINER ---
        total_leads = len(processed_leads)
        qualified_leads = sum(1 for _, lead in processed_leads if lead.is_qualified)
        qualification_rate = (qualified_leads / total_leads) * 100 if total_leads > 0 else 0
        avg_score = sum(lead.qualification_score for _, lead in processed_leads) / total_leads if total_leads > 0 else 0

        st.markdown("### 📊 Pipeline Insights Dashboard")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f'<div style="background: #1e293b; padding: 1.25rem; border-radius: 0.75rem; border: 1px solid #334155; text-align: center;"><p style="color: #9ca3af; margin: 0; font-size: 0.875rem; font-weight: 600; text-transform: uppercase;">Total Leads</p><h2 style="color: #ffffff; margin: 0.5rem 0 0 0; font-size: 2rem; font-weight: 800;">{total_leads}</h2></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div style="background: #1e293b; padding: 1.25rem; border-radius: 0.75rem; border: 1px solid #334155; text-align: center;"><p style="color: #10b981; margin: 0; font-size: 0.875rem; font-weight: 600; text-transform: uppercase;">✅ Qualified</p><h2 style="color: #10b981; margin: 0.5rem 0 0 0; font-size: 2rem; font-weight: 800;">{qualified_leads}</h2></div>', unsafe_allow_html=True)
        with col3:
            st.markdown(f'<div style="background: #1e293b; padding: 1.25rem; border-radius: 0.75rem; border: 1px solid #334155; text-align: center;"><p style="color: #3b82f6; margin: 0; font-size: 0.875rem; font-weight: 600; text-transform: uppercase;">Conversion Rate</p><h2 style="color: #3b82f6; margin: 0.5rem 0 0 0; font-size: 2rem; font-weight: 800;">{qualification_rate:.1f}%</h2></div>', unsafe_allow_html=True)
        with col4:
            st.markdown(f'<div style="background: #1e293b; padding: 1.25rem; border-radius: 0.75rem; border: 1px solid #334155; text-align: center;"><p style="color: #f59e0b; margin: 0; font-size: 0.875rem; font-weight: 600; text-transform: uppercase;">Avg Match Score</p><h2 style="color: #f59e0b; margin: 0.5rem 0 0 0; font-size: 2rem; font-weight: 800;">{avg_score:.1f}/100</h2></div>', unsafe_allow_html=True)
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        # DYNAMIC THRESHOLD SLIDER
        min_score_filter = st.slider("⚡ Filter displayed leads by minimum score threshold:", min_value=0, max_value=100, value=0, step=5)
        st.markdown("<hr>", unsafe_allow_html=True)

        # Apply filtering
        filtered_leads = [item for item in processed_leads if item[1].qualification_score >= min_score_filter]

        for idx, item in enumerate(filtered_leads):
            url, lead = item
            
            # Interactive Checkbox to add/remove this company from the final download sheet
            is_selected = st.checkbox(
                f"📥 Include {lead.company.name} in final batch download", 
                value=st.session_state.selected_leads.get(url, True),
                key=f"final_batch_check_{url}_{idx}"
            )
            st.session_state.selected_leads[url] = is_selected

            badge_class = "badge-qualified" if lead.is_qualified else "badge-unqualified"
            badge_text = f"QUALIFIED ({lead.qualification_score}/100)" if lead.is_qualified else f"DISQUALIFIED ({lead.qualification_score}/100)"

            # Inject modern glassmorphic/glowing CSS styles dynamically
        st.markdown("""
        <style>
        .custom-lead-card {
            background: linear-gradient(145deg, #1e293b, #0f172a);
            border: 1px solid #334155;
            padding: 1.5rem;
            border-radius: 1rem;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            margin-bottom: 1rem;
            transition: transform 0.2s ease, border-color 0.2s ease;
        }
        .custom-lead-card:hover {
            border-color: #4f46e5;
            transform: translateY(-2px);
        }
        .status-badge {
            padding: 0.4rem 0.8rem;
            border-radius: 2rem;
            font-size: 0.85rem;
            font-weight: 700;
            letter-spacing: 0.05rem;
            text-transform: uppercase;
        }
        .badge-q { background-color: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
        .badge-d { background-color: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
        </style>
        """, unsafe_allow_html=True)

        # Ensure our target deletion tracker state is initialized
        if "removed_lead_urls" not in st.session_state:
            st.session_state.removed_lead_urls = set()

        # Filter out anything the user manually tossed into the trash bin
        active_display_leads = [item for item in filtered_leads if item[0] not in st.session_state.removed_lead_urls]

        # Inject high-performance CSS styles for advanced components
        st.markdown("""
        <style>
        .premium-lead-card {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border: 1px solid #334155;
            padding: 1.5rem;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.25);
            margin-top: 0.5rem;
            margin-bottom: 0.5rem;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .premium-lead-card:hover {
            border-color: #6366f1;
            box-shadow: 0 0 20px rgba(99, 102, 241, 0.2);
            transform: translateY(-2px);
        }
        .glow-badge {
            padding: 0.35rem 0.8rem;
            border-radius: 30px;
            font-size: 0.8rem;
            font-weight: 700;
            letter-spacing: 0.06rem;
            text-transform: uppercase;
            display: inline-block;
        }
        .badge-qualified-glow {
            background: rgba(16, 185, 129, 0.1);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.4);
        }
        .badge-disqualified-glow {
            background: rgba(239, 68, 68, 0.1);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.4);
        }
        .reasoning-box {
            background: rgba(15, 23, 42, 0.5);
            padding: 1rem;
            border-radius: 8px;
            border-left: 4px solid #6366f1;
            margin-top: 1rem;
        }
        </style>
        """, unsafe_allow_html=True)

        for idx, item in enumerate(active_display_leads):
            url, lead = item
            
            # CONTROL TOP PANEL: Selection Checkbox alongside a Trash Deletion Button
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

            # Card Engine Graphics Rendering
            st.markdown(f"""
            <div class="premium-lead-card">
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

            # Interactive Social Platform Connectors
            has_linkedin = bool(getattr(lead.company, 'linkedin_url', None))
            has_twitter = bool(getattr(lead.company, 'twitter_url', None))
            
            if has_linkedin or has_twitter:
                col_li, col_tw, _ = st.columns([1.5, 1.5, 4])
                with col_li:
                    if has_linkedin:
                        st.link_button("🤝 Company LinkedIn", lead.company.linkedin_url, use_container_width=True)
                with col_tw:
                    if has_twitter:
                        st.link_button("🐦 Company Twitter/X", lead.company.twitter_url, use_container_width=True)

            # Copywriting Sequences Panels
            if lead.outreach_sequence:
               with st.expander(f"✉️ View Outreach Strategy Draft ({st.session_state.marketing_framework})"):
                    tab_email, tab_linkedin = st.tabs(["📧 Email Sequence", "🤝 LinkedIn Connect Note"])
                    
                    with tab_email:
                        st.markdown(f"**Subject Line:** `{lead.outreach_sequence.subject_line}`")
                        editable_email = st.text_area(
                            "✍️ Modify Context Template Output:", 
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
                                    params = {
                                        "from": sender_email,
                                        "to": [target_recipient],
                                        "subject": lead.outreach_sequence.subject_line,
                                        "text": editable_email
                                    }
                                    resend.Emails.send(params)
                                    st.success(f"📩 Email successfully dispatched to {target_recipient}!")
                                except Exception as email_err:
                                    st.error(f"Failed to deliver email: {email_err}")
                                    
                    with tab_linkedin:
                        st.markdown("**Personalized Connection Request Note:**")
                        editable_linkedin = st.text_area(
                            "✍nt Edit LinkedIn Note:", 
                            value=lead.outreach_sequence.linkedin_note, 
                            height=120, 
                            key=f"edit_li_{url}_{idx}"
                        )
                        
                        char_count = len(editable_linkedin)
                        color = "#10b981" if char_count <= 300 else "#ef4444"
                        st.markdown(f"<span style='color: {color}; font-weight:bold;'>Character Count: {char_count}/300</span>", unsafe_allow_html=True)
                        
                        if char_count > 300:
                            st.warning("⚠️ This note exceeds the 300-character LinkedIn connection request limit!")
        # Dynamic Batch Spreadsheet Builder
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