from app.clients.shopify_rest_client import ShopifyRestClient
from app.config import get_settings


def get_shopify_client():
    client = ShopifyRestClient(get_settings())
    try:
        yield client
    finally:
        client.close()
