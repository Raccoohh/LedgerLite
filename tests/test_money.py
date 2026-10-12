from decimal import Decimal

import pytest
from pydantic import ValidationError

from ledgerlite.common.money import credit_price, provider_fee
from ledgerlite.wallet.schemas import DepositRequest, PurchaseRequest


@pytest.mark.parametrize(
    "paid,fee,net",
    [
        ("10.00", "0.15", "9.85"),
        ("0.99", "0.01", "0.98"),
        ("33.33", "0.50", "32.83"),
        ("1.00", "0.02", "0.98"),
        ("0.01", "0.00", "0.01"),
    ],
)
def test_provider_fee(paid, fee, net):
    result = provider_fee(Decimal(paid))
    assert result == Decimal(fee)
    assert Decimal(paid) - result == Decimal(net)


@pytest.mark.parametrize(
    "credits,price",
    [
        (333, "33.30"),
        (507, "48.17"),
        (1005, "87.94"),
        (499, "49.90"),
        (500, "47.50"),
        (999, "94.91"),
        (1000, "87.50"),
        (1, "0.10"),
    ],
)
def test_credit_prices(credits, price):
    assert credit_price(credits) == Decimal(price)


@pytest.mark.parametrize(
    "value",
    [
        10,
        10.0,
        True,
        None,
        "1.001",
        "0",
        "-1",
        "NaN",
        "Infinity",
        "1e2",
        " 1.00",
        "1.",
        ".1",
        "1,00",
        "1000000000000.00",
    ],
)
def test_invalid_money(value):
    with pytest.raises(ValidationError):
        DepositRequest(amount=value)


@pytest.mark.parametrize("value", [0, -1, True, "500", 1.5, 1_000_000_001])
def test_invalid_credits(value):
    with pytest.raises(ValidationError):
        PurchaseRequest(credits=value)
