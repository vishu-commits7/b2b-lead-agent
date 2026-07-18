"""CRM export formats for HubSpot, Salesforce, and Pipedrive."""

import csv
import io
import json
from typing import List, Tuple

from models.schemas import LeadQualificationResult


def export_standard_csv(processed: List[Tuple[str, LeadQualificationResult]], selected: dict) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "URL", "Company", "Industry", "Business Model", "Employees", "Score", "Status",
        "Pain Points", "Buying Signals", "Contact Name", "Contact Title", "Email Pattern",
        "Subject", "Email Body", "LinkedIn Note", "LinkedIn URL", "Twitter URL",
    ])
    for url, lead in processed:
        if not selected.get(url, True):
            continue
        contact = lead.primary_contact
        writer.writerow([
            url, lead.company.name, lead.company.industry, lead.company.business_model,
            lead.company.employee_estimate, lead.qualification_score,
            "Qualified" if lead.is_qualified else "Disqualified",
            "; ".join(lead.pain_points), "; ".join(lead.buying_signals),
            contact.full_name if contact else "",
            contact.title if contact else "",
            contact.email_pattern if contact else "",
            lead.outreach_sequence.subject_line,
            lead.outreach_sequence.email_body,
            lead.outreach_sequence.linkedin_note,
            lead.company.linkedin_url, lead.company.twitter_url,
        ])
    return output.getvalue()


def export_hubspot_csv(processed: List[Tuple[str, LeadQualificationResult]], selected: dict) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Company name", "Company Domain Name", "Industry", "Number of Employees",
        "Lead Status", "Lead Score", "Notes", "LinkedIn Company Page",
    ])
    for url, lead in processed:
        if not selected.get(url, True):
            continue
        writer.writerow([
            lead.company.name, url, lead.company.industry,
            lead.company.employee_estimate,
            "OPEN" if lead.is_qualified else "UNQUALIFIED",
            lead.qualification_score,
            lead.reasoning[:500],
            lead.company.linkedin_url,
        ])
    return output.getvalue()


def export_salesforce_csv(processed: List[Tuple[str, LeadQualificationResult]], selected: dict) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Company", "Website", "Industry", "Rating", "Description",
        "LeadSource", "Status",
    ])
    for url, lead in processed:
        if not selected.get(url, True):
            continue
        writer.writerow([
            lead.company.name, f"https://{url}", lead.company.industry,
            lead.qualification_score,
            lead.reasoning[:32000],
            "LeadAgent.io", "Open - Not Contacted" if lead.is_qualified else "Unqualified",
        ])
    return output.getvalue()


def export_json(processed: List[Tuple[str, LeadQualificationResult]]) -> str:
    payload = []
    for url, lead in processed:
        payload.append({"url": url, **lead.model_dump()})
    return json.dumps(payload, indent=2)
