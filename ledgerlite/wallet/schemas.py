from uuid import UUID

from pydantic import Field, StrictInt

from ledgerlite.common.money import Money
from ledgerlite.common.schemas import StrictModel


class DepositRequest(StrictModel):
    amount: Money = Field(gt=0)


class TransferRequest(DepositRequest):
    to_account_id: UUID


class PurchaseRequest(StrictModel):
    credits: StrictInt = Field(gt=0, le=1_000_000_000)
