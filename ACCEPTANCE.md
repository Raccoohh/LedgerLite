# Acceptance audit - 2026-10-13 (post-review fixes)

The four-page assignment is the source of requirements. PASS means implemented and
checked using the named evidence, not a claim that every possible input was tested.
F-01, F-02 and F-03 from the independent review were reproduced before changes and fixed.
This document distinguishes current local verification from the older published commit.

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
| Per-user paginated history | PASS | Pagination/isolation; offset 0/max accepted, negative/max+1/100-digit rejected with 422 (F-01) |
| Error envelope and tested HTTP codes | PASS | Auth/conflict/provider/rollback cases; oversized offset and signed NUL in either ID now return 422 (F-01/F-03) |
| Invalid webhook identifiers do not mutate state | PASS | NUL at start/middle/end of both IDs; DB processing not called, balance/deposit/history/events unchanged; valid retry settles once |
| String money; <=2 decimal places; Decimal; HALF_UP | PASS | 34 money/validation cases plus API malformed-money tests; OpenAPI string schema inspected |
| PostgreSQL and versioned migrations | PASS | Fresh isolated PostgreSQL 16: upgrade to 69cc5928ace9, alembic current/check; no schema changes required |
| Compose starts both services and database | PASS | Fresh ledgerlite-final-verification stack: up -d --wait, services healthy, HTTP smoke and live audit passed |
| Environment configuration; no detected tracked secrets | PASS (bounded scan) | Ignored .env; exact local secrets and common credential patterns checked in reachable commits and pending source; not a universal secret guarantee |
| pytest and lint with PostgreSQL | PASS | Built image on fresh database: 102 main tests (84 original + 18 new), 35 independent checks; Ruff lint/format clean |
| GitHub Actions configuration | PASS | Workflow installs lock, lints, migrates and runs PostgreSQL tests |
| Hosted GitHub Actions for pre-fix bad674b | PASS (historical) | [Run 38283614583](https://github.com/Raccoohh/LedgerLite/actions/runs/38283614583): lint, formatting, migrations and 84 tests |
| Hosted GitHub Actions for post-review fixes | NOT VERIFIED | Local checks pass; no push authorized in the fix request |
| README commands, diagram, decisions, limitations | PASS | Reviewed against successful commands and implementation |
| AI_NOTES content and length | PASS (content) | Concise note with three reproduced/fixed defects, user-confirmed human role and explicitly unmeasured personal time; Markdown has no fixed pagination |
| Unsquashed local commits | PASS | Implementation, tests/fixes and documentation commits |
| Repository access for reviewers | PASS (pre-fix version) | [Public repository](https://github.com/Raccoohh/LedgerLite); fixed commit still requires authorized push |
| Optional reconciliation | PASS | Old pending polling, concurrent webhook race, lost callback HTTP smoke |
| Optional 30 POST/min/key; 429 Retry-After; webhook exempt | PASS | Malformed bodies on all three POST routes, mixed valid/invalid bodies, exactly-once counting, concurrency, key/window isolation and webhook exemption (F-02) |

The smoke leaves uniquely named demo accounts. Expected final balances are 52.72 USD /
507 credits and 5.00 USD / 0 credits. One upstream Starlette/HTTPX deprecation warning
is present in pytest and documented in README.

Timeout handling uses controlled transport failure injection; real network unavailability
and successful callback delivery were separately exercised with containers.
Database-sensitive tests never use SQLite or mocked transactions.

## Post-review evidence

- Before changes, the three targeted independent regressions failed exactly as reported:
  offset 500, all 31 malformed bodies 422, signed NUL event ID 500.
- `docker compose --profile test run --build --rm tests`: 102 passed, 1 existing warning;
  migrations/drift check and Ruff lint/format passed.
- Unmodified `tmp/independent_audit/test_independent.py`: 35 passed, 1 existing warning.
- Fresh stack config: `tmp/final_verification/compose.yml` (test-only credentials, tmpfs DB,
  no published ports). Both test suites also passed against this new database.
- HTTP smoke passed deposit, duplicates, transfers/replays, purchase, reconciliation and expiry.
- Original live-audit script preserved. A copy in `tmp/final_verification/live_audit_fixed.py`
  replaces expectations for the three known bugs with the required behavior and adds NUL
  invoice/state checks: 30 malformed bodies -> 422, 31st/next -> 429 + Retry-After; oversized
  offset -> 422; both NUL IDs -> 422; valid retry -> 200. Concurrent financial cases and
  all five accounts' history/balance invariants still pass.
- Audit helpers remain gitignored; all three defect regressions are in the committed main suite.
- No new failures observed. Existing documented limitations and TestClient warning remain.
