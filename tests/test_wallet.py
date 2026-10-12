import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ledgerlite.common.config import settings
from ledgerlite.common.security import signature
from ledgerlite.wallet import services
from ledgerlite.wallet.app import app
from ledgerlite.wallet.cli import reconcile
from ledgerlite.wallet.db import engine
from ledgerlite.wallet.models import Account, Deposit, Event, Idempotency, RateRequest, Transaction
from ledgerlite.wallet.provider_client import InvoiceCreated, InvoiceState, ProviderClient


def webhook(
    client, event_id="evt_test", status="paid", amount="10.00", age=0, bad_signature=False, **extra
):
    event = {
        "event_id": event_id,
        "invoice_id": "inv_test",
        "status": status,
        "paid_amount": amount,
        "occurred_at": datetime.now(UTC).isoformat(),
        **extra,
    }
    raw = json.dumps(event).encode()
    timestamp = str(int(time.time()) - age)
    digest = signature(settings().webhook_secret, timestamp, raw)
    return client.post(
        "/v1/webhooks/provider",
        content=raw,
        headers={
            "X-Timestamp": timestamp,
            "X-Signature": "sha256=wrong" if bad_signature else digest,
            "Content-Type": "application/json",
        },
    )


def balance(db, account_id):
    db.expire_all()
    return db.get(Account, account_id).balance


def test_auth_and_account(client, db, users):
    assert client.get("/v1/accounts/me").json()["usd_balance"] == "100.00"
    assert client.get("/v1/accounts/me", headers={"X-API-Key": "bad"}).status_code == 401
    assert db.get(Account, users[0]).api_key_hash != "alice-test-key"


@pytest.mark.parametrize(
    "status,amount,expected",
    [
        ("paid", "10.00", "109.85"),
        ("partially_paid", "7.50", "107.39"),
        ("expired", "7.50", "100.00"),
    ],
)
def test_settlement(client, db, users, deposit, status, amount, expected):
    result = webhook(client, status=status, amount=amount)
    assert result.status_code == 200, result.text
    assert result.json()["applied"]
    assert balance(db, users[0]) == Decimal(expected)
    assert db.get(Deposit, deposit).status == status
    assert db.scalar(select(func.count()).select_from(Transaction)) == 1


@pytest.mark.parametrize("options", [{"bad_signature": True}, {"age": 301}, {"age": -301}])
def test_invalid_webhook(client, db, users, deposit, options):
    assert webhook(client, **options).status_code == 401
    assert balance(db, users[0]) == Decimal("100")
    assert db.get(Deposit, deposit).status == "pending"


def test_signature_uses_raw_body(client, deposit):
    raw = b'{"event_id":"evt"}'
    timestamp = str(int(time.time()))
    response = client.post(
        "/v1/webhooks/provider",
        content=raw + b" ",
        headers={
            "X-Timestamp": timestamp,
            "X-Signature": signature(settings().webhook_secret, timestamp, raw),
        },
    )
    assert response.status_code == 401


def test_duplicate_and_finalized(client, db, users, deposit):
    assert webhook(client).json()["applied"]
    assert not webhook(client).json()["applied"]
    assert not webhook(client, event_id="evt_other", amount="99.00").json()["applied"]
    assert balance(db, users[0]) == Decimal("109.85")
    assert db.scalar(select(func.count()).select_from(Transaction)) == 1


def test_missing_deposit_does_not_consume_event(client, db):
    assert webhook(client).status_code == 404
    assert db.scalar(select(func.count()).select_from(Event)) == 0


def test_malformed_signed_webhook(client, deposit):
    assert webhook(client, amount=10).status_code == 422


def transfer(client, recipient, amount="5.00", key="key-1"):
    return client.post(
        "/v1/transfers",
        json={"to_account_id": recipient, "amount": amount},
        headers={"Idempotency-Key": key},
    )


def test_transfer_idempotency(client, db, users):
    first = transfer(client, users[1])
    assert first.status_code == 201, first.text
    retry = transfer(client, users[1])
    assert (retry.status_code, retry.json()) == (first.status_code, first.json())
    assert transfer(client, users[1], "6.00").status_code == 409
    assert balance(db, users[0]) == Decimal("95")
    assert balance(db, users[1]) == Decimal("5")
    assert db.scalar(select(func.count()).select_from(Transaction)) == 2


def test_insufficient_funds_saved_response(client, db, users):
    first = transfer(client, users[1], "101.00")
    assert first.status_code == 409
    assert first.json()["error"]["code"] == "insufficient_funds"
    db.get(Account, users[0]).balance = Decimal("200.00")
    db.commit()
    assert transfer(client, users[1], "101.00").json() == first.json()
    assert balance(db, users[0]) == Decimal("200")


