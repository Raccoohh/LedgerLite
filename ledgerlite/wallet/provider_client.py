import httpx
from pydantic import BaseModel, Field, ValidationError

from ledgerlite.common.config import settings
from ledgerlite.common.errors import APIError
from ledgerlite.common.money import Money


class InvoiceCreated(BaseModel):
    invoice_id: str = Field(min_length=1, max_length=128)
    pay_url: str = Field(min_length=1)
    status: str


class InvoiceState(BaseModel):
    invoice_id: str
    status: str
    paid_amount: Money = Field(ge=0)


class ProviderClient:
    def request(self, method: str, path: str, **kwargs) -> dict:
        cfg = settings()
        try:
            with httpx.Client(base_url=cfg.provider_url, timeout=cfg.provider_timeout) as client:
                response = client.request(
                    method,
                    path,
                    headers={"Authorization": f"Bearer {cfg.provider_api_key}"},
                    **kwargs,
                )
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            raise APIError(504, "provider_timeout", "Provider did not respond in time") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise APIError(502, "provider_unavailable", "Provider request failed") from exc

    def create(self, deposit_id: str, amount: str) -> InvoiceCreated:
        data = self.request(
            "POST",
            "/invoices",
            json={
                "amount": amount,
                "currency": "USD",
                "external_id": deposit_id,
                "callback_url": settings().callback_url,
            },
        )
        try:
            result = InvoiceCreated.model_validate(data)
            if result.status != "pending":
                raise ValueError("New invoice must be pending")
            return result
        except (ValidationError, ValueError) as exc:
            raise APIError(502, "invalid_provider_response", "Invalid provider response") from exc

    def get(self, invoice_id: str) -> InvoiceState:
        data = self.request("GET", f"/invoices/{invoice_id}")
        try:
            result = InvoiceState.model_validate(data)
            if result.invoice_id != invoice_id or result.status not in {
                "pending",
                "paid",
                "partially_paid",
                "expired",
            }:
                raise ValueError("Invalid invoice state")
            return result
        except (ValidationError, ValueError) as exc:
            raise APIError(502, "invalid_provider_response", "Invalid provider response") from exc
