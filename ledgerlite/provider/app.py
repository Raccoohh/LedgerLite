import asyncio
import hmac
import json
import time
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, Header
from pydantic import Field

from ledgerlite.common.config import settings
from ledgerlite.common.errors import APIError, install_errors
from ledgerlite.common.money import Money
from ledgerlite.common.schemas import FinalStatus, StrictModel
from ledgerlite.common.security import signature

app = FastAPI(title="LedgerLite Provider Mock")
install_errors(app)
invoices: dict[str, dict] = {}
lock = asyncio.Lock()


def authenticate(authorization: Annotated[str, Header()] = ""):
    if not hmac.compare_digest(authorization, "Bearer " + settings().provider_api_key):
        raise APIError(401, "unauthorized", "Invalid provider API key")


class InvoiceRequest(StrictModel):
    amount: Money = Field(gt=0)
    currency: Literal["USD"]
    external_id: str = Field(min_length=1, max_length=128)
    callback_url: str


class SimulateRequest(StrictModel):
    status: FinalStatus
    paid_amount: Money = Field(ge=0)
    deliver_webhook: bool = True
    duplicate: bool = False


def lookup(invoice_id: str) -> dict:
    if invoice_id not in invoices:
        raise APIError(404, "invoice_not_found", "Invoice not found")
    return invoices[invoice_id]


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/invoices", status_code=201, dependencies=[Depends(authenticate)])
async def create_invoice(body: InvoiceRequest):
    # An exact configured callback prevents this mock from becoming an SSRF proxy.
    if body.callback_url != settings().callback_url:
        raise APIError(422, "invalid_callback", "Use the configured wallet callback URL")
    invoice_id = "inv_" + uuid4().hex
    invoice = {
        **body.model_dump(mode="json"),
        "invoice_id": invoice_id,
        "status": "pending",
        "paid_amount": "0.00",
        "pay_url": f"{settings().provider_public_url}/pay/{invoice_id}",
    }
    async with lock:
        invoices[invoice_id] = invoice
    return invoice


@app.get("/invoices/{invoice_id}", dependencies=[Depends(authenticate)])
async def get_invoice(invoice_id: str):
    return lookup(invoice_id)


@app.post("/invoices/{invoice_id}/simulate", dependencies=[Depends(authenticate)])
async def simulate(invoice_id: str, body: SimulateRequest):
    async with lock:
        invoice = lookup(invoice_id)
        amount = body.model_dump(mode="json")["paid_amount"]
        if invoice["status"] != "pending":
            if (invoice["status"], invoice["paid_amount"]) != (body.status, amount):
                raise APIError(409, "invoice_finalized", "Final invoice state cannot change")
        else:
            invoice.update(
                status=body.status,
                paid_amount=amount,
                event_id="evt_" + uuid4().hex,
                occurred_at=datetime.now(UTC).isoformat(),
            )
        event = {
            k: invoice[k]
            for k in ("event_id", "invoice_id", "status", "paid_amount", "occurred_at")
        }
        result = dict(invoice)
    delivery: list[int | str] = []
    if body.deliver_webhook:
        raw = json.dumps(event, separators=(",", ":")).encode()
        timestamp = str(int(time.time()))
        headers = {
            "Content-Type": "application/json",
            "X-Timestamp": timestamp,
            "X-Signature": signature(settings().webhook_secret, timestamp, raw),
        }
        async with httpx.AsyncClient(timeout=settings().provider_timeout) as client:
            for _ in range(2 if body.duplicate else 1):
                try:
                    response = await client.post(
                        invoice["callback_url"], content=raw, headers=headers
                    )
                    delivery.append(response.status_code)
                except httpx.RequestError:
                    delivery.append("unavailable")
    return {**result, "webhook_delivery": delivery}
