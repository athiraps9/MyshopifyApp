import os

# Fake settings, set before the app is imported. No real Shopify store is used in tests.
os.environ.update(
    SHOPIFY_STORE_DOMAIN="test-shop.myshopify.com",
    SHOPIFY_ADMIN_ACCESS_TOKEN="shpat_test",
    SHOPIFY_API_VERSION="2026-04",
    SHOPIFY_WEBHOOK_SECRET="whsec_test",
    DATABASE_URL="",
    SECRET_KEY="test-secret",
    CRM_VIEWER_TOKEN="viewer-token",
    CRM_STAFF_TOKEN="staff-token",
)

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.clients.shopify_rest_client import ShopifyRestClient
from app.config import get_settings
from app.database import Base, get_db
from app.deps import get_shopify_client
from app.main import app

FAKE_SHOPIFY = {
    "products.json": {"products": [{"id": 1, "title": "Vitamin C", "handle": "vitamin-c", "product_type": "Vitamins",
                                    "tags": "immune, daily", "variants": [{"id": 11, "price": "9.99", "title": "60 tabs"}]}]},
    "products/1.json": {"product": {"id": 1, "title": "Vitamin C", "handle": "vitamin-c", "body_html": "<p>Daily <b>support</b></p>",
                                    "variants": [{"id": 11, "price": "9.99", "title": "60 tabs", "sku": "VC60"}]}},
    "customers/5.json": {"customer": {"id": 5, "first_name": "Asha", "last_name": "N", "email": "a@example.com"}},
    "orders.json": {"orders": [{"id": 9, "name": "#1001", "financial_status": "paid", "line_items": [{"quantity": 2}]}]},
}


def fake_shopify_handler(request: httpx.Request) -> httpx.Response:
    key = request.url.path.split("/2026-04/")[-1]
    if key in FAKE_SHOPIFY:
        return httpx.Response(200, json=FAKE_SHOPIFY[key])
    return httpx.Response(404, json={"errors": "Not Found"})


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def db_override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    def shopify_override():
        yield ShopifyRestClient(get_settings(), transport=httpx.MockTransport(fake_shopify_handler), sleep=lambda s: None)

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_shopify_client] = shopify_override
    yield TestClient(app)
    app.dependency_overrides.clear()


STAFF = {"Authorization": "Bearer staff-token"}
VIEWER = {"Authorization": "Bearer viewer-token"}
