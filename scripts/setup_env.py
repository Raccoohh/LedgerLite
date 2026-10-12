"""Generate local secrets without overwriting existing configuration or printing secrets."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".env"
if target.exists():
    raise SystemExit(".env already exists; preserved existing configuration")
with target.open("x", encoding="utf-8") as file:
    for name in ("POSTGRES_PASSWORD", "PROVIDER_API_KEY", "WEBHOOK_SECRET"):
        file.write(f"{name}={secrets.token_hex(32)}\n")
    file.write("PROVIDER_TIMEOUT=5\nRATE_LIMIT_ENABLED=true\n")
print("Created .env with random local secrets. Do not commit it.")
