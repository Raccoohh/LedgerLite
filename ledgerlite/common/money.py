import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from pydantic import BeforeValidator, PlainSerializer

CENT = Decimal("0.01")
MAX_MONEY = Decimal("999999999999.99")


def parse_money(value: object) -> Decimal:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,12}(\.[0-9]{1,2})?", value):
        raise ValueError("Money must be a decimal string with at most two decimal places")
    result = Decimal(value).quantize(CENT)
    if result > MAX_MONEY:
        raise ValueError("Money exceeds supported range")
    return result


Money = Annotated[
    Decimal,
    BeforeValidator(parse_money, json_schema_input_type=str),
    PlainSerializer(lambda v: format(v, ".2f")),
]


def provider_fee(paid: Decimal) -> Decimal:
    return (paid * Decimal("0.015")).quantize(CENT, rounding=ROUND_HALF_UP)


def credit_price(credits: int) -> Decimal:
    discount = (
        Decimal("0.125")
        if credits >= 1000
        else (Decimal("0.05") if credits >= 500 else Decimal("0"))
    )
    return (Decimal(credits) * Decimal("0.10") * (1 - discount)).quantize(
        CENT, rounding=ROUND_HALF_UP
    )


def money_string(value: Decimal) -> str:
    return format(value, ".2f")
