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
from google import genai
from google.genai import types

# --- 1. DATA STRUCTURES ---
class LeadCompanyInfo(BaseModel):
    name: str = Field(description="The name of the target company")
    industry: str = Field(description="The primary industry or vertical")
    company_size: str = Field(description="Estimated size range or employee count")
    business_model: str = Field(description="B2B SaaS, Agency, E-commerce, etc.")
    core_pain_points: List[str] = Field(description="Key pain points discovered from live text")

class OutreachDraft(BaseModel):
    subject_line: str = Field(description="A distinct, professional, non-spammy email subject line")
    email_body: str = Field(description="A highly personalized cold email draft under 120 words referencing their site copy")

class LeadQualificationResult(BaseModel):
    company: LeadCompanyInfo
    qualification_score: int = Field(description="ICP qualification score from 0 to 100")
    is_qualified: bool = Field(description="True if qualification_score is >= 70")
    reasoning: str = Field(description="Clear breakdown explaining the qualification score")
    outreach_sequence: Optional[OutreachDraft] = Field(None)

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
    <p class="saas-subtitle">Autonomous Data Terminal for Hyper-Personalized Prospecting</p>
</div>
""", unsafe_allow_html=True)

# Sidebar UI
st.sidebar.markdown("<h1 style='color:#ffffff; font-size:2rem; font-weight:800; letter-spacing:-0.05em; margin-bottom:1.5rem;'>Data Terminal</h1>", unsafe_allow_html=True)
st.sidebar.markdown("<h2 style='color:#9ca3af; font-size:1rem; font-weight:600;'>🛠️ Connection Security</h2>", unsafe_allow_html=True)
api_key = st.sidebar.text_input("Gemini API Key", value=os.environ.get("GEMINI_API_KEY", ""), type="password")
model_choice = st.sidebar.selectbox("Select Core Engine", ["gemini-3.1-flash-lite", "gemini-3.5-flash"])

st.sidebar.markdown("---")
st.sidebar.markdown("<h2 style='color:#9ca3af; font-size:1rem; font-weight:600;'>🎯 Target ICP Profile</h2>", unsafe_allow_html=True)
icp_instruction = st.sidebar.text_area("Ideal Customer Profile Criteria", 
    value="B2B SaaS or Enterprise software platforms looking for infrastructure scaling automation.", height=120)

# Inputs
urls_input = st.text_area("🔗 Target Domains (Enter one per line)", 
                          value="stripe.com\nhubspot.com\nzapier.com", height=120)

st.markdown("<br>", unsafe_allow_html=True)

if st.button("🚀 Initialize Autonomous Agents Pipeline", type="primary", use_container_width=True):
    if not api_key:
        st.error("Authentication Failure: Please provide a valid Gemini API Key to run the pipeline.")
    else:
        urls = [u.strip() for u in urls_input.split("\n") if u.strip()]
        
        try:
            client = genai.Client(api_key=api_key)
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
                log_text = f"**[Terminal Log]** Authenticating... SUCCESS. Model Core: `{model_choice}`\n\n**[Terminal Log]** Initializing crawling for: `{url}`..."
                console_log.markdown(log_text)
                
                site_copy = scrape_live_company_site(url)
                
                # Update 2: Show successful scrape size
                log_text += f"\n\n**[Terminal Log]** Web Scraping: COMPLETE ({len(site_copy)} characters found)"
                console_log.markdown(log_text)
                
                # Update 3: Evaluating AI matching rules
                log_text += f"\n\n**[Terminal Log]** Querying {model_choice} engine for ICP Match..."
                console_log.markdown(log_text)
                
                prompt = f"Analyze the scraped webpage text from {url}. Evaluate against the target ICP: {icp_instruction}\n\nContext:\n{site_copy}"
                
                try:
                    response = client.models.generate_content(
                        model=model_choice,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction="You are a professional B2B lead generation workflow engine. Output structural JSON matching the target schema.",
                            response_mime_type="application/json",
                            response_schema=LeadQualificationResult,
                            temperature=0.1,
                        ),
                    )
                    result = LeadQualificationResult.model_validate_json(response.text)
                    processed_leads.append((url, result))
                    
                    # Update 4: Final output status of current run
                    status_type = "QUALIFIED" if result.is_qualified else "DISQUALIFIED"
                    log_text += f"\n\n**[Terminal Log]** AI Evaluation: COMPLETE. Result: `{status_type}` ({result.qualification_score}/100)."
                    console_log.markdown(log_text)
                    time.sleep(0.8) # Quick pause to allow user to visually read the log stream
                    
                except Exception as e:
                    st.error(f"Error evaluating {url}: {e}")
                
                p_bar.progress((idx + 1) / len(urls))
            
            console_log.markdown("**[TERMINAL STATE]** Pipeline analysis finalized. See immersive results below.")
        
        st.markdown("<br><hr><br>", unsafe_allow_html=True)
        
        # Display Dynamic, Claude-style Results
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Target URL", "Company Name", "Industry", "Score", "Qualified", "Reasoning", "Subject Line", "Email Body"])
        
        for url, lead in processed_leads:
            writer.writerow([
                url, lead.company.name, lead.company.industry, lead.qualification_score,
                lead.is_qualified, lead.reasoning,
                lead.outreach_sequence.subject_line if lead.outreach_sequence else "N/A",
                lead.outreach_sequence.email_body if lead.outreach_sequence else "N/A"
            ])
            
            badge_class = "badge-qualified" if lead.is_qualified else "badge-unqualified"
            badge_text = f"QUALIFIED ({lead.qualification_score}/100)" if lead.is_qualified else f"DISQUALIFIED ({lead.qualification_score}/100)"
            
            st.markdown(f"""
            <div class="result-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                    <h3 style="margin:0; color:#ffffff; font-size:1.6rem; font-weight:800; letter-spacing:-0.03em;">🏢 {lead.company.name}</h3>
                    <span class="{badge_class}">{badge_text}</span>
                </div>
                <p style="color:#9ca3af; margin: 0.2rem 0;"><strong>Detected Industry:</strong> {lead.company.industry} | <strong>Business Model:</strong> {lead.company.business_model}</p>
                <p style="color:#d1d5db; margin-top:0.8rem; line-height:1.6;">💡 <strong>AI Analysis reasoning:</strong> {lead.reasoning}</p>
            </div>
            """, unsafe_allow_html=True)
            
            if lead.outreach_sequence:
                with st.expander(f"✉️ View Outreach Strategy Draft for {lead.company.name}"):
                    st.markdown(f"**Subject Line:** `{lead.outreach_sequence.subject_line}`")
                    st.code(lead.outreach_sequence.email_body, language="text")
        
        # Export Actions
        st.markdown("<br>", unsafe_allow_html=True)
        st.download_button(
            label="📥 Export Immersive Data CSV Spreadsheet",
            data=output.getvalue(),
            file_name="autonomous_leads_export.csv",
            mime="text/csv",
            use_container_width=True
        )