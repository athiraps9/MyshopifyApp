import base64
import hashlib
import hmac
import json

BODY = json.dumps({"id": 5, "first_name": "Asha", "last_name": "N"}).encode()


def sign(body, secret="whsec_test"):
    return base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()


def headers(sig, event_id="evt-1"):
    return {"X-Shopify-Hmac-Sha256": sig, "X-Shopify-Event-Id": event_id, "X-Shopify-Topic": "customers/update",
            "X-Shopify-Shop-Domain": "test-shop.myshopify.com", "Content-Type": "application/json"}


def test_invalid_signature_rejected(client):
    r = client.post("/api/v1/webhooks/shopify", content=BODY, headers=headers(sign(BODY, "wrong")))
    assert r.status_code == 401


def test_tampered_body_rejected(client):
    r = client.post("/api/v1/webhooks/shopify", content=BODY + b" ", headers=headers(sign(BODY)))
    assert r.status_code == 401


def test_valid_then_duplicate(client):
    first = client.post("/api/v1/webhooks/shopify", content=BODY, headers=headers(sign(BODY)))
    assert first.status_code == 200 and first.json()["status"] == "processed"
    again = client.post("/api/v1/webhooks/shopify", content=BODY, headers=headers(sign(BODY)))
    assert again.json()["status"] == "duplicate"


def test_missing_event_id(client):
    h = headers(sign(BODY))
    del h["X-Shopify-Event-Id"]
    assert client.post("/api/v1/webhooks/shopify", content=BODY, headers=h).status_code == 400


def test_webhook_updates_known_crm_customer_name(client):
    staff = {"Authorization": "Bearer staff-token"}
    client.post("/api/v1/crm/customers/5/interactions", headers=staff, json={"channel": "chat", "summary": "hi"})
    new_body = json.dumps({"id": 5, "first_name": "Asha", "last_name": "Nair"}).encode()
    client.post("/api/v1/webhooks/shopify", content=new_body, headers=headers(sign(new_body), "evt-2"))
    rows = client.get("/api/v1/crm/customers", headers=staff).json()
    assert rows[0]["display_name"] == "Asha Nair"
