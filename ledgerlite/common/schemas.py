from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from ledgerlite.common.money import Money

FinalStatus = Literal["paid", "partially_paid", "expired"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Webhook(StrictModel):
    event_id: str = Field(min_length=1, max_length=128)
    invoice_id: str = Field(min_length=1, max_length=128)
    status: FinalStatus
    paid_amount: Money = Field(ge=0)
    occurred_at: AwareDatetime

    @field_validator("event_id", "invoice_id")
    @classmethod
    def reject_nul(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("Webhook identifiers must not contain NUL characters")
        return value
