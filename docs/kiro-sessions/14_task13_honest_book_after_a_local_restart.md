# Kiro run: task 13 (a honest book after a local restart)

## Instructions given

```text
TASK 13: A HONEST BOOK AFTER A LOCAL RESTART. Found by a human click-through. Spec first (Requirement 13, task 13), then build, with tests.

What happens: run the app locally without CARBON_COPY_KEY, run Maya's day, restart the server, run the day again. The server now signs with a new temporary key; the browser still trusts the first one (localStorage), so "Check the book" on an honest book says CHANGED, "it was signed with a different key than the one your device trusts", with no explanation. A judge trying the app on their own machine will hit this. The hosted demo has a fixed key and does not.

Keep the verdict exactly as it is (a key change must never be excused automatically: an attacker could claim a restart). Add the explanation and the way out:
1. GET /api/carbon/key already says temporary true or false. When the book's key differs from the device's pinned key AND the server says its key is temporary, show under the verdict, in plain words: "This server makes a new temporary signing key every time it starts. If you restarted it yourself, that is why the key changed: press 'Forget what this device trusts' and run the day again. The hosted demo uses a fixed key, so this never happens there." When the server's key is NOT temporary, show nothing extra (a fixed key that changed is exactly what the check is for).
2. The footer's "Signing key: temporary (changes on restart)" stays.
3. README, "Try it" on your machine: one line before the run commands: set a fixed key so restarts do not change it, e.g. PowerShell `$env:CARBON_COPY_KEY = "any phrase you like"` and macOS/Linux `export CARBON_COPY_KEY="any phrase you like"`, with one sentence on why.
4. Tests: the explanation appears for a temporary key and does not for a fixed one (test the function that decides, and the endpoint values it uses).

Follow every steering file. Run .venv\Scripts\python.exe -m pytest -q until everything passes. Do not touch receipts/measure.py, receipts/rules.py, results/ or render.yaml.
```

## What Kiro did and reported

```text
kiro-cli.exe : [INFO] [KRS] <-- GenerateAssistantResponseCommand done totalEvents=10
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
Too noisy. Let me look at specific pieces.
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Completed
Now the code.
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
Task 13 is built and the full suite passes (344 tests).
- **Spec:** I added Requirement 13, a "Task 13" design section and task 13 to `.kiro/specs/carbon-copy/`, before the code.
- **Deciding function:** `restart_note(book_key, trusted_key, temporary)` is in `receipts/carbon.py`, with an identical `restartNote` in `static/carbon_verify.js`. It is plain code. It returns your explanation only when the server key is temporary, the device already trusts a key, and the book's key differs (case-insensitive). Otherwise it returns nothing. `verify()` is unchanged, so the verdict still says CHANGED for any key change.
- **Screen:** after "Check the book" gives a CHANGED verdict, the page reads `/api/carbon/key`. It shows the note under the verdict if the server's key is temporary, and shows nothing for a fixed key. If that request fails, it shows nothing. The footer's "Signing key: temporary (changes on restart)" is untouched. I bumped the script version strings in `static/index.html` so browsers pick up the new files.
- **README:** "Try it" now has the fixed-key line before the run commands. It gives the PowerShell `$env:CARBON_COPY_KEY = "any phrase you like"` and the macOS/Linux `export` forms, plus one sentence on why.
- **Tests:** `tests/test_carbon_restart.py` covers these cases:
  - Temporary key: the note appears.
  - Fixed key, matching key, or no trusted key: no note.
  - The verdict is unchanged.
  - `/api/carbon/key` returns the `temporary` value for both key kinds.
  - The JavaScript function gives the same answers as the Python one, run under node.
I didn't test the new note in a browser. The Python function, the endpoint values and the JavaScript function are tested, but the page code that shows the note is not.
The note is tied only to your three conditions. A forged book signed with a different key from a temporary-key server would also show it. It is only text, and the verdict still says CHANGED. If you want it limited to books signed with the server's current key, that is a small change.
I did not touch `receipts/measure.py`, `receipts/rules.py`, `results/` or `render.yaml`.
```
