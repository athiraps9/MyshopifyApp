# Pharmacy Shopify Integration (REST only)

Shopify stays the real store (cart, checkout, payments). This project adds:

- **FastAPI** backend that reads Shopify through the **REST Admin API only**
- **React + Vite** dashboard (products, customers, orders, CRM)
- **SQL Server** for CRM notes, follow-ups and webhook records

**No GraphQL is used anywhere** (no Admin/Storefront GraphQL, no queries, no mutations, no client libraries).

> Status: tested only with **mocked** Shopify responses. The real store is **not** verified as connected until you add credentials and run the checks in "First real connection test".

## REST limitations (read this first)

Checked against Shopify's docs (shopify.dev):

- The REST Admin API is a **legacy API** since 1 Oct 2024. New *public* apps must use GraphQL, so this project only fits a **custom app** on your own store.
- **Product** list/create/update/delete REST endpoints are **deprecated** (since 2024-04). `GET products` and `GET products/{id}` are still callable today on many versions, but Shopify can remove them. If that happens, the Products page shows an error. We do not work around it with GraphQL.
- Because of this, only **read** operations are implemented. No product writes.
- **Orders**: only the last 60 days are returned unless the app has `read_all_orders`.
- **Customers/orders** contain personal data. Shopify may require extra approval for protected customer data on some app types.
- `inventory_quantity` on variants may be missing or stale; inventory levels are not fetched separately.
- Customer **search** (`customers/search`) returns one page; no next/previous.
- REST paging is **cursor based** (`page_info`). With a cursor, only `limit` can be combined, so changing a filter restarts at page 1.
- `GET /api/v1/crm/customers` lists customers that already have a CRM record, not all Shopify customers (use `/customers` for those).

## Shopify app setup

1. Shopify admin > Settings > Apps and sales channels > Develop apps > create a custom app.
2. Admin API scopes: `read_products`, `read_customers`, `read_orders` (add `read_all_orders` for older orders).
3. Install the app, copy the Admin API access token into `SHOPIFY_ADMIN_ACCESS_TOKEN` (shown once).
4. `SHOPIFY_STORE_DOMAIN` = `your-shop.myshopify.com`, `SHOPIFY_API_VERSION` = a supported version such as `2026-04`.

For an OAuth-installed app, set `SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_REDIRECT_URI`, and `SHOPIFY_OAUTH_SCOPES` in the backend `.env`. Set the app URL to the public backend URL ending in `/new-install` and add the exact `SHOPIFY_REDIRECT_URI` to the app's allowed redirection URLs. The `/new-install` route validates Shopify's signed install request and starts OAuth; `/api/v1/shopify/callback` validates the callback and state, exchanges the code, and stores the access token in the git-ignored backend `.env`. Keep the client secret private. For local development, use a public HTTPS tunnel and restart the backend after changing `.env`.

## Windows setup

Install: Python 3.11+, Node 18+, SQL Server (Express is fine), and **ODBC Driver 18 for SQL Server**.

```powershell
cd shopify-pharmacy
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        # then fill in the values
cd frontend
copy .env.example .env
npm install
```

### SQL Server

1. Create an empty database, e.g. `pharmacy_crm` (SSMS: right-click Databases > New Database).
2. Create a SQL login with rights on that database (or use Windows auth).
3. Set `DATABASE_URL` in `.env`, for example:

```
mssql+pyodbc://crm_user:YourPassword@localhost\SQLEXPRESS/pharmacy_crm?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
```

Tables are created automatically on first start (`create_all`). There are no migrations.

### Snapshot Shopify data into SQL Server

After the backend `.env` has a valid `DATABASE_URL` and Shopify token with product, customer, and order read scopes, run this from the project root:

```powershell
python -m app.sync_shopify
```

The command can be rerun; it updates existing rows and adds new Shopify records. It stores product/variant details, customer name/email and summary totals, plus order/line-item summaries. It does not store customer addresses, phone numbers, or payment details. Shopify currently limits order access to the last 60 days unless the app is granted `read_all_orders`. The website continues to read live data from Shopify; this command creates SQL snapshots and does not switch the website to SQL reads.

