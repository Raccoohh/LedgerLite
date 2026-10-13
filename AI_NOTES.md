# AI usage notes

**AI tools and work.** The submitter identifies ChatGPT Astra High as the tool used for
the initial implementation and independent Senior Code Review in a separate chat.
The recorded Codex desktop session reproduced and fixed the findings, ran terminal,
Docker/PostgreSQL, pytest and Ruff checks, and edited documentation. AI wrote the
application and tests. The application itself calls no AI API.

**Human decisions and contribution.** The submitter supplied the assignment, organized
AI-assisted development, reviewed results and monitored completion. They initiated the
independent review and chose to address F-01/F-02/F-03 without unnecessary refactoring.
They did not write code, manually run technical tests or choose the implementation details.

**Three confirmed AI-code mistakes.** Independent audit checks found these defects;
each failure was reproduced before correction, then verified by regression tests and HTTP:

1. **F-01:** An unbounded history offset exceeded PostgreSQL bigint and returned 500.
   Added an upper bound of 9223372036854775807. Boundary/overflow tests now return 200/422
   as appropriate; the HTTP probe returns 422.
2. **F-02:** Authentication-dependent rate counting ran after JSON parsing, so malformed
   bodies bypassed the limiter. A wallet route wrapper now authenticates/counts once before
   parsing; the existing account dependency reuses that result. Tests and HTTP confirm
   30 malformed requests return 422, then 429 with Retry-After; webhooks remain exempt.
3. **F-03:** NUL in signed webhook identifiers reached PostgreSQL and returned 500.
   Both IDs now reject NUL during validation. Tests and HTTP confirm 422, unchanged
   financial state and a successful valid retry; no UUID-only restriction was added.

**Verification.** All 84 original tests plus 18 new regressions pass (102 total); all 35
independent checks pass. Fresh Compose/PostgreSQL, migrations, Ruff and real HTTP checks
also pass. Published commit `56cab36` passed GitHub Actions with 102 tests.

**Time.** The submitter estimates approximately 7 hours of personal involvement in
coordination, reviewing results and the audit. This is an approximate recollection,
not tracked coding/testing time. Total AI execution time was not reliably measured.
