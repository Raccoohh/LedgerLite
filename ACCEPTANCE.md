# Acceptance audit - 2026-10-12

The four-page assignment is the source of requirements. PASS means implemented and
checked using the named evidence; remote hosting claims are explicitly excluded.

| Requirement | Status | Evidence |
| --- | --- | --- |
| Provider POST/GET invoices, simulate, final states | PASS | Provider tests (all three states); real HTTP smoke |
| Duplicate and missing callbacks, stable event ID | PASS | Signed duplicate delivery, provider retry tests, smoke |
| Provider bearer authentication | PASS | Provider auth test; real HTTP unauthorized request |
| HMAC-SHA256 over timestamp + dot + raw body | PASS | Signature tests, provider delivery verification, raw-body tamper test |
| Five-minute freshness; invalid signature gets 401 | PASS | Stale/future/invalid signature and malformed timestamp tests |
| Hashed wallet keys; USD and credits balances | PASS | Account/auth test, source inspection, smoke |
| Deposit returns pay_url and persists pending | PASS | Create-deposit test; real HTTP deposit |
| Provider timeouts and understandable errors | PASS | Injected HTTPX timeout -> 504 and connect error -> 502; stopped container -> 502, no deposit |
| Duplicate event, final-state guard, atomic credit | PASS | Duplicate/finalized tests; eight concurrent callbacks; rollback injection |
| Partial payment minus fee; expiry without credit | PASS | Parameterized settlement tests; smoke and DB assertions |
| Required user-scoped transfer idempotency | PASS | Required header, replay/conflict, scoped-key and saved-error tests |
| Concurrent same key, including different payloads | PASS | Concurrent same-key tests; exactly one operation |
| Atomic transfers; no negative balances; lock order | PASS | Overspending, 12 opposite-direction transfers, direct DB constraint, rollback tests |
| Atomic credit purchase and discounts | PASS | Reference/boundary prices, purchase/history, eight concurrent purchases |
| Per-user paginated history | PASS | Pagination/isolation test; successful operations record history |
| Unified errors and correct HTTP codes | PASS | Shared handlers; validation/auth/conflict/provider/500 rollback checks |
| String money; <=2 decimal places; Decimal; HALF_UP | PASS | 34 money/validation cases plus API malformed-money tests; OpenAPI string schema inspected |
| PostgreSQL and versioned migrations | PASS | PostgreSQL 16 tests; clean database upgrade/downgrade/upgrade and alembic check |
| Compose starts both services and database | PASS | docker compose up --build -d --wait; three services healthy |
| Environment configuration; no tracked local secrets | PASS | Environment example, random setup script, gitignore and secret-value scan |
| pytest and lint with PostgreSQL | PASS | Standard image and clean Git archive: 84 passed; Ruff lint/format clean |
| GitHub Actions configuration | PASS (local equivalent) | Workflow installs lock, lints, migrates and runs PostgreSQL tests |
| Hosted GitHub Actions execution | NOT VERIFIED | Repository not published; requires the user's chosen remote |
| README commands, diagram, decisions, limitations | PASS | Reviewed against successful commands and implementation |
| AI_NOTES <=1 page, actual mistakes, human role, time | PASS | Concise account of observed errors; no invented human decisions |
| Unsquashed local commits | PASS | Implementation, tests/fixes and documentation commits |
| Repository access for reviewers | NOT DONE | Publication explicitly awaits user authorization |
| Optional reconciliation | PASS | Old pending polling, concurrent webhook race, lost callback HTTP smoke |
| Optional 30 POST/min/key; 429 Retry-After; webhook exempt | PASS | Limit, concurrency, per-key isolation, window expiry and exemption tests |

The smoke leaves uniquely named demo accounts. Expected final balances are 52.72 USD /
507 credits and 5.00 USD / 0 credits. One upstream Starlette/HTTPX deprecation warning
is present in pytest and documented in README.

Timeout handling uses controlled transport failure injection; real network unavailability
and successful callback delivery were separately exercised with containers.
Database-sensitive tests never use SQLite or mocked transactions.
