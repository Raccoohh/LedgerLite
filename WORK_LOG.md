# Work log

## 2026-10-12 - analysis and setup
- Read and visually inspected all four PDF pages, including both reference tables.
- Empty workspace; Docker Desktop and Compose available after granting engine access.
- Chosen: two FastAPI applications, sync SQLAlchemy/psycopg, PostgreSQL, Alembic.
- Core risks: duplicate settlement, concurrent overspending, idempotency races,
  ambiguous provider timeout, rounding at discount thresholds.
- Plan: infrastructure/money; provider and wallet; integration/concurrency tests;
  Compose end-to-end; review, documentation and acceptance audit.
- PDF extraction initially failed due to Windows output encoding; UTF-8 fixed it.
- No external repository publication or remote changes are authorized.

## Implementation and first checks
- Implemented Decimal money parsing, signed final-state provider invoices, wallet API,
  row-lock settlement/transfers/purchases, saved idempotency responses and history.
- Added PostgreSQL-backed rolling rate limit and reconciliation using the same settlement function.
- 34 pure financial/validation tests passed locally; lint formatting fixed.
- Dependency setup first hit sandbox cache/network restrictions; used a workspace cache,
  bundled Python 3.12 and approved dependency download. Versions locked for both OSes.
- Review found string `hmac.compare_digest` raises on non-ASCII attacker input, yielding
  500 instead of 401. Changed both comparisons to bytes and added a regression test.
- First PostgreSQL run: 76 passed, 2 failed. Concurrent transfers exposed a real
  deadlock: inserting the idempotency FK held KEY SHARE before FOR UPDATE. Replaced
  balance locks with ordered FOR NO KEY UPDATE, compatible with FK checks.
- The same run exposed stale installed code in the test image despite source mounts.
  Added PYTHONPATH=/app and pytest pythonpath so tests exercise current source.
- Added opposite-direction transfers, purchase races and webhook/reconciliation races.
  First expanded run: 82 passed, 1 test failed from missing test imports; restored imports.

## Integration, review and delivery
- Full PostgreSQL run passed 83 tests; added concurrency/key/window coverage for the rate
  limiter. Final standard image run passed 84 tests, Ruff lint/format and Alembic drift
  check. One upstream TestClient deprecation warning remains.
- Compose startup succeeded; wallet, provider and PostgreSQL healthy.
- Real HTTP smoke passed deposits, duplicate callbacks, transfer replay/conflict,
  purchase, missing-callback reconciliation, late callbacks and expiry; checked database
  balances 52.72/5.00 and 507 credits.
- Stopped only this project's provider; real wallet request returned structured 502
  and left no deposit. Restored via the final application build.
- Self-review covered lock ordering/FK compatibility, rollback, final-state guards,
  Decimal parsing, auth, callback restriction and secrets. Documented the external-invoice
  creation/DB commit gap instead of claiming a distributed transaction.
- Added English README, requirement audit and truthful AI notes.
- Local commits retain implementation and test/fix stages. No remote was configured.
- Exported committed source using git archive, generated separate local configuration,
  and built it as isolated Compose project ledgerlite-clean with a new PostgreSQL database.
  Upgrade -> downgrade -> upgrade, schema drift, Ruff and all 84 tests passed (exit 0).
- Final running application image passed the HTTP smoke and Alembic drift check again.
- Verified generated local secret values are absent from tracked files and .env is ignored.

## Authorized GitHub publication
- User explicitly approved a public repository and confirmed the browser creation step.
- Created https://github.com/Raccoohh/LedgerLite and pushed all four existing commits
  without squashing. Verified Public visibility and uploaded files.
- Scanned all four pre-publication commits for generated local secret values and .env;
  no matches. Git used the existing Raccoohh credential without exposing it.
- GitHub Actions run 38283426668 passed lint, formatting, migrations and all 84 tests.
- Updated delivery documentation and added the CI badge and clone instructions.

## 2026-10-13 - independent audit fixes (local only)
- Read the complete supplied REPORT.md and both independent test scripts. Starting HEAD
  bad674b had a clean working tree. No source changes from the audit were present.
- Reproduced all three reported failures before editing: offset overflow -> 500,
  31 malformed JSON requests -> 422 without quota use, signed NUL event ID -> 500.
- F-01: bounded offset to PostgreSQL signed bigint. F-02: a scoped APIRoute authenticates
  and counts once before body parsing; dependencies reuse the account ID and webhooks
  stay on the ordinary router. F-03: field validators reject NUL in both webhook IDs.
- Added tests/test_audit_regressions.py with 18 cases; retained all 84 original tests.
  Both source-mounted and rebuilt-image suites passed 102 tests. The original independent
  pytest file passed all 35 checks without modification. Each suite has one existing
  Starlette/HTTPX deprecation warning, no failures.
- Standard Compose test command passed migrations, drift check, lint and formatting.
  Created ledgerlite-final-verification with a new tmpfs PostgreSQL and no published
  ports; initial migrations, health checks and HTTP smoke passed. Both pytest suites
  also passed there: 102 in 4.00s and 35 in 2.00s, exit 0.
- Preserved original live_audit.py (it asserts the old broken behavior). Ran a separate
  copy with required expected statuses and extra invoice-NUL/state checks. Real HTTP
  confirmed 30 malformed 422 responses, then 429/Retry-After, webhook exemption,
  offset/NUL -> 422, successful valid retry, concurrent transfers and duplicate callbacks.
  All five audit account balances matched history deltas.
- Security review: financial services/locks and schema unchanged; validation precedes
  PostgreSQL processing; API key remains documented in OpenAPI. Scan covered five
  reachable commits, 54 distinct blobs and 42 current files for .env, exact generated
  secret values and common credential patterns: no matches (not an exhaustive guarantee).
- Developer confirmed personal contribution: supplied requirements, supervised AI work,
  initiated separate Astra High review, selected the three fixes and minimal scope;
  did not write code or manually run technical tests; personal time was not tracked.
  Rewrote AI_NOTES with those facts and the three reproduced/fixed examples.
- README and ACCEPTANCE distinguish current local verification from hosted pre-fix CI.
  No push is authorized for this fix session; hosted CI must run after a later approved push.
- Rebuilt and restarted only the main wallet service; health and OpenAPI checks passed.
  Existing provider state and the main database were preserved. Removed the temporary
  ledgerlite-final-verification stack after its successful checks.
