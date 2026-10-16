import httpx
import pytest

from app.clients.shopify_rest_client import ShopifyError, ShopifyRestClient
from app.config import Settings


def make_client(handler, **kw):
    settings = Settings(shopify_store_domain="test-shop.myshopify.com", shopify_admin_access_token="t",
                        shopify_api_version="2026-04")
    return ShopifyRestClient(settings, transport=httpx.MockTransport(handler), sleep=lambda s: None, **kw)


def test_url_header_and_pagination():
    seen = {}

    def handler(request):
        seen["url"], seen["token"] = str(request.url), request.headers["X-Shopify-Access-Token"]
        link = '<https://test-shop.myshopify.com/admin/api/2026-04/products.json?page_info=abc&limit=2>; rel="next"'
        return httpx.Response(200, json={"products": [{"id": 1}]}, headers={"Link": link})

    page = make_client(handler).list_products(limit=2)
    assert seen["url"].startswith("https://test-shop.myshopify.com/admin/api/2026-04/products.json")
    assert seen["token"] == "t"
    assert page["next_page_info"] == "abc" and page["previous_page_info"] is None


def test_page_info_request_drops_other_filters():
    seen = {}

    def handler(request):
        seen["q"] = dict(request.url.params)
        return httpx.Response(200, json={"products": []})

    make_client(handler).list_products(page_info="abc", limit=5, title="x")
    assert seen["q"] == {"limit": "5", "page_info": "abc"}


def test_retries_on_rate_limit_then_succeeds():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(429, headers={"Retry-After": "1"})
        return httpx.Response(200, json={"shop": {"name": "Demo"}})

    assert make_client(handler).get_shop()["name"] == "Demo"
    assert len(calls) == 3


def test_gives_up_after_max_retries():
    with pytest.raises(ShopifyError) as err:
        make_client(lambda r: httpx.Response(429), max_retries=2).get_shop()
    assert err.value.status_code == 503


def test_forbidden_gives_safe_message():
    with pytest.raises(ShopifyError) as err:
        make_client(lambda r: httpx.Response(403, text="secret details")).list_orders()
    assert "secret" not in err.value.message and err.value.status_code == 502


def test_rejects_bad_domain():
    bad = Settings(shopify_store_domain="evil.example.com", shopify_admin_access_token="t", shopify_api_version="2026-04")
    with pytest.raises(ShopifyError):
        ShopifyRestClient(bad)
