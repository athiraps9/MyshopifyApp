"""Shopify OAuth installation and callback for a single configured store."""
import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.config import DOMAIN_RE, Settings, get_settings

router = APIRouter(tags=["shopify oauth"])
STATE_COOKIE = "shopify_oauth_state"
STATE_MAX_AGE = 600
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def _oauth_ready(settings: Settings) -> bool:
    redirect = urlparse(settings.shopify_redirect_uri)
    return bool(
        settings.shopify_store_domain
        and DOMAIN_RE.fullmatch(settings.shopify_store_domain)
        and settings.shopify_api_key
        and settings.shopify_api_secret
        and redirect.scheme == "https"
        and redirect.netloc
        and redirect.path
    )


def _verify_query_hmac(query: list[tuple[str, str]], secret: str) -> bool:
    values: dict[str, list[str]] = {}
    supplied_hmac = None
    for key, value in query:
        if key == "hmac":
            supplied_hmac = value
        elif key != "signature":
            values.setdefault(key, []).append(value)
    if not supplied_hmac:
        return False
    message = "&".join(
        f"{key}={','.join(values[key])}" for key in sorted(values)
    )
    digest = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, supplied_hmac)


def _verify_timestamp(value: str | None) -> bool:
    try:
        return abs(time.time() - int(value or "")) <= 300
    except ValueError:
        return False


def _save_access_token(token: str) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    key = "SHOPIFY_ADMIN_ACCESS_TOKEN"
    replacement = f"{key}={token}"
    for index, line in enumerate(lines):
        if line.partition("=")[0].strip() == key:
            lines[index] = replacement
            break
    else:
        lines.append(replacement)

    temporary_path = ENV_PATH.with_suffix(".env.tmp")
    temporary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(temporary_path, ENV_PATH)
    os.environ[key] = token
    get_settings.cache_clear()


async def _exchange_code(code: str, settings: Settings) -> str:
    url = f"https://{settings.shopify_store_domain}/admin/oauth/access_token"
    payload = {
        "client_id": settings.shopify_api_key,
        "client_secret": settings.shopify_api_secret,
        "code": code,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, data=payload)
            response.raise_for_status()
            token = response.json().get("access_token")
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "Shopify token exchange failed.") from exc
    if not isinstance(token, str) or not token:
        raise HTTPException(502, "Shopify did not return an access token.")
    return token


@router.get("/new-install")
async def start_install(request: Request, settings: Settings = Depends(get_settings)):
    if not _oauth_ready(settings):
        raise HTTPException(503, "Shopify OAuth settings are incomplete on the server.")
    query = list(request.query_params.multi_items())
    params = dict(query)
    if not _verify_query_hmac(query, settings.shopify_api_secret):
        raise HTTPException(401, "Invalid Shopify install signature.")
    if params.get("shop") != settings.shopify_store_domain or not _verify_timestamp(params.get("timestamp")):
        raise HTTPException(400, "Invalid or expired Shopify install request.")

    state = secrets.token_urlsafe(32)
    authorize_url = f"https://{settings.shopify_store_domain}/admin/oauth/authorize?" + urlencode(
        {
            "client_id": settings.shopify_api_key,
            "scope": settings.shopify_oauth_scopes,
            "redirect_uri": settings.shopify_redirect_uri,
            "state": state,
        }
    )
    response = RedirectResponse(authorize_url, status_code=302)
    response.set_cookie(
        STATE_COOKIE,
        state,
        max_age=STATE_MAX_AGE,
        secure=True,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/api/v1/shopify/callback")
async def shopify_callback(request: Request, settings: Settings = Depends(get_settings)):
    if not _oauth_ready(settings):
        raise HTTPException(503, "Shopify OAuth settings are incomplete on the server.")
    query = list(request.query_params.multi_items())
    params = dict(query)
    if not _verify_query_hmac(query, settings.shopify_api_secret):
        raise HTTPException(401, "Invalid Shopify callback signature.")
    if params.get("shop") != settings.shopify_store_domain or not _verify_timestamp(params.get("timestamp")):
        raise HTTPException(400, "Invalid or expired Shopify callback.")

    expected_state = request.cookies.get(STATE_COOKIE, "")
    actual_state = params.get("state", "")
    if not expected_state or not hmac.compare_digest(expected_state, actual_state):
        raise HTTPException(400, "Invalid or expired OAuth state.")
    code = params.get("code")
    if not code:
        raise HTTPException(400, "Shopify did not return an authorization code.")

    token = await _exchange_code(code, settings)
    try:
        _save_access_token(token)
    except OSError as exc:
        raise HTTPException(500, "Could not securely save the Shopify token to the backend environment file.") from exc

    response = RedirectResponse(settings.frontend_origin, status_code=303)
    response.delete_cookie(STATE_COOKIE, secure=True, httponly=True, samesite="lax")
    return response