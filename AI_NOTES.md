# AI usage notes

**AI work.** The developer identifies ChatGPT Astra High as the tool used for implementation
and a separate Senior Code Review chat. AI produced the services, tests and documentation.
This Codex workspace session reproduced and fixed the review findings using terminal,
Docker/PostgreSQL, pytest and Ruff. The application itself calls no AI API.

**Human contribution.** The developer supplied the assignment, organized AI-assisted work,
reviewed results and monitored completion. They initiated the independent review, read its
findings, and chose to fix F-01/F-02/F-03 while avoiding unnecessary refactoring. They
confirmed they did not write code or manually run technical tests. No additional technical
choices or manual validation are attributed to them.

**Independent audit and three actual AI-code mistakes.** The supplied report recorded
84 original tests passing and 32/35 independent checks passing. All three failures were
reproduced before correction:

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
also pass. Hosted CI for these local fixes awaits an authorized push.

**Time.** The developer did not track personal time. Earlier session notes estimated
20-25 minutes for the initial agent implementation; that excludes publication, independent
review and this fix session. No reliable end-to-end duration or human hours are claimed.
