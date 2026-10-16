"""CRM routes. Notes and follow-ups live in SQL Server, linked to Shopify customer IDs."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clients.shopify_rest_client import ShopifyRestClient
from app.config import Settings, get_settings
from app.database import get_db
from app.deps import get_shopify_client
from app.models import CRMCustomer, CRMFollowUp, CRMInteraction, ShopifyWebhookEvent, utcnow
from app.schemas import (CRMCustomerOut, FollowUpIn, FollowUpOut, InteractionIn, InteractionOut)
from app.security import require_staff, require_viewer

router = APIRouter(prefix="/api/v1/crm", tags=["crm"])


def _name(c: dict) -> str:
    return f"{c.get('first_name') or ''} {c.get('last_name') or ''}".strip() or "(no name)"


def get_or_create_customer(db: Session, shopify: ShopifyRestClient, shopify_id: int) -> CRMCustomer:
    """Checks the customer exists in Shopify, then keeps a small CRM record for it."""
    record = db.scalar(select(CRMCustomer).where(CRMCustomer.shopify_customer_id == shopify_id))
    if record:
        return record
    shopify_customer = shopify.get_customer(shopify_id)  # raises 404 if missing
    record = CRMCustomer(shopify_customer_id=shopify_id, display_name=_name(shopify_customer), last_synced_at=utcnow())
    db.add(record)
    db.flush()
    return record


@router.get("/dashboard", dependencies=[Depends(require_viewer)])
def dashboard(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    today = date.today()
    open_q = select(func.count()).select_from(CRMFollowUp).where(CRMFollowUp.status == "open")
    events = db.execute(select(ShopifyWebhookEvent.status, func.count()).group_by(ShopifyWebhookEvent.status)).all()
    upcoming = db.scalars(
        select(CRMFollowUp).where(CRMFollowUp.status == "open").order_by(CRMFollowUp.due_date).limit(5)
    ).all()
    return {
        "store_url": settings.public_store_url if settings.shopify_store_domain else None,
        "crm_customers": db.scalar(select(func.count()).select_from(CRMCustomer)),
        "interactions": db.scalar(select(func.count()).select_from(CRMInteraction)),
        "open_follow_ups": db.scalar(open_q),
        "overdue_follow_ups": db.scalar(open_q.where(CRMFollowUp.due_date < today)),
        "webhook_events": {status: n for status, n in events},
        "next_follow_ups": [FollowUpOut.model_validate(f) for f in upcoming],
    }


@router.get("/customers", dependencies=[Depends(require_viewer)])
def list_crm_customers(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    rows = db.scalars(select(CRMCustomer).order_by(CRMCustomer.created_at.desc()).limit(limit)).all()
    return [CRMCustomerOut.model_validate(r) for r in rows]


@router.get("/customers/{customer_id}", dependencies=[Depends(require_viewer)])
def get_crm_customer(customer_id: int, db: Session = Depends(get_db), shopify: ShopifyRestClient = Depends(get_shopify_client)):
    """customer_id is the Shopify customer ID. Live Shopify data + our CRM record (if any)."""
    c = shopify.get_customer(customer_id)
    record = db.scalar(select(CRMCustomer).where(CRMCustomer.shopify_customer_id == customer_id))
    return {
        "shopify": {
            "id": c.get("id"), "name": _name(c), "email": c.get("email"),
            "orders_count": c.get("orders_count"), "total_spent": c.get("total_spent"),
        },
        "crm": CRMCustomerOut.model_validate(record) if record else None,
    }


@router.get("/customers/{customer_id}/interactions", dependencies=[Depends(require_viewer)])
def list_interactions(customer_id: int, db: Session = Depends(get_db)):
    record = db.scalar(select(CRMCustomer).where(CRMCustomer.shopify_customer_id == customer_id))
    if not record:
        return []
    rows = db.scalars(
        select(CRMInteraction).where(CRMInteraction.crm_customer_id == record.id).order_by(CRMInteraction.created_at.desc())
    ).all()
    return [InteractionOut.model_validate(r) for r in rows]


@router.post("/customers/{customer_id}/interactions", response_model=InteractionOut, status_code=201,
              dependencies=[Depends(require_staff)])
def add_interaction(customer_id: int, body: InteractionIn, db: Session = Depends(get_db),
                    shopify: ShopifyRestClient = Depends(get_shopify_client)):
    record = get_or_create_customer(db, shopify, customer_id)
    item = CRMInteraction(crm_customer_id=record.id, **body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/follow-ups", dependencies=[Depends(require_viewer)])
def list_follow_ups(status: str | None = Query(None, pattern="^(open|done|cancelled)$"),
                    shopify_customer_id: int | None = None, db: Session = Depends(get_db)):
    q = select(CRMFollowUp).order_by(CRMFollowUp.due_date)
    if status:
        q = q.where(CRMFollowUp.status == status)
    if shopify_customer_id:
        q = q.join(CRMCustomer).where(CRMCustomer.shopify_customer_id == shopify_customer_id)
    return [FollowUpOut.model_validate(r) for r in db.scalars(q.limit(200)).all()]


@router.post("/follow-ups", response_model=FollowUpOut, status_code=201, dependencies=[Depends(require_staff)])
def add_follow_up(body: FollowUpIn, db: Session = Depends(get_db), shopify: ShopifyRestClient = Depends(get_shopify_client)):
    record = get_or_create_customer(db, shopify, body.shopify_customer_id)
    item = CRMFollowUp(crm_customer_id=record.id, title=body.title, due_date=body.due_date, assigned_to=body.assigned_to)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
