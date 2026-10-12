"""Run inside the wallet container; leaves uniquely named demo data for inspection."""

import secrets
from decimal import Decimal
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session

from ledgerlite.common.config import settings
from ledgerlite.common.security import key_hash
from ledgerlite.wallet.cli import reconcile
from ledgerlite.wallet.db import engine
from ledgerlite.wallet.models import Account


def main():
    tag = uuid4().hex[:8]
    keys = [secrets.token_urlsafe(32) for _ in range(2)]
    with Session(engine()) as db, db.begin():
        accounts = [
            Account(name=f"smoke-{tag}-{i}", api_key_hash=key_hash(key))
            for i, key in enumerate(keys)
        ]
        db.add_all(accounts)
        db.flush()
        ids = [account.id for account in accounts]

    with (
        httpx.Client(
            base_url="http://wallet:8000", timeout=15, headers={"X-API-Key": keys[0]}
        ) as wallet,
        httpx.Client(
            base_url=settings().provider_url,
            timeout=15,
            headers={"Authorization": "Bearer " + settings().provider_api_key},
        ) as provider,
    ):
        assert wallet.get("/health").status_code == 200
        assert provider.get("/health").status_code == 200
        assert (
            provider.get("/invoices/missing", headers={"Authorization": "bad"}).status_code == 401
        )
        deposit = wallet.post("/v1/deposits", json={"amount": "100.00"})
        assert deposit.status_code == 201, deposit.text
        invoice_id = deposit.json()["invoice_id"]
        simulated = provider.post(
            f"/invoices/{invoice_id}/simulate",
            json={
                "status": "paid",
                "paid_amount": "100.00",
                "duplicate": True,
            },
        )
        assert simulated.status_code == 200, simulated.text
        assert simulated.json()["webhook_delivery"] == [200, 200]
        assert wallet.get("/v1/accounts/me").json()["usd_balance"] == "98.50"
        payload = {"to_account_id": ids[1], "amount": "5.00"}
        headers = {"Idempotency-Key": "smoke-transfer"}
        transfer = wallet.post("/v1/transfers", json=payload, headers=headers)
        assert transfer.status_code == 201, transfer.text
        assert wallet.post("/v1/transfers", json=payload, headers=headers).json() == transfer.json()
        assert (
            wallet.post(
                "/v1/transfers", json={**payload, "amount": "6.00"}, headers=headers
            ).status_code
            == 409
        )
        purchase = wallet.post("/v1/purchases", json={"credits": 507})
        assert purchase.status_code == 201 and purchase.json()["price"] == "48.17"
        assert wallet.get("/v1/accounts/me").json()["usd_balance"] == "45.33"
        missed = wallet.post("/v1/deposits", json={"amount": "10.00"}).json()["invoice_id"]
        result = provider.post(
            f"/invoices/{missed}/simulate",
            json={
                "status": "partially_paid",
                "paid_amount": "7.50",
                "deliver_webhook": False,
            },
        )
        assert result.status_code == 200 and result.json()["webhook_delivery"] == []
        reconciliation = reconcile(0)
        assert reconciliation["settled"] >= 1 and reconciliation["failed"] == 0, reconciliation
        late = provider.post(
            f"/invoices/{missed}/simulate",
            json={
                "status": "partially_paid",
                "paid_amount": "7.50",
                "duplicate": True,
            },
        )
        assert late.json()["webhook_delivery"] == [200, 200]
        expired = wallet.post("/v1/deposits", json={"amount": "1.00"}).json()["invoice_id"]
        assert provider.post(
            f"/invoices/{expired}/simulate",
            json={
                "status": "expired",
                "paid_amount": "0.00",
            },
        ).json()["webhook_delivery"] == [200]
        account = wallet.get("/v1/accounts/me").json()
        assert (account["usd_balance"], account["credits_balance"]) == ("52.72", 507)
        assert wallet.get("/v1/transactions?limit=2").json()["total"] == 5
        recipient = wallet.get("/v1/accounts/me", headers={"X-API-Key": keys[1]}).json()
        assert recipient["usd_balance"] == "5.00"
        with Session(engine()) as db:
            assert db.get(Account, ids[0]).balance == Decimal("52.72")
            assert db.get(Account, ids[1]).balance == Decimal("5.00")
    print(
        f"PASS: real HTTP deposit/duplicate webhook/transfer/replay/purchase/reconciliation/expiry "
        f"and DB balances. Demo prefix: smoke-{tag}. No API keys printed."
    )


if __name__ == "__main__":
    main()
