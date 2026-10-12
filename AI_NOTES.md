# AI usage notes

**Tools and ownership.** OpenAI Codex in the desktop app read the four-page assignment,
implemented the Python services, migrations, tests, Compose/CI and documentation, and ran
Ruff, pytest and real Docker/HTTP checks. PDF extraction/rendering and terminal tools were
used; no external AI API was called by the application. No subagents were used.

**Human decisions.** The user supplied the assignment and detailed engineering brief,
selected the LedgerLite workspace, made Docker/VS Code available, and initially required
local work, then explicitly approved public GitHub publication. Implementation choices were
made by Codex. No claim
is made that a human independently designed or reviewed those choices. The submitter
should add their own actual review decisions before delivery.

**Real mistakes and corrections.**

1. The initial transfer code inserted an idempotency row (taking an account FK KEY SHARE
   lock), then used FOR UPDATE for balances. The PostgreSQL concurrent-spending test failed
   with a deadlock. Ordered FOR NO KEY UPDATE locks fixed the conflict while preserving
   exclusive balance mutation; overspending and opposite-direction tests passed.
2. String-based hmac.compare_digest raised TypeError on non-ASCII signature input,
   potentially returning 500 instead of 401. Code review identified it and a regression
   test demonstrated the failure against the original image. Both authentication
   comparisons now use bytes; the regression passes.
3. The initial container could import the installed package instead of newly mounted
   source during pytest. Tracebacks revealed stale code despite the local signature fix.
   Explicit PYTHONPATH and pytest source-path configuration fixed the test environment;
   the final standard image was rebuilt and tested without source mounts.
4. After adding the reconciliation race test, two imports previously removed as unused
   were missing. Ruff and pytest caught the NameError; imports were restored and the
   complete suite rerun. No failing tests were removed to obtain a green result.

**Time and limits.** Approximately 20-25 minutes of agent execution, including document
review, setup, implementation and verification on 12 October 2026. Human time was not
measured. The first recorded setup timestamp was 19:15 EEST. Subsequent publication and CI
verification were separate follow-up work. The public repository and hosted GitHub Actions
have now been verified; all 84 tests passed on GitHub.
