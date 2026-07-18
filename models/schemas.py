"""Core data models for LeadAgent.io enterprise pipeline."""

from typing import List, Optional

from pydantic import BaseModel, Field


class LeadCompanyInfo(BaseModel):
    model_config = {"extra": "ignore"}
    name: str = Field(description="Company name")
    industry: str = Field(description="Primary industry or sector")
    business_model: str = Field(description="How the company makes money")
    linkedin_url: str = Field(description="Company LinkedIn URL or empty string")
    twitter_url: str = Field(description="Company Twitter/X URL or empty string")
    employee_estimate: str = Field(
        default="Unknown",
        description="Estimated company size band, e.g. '11-50', '51-200'",
    )
    tech_stack_signals: List[str] = Field(
        default_factory=list,
        description="Technologies or platforms inferred from the website",
    )


class ContactEnrichment(BaseModel):
    model_config = {"extra": "ignore"}
    full_name: str = Field(description="Likely decision maker full name")
    title: str = Field(description="Job title, e.g. VP of Sales, Founder")
    email_pattern: str = Field(
        description="Best-guess email pattern, e.g. first.last@company.com"
    )
    linkedin_search_query: str = Field(
        description="LinkedIn search string to find this person"
    )
    confidence: int = Field(description="Confidence 0-100 that this contact is reachable")


class OutreachDraft(BaseModel):
    subject_line: str = Field(description="Email subject line; empty if not qualified")
    email_body: str = Field(description="Cold email under 120 words; empty if not qualified")
    linkedin_note: str = Field(description="LinkedIn note under 300 chars; empty if not qualified")
    chosen_framework: str = Field(description="Copywriting framework used; 'N/A' if not qualified")


class EmailSequenceTouch(BaseModel):
    touch_number: int = Field(description="1, 2, or 3 in the sequence")
    delay_days: int = Field(description="Days after previous touch")
    subject_line: str
    email_body: str
    purpose: str = Field(description="e.g. 'Initial outreach', 'Value add follow-up', 'Breakup email'")


class EmailSequence(BaseModel):
    touches: List[EmailSequenceTouch] = Field(default_factory=list)


class LeadQualificationResult(BaseModel):
    model_config = {"extra": "ignore"}
    company: LeadCompanyInfo
    qualification_score: int = Field(description="Fit score 0-100 against ICP")
    is_qualified: bool
    reasoning: str
    pain_points: List[str] = Field(default_factory=list, description="Identified business pain points")
    buying_signals: List[str] = Field(default_factory=list, description="Signals they may be in-market")
    outreach_sequence: OutreachDraft
    primary_contact: Optional[ContactEnrichment] = None
    email_sequence: Optional[EmailSequence] = None
