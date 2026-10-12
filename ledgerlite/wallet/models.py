import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="account_nonnegative_balance"),
        CheckConstraint("credits >= 0", name="account_nonnegative_credits"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    credits: Mapped[int] = mapped_column(BigInteger, default=0)


class Deposit(Base):
    __tablename__ = "deposits"
    __table_args__ = (
        CheckConstraint("amount > 0", name="deposit_positive_amount"),
        CheckConstraint("paid_amount >= 0 AND fee >= 0", name="deposit_nonnegative_payment"),
        CheckConstraint(
            "status IN ('pending','paid','partially_paid','expired')", name="deposit_status"
        ),
        Index("ix_pending_deposits", "status", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    invoice_id: Mapped[str] = mapped_column(String(128), unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    fee: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    __tablename__ = "webhook_events"
    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    invoice_id: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Idempotency(Base):
    __tablename__ = "idempotency_records"
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), primary_key=True)
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("operation_id", "account_id", name="uq_operation_account"),
        Index("ix_transactions_account_time", "account_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    operation_id: Mapped[str] = mapped_column(String(36))
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    kind: Mapped[str] = mapped_column(String(32))
    usd_delta: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    credits_delta: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RateRequest(Base):
    __tablename__ = "rate_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
