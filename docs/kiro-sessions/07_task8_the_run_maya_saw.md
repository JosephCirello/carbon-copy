# Kiro run: task 8 (the run Maya saw)

## Instructions given

```text
A bug seen on the live demo (https://carbon-copy-ywv3.onrender.com), by a human click-through. Fix it, spec first.

What happened: "Run the day" starts TWO replays side by side, one with the checker off (mode "observe") and one with it on (mode "enforce"). After Maya declined the held payment on her phone, the Carbon copy tab showed the book of the OFF run: 10 receipts, the fifth reading "Carbon Copy was off. It would have held for Maya ...". The ON run's book (11 receipts, with Maya's decline) was not shown, so "Try to change one" found no owner action and fell back to the amount change ($298.00 to $299.00) instead of telling the real lie (Maya approved the payment she declined). Locally the ON book happened to show; online the OFF run finished last. GET /api/carbon without a session picks whichever session registered last, which is a race.

Do this:
1. design.md and requirements.md (Requirement 6): the Carbon copy tab shows the book of the visitor's most recent ENFORCE run by default. When that run had an observe twin, a small switch above the receipts reads "Showing: Carbon Copy on (the run Maya saw)" with a second choice "Carbon Copy off (nothing checked it)", and the source line names which run is shown. tamper and verify act on the book that is shown.
2. app.py: GET /api/carbon and POST /api/carbon/tamper take an optional mode ("enforce" or "observe") and otherwise choose the visitor's latest enforce session, falling back to the latest session of any mode only when no enforce session exists. Remove the race: the choice must not depend on which replay finished last.
3. static/app.js: the switch, and every call passes the mode that is shown.
4. Tests in tests/test_carbon_app.py: start both replays for one visitor in either finishing order; GET /api/carbon returns the enforce book both times; after a decline, tamper on the default book returns the approved-instead-of-declined sentence; mode=observe returns the observe book.

Follow every steering file. Run .venv\Scripts\python.exe -m pytest -q until everything passes. Tick a new task 8 in tasks.md. Do not touch receipts/measure.py, receipts/rules.py or results/.
```

## What Kiro did and reported

```text
kiro-cli.exe : [INFO] [KRS] <-- GenerateAssistantResponseCommand done totalEvents=9
[tool] Run Command
[tool] status: Completed
Noisy. Let me read the relevant parts.
[tool] Run Command
[tool] status: Failed: Run Command
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
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
Use the str_replace tool for the spec edits.
[tool] Replace in File
[tool] Run Command
[tool] status: Completed
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
Case issue in my test; the behavior is right.
[tool] Run Command
[tool] status: Completed
The Carbon copy tab now shows the Carbon Copy ON run's book by default, whichever replay finishes last. All 161 tests pass. I haven't clicked through the switch in a browser; the JavaScript only passed a syntax check.
- **The race:** `GET /api/carbon` took the last session registered, which depended on which replay finished last. It now picks the visitor's latest enforce session by mode. It falls back to the latest session of any mode only when no enforce session exists.
- **Spec:** Requirement 6 has new points 6 to 8, and `design.md` has a new section "Which book the tab shows (task 8)".
- **`app.py`:** `GET /api/carbon` and `POST /api/carbon/tamper` take an optional `mode`, and any other value is a 400. A `sid` still takes precedence over `mode`. The book response also carries `mode` and `has_twin`.
- **`static/app.js` and the page:**
  - **Switch:** a switch reads "Showing: Carbon Copy on (the run Maya saw)" with a second choice "Carbon Copy off (nothing checked it)". It appears only when the visitor has a run of both modes for the same day.
  - **Source line:** it now names which run is shown.
  - **Calls:** the tamper call passes the mode that is shown. Check and download already use the book on screen.
  - **Styling:** the switch has a few lines of CSS in `static/style.css`.
- **Tests:** `tests/test_carbon_app.py` has new tests for each case in your list, in both finishing orders. They also cover the observe-only fallback and the 400 on a bad mode. After a decline, tamper on the default book returns "…says Maya APPROVED the $1,836.00 payment… She declined it."
- **`tasks.md`:** task 8 is added and ticked, with sub-tasks 8.1 to 8.4.
I didn't touch `receipts/measure.py`, `receipts/rules.py` or `results/`. `README.md` already had uncommitted edits before I started, and I left it alone.
I read "twin" as an observe run for the same scenario in the same visitor's sessions. The switch doesn't check that the two runs are a pair from the same "Run the day" click.
```
