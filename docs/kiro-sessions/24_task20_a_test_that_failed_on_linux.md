# Kiro run: task 20 (a test that failed only on GitHub's Linux runner)

## Instructions given

```text
TASK 20: ONE TEST THAT PASSES ON WINDOWS AND FAILS ON GITHUB'S LINUX RUNNER. Add task 20 to tasks.md (Requirement 15, item F13).

GitHub Actions run 45415864404 failed: tests/test_carbon_round3.py::test_f13_when_even_the_cleaned_form_fails_a_placeholder_is_sent got type "call" instead of "unshown". The test relies on json.dumps raising RecursionError on a 3,000-deep event, which happens on Windows but not on the Linux runner's Python, so the first path of app._data succeeds and the placeholder path is never reached. Make the test reach the placeholder path on every platform without depending on recursion limits (for example: an event the first json.dumps refuses on every platform, such as one holding float("nan") with allow_nan=False, while safe_json is patched to fail). Check the other tests in tests/ for the same platform dependence (any test that needs a RecursionError, a path separator, CRLF line endings, a Windows-only command or a time zone) and fix any you find the same way. Do not change app.py's behaviour.

Run .venv\Scripts\python.exe -m pytest -q until everything passes. Report what you changed.
```

## What Kiro did and reported

```text
kiro-cli.exe : [INFO] [KRS] <-- GenerateAssistantResponseCommand done totalEvents=10
[tool] Run Command
[tool] status: Completed
[tool] Read File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Completed
Those are already platform-safe. Fix the one test.
[tool] Replace in File
[tool] status: Completed
[tool] Replace in File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
The full run passes with the fix in place: 415 passed, 5 deselected. I couldn't reproduce the Linux failure here, so I haven't confirmed it on GitHub's runner.
- **The fix:** In `tests/test_carbon_round3.py`, `test_f13_when_even_the_cleaned_form_fails_a_placeholder_is_sent` now uses an event that holds `float("nan")`. The first `json.dumps(..., allow_nan=False)` in `app._data` refuses NaN on every platform, and `safe_json` is still patched to fail. That sends the event down the placeholder path, which returns type `"unshown"`. The test no longer depends on a recursion limit.
- **Other tests:** I searched `tests/` for tests that need a RecursionError, a path separator, CRLF line endings, a Windows-only command or a time zone. None needed a change.
  - The `mcp.json` path tests already normalise `\` and `/`.
  - The `render.yaml` check already normalises CRLF.
  - The subprocess tests use `sys.executable`, and the Node tests are skipped when Node is missing.
  - The other two 3,000-deep F13 tests pass whichever way `json.dumps` behaves.
- **Spec:** I added task 20 (20.1 and 20.2, Requirement 15) to `.kiro/specs/carbon-copy/tasks.md`. `app.py` is unchanged.
```
