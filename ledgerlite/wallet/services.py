import hashlib
import json
import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ledgerlite.common.errors import APIError, envelope
from ledgerlite.common.money import MAX_MONEY, credit_price, money_string, provider_fee
from ledgerlite.wallet.models import (
    Account,
    Deposit,
    Event,
    Idempotency,
    RateRequest,
    Transaction,
    new_id,
)
from ledgerlite.wallet.schemas import TransferRequest


def add_history(
    db: Session, account_id: str, operation_id: str, kind: str, amount: Decimal, credits: int = 0
):
    db.add(
        Transaction(
            account_id=account_id,
            operation_id=operation_id,
            kind=kind,
            usd_delta=amount,
            credits_delta=credits,
        )
    )


def ensure_capacity(account: Account, amount: Decimal):
    if account.balance + amount > MAX_MONEY:
        raise APIError(409, "balance_limit", "Recipient balance would exceed supported range")


def settle(
    db: Session, invoice_id: str, status: str, paid_amount: Decimal, event_id: str | None = None
) -> bool:
    """Caller owns transaction. All settlement sources take deposit then account locks."""
    if event_id:
        inserted = db.execute(
            insert(Event)
            .values(event_id=event_id, invoice_id=invoice_id)
            .on_conflict_do_nothing()
            .returning(Event.event_id)
        ).scalar_one_or_none()
        if inserted is None:
            return False
    deposit = db.scalar(select(Deposit).where(Deposit.invoice_id == invoice_id).with_for_update())
    if deposit is None:
        raise APIError(404, "deposit_not_found", "Deposit not found; retry delivery later")
    if deposit.status != "pending":
        return False
    if status not in {"paid", "partially_paid", "expired"}:
        raise ValueError("Settlement requires a final status")
    deposit.status, deposit.paid_amount = status, paid_amount
    if status == "expired":
        add_history(db, deposit.account_id, deposit.id, "deposit_expired", Decimal("0.00"))
        return True
    fee = provider_fee(paid_amount)
    credited = paid_amount - fee
    account = db.scalar(select(Account).where(Account.id == deposit.account_id).with_for_update())
    ensure_capacity(account, credited)
    account.balance += credited
    deposit.fee = fee
    add_history(db, account.id, deposit.id, "deposit", credited)
    return True


def transfer(db: Session, account_id: str, key: str, body: TransferRequest) -> tuple[dict, int]:
    canonical = json.dumps(body.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    request_hash = hashlib.sha256(canonical.encode()).hexdigest()
    # A conflicting insert waits for the first transaction to commit (or roll back).
    db.execute(
        insert(Idempotency)
        .values(account_id=account_id, key=key, request_hash=request_hash)
        .on_conflict_do_nothing()
    )
    record = db.get(Idempotency, (account_id, key))
    if record.request_hash != request_hash:
        raise APIError(409, "idempotency_conflict", "Key was already used with another request")
    if record.response is not None:
        return record.response, record.status_code
    to_id = str(body.to_account_id)
    # Always lock accounts in the same order, including opposite-direction transfers.
    accounts = {
        a.id: a
        for a in db.scalars(
            select(Account)
            .where(Account.id.in_([account_id, to_id]))
            .order_by(Account.id)
            .with_for_update()
        )
    }
    sender, recipient = accounts[account_id], accounts.get(to_id)
    status_code = 201
    if to_id == account_id:
        response, status_code = envelope("self_transfer", "Cannot transfer to yourself"), 422
    elif recipient is None:
        response, status_code = envelope("account_not_found", "Recipient not found"), 404
    elif sender.balance < body.amount:
        response, status_code = envelope("insufficient_funds", "Insufficient USD balance"), 409
    elif recipient.balance + body.amount > MAX_MONEY:
        response, status_code = envelope("balance_limit", "Recipient balance limit exceeded"), 409
    else:
        operation_id = new_id()
        sender.balance -= body.amount
        recipient.balance += body.amount
        add_history(db, account_id, operation_id, "transfer_out", -body.amount)
        add_history(db, to_id, operation_id, "transfer_in", body.amount)
        response = {
            "transfer_id": operation_id,
            "to_account_id": to_id,
            "amount": money_string(body.amount),
            "status": "completed",
        }
    record.response, record.status_code = response, status_code
    return response, status_code


def purchase(db: Session, account_id: str, credits: int) -> dict:
    price = credit_price(credits)
    account = db.scalar(select(Account).where(Account.id == account_id).with_for_update())
    if account.balance < price:
        raise APIError(409, "insufficient_funds", "Insufficient USD balance")
    if account.credits + credits > 9_223_372_036_854_775_807:
        raise APIError(409, "credits_limit", "Credits balance limit exceeded")
    operation_id = new_id()
    account.balance -= price
    account.credits += credits
    add_history(db, account_id, operation_id, "purchase", -price, credits)
    return {"purchase_id": operation_id, "credits": credits, "price": money_string(price)}


def check_rate_limit(db: Session, account_id: str) -> None:
    # Account lock serializes checks across workers. This transaction commits before business work.
    db.scalar(select(Account.id).where(Account.id == account_id).with_for_update())
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=60)
    db.execute(
        delete(RateRequest).where(
            RateRequest.account_id == account_id, RateRequest.created_at <= cutoff
        )
    )
    count, earliest = db.execute(
        select(func.count(), func.min(RateRequest.created_at)).where(
            RateRequest.account_id == account_id
        )
    ).one()
    if count >= 30:
        retry = max(1, math.ceil((earliest + timedelta(seconds=60) - now).total_seconds()))
        raise APIError(
            429, "rate_limited", "Maximum 30 POST requests per minute", {"Retry-After": str(retry)}
        )
    db.add(RateRequest(account_id=account_id, created_at=now))
