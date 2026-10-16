"""Shopify webhook receiver: verify HMAC on the raw body, dedupe by event id, record status."""
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import CRMCustomer, ShopifyWebhookEvent, utcnow
from app.security import verify_shopify_hmac

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


def _process(db: Session, topic: str, payload: dict) -> None:
    # Only refresh the cached name of customers we already track in the CRM.
    if topic in ("customers/create", "customers/update") and payload.get("id"):
        record = db.scalar(select(CRMCustomer).where(CRMCustomer.shopify_customer_id == payload["id"]))
        if record:
            name = f"{payload.get('first_name') or ''} {payload.get('last_name') or ''}".strip()
            record.display_name = name or record.display_name
            record.last_synced_at = utcnow()
    # Other topics (orders/*, products/*) are only recorded; Shopify remains the source of truth.


@router.post("/shopify")
async def shopify_webhook(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    if not settings.shopify_webhook_secret:
        raise HTTPException(503, "Webhook secret is not configured.")
    raw = await request.body()  # raw bytes: the signature is computed over exactly these
    if not verify_shopify_hmac(raw, request.headers.get("X-Shopify-Hmac-Sha256", ""), settings.shopify_webhook_secret):
        raise HTTPException(401, "Invalid webhook signature.")

    event_id = request.headers.get("X-Shopify-Event-Id") or request.headers.get("X-Shopify-Webhook-Id")
    if not event_id:
        raise HTTPException(400, "Missing event id.")
    topic = request.headers.get("X-Shopify-Topic", "unknown")

    event = ShopifyWebhookEvent(event_id=event_id, topic=topic, shop_domain=request.headers.get("X-Shopify-Shop-Domain"))
    db.add(event)
    try:
        db.commit()
    except IntegrityError:  # seen before
        db.rollback()
        event = db.scalar(select(ShopifyWebhookEvent).where(ShopifyWebhookEvent.event_id == event_id))
        if event.status == "processed":
            return {"status": "duplicate"}

    try:
        _process(db, topic, json.loads(raw or b"{}"))
        event.status, event.error = "processed", None
        event.processed_at = utcnow()
        db.commit()
        return {"status": "processed"}
    except Exception as exc:
        db.rollback()
        event = db.get(ShopifyWebhookEvent, event.id)
        event.status, event.error = "failed", type(exc).__name__
        db.commit()
        raise HTTPException(500, "Webhook processing failed.")
