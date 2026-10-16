"""Small Shopify REST Admin API client (no GraphQL).

URL pattern: https://{shop_domain}/admin/api/{api_version}/{resource}.json
Auth header: X-Shopify-Access-Token
"""
import logging
import time
from urllib.parse import parse_qs, urlparse

import httpx

from app.config import DOMAIN_RE, VERSION_RE, Settings

log = logging.getLogger("shopify")


class ShopifyError(Exception):
    """Safe error: the message is fine to show to API users."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class ShopifyRestClient:
    def __init__(self, settings: Settings, transport=None, sleep=time.sleep, max_retries=3):
        if not settings.shopify_configured:
            raise ShopifyError(503, "Shopify is not configured on the server.")
        if not DOMAIN_RE.match(settings.shopify_store_domain):
            raise ShopifyError(503, "SHOPIFY_STORE_DOMAIN must look like my-shop.myshopify.com.")
        if not VERSION_RE.match(settings.shopify_api_version):
            raise ShopifyError(503, "SHOPIFY_API_VERSION must look like 2026-04.")
        self.base_url = (
            f"https://{settings.shopify_store_domain}/admin/api/{settings.shopify_api_version}"
        )
        self._sleep = sleep
        self.max_retries = max_retries
        self._http = httpx.Client(
            headers={
                "X-Shopify-Access-Token": settings.shopify_admin_access_token,
                "Accept": "application/json",
            },
            timeout=httpx.Timeout(10.0),
            transport=transport,
        )

    def close(self):
        self._http.close()

    # ---- low level -------------------------------------------------
    def _request(self, path: str, params: dict | None = None) -> httpx.Response:
        url = f"{self.base_url}/{path}.json"
        resp = None
        for attempt in range(self.max_retries + 1):
            last = attempt == self.max_retries
            try:
                resp = self._http.get(url, params=params)
            except httpx.HTTPError:
                if last:
                    raise ShopifyError(502, "Could not reach Shopify.")
                self._sleep(2**attempt)
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                if last:
                    code = 503 if resp.status_code == 429 else 502
                    raise ShopifyError(code, "Shopify is busy or unavailable. Try again shortly.")
                try:
                    wait = float(resp.headers.get("Retry-After", 2**attempt))
                except ValueError:
                    wait = 2**attempt
                log.warning("Shopify returned %s for %s, retrying", resp.status_code, path)
                self._sleep(min(wait, 10))
                continue
            break

        if resp.status_code in (401, 403):
            raise ShopifyError(502, "Shopify rejected the request. Check the access token and app permissions (scopes).")
        if resp.status_code == 404:
            raise ShopifyError(404, "Not found in Shopify. The endpoint may be removed for this API version.")
        if resp.status_code >= 400:
            raise ShopifyError(502, "Shopify could not process the request.")
        return resp

    @staticmethod
    def _page_info(resp: httpx.Response, rel: str) -> str | None:
        link = resp.links.get(rel)
        if not link:
            return None
        return parse_qs(urlparse(link["url"]).query).get("page_info", [None])[0]

    def get_page(self, resource: str, key: str, params: dict, page_info: str | None = None, limit: int = 20):
        """Cursor pagination. With page_info, Shopify only allows limit + page_info."""
        query = {"limit": limit, "page_info": page_info} if page_info else {**params, "limit": limit}
        resp = self._request(resource, query)
        return {
            "items": resp.json().get(key, []),
            "next_page_info": self._page_info(resp, "next"),
            "previous_page_info": self._page_info(resp, "previous"),
        }

    # ---- operations ------------------------------------------------
    def get_shop(self) -> dict:
        return self._request("shop").json().get("shop", {})

    def list_products(self, page_info=None, limit=20, title=None, product_type=None, status="active"):
        params = {"status": status}
        if title:
            params["title"] = title
        if product_type:
            params["product_type"] = product_type
        return self.get_page("products", "products", params, page_info, limit)

    def get_product(self, product_id: int) -> dict:
        return self._request(f"products/{product_id}").json().get("product", {})

    def list_customers(self, page_info=None, limit=20, query=None):
        if query:  # the search endpoint has no cursor pagination
            resp = self._request("customers/search", {"query": query, "limit": limit})
            return {"items": resp.json().get("customers", []), "next_page_info": None, "previous_page_info": None}
        return self.get_page("customers", "customers", {}, page_info, limit)

    def get_customer(self, customer_id: int) -> dict:
        return self._request(f"customers/{customer_id}").json().get("customer", {})

    def list_orders(self, page_info=None, limit=20, status="any", financial_status=None, fulfillment_status=None):
        params = {"status": status}
        if financial_status:
            params["financial_status"] = financial_status
        if fulfillment_status:
            params["fulfillment_status"] = fulfillment_status
        return self.get_page("orders", "orders", params, page_info, limit)
