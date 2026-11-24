# Kiro run: task 14 (Try to change one is checked in the browser)

## Instructions given

```text
TASK 14: "TRY TO CHANGE ONE" IS CHECKED IN THE BROWSER TOO. Found while planning the demo video. Spec first (Requirement 14, design section "Task 14", task 14), then build, with tests.

What happens now: on the Carbon copy tab, "Check the book" and "Try to forge a new book" both run the check in the browser and say "Checked in your browser". "Try to change one" does not: POST /api/carbon/tamper changes one receipt in a copy of the book, runs verify() on the server, and the page prints the server's answer under an amber "Checked by the server". The pitch says the check runs on Maya's side, not ours, and the button a judge presses first contradicts it.

Make "Try to change one" work like "Try to forge a new book":
1. POST /api/carbon/tamper SHALL also return the changed copy of the book (the same shape as /api/carbon/forge's "book": public_key, head, receipts), as well as what it returns now (n, field, before, after, say, result). The real book is still never touched.
2. The page SHALL run the changed copy through checkOnDevice() (the device's stamps and pinned key, the browser's own SHA-256 and Ed25519) and show THAT result and ccWhere(...), so it says "Checked in your browser" exactly as the other two buttons do. Only when the browser has no Ed25519 does it fall back to the server, as Requirement 9.8 already says. The server's own "result" stays in the response for the command line and the tests, but the screen shows the device's.
3. The verdict a judge sees for Maya's book SHALL stay CHANGED AT #N naming the changed receipt (the receipt holding her decline). Check that the browser's check names the same receipt number and the same reason as the server's verify() for the changed copy; if they differ, that is a bug in one of them, fix it and say which.
4. Tests: the endpoint returns a book; the returned book is changed exactly at n and fails verify() with the same reason the response's result gives; the browser parity test (tests that run static/carbon_verify.js under node) checks the tampered copy too and agrees with Python on intact, the receipt number and the reason. The real book still verifies intact after the call.
5. README: if it says anywhere which buttons are checked where, make it true.

Follow every steering file. Run .venv\Scripts\python.exe -m pytest -q until everything passes. Do not touch receipts/measure.py, receipts/rules.py, results/ or render.yaml. Report what you changed, the test count, and the exact text the result area shows after pressing "Try to change one" on Maya's Tuesday book.
```

## What Kiro did and reported

```text
kiro-cli.exe : [INFO] [KRS] <-- GenerateAssistantResponseCommand done totalEvents=10
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Replace in File
[tool] status: Completed
[tool] Replace in File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
Those two tests pin the README's count wording, so I'll look at what they assert.
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
"Try to change one" is now checked in the browser, like "Try to forge a new book". The full suite passes: 347 tests, up from 345 before the README count tests were updated.
**What changed**
- **Server:** `tamper_demo()` in `receipts/carbon.py` now also returns `book`, the changed deep copy. It is `None` for an empty book. `POST /api/carbon/tamper` passes it through next to `n`, `field`, `before`, `after`, `say` and `result`. The real book is never touched. The hook check found no code path that edits, reorders or deletes a receipt in the real book.
- **Page:** the `#ccTamper` handler in `static/app.js` runs `t.book` through `checkOnDevice()`. It shows the device's verdict, the reason, and `ccWhere(...)`. Only a browser without Ed25519 falls back to the server. The server's `result` stays in the response but is no longer shown.
- **Spec:** Requirement 14, the design section "Task 14" and task 14 are in `.kiro/specs/carbon-copy/`.
- **README:** the demo walkthrough and the browser-check paragraph now say all three buttons are checked in the browser. The counts now read 14 requirements and tasks 1 to 14. I updated the two existing README-wording tests (`test_readme_is_in_line_with_task_10` and `_task_11`) to match those counts.
- **Not touched:** `receipts/measure.py`, `receipts/rules.py`, `results/` and `render.yaml`.
**Tests added**
- `tests/test_carbon_app.py`: the endpoint returns a book with the three parts. The book differs from the real one only at receipt `n`, where the decline becomes approved. `verify()` on it equals the response's `result`, and the real book still verifies intact afterwards. A second test checks that the page uses `checkOnDevice(t.book)` and never shows the server's answer.
- `tests/test_carbon_parity.py`: it runs the changed copy of a decline book under node with stamps and key, and with neither. Both runs agree with Python on `intact`, `first_bad` and `why`, and the real book stays intact.
**Browser and server agree.** For the changed copy both name the same receipt with the same reason, "its content was changed", so there was no bug to fix in either.
**Text after pressing "Try to change one" on Maya's Tuesday book**
I got this from a replay of the recorded S14 run with the decline tapped, run through the endpoint with the test client. I did not press the button in a real browser. This is the result area's content, assuming the device has the key and stamps from that run:
- Stamp: **CHANGED AT #12**
- "We changed receipt #12 in a copy of the book so it says Maya APPROVED the $1,836.00 payment to Blue Ridge Finishes. She declined it. The real book was not touched."
- "its content was changed"
- "Checked in your browser"
Receipt #12 is the one holding her decline. If the device has no stamp for the run, one extra line sits above the reason: "This device kept no stamp for this run, so it cannot tell whether the end of the book was rewritten." The verdict is the same.
```
