import os
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from ledgerlite.common.security import key_hash  # noqa: E402
from ledgerlite.wallet.app import app  # noqa: E402
from ledgerlite.wallet.db import engine  # noqa: E402
from ledgerlite.wallet.models import Account, Deposit  # noqa: E402


@pytest.fixture
def db():
    # Refuse to truncate any database whose name is not explicitly a test database.
    url = make_url(str(engine().url))
    if not url.database or not url.database.endswith("_test"):
        pytest.fail("Integration tests require DATABASE_URL with database name ending in _test")
    with engine().begin() as connection:
        connection.execute(
            text(
                "TRUNCATE rate_requests, transactions, idempotency_records, webhook_events, "
                "deposits, accounts CASCADE"
            )
        )
    with Session(engine()) as session:
        yield session


@pytest.fixture
def users(db):
    alice = Account(
        name="alice", api_key_hash=key_hash("alice-test-key"), balance=Decimal("100.00")
    )
    bob = Account(name="bob", api_key_hash=key_hash("bob-test-key"), balance=Decimal("0.00"))
    db.add_all([alice, bob])
    db.commit()
    return alice.id, bob.id


@pytest.fixture
def client(users):
    with TestClient(app) as client:
        client.headers["X-API-Key"] = "alice-test-key"
        yield client


@pytest.fixture
def deposit(db, users):
    row = Deposit(account_id=users[0], invoice_id="inv_test", amount=Decimal("10.00"))
    db.add(row)
    db.commit()
    return row.id
