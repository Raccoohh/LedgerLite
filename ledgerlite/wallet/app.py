from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ledgerlite.common.config import settings
from ledgerlite.common.errors import APIError, install_errors
from ledgerlite.common.money import money_string
from ledgerlite.common.schemas import Webhook
from ledgerlite.common.security import key_hash, valid_signature
from ledgerlite.wallet.db import engine, session
from ledgerlite.wallet.models import Account, Deposit, Transaction, new_id
from ledgerlite.wallet.provider_client import ProviderClient
from ledgerlite.wallet.schemas import DepositRequest, PurchaseRequest, TransferRequest
from ledgerlite.wallet.services import check_rate_limit, purchase, settle, transfer

app = FastAPI(title="LedgerLite Wallet")
install_errors(app)
DB = Annotated[Session, Depends(session)]


def authenticate(request: Request, x_api_key: str) -> str:
    with Session(engine()) as db, db.begin():
        account_id = db.scalar(
            select(Account.id).where(Account.api_key_hash == key_hash(x_api_key))
        )
        if account_id is None:
            raise APIError(401, "unauthorized", "Invalid API key")
        if request.method == "POST" and settings().rate_limit_enabled:
            check_rate_limit(db, account_id)
        return account_id


class AuthenticatedRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def authenticated_handler(request: Request) -> Response:
            # Authenticate/count exactly once, before FastAPI parses even malformed JSON.
            request.state.account_id = await run_in_threadpool(
                authenticate, request, request.headers.get("X-API-Key", "")
            )
            return await handler(request)

        return authenticated_handler


def current_account(request: Request, x_api_key: Annotated[str, Header()] = "") -> str:
    # Keep the API-key header in OpenAPI; the route has already authenticated it.
    return request.state.account_id


wallet_routes = APIRouter(route_class=AuthenticatedRoute)
User = Annotated[str, Depends(current_account)]
Provider = Annotated[ProviderClient, Depends(ProviderClient)]


@app.get("/health")
def health(db: DB):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@wallet_routes.get("/v1/accounts/me")
def me(account_id: User, db: DB):
    account = db.get(Account, account_id)
    return {
        "account_id": account.id,
        "name": account.name,
        "usd_balance": money_string(account.balance),
        "credits_balance": account.credits,
    }


@wallet_routes.post("/v1/deposits", status_code=201)
def create_deposit(body: DepositRequest, account_id: User, db: DB, provider: Provider):
    deposit_id = new_id()
    invoice = provider.create(deposit_id, money_string(body.amount))
    with db.begin():
        db.add(
            Deposit(
                id=deposit_id,
                account_id=account_id,
                invoice_id=invoice.invoice_id,
                amount=body.amount,
            )
        )
    return {
        "deposit_id": deposit_id,
        "invoice_id": invoice.invoice_id,
        "status": "pending",
        "pay_url": invoice.pay_url,
    }


def process_webhook(event: Webhook) -> bool:
    with Session(engine()) as db, db.begin():
        return settle(db, event.invoice_id, event.status, event.paid_amount, event.event_id)


@app.post("/v1/webhooks/provider")
async def webhook(request: Request):
    raw = await request.body()
    if not valid_signature(
        settings().webhook_secret,
        request.headers.get("X-Timestamp", ""),
        raw,
        request.headers.get("X-Signature", ""),
    ):
        raise APIError(401, "invalid_signature", "Invalid signature or stale timestamp")
    try:
        event = Webhook.model_validate_json(raw)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    changed = await run_in_threadpool(process_webhook, event)
    return {"status": "accepted", "applied": changed}


@wallet_routes.post("/v1/transfers")
def create_transfer(
    body: TransferRequest,
    account_id: User,
    db: DB,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=128)],
):
    with db.begin():
        response, status = transfer(db, account_id, idempotency_key, body)
    return JSONResponse(response, status)


@wallet_routes.post("/v1/purchases", status_code=201)
def create_purchase(body: PurchaseRequest, account_id: User, db: DB):
    with db.begin():
        return purchase(db, account_id, body.credits)


@wallet_routes.get("/v1/transactions")
def transactions(
    account_id: User,
    db: DB,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=2**63 - 1)] = 0,
):
    query = select(Transaction).where(Transaction.account_id == account_id)
    rows = db.scalars(
        query.order_by(Transaction.created_at.desc(), Transaction.id.desc())
        .limit(limit)
        .offset(offset)
    )
    total = db.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.account_id == account_id)
    )
    return {
        "items": [
            {
                "id": row.id,
                "operation_id": row.operation_id,
                "kind": row.kind,
                "usd_delta": money_string(row.usd_delta),
                "credits_delta": row.credits_delta,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
        "limit": limit,
        "offset": offset,
        "total": total,
    }


# Health and provider webhooks intentionally use the ordinary, unauthenticated router.
app.include_router(wallet_routes)
