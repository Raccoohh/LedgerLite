from decimal import Decimal

import pytest
from sqlalchemy import func, select
from test_wallet import concurrent, webhook

from ledgerlite.common.config import settings
from ledgerlite.wallet.models import Account, Deposit, Event, RateRequest, Transaction


@pytest.mark.parametrize(
    "offset,status", [(0, 200), (2**63 - 1, 200), (2**63, 422), (10**100, 422), (-1, 422)]
)
def test_offset_postgresql_bounds(client, offset, status):
    response = client.get("/v1/transactions", params={"offset": str(offset)})
    assert response.status_code == status
    if status == 200:
        assert response.json()["items"] == []
        assert response.json()["offset"] == offset
    else:
        assert response.json()["error"]["code"] == "validation_error"


def malformed(client, path="/v1/purchases", **headers):
    return client.post(path, content="{", headers={"Content-Type": "application/json", **headers})


@pytest.mark.parametrize("path", ["/v1/deposits", "/v1/transfers", "/v1/purchases"])
def test_malformed_json_counts_once_before_validation(client, db, users, monkeypatch, path):
    monkeypatch.setattr(settings(), "rate_limit_enabled", True)
    responses = [malformed(client, path) for _ in range(31)]
    assert [r.status_code for r in responses] == [422] * 30 + [429]
    assert all(r.json()["error"]["code"] == "validation_error" for r in responses[:30])
    assert responses[-1].json()["error"]["code"] == "rate_limited"
    assert 1 <= int(responses[-1].headers["Retry-After"]) <= 60
    assert db.scalar(select(func.count()).select_from(RateRequest)) == 30
    assert db.get(Account, users[0]).balance == Decimal("100.00")
    assert db.scalar(select(func.count()).select_from(Transaction)) == 0
    assert db.scalar(select(func.count()).select_from(Deposit)) == 0


def test_mixed_post_bodies_share_limit_and_webhooks_stay_exempt(
    client, db, users, deposit, monkeypatch
):
    monkeypatch.setattr(settings(), "rate_limit_enabled", True)
    for _ in range(15):
        assert client.post("/v1/purchases", json={"credits": 1}).status_code == 201
        assert malformed(client).status_code == 422
    assert client.post("/v1/purchases", json={"credits": 1}).status_code == 429
    assert db.scalar(select(func.count()).select_from(RateRequest)) == 30
    assert db.get(Account, users[0]).balance == Decimal("98.50")
    assert db.get(Account, users[0]).credits == 15
    assert client.get("/v1/accounts/me").status_code == 200
    # Both valid delivery and a bad signature bypass API-key authentication/rate limiting.
    response = webhook(client)
    assert response.status_code == 200 and response.json()["applied"]
    assert malformed(client, "/v1/webhooks/provider").status_code == 401
    assert db.scalar(select(func.count()).select_from(RateRequest)) == 30


@pytest.mark.parametrize("key", ["", "invalid-key"])
def test_malformed_body_with_invalid_key_is_not_counted(client, db, monkeypatch, key):
    monkeypatch.setattr(settings(), "rate_limit_enabled", True)
    for _ in range(31):
        response = malformed(client, **{"X-API-Key": key})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"
    assert db.scalar(select(func.count()).select_from(RateRequest)) == 0
    assert malformed(client).status_code == 422
    assert db.scalar(select(func.count()).select_from(RateRequest)) == 1


def test_concurrent_malformed_bodies_respect_limit(client, db, monkeypatch):
    monkeypatch.setattr(settings(), "rate_limit_enabled", True)
    for _ in range(28):
        assert malformed(client).status_code == 422
    responses = concurrent(8, lambda worker, i: malformed(worker))
    assert sorted(r.status_code for r in responses) == [422] * 2 + [429] * 6
    assert db.scalar(select(func.count()).select_from(RateRequest)) == 30


@pytest.mark.parametrize("field", ["event_id", "invoice_id"])
@pytest.mark.parametrize("value", ["\x00identifier", "id\x00entifier", "identifier\x00"])
def test_signed_nul_identifiers_rejected_before_database(
    client, db, users, deposit, monkeypatch, field, value
):
    def must_not_process(*args):
        pytest.fail("Invalid identifier reached the database-processing boundary")

    with monkeypatch.context() as patch:
        patch.setattr("ledgerlite.wallet.app.process_webhook", must_not_process)
        response = webhook(client, **{field: value})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    db.expire_all()
    assert db.get(Account, users[0]).balance == Decimal("100.00")
    row = db.get(Deposit, deposit)
    assert (row.status, row.paid_amount, row.fee) == ("pending", Decimal("0"), Decimal("0"))
    assert db.scalar(select(func.count()).select_from(Event)) == 0
    assert db.scalar(select(func.count()).select_from(Transaction)) == 0
    # Valid identifiers need not follow the mock's UUID format; a retry still settles once.
    assert webhook(client, event_id="valid:external/event").json()["applied"]
    assert not webhook(client, event_id="valid:external/event").json()["applied"]
    db.expire_all()
    assert db.get(Account, users[0]).balance == Decimal("109.85")
    assert db.get(Deposit, deposit).status == "paid"
    assert db.scalar(select(func.count()).select_from(Transaction)) == 1
