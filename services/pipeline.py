"""Discovery, scraping, and Gemini qualification pipeline."""

import re
import time
from typing import Callable, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
import google.generativeai as genai
from bs4 import BeautifulSoup

import config
from models.schemas import LeadQualificationResult


def scrape_live_company_site(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 LeadAgent.io/3.0 Enterprise"}
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        response = httpx.get(url, headers=headers, timeout=10.0, follow_redirects=True)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(["script", "style", "meta", "noscript"]):
                tag.decompose()
            return " ".join(soup.get_text().split())[:6000]
        return f"Error: Status code {response.status_code}"
    except Exception as e:
        return f"Network Error: {str(e)}"


def discover_company_urls(query: str, serper_api_key: str, num_results: int = 5) -> List[str]:
    discovered_urls = []
    if not serper_api_key:
        return discovered_urls

    payload = {"q": query, "num": num_results + 8}
    headers = {"X-API-KEY": serper_api_key, "Content-Type": "application/json"}

    try:
        response = httpx.post(
            "https://google.serper.dev/search",
            json=payload,
            headers=headers,
            timeout=12.0,
        )
        if response.status_code == 200:
            skip_domains = {
                "google.com", "linkedin.com", "yelp.com", "clutch.co",
                "upwork.com", "wikipedia.org", "facebook.com", "instagram.com",
                "twitter.com", "x.com", "youtube.com", "crunchbase.com",
            }
            for item in response.json().get("organic", []):
                link = item.get("link", "")
                if not link:
                    continue
                if any(x in link for x in skip_domains):
                    continue
                domain = urlparse(link).netloc.replace("www.", "")
                if domain and domain not in discovered_urls:
                    discovered_urls.append(domain)
                if len(discovered_urls) >= num_results:
                    break
    except Exception:
        pass

    return discovered_urls


def call_gemini_with_retry(
    model,
    prompt: str,
    generation_config,
    max_retries: int = 3,
    on_rate_limit: Optional[Callable[[int, int, int], None]] = None,
):
    last_error: Exception = RuntimeError("Gemini call failed")
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
            if on_rate_limit and attempt < max_retries - 1:
                on_rate_limit(wait_seconds, attempt + 1, max_retries)
            if attempt < max_retries - 1:
                time.sleep(wait_seconds)
    raise last_error


def build_qualification_prompt(
    url: str,
    site_copy: str,
    icp_instruction: str,
    marketing_framework: str,
    custom_hook: str,
    include_enrichment: bool,
    include_sequence: bool,
) -> str:
    enrichment_block = ""
    if include_enrichment:
        enrichment_block = """
Also populate primary_contact with the most likely decision maker:
- full_name, title, email_pattern (e.g. first.last@domain), linkedin_search_query, confidence 0-100
"""
    sequence_block = ""
    if include_sequence:
        sequence_block = """
Also populate email_sequence with exactly 3 touches:
- Touch 1 (delay_days=0): Initial value-first outreach
- Touch 2 (delay_days=3): Social proof / case study follow-up
- Touch 3 (delay_days=7): Polite breakup email
Each touch needs subject_line, email_body, purpose.
"""

    return f"""
{config.SYSTEM_INSTRUCTIONS}

Analyze the scraped webpage from {url} against this ICP:
{icp_instruction or "B2B companies with 10-200 employees, decision makers in sales/growth/product."}

Website copy:
{site_copy}

Requirements:
- Populate pain_points (2-4 items) and buying_signals (1-3 items) from evidence in the copy.
- Populate company.employee_estimate and company.tech_stack_signals when inferable.
- Outreach tone: {marketing_framework}
- CTA/offer: {custom_hook or "Propose a brief introductory call"}
- linkedin_note must be under 300 characters.
{enrichment_block}
{sequence_block}
If not qualified, leave outreach fields empty and set primary_contact/email_sequence to null.
"""


def qualify_lead(
    model,
    url: str,
    site_copy: str,
    icp_instruction: str,
    marketing_framework: str,
    custom_hook: str,
    include_enrichment: bool = False,
    include_sequence: bool = False,
    on_rate_limit: Optional[Callable[[int, int, int], None]] = None,
) -> LeadQualificationResult:
    prompt = build_qualification_prompt(
        url, site_copy, icp_instruction, marketing_framework,
        custom_hook, include_enrichment, include_sequence,
    )
    generation_config = genai.types.GenerationConfig(
        response_mime_type="application/json",
        response_schema=LeadQualificationResult,
        temperature=0.15,
    )
    response = call_gemini_with_retry(model, prompt, generation_config, on_rate_limit=on_rate_limit)
    return LeadQualificationResult.model_validate_json(response.text)


def run_pipeline(
    urls: List[str],
    api_key: str,
    icp_instruction: str,
    marketing_framework: str,
    custom_hook: str,
    include_enrichment: bool = False,
    include_sequence: bool = False,
    free_tier_throttle: bool = True,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    log_callback: Optional[Callable[[str], None]] = None,
    on_rate_limit: Optional[Callable[[int, int, int], None]] = None,
) -> List[Tuple[str, LeadQualificationResult]]:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name=config.GEMINI_MODEL)
    results: List[Tuple[str, LeadQualificationResult]] = []

    for idx, url in enumerate(urls):
        if log_callback:
            log_callback(f"({idx + 1}/{len(urls)}) Scraping {url}...")

        site_copy = scrape_live_company_site(url)
        if site_copy.startswith("Error") or site_copy.startswith("Network Error"):
            if log_callback:
                log_callback(f"({idx + 1}/{len(urls)}) Skipped — scrape failed")
            if progress_callback:
                progress_callback(idx + 1, len(urls))
            continue

        if log_callback:
            log_callback(f"({idx + 1}/{len(urls)}) Qualifying with {config.GEMINI_MODEL}...")

        try:
            result = qualify_lead(
                model, url, site_copy, icp_instruction, marketing_framework,
                custom_hook, include_enrichment, include_sequence, on_rate_limit,
            )
            results.append((url, result))
            if log_callback:
                log_callback(f"({idx + 1}/{len(urls)}) Score: {result.qualification_score}/100")
        except Exception as e:
            if log_callback:
                log_callback(f"({idx + 1}/{len(urls)}) Skipped — {e}")

        if free_tier_throttle and idx < len(urls) - 1:
            time.sleep(12)

        if progress_callback:
            progress_callback(idx + 1, len(urls))

    return results
