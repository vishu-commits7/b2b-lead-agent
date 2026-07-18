"""
LeadAgent.io REST API — Enterprise programmatic access.
Run: uvicorn api.server:app --host 0.0.0.0 --port 8000
"""

import os
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

import config
from database import (
    create_run,
    finalize_run,
    get_leads_for_run,
    get_runs_for_user,
    init_db,
    save_lead,
    verify_api_key,
)
from services.pipeline import discover_company_urls, run_pipeline
from services.plans import check_can_run_pipeline, feature_enabled, record_pipeline_run

init_db()

app = FastAPI(
    title="LeadAgent.io API",
    description="Enterprise B2B lead discovery and qualification API",
    version="3.0.0",
)


class RunRequest(BaseModel):
    niche: str = Field(example="B2B SaaS companies")
    city: str = Field(example="San Francisco")
    icp: str = Field(default="", example="10-100 employees, uses Salesforce")
    num_leads: int = Field(default=5, ge=1, le=50)
    marketing_framework: str = Field(default="PAS (Problem, Agitation, Solution)")


class RunResponse(BaseModel):
    run_id: int
    status: str
    leads_found: int
    qualified: int


def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    raw_key = authorization.replace("Bearer ", "").strip()
    user = verify_api_key(raw_key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")
    if not feature_enabled(user["plan"], "api_access"):
        raise HTTPException(status_code=403, detail="API access requires Pro or Enterprise plan")
    return user


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": "LeadAgent.io", "version": "3.0.0"}


@app.post("/api/v1/runs", response_model=RunResponse)
def create_pipeline_run(body: RunRequest, user=Depends(get_current_user)):
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    serper_key = os.environ.get("SERPER_API_KEY", "")
    if not gemini_key or not serper_key:
        raise HTTPException(status_code=500, detail="Server missing GEMINI_API_KEY or SERPER_API_KEY")

    allowed, msg = check_can_run_pipeline(user["user_id"], user["plan"], body.num_leads)
    if not allowed:
        raise HTTPException(status_code=429, detail=msg)

    query = f"{body.niche} in {body.city}"
    urls = discover_company_urls(query, serper_key, num_results=body.num_leads)
    if not urls:
        raise HTTPException(status_code=404, detail="No companies found for this query")

    run_id = create_run(user["user_id"], body.niche, body.city, body.icp)
    include_enrichment = feature_enabled(user["plan"], "contact_enrichment")
    include_sequence = feature_enabled(user["plan"], "email_sequences")

    processed = run_pipeline(
        urls=urls,
        api_key=gemini_key,
        icp_instruction=body.icp,
        marketing_framework=body.marketing_framework,
        custom_hook="",
        include_enrichment=include_enrichment,
        include_sequence=include_sequence,
        free_tier_throttle=True,
    )

    for url, lead in processed:
        save_lead(user["user_id"], run_id, url, lead)

    qualified = sum(1 for _, l in processed if l.is_qualified)
    avg = sum(l.qualification_score for _, l in processed) / len(processed) if processed else 0
    finalize_run(run_id, len(processed), qualified, avg)
    record_pipeline_run(user["user_id"], {"run_id": run_id, "source": "api"})

    return RunResponse(run_id=run_id, status="completed", leads_found=len(processed), qualified=qualified)


@app.get("/api/v1/runs")
def list_runs(user=Depends(get_current_user)):
    runs = get_runs_for_user(user["user_id"], limit=50)
    return {"runs": runs}


@app.get("/api/v1/runs/{run_id}/leads")
def get_run_leads(run_id: int, user=Depends(get_current_user)):
    leads = get_leads_for_run(run_id, user["user_id"])
    if not leads:
        raise HTTPException(status_code=404, detail="Run not found or no leads")
    return {"run_id": run_id, "leads": leads}
