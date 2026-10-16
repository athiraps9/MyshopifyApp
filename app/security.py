"""Token auth for CRM/customer/order routes + webhook signature check."""
import base64
import hashlib
import hmac

from fastapi import Depends, Header, HTTPException

from app.config import Settings, get_settings


def _digest(value: str, key: str) -> bytes:
    return hmac.new(key.encode(), value.encode(), hashlib.sha256).digest()


def get_role(authorization: str | None = Header(default=None), settings: Settings = Depends(get_settings)) -> str:
    if not settings.crm_viewer_token and not settings.crm_staff_token:
        raise HTTPException(503, "CRM access tokens are not configured on the server.")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing access token.")
    given = _digest(authorization[7:].strip(), settings.secret_key)
    for role, token in (("staff", settings.crm_staff_token), ("viewer", settings.crm_viewer_token)):
        if token and hmac.compare_digest(given, _digest(token, settings.secret_key)):
            return role
    raise HTTPException(401, "Invalid access token.")


def require_viewer(role: str = Depends(get_role)) -> str:
    return role  # viewer or staff


def require_staff(role: str = Depends(get_role)) -> str:
    if role != "staff":
        raise HTTPException(403, "Staff access is required.")
    return role


def verify_shopify_hmac(raw_body: bytes, header_value: str, secret: str) -> bool:
    expected = base64.b64encode(hmac.new(secret.encode(), raw_body, hashlib.sha256).digest()).decode()
    return hmac.compare_digest(expected, header_value or "")
