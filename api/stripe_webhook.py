"""Stripe webhook handler — sync subscription status to user plans."""

import os

from fastapi import FastAPI, Header, HTTPException, Request

import config
from database import get_user_by_email, update_user_plan

webhook_app = FastAPI()


@webhook_app.post("/webhooks/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None, alias="Stripe-Signature")):
    if not config.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    try:
        import stripe
    except ImportError:
        raise HTTPException(status_code=500, detail="Stripe not installed")

    stripe.api_key = config.STRIPE_SECRET_KEY
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, config.STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = int(session.get("metadata", {}).get("user_id", 0))
        plan = session.get("metadata", {}).get("plan", "pro")
        customer_id = session.get("customer", "")
        subscription_id = session.get("subscription", "")
        if user_id:
            update_user_plan(user_id, plan, customer_id, subscription_id)

    elif event["type"] == "customer.subscription.deleted":
        sub = event["data"]["object"]
        customer_id = sub.get("customer", "")
        # Downgrade handled via billing portal — lookup by stripe_customer_id if needed
        pass

    return {"received": True}
