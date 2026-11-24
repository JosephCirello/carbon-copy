# Kiro run: task 5 (the screen)

## Instructions given

```text
Execute task 5 and its sub-tasks (5.1 to 5.3) from .kiro/specs/carbon-copy/tasks.md. First update design.md's "The screen" section with the changes below, then build.

DESIGN CHANGES (write them into design.md first):
- No drawn pictures anywhere: no wax seal image, no SVG or line-art objects. The verdict is a STAMPED WORD set in type: "INTACT" in green, or "CHANGED AT #7" (the first bad receipt) in red, rotated about -6 degrees with a double border, like a rubber stamp.
- The Halloween touch is in type and colour only: dark paper background, receipt text in a faint carbon blue, a typewriter face from Google Fonts (Special Elite for the receipts, the app's existing font for the buttons), each receipt row separated by a perforated dashed line.
- Plain words first. Each row is one sentence an owner can read, built from the event, for example: "Held for Maya: a $1,836.00 payout to Ashwood Timber Co. for INV-AT-1142. Why: PayPal already shows a payment for this bill on its way." Then the receipt number, the time, and the first 10 characters of the fingerprint. A "Developer view" toggle shows the raw receipt JSON.

THE SERVER (5.1), in app.py:
- Every Receipts object the app builds (live runs in /api/run and recorded replays in /api/replay) gets its own CarbonCopy with a Signer.from_env(), kept with the session in _sessions.
- The phone stamps returned by approve() and decline() are kept with the session and returned in the /api/approve and /api/decline responses.
- GET /api/carbon?sid=<session> returns the book plus "stamps" (the phone's stamps) and "source" ("live run" or "recorded run, replayed").
- POST /api/carbon/verify takes {"book": ..., "stamps": [...]} and returns verify(book, stamps).
- POST /api/carbon/tamper?sid=<session> returns tamper_demo(current book) and never changes the real book.
- Tests in tests/test_carbon_app.py using FastAPI's TestClient: an untouched book verifies intact; tamper says changed at the receipt it changed and the real book still verifies intact afterwards; a phone stamp round-trips.

THE SCREEN (5.2), in static/index.html, static/app.js, static/style.css:
- A sixth tab, "Carbon copy", after "Her book", with a title tooltip "Every move the AI made, sealed so nobody can quietly change it".
- It shows the current session's receipts, newest last, styled as above, with three buttons: "Check the book" (calls /api/carbon/verify and shows the stamp), "Try to change one" (calls /api/carbon/tamper and shows, in plain words, what was changed, e.g. "We changed receipt #7 from $1,836.00 to $18.36 in a copy of the book", then the red stamp naming #7), and "Download the carbon copies" (a JSON file with the book and the phone's stamps).
- On "Maya's phone", after an approve or decline, show one line: "Your phone kept stamp #N: the book had N receipts."
- When there is no run yet, the tab says: "Run Maya's day on the Watch tab first. Every move the AI makes will be copied here."

THE DOWNLOAD (5.3): the accountant's spreadsheet from "Her book" gains two columns, "Receipt #" and "Fingerprint", filled for rows from a live or replayed session that has a book, left blank for rows read from the recorded results files.

Follow every steering file. Keep all existing tests passing; run .venv\Scripts\python.exe -m pytest -q until everything passes. Then start the app (.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8091), request http://127.0.0.1:8091/ and /api/carbon once to confirm they answer, and stop it. Tick task 5 in tasks.md. Do not touch receipts/measure.py, receipts/rules.py or results/.
```

## What Kiro did and reported

```text
kiro-cli.exe : [INFO] [KRS] <-- GenerateAssistantResponseCommand done totalEvents=9
[tool] Run Command
[tool] status: Completed
[tool] Read File
[tool] Run Command
[tool] status: Completed
[tool] status: Completed
[tool] Run Command
[tool] Run Command
[tool] status: Completed
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
[tool] status: Completed
[tool] Write File
[tool] status: Completed
Clean up that clumsy assertion, then run.
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
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Completed
Now start the app, check it, and test the live ledger columns indirectly via the endpoints.
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
Task 5 and sub-tasks 5.1 to 5.3 are done and ticked in `tasks.md`. The full suite passes (145 tests). I started the app on port 8091: `/` and `/api/carbon` both answered 200, then I stopped it. I haven't looked at the new tab in a browser, so the styling is unchecked by eye.
- **design.md:** I rewrote "The screen" with your changes: the stamped word in type, type-and-colour Halloween, plain-words rows, and the Developer view toggle.
- **Server (`app.py`):**
  - Every live and replayed run gets its own `CarbonCopy` with a `Signer.from_env()`, kept in `_sessions` with its stamps and source.
  - `/api/approve` and `/api/decline` keep the phone's stamp and return it.
  - `GET /api/carbon`, `POST /api/carbon/verify` and `POST /api/carbon/tamper` are in as you specified.
  - Six new tests in `tests/test_carbon_app.py` cover an untouched book, tamper leaving the real book intact, and stamp round trips.
- **Screen:**
  - **Carbon copy tab:** the sixth tab sits after "Her book" and shows the receipts as plain sentences in Special Elite on dark paper, with dashed row separators and the rotated double-border stamp. It has the three buttons, the Developer view toggle and the empty-state message. The PayPal stand-in or sandbox is named on the tab and on each PayPal row.
  - **Maya's phone:** after an approve or decline it shows "Your phone kept stamp #N: the book had N receipts."
- **Spreadsheet download:** "Receipt #" and "Fingerprint" columns are in, and blank for rows from the recorded results files.
- **Existing test edited:** `test_a_visitor_cannot_decide_anothers_held_payment` expected the decline response to be exactly `{"declined": id}`. It now checks the `declined` key and that a stamp is present, since the response now carries the stamp.
- **Tamper wording:** it shows the real before and after values. `tamper_demo` adds 1 to an amount, so it reads "$1,836.00 to $1,837.00" rather than your "$18.36" example.
- **Replays and the spreadsheet:** the ledger never held replayed runs, so only live runs get the new columns. I didn't add replays to "Her book". Say if you want that.
- **No run yet:** `/api/carbon` without a session returns an empty book with 200, not a 404.
- **Run agent:** `receipts/agent.py` is unchanged. A live run's book is attached in `_register`, before its first event.
I didn't touch `receipts/measure.py`, `receipts/rules.py` or `results/`.
```
