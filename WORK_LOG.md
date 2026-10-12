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
