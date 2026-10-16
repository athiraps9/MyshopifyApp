"""Run with `python -m app.sync_shopify` to snapshot Shopify data locally."""
import json

from sqlalchemy.orm import sessionmaker

from app.clients.shopify_rest_client import ShopifyRestClient
from app.config import get_settings
from app.database import create_tables, get_engine
from app.shopify_sync import sync_shopify_data


def main() -> None:
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not configured.")

    create_tables()
    shopify = ShopifyRestClient(settings)
    session_factory = sessionmaker(bind=get_engine(), autoflush=False)
    try:
        with session_factory() as db:
            counts = sync_shopify_data(db, shopify)
    finally:
        shopify.close()

    print(json.dumps({"synced": counts}, indent=2))


if __name__ == "__main__":
    main()