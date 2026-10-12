# Acceptance checklist

Statuses will be updated only after verification. Mandatory unless marked optional.

| Requirement | Evidence / status |
| --- | --- |
| Provider create/read/simulate; final states; duplicate/missing webhook | NOT VERIFIED |
| Bearer authentication; HMAC over timestamp + dot + raw bytes | NOT VERIFIED |
| Hashed wallet keys; account balances | NOT VERIFIED |
| Pending deposits; provider timeouts and failures | NOT VERIFIED |
| Signature/freshness 401; event deduplication; atomic settlement | NOT VERIFIED |
| Finalized deposits immutable; partial payment; expiry | NOT VERIFIED |
| Transfers: required scoped idempotency, replay, conflict | NOT VERIFIED |
| Concurrent transfers; no negative balances; atomic history | NOT VERIFIED |
| Credit pricing and atomic purchase | NOT VERIFIED |
| Paginated history; consistent error envelope | NOT VERIFIED |
| String money validation; Decimal; six reference values | NOT VERIFIED |
| PostgreSQL constraints and migrations | NOT VERIFIED |
| Compose startup; configuration; no tracked secrets | NOT VERIFIED |
| Pytest and Ruff; PostgreSQL GitHub Actions | NOT VERIFIED |
| README, AI notes, unsquashed local commit history | NOT VERIFIED |
| Optional: reconciliation sharing settlement logic | NOT VERIFIED |
| Optional: 30 POST/min/key with Retry-After, webhook exempt | NOT VERIFIED |
