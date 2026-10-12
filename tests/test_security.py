import time

import pytest

from ledgerlite.common.security import signature, valid_signature


@pytest.mark.parametrize("timestamp", ["", "bad", "1.0", "-1", "9" * 100, "１２３"])
def test_invalid_timestamps(timestamp):
    assert not valid_signature("secret", timestamp, b"body", "bad")


def test_non_ascii_signature_is_invalid():
    assert not valid_signature("secret", str(int(time.time())), b"body", "sha256=помилка")


def test_fresh_signature():
    timestamp = str(int(time.time()))
    assert valid_signature(
        "secret", timestamp, b"raw body", signature("secret", timestamp, b"raw body")
    )
