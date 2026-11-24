# Kiro run: fix: a book through a browser

## Instructions given

```text
A FALSE ALARM IN THE HEADLINE FEATURE. Fix it, spec first.

What happened: in the running app, an untouched book was sent from the server to the browser (GET /api/carbon) and posted straight back to POST /api/carbon/verify. The check answered "CHANGED AT #5: its content was changed". Receipt 5 is a verdict whose event holds "amount": 1836.0 (a Python float). The browser's JSON.parse and JSON.stringify turn 1836.0 into 1836, so the server re-computes the fingerprint over canonical(...) containing 1836 where it was signed over 1836.0. Same number, different bytes, so the fingerprint differs. The command-line checker passed only because a Python-to-file-to-Python trip keeps 1836.0. This breaks money-rules.md rule 5 ("Same input, same fingerprint... float formatting... is a bug").

Do this, in order:
1. requirements.md, Requirement 2: add "THE fingerprint SHALL be the same after the book passes through any standard JSON reader and writer, including a web browser's, which writes a whole-number float such as 1836.0 as 1836."
2. design.md: canonical() first normalises the value: every float with no fractional part becomes an int, recursively through dicts and lists; tuples become lists; anything else JSON cannot hold goes through str as before. append() stores the NORMALISED event (what is hashed is exactly what is stored and handed out), and verify() normalises before hashing too, so books signed before this change still check out when they hold no whole-number floats.
3. receipts/carbon.py: implement it.
4. tests/test_carbon.py: a test that builds a book whose event holds 1836.0 and 298.5, passes it through a browser-like round trip (json.loads of json.dumps, then replace every whole-number float with an int, recursively) and verifies intact; a hypothesis property that any generated book survives that browser-like round trip and still verifies intact; and a test in tests/test_carbon_app.py that GETs /api/carbon after a run, applies the same browser-like transform, POSTs it to /api/carbon/verify and gets intact.
5. The command-line checker must also read a book saved with a UTF-8 byte-order mark (Windows PowerShell 5.1 and Notepad write one): open with encoding "utf-8-sig". Add a test.

Follow every steering file. Run .venv\Scripts\python.exe -m pytest -q until everything passes. Do not change receipts/measure.py, receipts/rules.py or results/.
```

## What Kiro did and reported

```text
kiro-cli.exe : [INFO] [KRS] <-- GenerateAssistantResponseCommand done totalEvents=9
[tool] Run Command
[tool] status: Completed
[tool] Read File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Replace in File
Oops, stray heredoc. Redo with the edit tools.
[tool] Read File
[tool] status: Completed
[tool] status: Completed
[tool] Replace in File
[tool] status: Completed
[tool] Replace in File
[tool] status: Completed
[tool] Replace in File
[tool] Replace in File
[tool] Replace in File
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
The false alarm is fixed. All 150 tests pass with `.venv\Scripts\python.exe -m pytest -q`. I did not run the new app test against the old code, so I haven't seen it fail without the fix. I also didn't check that the replayed book it uses holds a whole-number float.
**Spec**
- `requirements.md`: Requirement 2 now has item 4, which says the fingerprint stays the same after a trip through any standard JSON reader and writer, including a browser's.
- `design.md`: it now describes the normalising `canonical()`, the normalised event that `append()` stores, `verify()` normalising before it hashes, and the `utf-8-sig` reading in the command-line checker.
**Code (`receipts/carbon.py`)**
- A new `normalise()` turns every whole-number float into an int, recursively through dicts and lists. Tuples become lists. `canonical()` calls it first, so `verify()` gets the same behaviour without further changes.
- `append()` stores the normalised event, so what is hashed is exactly what is stored and handed out.
- The command-line checker opens the book and the stamps file as `utf-8-sig`.
- Books signed before this change still check out as long as they hold no whole-number floats.
- I did not touch `measure.py`, `rules.py` or `results/`.
**Tests**
- `tests/test_carbon.py`:
  - A book whose event holds 1836.0 and 298.5 verifies intact after a browser-like round trip.
  - `canonical()` gives the same bytes for 1836 and 1836.0.
  - A hypothesis property checks that any generated book survives that round trip.
  - A byte-order-mark test runs the command-line checker on a book written with a BOM.
- `tests/test_carbon_app.py`: the app test GETs `/api/carbon` after a replayed run, applies the browser-like transform and POSTs the result to `/api/carbon/verify`. It expects intact.
```
