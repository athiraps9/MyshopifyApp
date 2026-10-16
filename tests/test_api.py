import hashlib
import hmac
from time import time
from urllib.parse import parse_qs, urlencode, urlparse

from app.config import Settings, get_settings
from app.main import app
from app.routers import shopify_oauth
from tests.conftest import STAFF, VIEWER


OAUTH_SETTINGS = Settings(
    shopify_store_domain="test-shop.myshopify.com",
    shopify_admin_access_token="",
    shopify_api_version="2026-10",
    shopify_api_key="test-client-id",
    shopify_api_secret="test-client-secret",
    shopify_redirect_uri="https://example.ngrok-free.app/api/v1/shopify/callback",
)


def signed_query(params):
    message = "&".join(f"{key}={value}" for key, value in sorted(params.items()))
    signature = hmac.new(OAUTH_SETTINGS.shopify_api_secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return urlencode({**params, "hmac": signature})


def test_shopify_install_requires_valid_hmac(client):
    app.dependency_overrides[get_settings] = lambda: OAUTH_SETTINGS
    params = {"shop": OAUTH_SETTINGS.shopify_store_domain, "timestamp": str(int(time()))}

    response = client.get("/new-install?" + urlencode(params))

    assert response.status_code == 401


def test_shopify_install_redirects_with_state_cookie(client):
    app.dependency_overrides[get_settings] = lambda: OAUTH_SETTINGS
    params = {"shop": OAUTH_SETTINGS.shopify_store_domain, "timestamp": str(int(time()))}

    response = client.get("/new-install?" + signed_query(params), follow_redirects=False)

    assert response.status_code == 302
    authorization = urlparse(response.headers["location"])
    query = parse_qs(authorization.query)
    assert authorization.netloc == OAUTH_SETTINGS.shopify_store_domain
    assert query["client_id"] == [OAUTH_SETTINGS.shopify_api_key]
    assert query["redirect_uri"] == [OAUTH_SETTINGS.shopify_redirect_uri]
    assert response.cookies[shopify_oauth.STATE_COOKIE] == query["state"][0]


def test_shopify_callback_validates_state(client):
    app.dependency_overrides[get_settings] = lambda: OAUTH_SETTINGS
    params = {
        "code": "authorization-code",
        "shop": OAUTH_SETTINGS.shopify_store_domain,
        "state": "returned-state",
        "timestamp": str(int(time())),
    }

    response = client.get(
        "/api/v1/shopify/callback?" + signed_query(params),
        headers={"Cookie": f"{shopify_oauth.STATE_COOKIE}=expected-state"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired OAuth state."


def test_shopify_callback_exchanges_code_and_saves_token(client, monkeypatch):
    app.dependency_overrides[get_settings] = lambda: OAUTH_SETTINGS
    saved = {}

    async def exchange(code, settings):
        saved["code"] = code
        return "shpat_new_token"

    monkeypatch.setattr(shopify_oauth, "_exchange_code", exchange)
    monkeypatch.setattr(shopify_oauth, "_save_access_token", lambda token: saved.update(token=token))
    params = {
        "code": "authorization-code",
        "shop": OAUTH_SETTINGS.shopify_store_domain,
        "state": "matching-state",
        "timestamp": str(int(time())),
    }

    response = client.get(
        "/api/v1/shopify/callback?" + signed_query(params),
        headers={"Cookie": f"{shopify_oauth.STATE_COOKIE}=matching-state"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert saved == {"code": "authorization-code", "token": "shpat_new_token"}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "shopify_configured": True}


def test_products_list_and_detail(client):
    items = client.get("/api/v1/products").json()["items"]
    assert items[0]["title"] == "Vitamin C" and items[0]["price_from"] == 9.99
    assert items[0]["store_url"].endswith("/products/vitamin-c")
    detail = client.get("/api/v1/products/1").json()
    assert "<" not in detail["description"] and detail["variants"][0]["sku"] == "VC60"


def test_missing_product_is_404(client):
    assert client.get("/api/v1/products/999").status_code == 404


def test_orders_do_not_require_crm_token(client):
    orders = client.get("/api/v1/orders").json()["items"]
    assert orders[0]["item_count"] == 2 and "email" not in orders[0]


def test_viewer_cannot_write_but_staff_can(client):
    body = {"channel": "phone", "summary": "Asked about refill timing"}
    url = "/api/v1/crm/customers/5/interactions"
    assert client.post(url, json=body, headers=VIEWER).status_code == 403
    assert client.post(url, json=body).status_code == 401
    assert client.post(url, json=body, headers=STAFF).status_code == 201
    assert client.get(url, headers=VIEWER).json()[0]["summary"] == "Asked about refill timing"


def test_follow_up_and_dashboard(client):
    r = client.post("/api/v1/crm/follow-ups", headers=STAFF,
                    json={"shopify_customer_id": 5, "title": "Call back", "due_date": "2020-01-01"})
    assert r.status_code == 201
    assert len(client.get("/api/v1/crm/follow-ups?status=open", headers=VIEWER).json()) == 1
    dash = client.get("/api/v1/crm/dashboard", headers=VIEWER).json()
    assert dash["open_follow_ups"] == 1 and dash["overdue_follow_ups"] == 1 and dash["crm_customers"] == 1


def test_unknown_shopify_customer_is_rejected(client):
    r = client.post("/api/v1/crm/customers/404/interactions", headers=STAFF, json={"channel": "chat", "summary": "x"})
    assert r.status_code == 404


def test_validation(client):
    r = client.post("/api/v1/crm/follow-ups", headers=STAFF, json={"shopify_customer_id": 5, "title": "", "due_date": "bad"})
    assert r.status_code == 422
