"""Products, customers and orders read from Shopify (REST). Nothing is copied into SQL Server."""
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from app.clients.shopify_rest_client import ShopifyRestClient
from app.config import Settings, get_settings
from app.deps import get_shopify_client
from app.security import require_viewer

router = APIRouter(prefix="/api/v1", tags=["shopify"])


def _text(html: str | None) -> str:
    return re.sub(r"<[^>]+>", " ", html or "").replace("&nbsp;", " ").strip()


def _product(p: dict, settings: Settings, detail=False) -> dict:
    images = p.get("images") or []
    out = {
        "id": p["id"],
        "title": p.get("title"),
        "vendor": p.get("vendor"),
        "product_type": p.get("product_type"),
        "status": p.get("status"),
        "tags": [t.strip() for t in (p.get("tags") or "").split(",") if t.strip()],
        "image": (p.get("image") or (images[0] if images else None) or {}).get("src"),
        "price_from": min((float(v["price"]) for v in p.get("variants", []) if v.get("price")), default=None),
        "store_url": f"{settings.public_store_url}/products/{p.get('handle')}",
    }
    if detail:
        out["description"] = _text(p.get("body_html"))
        out["variants"] = [
            {
                "id": v["id"],
                "title": v.get("title"),
                "sku": v.get("sku"),
                "price": v.get("price"),
                "inventory_quantity": v.get("inventory_quantity"),  # may be absent
            }
            for v in p.get("variants", [])
        ]
    return out


@router.get("/products")
def list_products(
    page_info: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    category: str | None = Query(None, max_length=100),
    shopify: ShopifyRestClient = Depends(get_shopify_client),
    settings: Settings = Depends(get_settings),
):
    page = shopify.list_products(page_info, limit, title=search, product_type=category)
    page["items"] = [_product(p, settings) for p in page["items"]]
    return page


@router.get("/products/{product_id}")
def get_product(
    product_id: int,
    shopify: ShopifyRestClient = Depends(get_shopify_client),
    settings: Settings = Depends(get_settings),
):
    return _product(shopify.get_product(product_id), settings, detail=True)


@router.get("/customers", dependencies=[Depends(require_viewer)])
def list_customers(
    page_info: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    shopify: ShopifyRestClient = Depends(get_shopify_client),
):
    page = shopify.list_customers(page_info, limit, query=search)
    page["items"] = [
        {
            "id": c["id"],
            "name": f"{c.get('first_name') or ''} {c.get('last_name') or ''}".strip() or "(no name)",
            "email": c.get("email"),
            "orders_count": c.get("orders_count"),
            "total_spent": c.get("total_spent"),
            "created_at": c.get("created_at"),
        }
        for c in page["items"]
    ]
    return page


@router.get("/orders")
def list_orders(
    page_info: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    status: str = Query("any", pattern="^(any|open|closed|cancelled)$"),
    financial_status: str | None = Query(None, pattern="^[a-z_]+$"),
    fulfillment_status: str | None = Query(None, pattern="^[a-z_]+$"),
    shopify: ShopifyRestClient = Depends(get_shopify_client),
):
    page = shopify.list_orders(page_info, limit, status, financial_status, fulfillment_status)
    page["items"] = [
        {
            "id": o["id"],
            "name": o.get("name"),
            "created_at": o.get("created_at"),
            "financial_status": o.get("financial_status"),
            "fulfillment_status": o.get("fulfillment_status") or "unfulfilled",
            "total_price": o.get("total_price"),
            "currency": o.get("currency"),
            "customer_id": (o.get("customer") or {}).get("id"),
            "item_count": sum(i.get("quantity", 0) for i in o.get("line_items", [])),
        }
        for o in page["items"]
    ]
    return page
