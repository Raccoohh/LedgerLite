import argparse
import json
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ledgerlite.common.errors import APIError
from ledgerlite.common.security import key_hash
from ledgerlite.wallet.db import engine
from ledgerlite.wallet.models import Account, Deposit
from ledgerlite.wallet.provider_client import ProviderClient
from ledgerlite.wallet.services import settle


def seed(names: list[str]):
    result = []
    with Session(engine()) as db, db.begin():
        for name in names:
            if db.scalar(select(Account.id).where(Account.name == name)):
                result.append({"name": name, "status": "exists; key not recoverable"})
                continue
            key = secrets.token_urlsafe(32)
            account = Account(name=name, api_key_hash=key_hash(key))
            db.add(account)
            db.flush()
            result.append({"name": name, "account_id": account.id, "api_key": key})
    print(json.dumps(result, indent=2))


def reconcile(minutes: int) -> dict:
    cutoff = datetime.now(UTC) - timedelta(minutes=minutes)
    with Session(engine()) as db:
        invoices = list(
            db.scalars(
                select(Deposit.invoice_id).where(
                    Deposit.status == "pending", Deposit.created_at < cutoff
                )
            )
        )
    result = {"checked": len(invoices), "settled": 0, "failed": 0}
    provider = ProviderClient()
    for invoice_id in invoices:
        try:
            invoice = provider.get(invoice_id)
            if invoice.status != "pending":
                with Session(engine()) as db, db.begin():
                    changed = settle(db, invoice_id, invoice.status, invoice.paid_amount)
                result["settled"] += int(changed)
        except APIError:
            result["failed"] += 1
    return result


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    seed_parser = commands.add_parser("seed")
    seed_parser.add_argument("names", nargs="+", help="Unique account names; keys printed once")
    reconcile_parser = commands.add_parser("reconcile")
    reconcile_parser.add_argument("--minutes", type=int, default=5)
    args = parser.parse_args()
    if args.command == "seed":
        if any(not 1 <= len(name) <= 100 for name in args.names):
            parser.error("Account names must contain 1-100 characters")
        seed(args.names)
    else:
        if args.minutes < 0:
            parser.error("minutes must be nonnegative")
        result = reconcile(args.minutes)
        print(json.dumps(result))
        if result["failed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
