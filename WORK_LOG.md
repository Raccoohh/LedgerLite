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