def test_transfer_validation(client, users):
    assert (
        client.post("/v1/transfers", json={"to_account_id": users[1], "amount": "1.00"}).status_code
        == 422
    )
    assert transfer(client, users[0]).status_code == 422
    assert transfer(client, str(uuid4()), key="missing").status_code == 404


def test_scoped_key(client, db, users):
    assert transfer(client, users[1]).status_code == 201
    client.headers["X-API-Key"] = "bob-test-key"
    assert transfer(client, users[0]).status_code == 201
    assert balance(db, users[0]) == Decimal("100")


@pytest.mark.parametrize("value", [10, "1.001", "-1.00", "0.00"])
def test_api_money_validation(client, users, value):
    assert client.post("/v1/deposits", json={"amount": value}).status_code == 422
    assert transfer(client, users[1], value).status_code == 422


def test_purchase_and_history(client, db, users):
    response = client.post("/v1/purchases", json={"credits": 507})
    assert response.status_code == 201, response.text
    assert response.json()["price"] == "48.17"
    assert balance(db, users[0]) == Decimal("51.83")
    assert db.get(Account, users[0]).credits == 507
    assert client.post("/v1/purchases", json={"credits": 1005}).status_code == 409
    transfer(client, users[1])
    page1 = client.get("/v1/transactions?limit=1").json()
    page2 = client.get("/v1/transactions?limit=1&offset=1").json()
    assert page1["total"] == 2
    assert page1["items"][0]["id"] != page2["items"][0]["id"]
    client.headers["X-API-Key"] = "bob-test-key"
    assert client.get("/v1/transactions").json()["total"] == 1


def concurrent(count, operation):
    barrier = Barrier(count)

    def run(i):
        with TestClient(app) as worker:
            worker.headers["X-API-Key"] = "alice-test-key"
            barrier.wait(timeout=20)
            return operation(worker, i)

    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(run, range(count)))


def test_concurrent_overspending(client, db, users):
    responses = concurrent(8, lambda c, i: transfer(c, users[1], "30.00", f"key-{i}"))
    assert sorted(r.status_code for r in responses) == [201] * 3 + [409] * 5
    assert balance(db, users[0]) == Decimal("10")
    assert balance(db, users[1]) == Decimal("90")


def test_concurrent_same_key(client, db, users):
    responses = concurrent(8, lambda c, i: transfer(c, users[1]))
    assert all(r.status_code == 201 for r in responses)
    assert all(r.json() == responses[0].json() for r in responses)
    assert balance(db, users[0]) == Decimal("95")


def test_opposite_direction_transfers(client, db, users):
    db.get(Account, users[1]).balance = Decimal("100.00")
    db.commit()

    def operation(worker, i):
        worker.headers["X-API-Key"] = "alice-test-key" if i % 2 else "bob-test-key"
        return transfer(worker, users[1] if i % 2 else users[0], "1.00", f"opposite-{i}")

    responses = concurrent(12, operation)
    assert all(r.status_code == 201 for r in responses)
    assert balance(db, users[0]) == balance(db, users[1]) == Decimal("100")


def test_concurrent_same_key_different_payload(client, db, users):
    responses = concurrent(8, lambda c, i: transfer(c, users[1], f"{i + 1}.00"))
    assert sum(r.status_code == 201 for r in responses) == 1
    assert sum(r.status_code == 409 for r in responses) == 7
    assert balance(db, users[0]) + balance(db, users[1]) == Decimal("100")


def test_concurrent_purchases(client, db, users):
    responses = concurrent(8, lambda c, i: c.post("/v1/purchases", json={"credits": 333}))
    assert sum(r.status_code == 201 for r in responses) == 3
    assert sum(r.status_code == 409 for r in responses) == 5
    assert balance(db, users[0]) == Decimal("0.10")
    assert db.get(Account, users[0]).credits == 999


def test_reconcile_webhook_race(client, db, users, deposit):
    def operation(worker, i):
        if i % 2:
            return webhook(worker).json()["applied"]
        with Session(engine()) as own_db, own_db.begin():
            return services.settle(own_db, "inv_test", "paid", Decimal("10.00"))

    assert sum(concurrent(8, operation)) == 1
    assert balance(db, users[0]) == Decimal("109.85")


