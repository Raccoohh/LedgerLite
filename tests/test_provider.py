import json

import httpx
import pytest
from fastapi.testclient import TestClient

from ledgerlite.common.config import settings
from ledgerlite.common.security import valid_signature
from ledgerlite.provider.app import app, invoices


@pytest.fixture
def provider():
    invoices.clear()
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + settings().provider_api_key
        yield client


def create(provider):
    return provider.post(
        "/invoices",
        json={
            "amount": "10.00",
            "currency": "USD",
            "external_id": "deposit-1",
            "callback_url": settings().callback_url,
        },
    )


def test_provider_auth(provider):
    assert (
        provider.get("/invoices/no-such-invoice", headers={"Authorization": "bad"}).status_code
        == 401
    )
    assert provider.get("/invoices/no-such-invoice").status_code == 404


@pytest.mark.parametrize("status", ["paid", "partially_paid", "expired"])
def test_provider_final_states(provider, status):
    created = create(provider)
    assert created.status_code == 201
    invoice_id = created.json()["invoice_id"]
    assert provider.get(f"/invoices/{invoice_id}").json()["status"] == "pending"
    body = {"status": status, "paid_amount": "7.50", "deliver_webhook": False}
    first = provider.post(f"/invoices/{invoice_id}/simulate", json=body)
    assert first.status_code == 200
    retry = provider.post(f"/invoices/{invoice_id}/simulate", json=body)
    assert first.json()["event_id"] == retry.json()["event_id"]
    changed = provider.post(
        f"/invoices/{invoice_id}/simulate", json={**body, "paid_amount": "9.00"}
    )
    assert changed.status_code == 409
    assert provider.get(f"/invoices/{invoice_id}").json()["paid_amount"] == "7.50"


def test_provider_duplicate_signed_delivery(provider, monkeypatch):
    deliveries = []

    async def post(self, url, content, headers):
        assert valid_signature(
            settings().webhook_secret, headers["X-Timestamp"], content, headers["X-Signature"]
        )
        deliveries.append(json.loads(content))
        return httpx.Response(200)

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    invoice_id = create(provider).json()["invoice_id"]
    response = provider.post(
        f"/invoices/{invoice_id}/simulate",
        json={
            "status": "paid",
            "paid_amount": "10.00",
            "duplicate": True,
        },
    )
    assert response.json()["webhook_delivery"] == [200, 200]
    assert len(deliveries) == 2 and deliveries[0] == deliveries[1]


def test_provider_rejects_arbitrary_callback(provider):
    response = provider.post(
        "/invoices",
        json={
            "amount": "10.00",
            "currency": "USD",
            "external_id": "d1",
            "callback_url": "http://untrusted.invalid/internal",
        },
    )
    assert response.status_code == 422
