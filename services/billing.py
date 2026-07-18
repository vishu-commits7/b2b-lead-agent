"""Stripe billing integration for subscription plans."""

from typing import Optional, Tuple

import config

try:
    import stripe
except ImportError:
    stripe = None


def stripe_configured() -> bool:
    return bool(stripe and config.STRIPE_SECRET_KEY)


def create_checkout_session(user_id: int, user_email: str, plan: str) -> Tuple[bool, str, Optional[str]]:
    if not stripe_configured():
        return False, "Stripe is not configured. Set STRIPE_SECRET_KEY and price IDs in .env.", None

    price_map = {
        "pro": config.STRIPE_PRICE_PRO,
        "enterprise": config.STRIPE_PRICE_ENTERPRISE,
    }
    price_id = price_map.get(plan)
    if not price_id:
        return False, f"No Stripe price configured for plan '{plan}'.", None

    stripe.api_key = config.STRIPE_SECRET_KEY
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer_email=user_email,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{config.APP_URL}/?upgrade=success&plan={plan}",
            cancel_url=f"{config.APP_URL}/?upgrade=cancelled",
            metadata={"user_id": str(user_id), "plan": plan},
        )
        return True, "Redirecting to checkout...", session.url
    except Exception as e:
        return False, f"Checkout failed: {e}", None


def create_billing_portal(customer_id: str) -> Tuple[bool, str, Optional[str]]:
    if not stripe_configured() or not customer_id:
        return False, "Billing portal unavailable.", None
    stripe.api_key = config.STRIPE_SECRET_KEY
    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=config.APP_URL,
        )
        return True, "Opening billing portal...", session.url
    except Exception as e:
        return False, f"Portal error: {e}", None
