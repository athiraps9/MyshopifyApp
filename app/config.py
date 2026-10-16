"""Settings read from environment variables / .env (Pydantic Settings)."""
import re
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9-]*\.myshopify\.com$")
VERSION_RE = re.compile(r"^\d{4}-\d{2}$")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    shopify_store_domain: str = ""
    shopify_admin_access_token: str = ""
    shopify_api_version: str = ""
    shopify_api_key: str = ""
    shopify_api_secret: str = ""
    shopify_redirect_uri: str = ""
    shopify_oauth_scopes: str = "read_products,read_customers,read_orders"
    shopify_webhook_secret: str = ""
    database_url: str = ""
    secret_key: str = ""
    frontend_origin: str = "http://localhost:5173"
    crm_viewer_token: str = ""  # read-only CRM access
    crm_staff_token: str = ""   # can also write notes and follow-ups
    storefront_url: str = ""    # public shop URL; defaults to https://<store domain>

    @property
    def shopify_configured(self) -> bool:
        return bool(
            self.shopify_store_domain
            and self.shopify_admin_access_token
            and self.shopify_api_version
        )

    @property
    def public_store_url(self) -> str:
        return (self.storefront_url or f"https://{self.shopify_store_domain}").rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
