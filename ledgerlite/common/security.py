import hashlib
import hmac
import re
import time


def key_hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def signature(secret: str, timestamp: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256)
    return "sha256=" + digest.hexdigest()


def valid_signature(secret: str, timestamp: str, body: bytes, supplied: str) -> bool:
    if not re.fullmatch(r"[0-9]{1,12}", timestamp):
        return False
    if abs(time.time() - int(timestamp)) > 300:
        return False
    return hmac.compare_digest(signature(secret, timestamp, body).encode(), supplied.encode())