def test_webhook_rollback(client, db, users, deposit, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("Injected history failure")

    monkeypatch.setattr(services, "add_history", fail)
    with TestClient(app, raise_server_exceptions=False) as failing:
        assert webhook(failing).status_code == 500
    assert balance(db, users[0]) == Decimal("100")
    assert db.get(Deposit, deposit).status == "pending"
    assert db.scalar(select(func.count()).select_from(Event)) == 0


def test_concurrent_webhooks(client, db, users, deposit):
    responses = concurrent(8, lambda c, i: webhook(c, event_id=f"evt_{i % 3}"))
    assert all(r.status_code == 200 for r in responses)
    assert sum(r.json()["applied"] for r in responses) == 1
    assert balance(db, users[0]) == Decimal("109.85")


def test_transaction_rollback(client, db, users, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("Injected history failure after balance mutation")

    monkeypatch.setattr(services, "add_history", fail)
    with TestClient(app, raise_server_exceptions=False) as failing:
        failing.headers["X-API-Key"] = "alice-test-key"
        assert transfer(failing, users[1]).status_code == 500
    assert balance(db, users[0]) == Decimal("100")
    assert balance(db, users[1]) == Decimal("0")
    assert db.scalar(select(func.count()).select_from(Idempotency)) == 0


def test_database_rejects_negative_balance(db, users):
    db.get(Account, users[0]).balance = Decimal("-0.01")
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    assert balance(db, users[0]) == Decimal("100")


def test_create_deposit(client, db, monkeypatch):
    monkeypatch.setattr(
        ProviderClient,
        "create",
        lambda *args: InvoiceCreated(
            invoice_id="inv_created", status="pending", pay_url="http://provider/pay/inv_created"
        ),
    )
    result = client.post("/v1/deposits", json={"amount": "10.00"})
    assert result.status_code == 201
    assert db.get(Deposit, result.json()["deposit_id"]).status == "pending"


@pytest.mark.parametrize("failure,expected", [(httpx.ConnectError, 502), (httpx.ReadTimeout, 504)])
def test_provider_failures(client, db, monkeypatch, failure, expected):
    def fail(*args, **kwargs):
        raise failure("Injected transport failure")

    monkeypatch.setattr(httpx.Client, "request", fail)
    # TestClient inherits httpx.Client, so use the original TestClient transport via send.
    request = client.build_request("POST", "/v1/deposits", json={"amount": "10.00"})
    response = client.send(request)
    assert response.status_code == expected
    assert db.scalar(select(func.count()).select_from(Deposit)) == 0


def test_reconciliation(client, db, users, deposit, monkeypatch):
    db.get(Deposit, deposit).created_at = datetime.now(UTC) - timedelta(minutes=10)
    db.commit()
    monkeypatch.setattr(
        ProviderClient,
        "get",
        lambda *args: InvoiceState(
            invoice_id="inv_test", status="partially_paid", paid_amount="7.50"
        ),
    )
    assert reconcile(5) == {"checked": 1, "settled": 1, "failed": 0}
    assert not webhook(client).json()["applied"]
    assert balance(db, users[0]) == Decimal("107.39")


def test_rate_limit(client, db, users, deposit, monkeypatch):
    monkeypatch.setattr(settings(), "rate_limit_enabled", True)
    responses = [client.post("/v1/purchases", json={"credits": 1}) for _ in range(31)]
    assert all(r.status_code == 201 for r in responses[:30])
    assert responses[30].status_code == 429
    assert 1 <= int(responses[30].headers["Retry-After"]) <= 60
    assert client.get("/v1/accounts/me").status_code == 200
    assert webhook(client).status_code == 200


def test_concurrent_rate_limit_and_key_scope(client, db, users, monkeypatch):
    monkeypatch.setattr(settings(), "rate_limit_enabled", True)
    for _ in range(28):
        assert client.post("/v1/purchases", json={"credits": 1}).status_code == 201
    results = concurrent(8, lambda c, i: c.post("/v1/purchases", json={"credits": 1}))
    assert sum(r.status_code == 201 for r in results) == 2
    assert sum(r.status_code == 429 for r in results) == 6
    client.headers["X-API-Key"] = "bob-test-key"
    # Bob is independently allowed through the limiter, then fails the balance check.
    assert (
        client.post("/v1/purchases", json={"credits": 1}).json()["error"]["code"]
        == "insufficient_funds"
    )
    for row in db.scalars(select(RateRequest).where(RateRequest.account_id == users[0])):
        row.created_at = datetime.now(UTC) - timedelta(seconds=61)
    db.commit()
    client.headers["X-API-Key"] = "alice-test-key"
    assert client.post("/v1/purchases", json={"credits": 1}).status_code == 201
