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
