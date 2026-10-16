from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.clients.shopify_rest_client import ShopifyError
from app.config import get_settings
from app.database import create_tables
from app.routers import catalog, crm, shopify_oauth, webhooks


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().database_url:
        create_tables()
    yield


app = FastAPI(title="Pharmacy Shopify Integration", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(ShopifyError)
async def shopify_error_handler(request: Request, exc: ShopifyError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.get("/health")
def health():
    # "configured" only means settings are present, not that Shopify was reached.
    return {"status": "ok", "shopify_configured": get_settings().shopify_configured}


app.include_router(catalog.router)
app.include_router(crm.router)
app.include_router(shopify_oauth.router)
app.include_router(webhooks.router)
