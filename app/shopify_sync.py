"""Copy minimal Shopify product, customer, and order snapshots into SQL Server."""
from collections.abc import Callable, Iterator

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.clients.shopify_rest_client import ShopifyRestClient
from app.models import (
    ShopifyCustomerSnapshot,
    ShopifyOrderLineItemSnapshot,
    ShopifyOrderSnapshot,
    ShopifyProductSnapshot,
    ShopifyProductVariantSnapshot,
    utcnow,
)


def _pages(fetch: Callable[..., dict]) -> Iterator[list[dict]]:
    cursor = None
    seen_cursors = set()
    while True:
        page = fetch(page_info=cursor, limit=250)
        yield page["items"]
        cursor = page["next_page_info"]
        if not cursor:
            return
        if cursor in seen_cursors:
            raise RuntimeError("Shopify returned a repeated pagination cursor.")
        seen_cursors.add(cursor)


def _sync_products(db: Session, shopify: ShopifyRestClient) -> int:
    count = 0
    for status in ("active", "draft", "archived"):
        for products in _pages(lambda **kwargs: shopify.list_products(status=status, **kwargs)):
            for data in products:
                product_id = data.get("id")
                if not product_id:
                    continue
                product_id = int(product_id)
                product = db.get(ShopifyProductSnapshot, product_id)
                if product is None:
                    product = ShopifyProductSnapshot(shopify_product_id=product_id, title=data.get("title") or "")
                    db.add(product)
                image = data.get("image") or {}
                product.title = data.get("title") or ""
                product.handle = data.get("handle")
                product.vendor = data.get("vendor")
                product.product_type = data.get("product_type")
                product.status = data.get("status") or status
                product.description = data.get("body_html")
                product.tags = data.get("tags")
                product.image_url = image.get("src")
                product.updated_at = data.get("updated_at")
                product.synced_at = utcnow()
                db.flush()

                variants = data.get("variants") or []
                variant_ids = {int(item["id"]) for item in variants if item.get("id")}
                existing = {
                    row.shopify_variant_id: row
                    for row in db.scalars(
                        select(ShopifyProductVariantSnapshot).where(
                            ShopifyProductVariantSnapshot.shopify_product_id == product_id
                        )
                    ).all()
                }
                for variant_id, row in existing.items():
                    if variant_id not in variant_ids:
                        db.delete(row)
                for item in variants:
                    if not item.get("id"):
                        continue
                    variant_id = int(item["id"])
                    row = existing.get(variant_id)
                    if row is None:
                        row = ShopifyProductVariantSnapshot(
                            shopify_variant_id=variant_id, shopify_product_id=product_id
                        )
                        db.add(row)
                    row.title = item.get("title")
                    row.sku = item.get("sku")
                    row.price = item.get("price")
                    row.inventory_quantity = item.get("inventory_quantity")
                count += 1
            db.commit()
    return count


def _sync_customers(db: Session, shopify: ShopifyRestClient) -> int:
    count = 0
    for customers in _pages(shopify.list_customers):
        for data in customers:
            customer_id = data.get("id")
            if not customer_id:
                continue
            customer_id = int(customer_id)
            row = db.get(ShopifyCustomerSnapshot, customer_id)
            if row is None:
                row = ShopifyCustomerSnapshot(shopify_customer_id=customer_id)
                db.add(row)
            row.first_name = data.get("first_name")
            row.last_name = data.get("last_name")
            row.email = data.get("email")
            row.orders_count = data.get("orders_count")
            row.total_spent = data.get("total_spent")
            row.created_at = data.get("created_at")
            row.updated_at = data.get("updated_at")
            row.synced_at = utcnow()
            count += 1
        db.commit()
    return count


def _sync_orders(db: Session, shopify: ShopifyRestClient) -> int:
    count = 0
    for orders in _pages(lambda **kwargs: shopify.list_orders(status="any", **kwargs)):
        for data in orders:
            order_id = data.get("id")
            if not order_id:
                continue
            order_id = int(order_id)
            row = db.get(ShopifyOrderSnapshot, order_id)
            if row is None:
                row = ShopifyOrderSnapshot(shopify_order_id=order_id)
                db.add(row)
            customer = data.get("customer") or {}
            line_items = data.get("line_items") or []
            row.name = data.get("name")
            row.customer_id = customer.get("id")
            row.created_at = data.get("created_at")
            row.updated_at = data.get("updated_at")
            row.financial_status = data.get("financial_status")
            row.fulfillment_status = data.get("fulfillment_status")
            row.total_price = data.get("total_price")
            row.currency = data.get("currency")
            row.item_count = sum(item.get("quantity", 0) for item in line_items)
            row.synced_at = utcnow()
            db.flush()

            item_ids = {int(item["id"]) for item in line_items if item.get("id")}
            existing = {
                item.shopify_line_item_id: item
                for item in db.scalars(
                    select(ShopifyOrderLineItemSnapshot).where(
                        ShopifyOrderLineItemSnapshot.shopify_order_id == order_id
                    )
                ).all()
            }
            for item_id, old_item in existing.items():
                if item_id not in item_ids:
                    db.delete(old_item)
            for item in line_items:
                if not item.get("id"):
                    continue
                item_id = int(item["id"])
                saved_item = existing.get(item_id)
                if saved_item is None:
                    saved_item = ShopifyOrderLineItemSnapshot(
                        shopify_line_item_id=item_id,
                        shopify_order_id=order_id,
                        quantity=0,
                    )
                    db.add(saved_item)
                saved_item.title = item.get("title")
                saved_item.sku = item.get("sku")
                saved_item.quantity = item.get("quantity", 0)
                saved_item.price = item.get("price")
            count += 1
        db.commit()
    return count


def sync_shopify_data(db: Session, shopify: ShopifyRestClient) -> dict[str, int]:
    """Upsert all API-accessible snapshots; addresses and payment data are omitted."""
    return {
        "products": _sync_products(db, shopify),
        "customers": _sync_customers(db, shopify),
        "orders": _sync_orders(db, shopify),
    }