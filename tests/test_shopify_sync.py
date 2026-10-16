from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models import (
    ShopifyCustomerSnapshot,
    ShopifyOrderLineItemSnapshot,
    ShopifyOrderSnapshot,
    ShopifyProductSnapshot,
    ShopifyProductVariantSnapshot,
)
from app.shopify_sync import sync_shopify_data


class FakeShopify:
    def list_products(self, **kwargs):
        if kwargs["status"] != "active":
            return {"items": [], "next_page_info": None}
        return {
            "items": [{
                "id": 101,
                "title": "Vitamin D3",
                "handle": "vitamin-d3",
                "status": "active",
                "body_html": "Description",
                "image": {"src": "https://example.test/vitamin-d3.jpg"},
                "variants": [{"id": 1001, "title": "60 tablets", "sku": "D3-60", "price": "12.50", "inventory_quantity": 8}],
            }],
            "next_page_info": None,
        }

    def list_customers(self, **kwargs):
        return {
            "items": [{
                "id": 201,
                "first_name": "Asha",
                "last_name": "N",
                "email": "asha@example.test",
                "orders_count": 2,
                "total_spent": "25.00",
            }],
            "next_page_info": None,
        }

    def list_orders(self, **kwargs):
        return {
            "items": [{
                "id": 301,
                "name": "#1001",
                "customer": {"id": 201},
                "financial_status": "paid",
                "fulfillment_status": "fulfilled",
                "total_price": "25.00",
                "currency": "USD",
                "line_items": [{"id": 3001, "title": "Vitamin D3", "sku": "D3-60", "quantity": 2, "price": "12.50"}],
            }],
            "next_page_info": None,
        }


def test_sync_persists_and_upserts_shopify_snapshots():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    shopify = FakeShopify()

    with Session(engine) as db:
        assert sync_shopify_data(db, shopify) == {"products": 1, "customers": 1, "orders": 1}
        assert sync_shopify_data(db, shopify) == {"products": 1, "customers": 1, "orders": 1}

        product = db.get(ShopifyProductSnapshot, 101)
        variant = db.get(ShopifyProductVariantSnapshot, 1001)
        customer = db.get(ShopifyCustomerSnapshot, 201)
        order = db.get(ShopifyOrderSnapshot, 301)
        line_item = db.get(ShopifyOrderLineItemSnapshot, 3001)

        assert product.title == "Vitamin D3" and product.image_url.endswith("vitamin-d3.jpg")
        assert variant.sku == "D3-60" and float(variant.price) == 12.5
        assert customer.email == "asha@example.test"
        assert order.customer_id == 201 and order.item_count == 2
        assert line_item.quantity == 2 and float(line_item.price) == 12.5
        assert db.scalar(select(func.count()).select_from(ShopifyProductSnapshot)) == 1
        assert db.scalar(select(func.count()).select_from(ShopifyOrderSnapshot)) == 1

    engine.dispose()