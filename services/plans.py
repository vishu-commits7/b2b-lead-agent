"""Plan limits and usage enforcement."""

from typing import Tuple

import config
from database import count_usage_this_month, log_usage_event


def get_plan_limits(plan: str) -> dict:
    return config.PLANS.get(plan, config.PLANS["free"])


def check_can_run_pipeline(user_id: int, plan: str, num_leads: int) -> Tuple[bool, str]:
    limits = get_plan_limits(plan)
    max_runs = limits["runs_per_month"]
    max_leads = limits["leads_per_run"]

    if max_runs >= 0:
        used = count_usage_this_month(user_id, "pipeline_run")
        if used >= max_runs:
            return False, f"Monthly run limit reached ({max_runs}). Upgrade to Pro for more."

    if num_leads > max_leads:
        return False, f"Your {limits['name']} plan allows up to {max_leads} leads per run."

    return True, ""


def feature_enabled(plan: str, feature: str) -> bool:
    limits = get_plan_limits(plan)
    return bool(limits.get(feature, False))


def record_pipeline_run(user_id: int, metadata: dict):
    log_usage_event(user_id, "pipeline_run", metadata)


def record_email_sent(user_id: int, lead_id: int):
    log_usage_event(user_id, "email_sent", {"lead_id": lead_id})