### Other settings in `.env`

| Variable | Meaning |
|---|---|
| `SECRET_KEY` | Long random string (used when comparing access tokens) |
| `CRM_VIEWER_TOKEN` | Read-only access to customers, orders and CRM |
| `CRM_STAFF_TOKEN` | Same, plus adding interactions and follow-ups |
| `STOREFRONT_URL` | Optional public shop URL (custom domain); defaults to `https://<SHOPIFY_STORE_DOMAIN>` |

Generate tokens: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

## Start

```powershell
# terminal 1 (project root, venv active)
uvicorn app.main:app --reload --port 8000

# terminal 2
cd frontend
npm run dev
```

Open http://localhost:5173 and paste a CRM token in the header box ("Sign in"). Tokens are kept in `sessionStorage` only. API docs: http://127.0.0.1:8000/docs

## Tests

```powershell
python -m pytest -q
```

Shopify calls are mocked and the DB is in-memory SQLite, so no store or SQL Server is needed.

## API

| Route | Auth | Notes |
|---|---|---|
| `GET /health` | none | `shopify_configured` only means settings exist |
| `GET /api/v1/products` | none | `search`, `category`, `limit`, `page_info` |
| `GET /api/v1/products/{id}` | none | variants, plain-text description |
| `GET /api/v1/customers` | viewer | `search`, `limit`, `page_info` |
| `GET /api/v1/orders` | viewer | `status`, `financial_status`, `fulfillment_status`, `limit`, `page_info` |
| `GET /api/v1/crm/dashboard` | viewer | counts, next follow-ups, webhook status counts, store URL |
| `GET /api/v1/crm/customers` | viewer | customers that have a CRM record |
| `GET /api/v1/crm/customers/{id}` | viewer | `{id}` = Shopify customer ID; live Shopify data + CRM record |
| `GET/POST /api/v1/crm/customers/{id}/interactions` | viewer / staff | notes |
| `GET/POST /api/v1/crm/follow-ups` | viewer / staff | filter `status`, `shopify_customer_id` |
| `POST /api/v1/webhooks/shopify` | HMAC | Shopify only |

Send tokens as `Authorization: Bearer <token>`. Reading store info (`shop.json`) is implemented in the client (`get_shop`) but no route exposes it, because none was in the required list.

## Webhooks

Endpoint: `https://<public-host>/api/v1/webhooks/shopify` (must be HTTPS and public; for local testing use a tunnel such as ngrok or Cloudflare Tunnel).

Setup (either way):
- Shopify admin > Settings > Notifications > Webhooks > Create webhook (JSON), e.g. `customers/update`, `orders/create`. The signing secret shown on that page goes in `SHOPIFY_WEBHOOK_SECRET`.
- Or the REST endpoint `POST /admin/api/{version}/webhooks.json` (needs the matching scopes). For app-created webhooks, Shopify signs with the app's client secret.

Behaviour: signature checked on the raw body (`X-Shopify-Hmac-Sha256`), bad signature = 401, events deduplicated by `X-Shopify-Event-Id`, status saved as `received`/`processed`/`failed`. Only metadata is stored, never the body. Failed events return 500 so Shopify retries, and the retry is reprocessed. `customers/create|update` refreshes the cached name of customers already in the CRM.

## Security notes

- Shopify token lives only in backend `.env`; the browser never sees it.
- CORS allows only `FRONTEND_ORIGIN`.
- Customer, order and CRM routes need a token; writes need the staff token.
- Shopify error details are not passed to clients, secrets are not logged.
- Domain and API version are validated, so the backend cannot be pointed at another host.
- No payment data is handled. Do not store prescriptions or health details in CRM notes.
- Simple shared tokens are used for simplicity. For many staff, add real user login (e.g. OAuth/JWT).

## First real connection test

1. Fill `.env`, start the backend, open `/health` (should show `shopify_configured: true`).
2. Call `/api/v1/products?limit=1`. A 502 means token/scope problem; 404 may mean the product endpoint was removed for your API version.
3. Sign in with a token and check Orders and Customers.
