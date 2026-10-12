from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

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
