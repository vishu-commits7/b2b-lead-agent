"""
LeadAgent.io — Enterprise configuration
Pricing tiers, plan limits, and AI system instructions.
"""

import os

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

ADMIN_EMAILS = [
    e.strip().lower()
    for e in os.environ.get("ADMIN_EMAILS", "").split(",")
    if e.strip()
]

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_PRO = os.environ.get("STRIPE_PRICE_PRO", "")
STRIPE_PRICE_ENTERPRISE = os.environ.get("STRIPE_PRICE_ENTERPRISE", "")

APP_URL = os.environ.get("APP_URL", "http://localhost:8501")

PLANS = {
    "free": {
        "name": "Starter",
        "price_monthly": 0,
        "price_annual": 0,
        "runs_per_month": 5,
        "leads_per_run": 5,
        "api_access": False,
        "email_sequences": False,
        "contact_enrichment": False,
        "crm_export": True,
        "priority_support": False,
        "white_label": False,
        "team_seats": 1,
    },
    "pro": {
        "name": "Professional",
        "price_monthly": 497,
        "price_annual": 4970,
        "runs_per_month": 100,
        "leads_per_run": 20,
        "api_access": True,
        "email_sequences": True,
        "contact_enrichment": True,
        "crm_export": True,
        "priority_support": True,
        "white_label": False,
        "team_seats": 3,
    },
    "enterprise": {
        "name": "Enterprise",
        "price_monthly": 2497,
        "price_annual": 24970,
        "runs_per_month": -1,
        "leads_per_run": 50,
        "api_access": True,
        "email_sequences": True,
        "contact_enrichment": True,
        "crm_export": True,
        "priority_support": True,
        "white_label": True,
        "team_seats": 25,
    },
}

DEFAULT_ICP = {
    "target_industries": ["SaaS", "Fintech", "Healthtech", "E-commerce", "AI/ML Startups"],
    "company_sizes": ["10-50 employees", "50-200 employees"],
    "key_decision_makers": ["CEO", "CTO", "Founder", "VP of Sales", "Head of Growth"],
    "geography": ["North America", "Europe", "APAC"],
}

SYSTEM_INSTRUCTIONS = """
You are LeadAgent.io — an enterprise B2B lead intelligence agent used by revenue teams
at high-growth companies. Your job is to analyze company websites, score ICP fit with
evidence, identify decision makers, surface buying signals, and craft outreach that
converts.

Rules:
1. Score 0-100 with explicit reasoning tied to ICP criteria — never inflate scores.
2. Identify 2-4 concrete pain points from website copy, not generic assumptions.
3. Flag buying signals: hiring, funding mentions, product launches, tech migrations.
4. Outreach must reference something specific from their site — no template spam.
5. Contact enrichment: infer the most likely decision maker title and email pattern.
6. Email sequences: 3 touches — value-first open, social proof follow-up, polite breakup.
7. All output must conform exactly to the requested JSON schema.
"""

MARKETING_FRAMEWORKS = [
    "PAS (Problem, Agitation, Solution)",
    "AIDA (Attention, Interest, Desire, Action)",
    "Direct Value Hook",
    "Soft Curiosity Drop",
    "Challenger Sale Insight",
    "SPIN Selling (Situation-Problem-Implication-Need)",
]
