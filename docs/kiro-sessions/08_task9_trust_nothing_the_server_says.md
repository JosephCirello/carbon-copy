# Kiro run: task 9 (trust nothing the server says)

## Instructions given

```text
TASK 9: TRUST NOTHING THE SERVER SAYS. Two independent attack reviews broke the headline claim. Every finding below was proven with a script. Fix them SPEC FIRST: add Requirement 9 ("The check does not trust the server") and update design.md and tasks.md (task 9 with sub-tasks), then build. Keep every existing test passing; add a test for every finding.

THE FINDINGS
F1. verify() checks signatures against whatever public_key the book carries, and the server makes a fresh key every run (no CARBON_COPY_KEY on Render). A book re-signed under a NEW key with Maya's decline flipped to "approved" reads intact.
F2. The "phone stamp" lives in the server session; the browser keeps only stamp.count, in memory. Check the book and Download send the stamps the SERVER returns. verify never checks a stamp's signature (sig "AAAA" is accepted). Rewrites after the last stamp are not caught.
F3. "Check the book" posts the book to the server, which can answer anything. Requirement 6.2 already says the check should run in the browser's own request.
F4. Agent-written content breaks the record: a lone surrogate (e.g. "\ud83d") in reply_to_customer's body sends the email and then the receipt write raises UnicodeEncodeError, so an action happens with no receipt; NaN or Infinity makes GET /api/carbon fail (Starlette refuses them); integers beyond 2**53 (e.g. 9007199254740993) and the float 2**60 come back changed after a browser JSON round trip, so an honest book reads CHANGED.
F5. A malformed stamp (count 5.0, count "5", a JSON string instead of an object) is skipped silently, so a cut-back book reads intact. The docstring says a false stamp fails closed.
F6. The wrong reason: a changed receipt inside the stamped part is reported as "the book is shorter than a stamp the owner's phone already holds" even when the book is the same length.
F7. The CLI exits 1 both for "changed" and for "could not read the file" (a traceback).
F8. default=str hashes Decimal, datetime, set and bytes one way and sends them another; not reached today, a trap for later.
F9. The fingerprint recipe is not reproducible outside this Python code (float exponent formats, key order for astral characters), so "anyone can check it" is only true with our checker.

THE DESIGN TO BUILD
D1. ONE CANONICAL FORM THAT ANY JSON TOOL REPRODUCES. At append time the event is cleaned into a "safe JSON" form and that cleaned form is what is stored, hashed and handed out: dict keys and strings with lone surrogates replaced by U+FFFD; integers kept only when abs(n) <= 2**53 - 1, otherwise written as their decimal string; floats that are whole and within that range become ints; every other float (including NaN, Infinity, 298.5) becomes the string Python's repr gives; tuples become lists; any other type (Decimal, datetime, set, bytes, objects) becomes str(value) explicitly at clean time, so nothing reaches json.dumps that it would not handle; keys are sorted by Unicode code point. canonical() = json.dumps(cleaned, sort_keys=True, separators=(",", ":"), ensure_ascii=False). With only strings, safe integers, booleans, null, lists and dicts, the browser's JSON.stringify with code-point-sorted keys gives the same bytes. Write this rule into the design word for word.
D2. A FIXED, PUBLISHED KEY. Signer.from_env() accepts any CARBON_COPY_KEY string: if it is 64 hex characters it is the seed as now; otherwise the seed is SHA-256 of the UTF-8 string (so Render's generated random value works). GET /api/carbon/key returns the public key and a short form (first 16 hex). The page footer prints "Signing key: <short form>" with a link to the full key. When no key is set the app still generates one in memory and the footer says "Signing key: temporary (changes on restart)".
D3. THE OWNER'S DEVICE PINS THE KEY AND KEEPS THE STAMPS. In the browser (static/app.js), the first time the visitor's device receives a stamp it stores the full public key in localStorage as the pinned key ("trust on first use"), and every stamp it receives is stored whole (count, last_fp, sig, public_key) in localStorage, kept per run. Stamps arrive not only on approve and decline but also with every event the browser receives during a run: the SSE stream carries the book's signed head with each event, so the device holds a stamp for every moment it saw. Wrap every localStorage access in try/catch; with storage unavailable it keeps them in memory and the screen says so.
D4. THE CHECK RUNS IN THE BROWSER. A new static/carbon_verify.js implements verify(book, stamps, pinnedKey) in the browser: the same canonical form, SHA-256 via crypto.subtle, Ed25519 via crypto.subtle.verify. "Check the book" runs it locally against the book, the DEVICE's stamps and the DEVICE's pinned key, and shows "Checked in your browser" under the stamp. If the browser has no Ed25519 in WebCrypto, say so on screen and fall back to the server's /api/carbon/verify with the device's stamps and pinned key, labelled "Checked by the server". The Python verify gains expected_key: a book whose public_key differs from expected_key is changed with the reason "it was signed with a different key than the one your device trusts". Each stamp's signature is checked against the expected key (or the book's key when none is given); a stamp that is malformed or whose signature fails makes the result changed with the reason "a stamp on your device is damaged or forged". A stamp whose position exists but whose last_fp does not match is changed with the reason "receipt #N no longer matches the stamp your device kept"; only a stamp whose count is beyond the book's end uses "the book is shorter than a stamp your device already holds".
D5. A PARITY TEST. tests/test_carbon_parity.py: if node is on PATH, write a book with tricky content (unicode, astral keys, 298.5, 2**60, 9007199254740993, NaN, a lone surrogate, nested lists) through Receipts with the book attached, then run static/carbon_verify.js under node (export the functions so node can require them; node has crypto.subtle) and assert it says intact on the untouched book and names the right receipt on a changed copy. Skip the test with a clear message if node is absent.
D6. THE CLI: exit 0 intact, 1 changed, 2 could not read the file (a plain message, never a traceback); --key <hex> pins the expected key; --stamps as now.
D7. THE DEMO SHOWS THE REAL ATTACK. Beside "Try to change one", add "Try to forge a new book": the server builds a copy of the book with Maya's decline flipped to approved and every receipt re-signed with a brand-new key, sends it to the browser, and the browser's own check rejects it, naming the reason (a different key than the one your device trusts). Plain words on screen: "We rewrote the whole book so it says Maya approved the payment, and re-sealed every page with a new key. Your device still holds the key it trusted and the stamps it saw, so the forgery is caught."
D8. README "Limits we know about": say plainly that the device must have seen the key first (trust on first use), that anything after the last stamp the device saw can still be rewritten by whoever holds the key, and that the check proves the book was not changed, not that what was written was true.

Follow every steering file. Run .venv\Scripts\python.exe -m pytest -q until everything passes, then start the app (PAYPAL_MODE=standin), load / and /api/carbon/key once to confirm they answer, and stop it. Do not touch receipts/measure.py, receipts/rules.py or results/. Do not change render.yaml.
```

## What Kiro did and reported

```text
kiro-cli.exe : [INFO] [KRS] <-- GenerateAssistantResponseCommand done totalEvents=10
I'll start by looking at the workspace.
[tool] Run Command
[tool] status: Completed
[tool] Read File
[tool] status: Completed
[tool] Read File
[tool] status: Completed
[tool] Read File
[tool] status: Completed
[tool] Read File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Read File
[tool] status: Completed
[tool] Read File
[tool] status: Completed
[tool] Read File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Read File
[tool] Read File
[tool] Run Command
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Read File
[tool] Read File
[tool] Read File
[tool] Read File
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
Writing the spec first: requirements, design, tasks.
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
Now the Python core.
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
The spec changes the stamp wording, so I'll update those assertions. The old tests relied on the old reasons and on unsigned stamps.
[tool] Run Command
[tool] status: Failed: Run Command
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
Now the browser check.
[tool] Write File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Write File
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
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Completed
Now app tests (key endpoint, forge, SSE heads, NaN, stamps with key, verify fallback).
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
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
Now a real-browser run through Edge, driven by a throwaway script outside the repo.
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
Task 9 is built, spec first. The full suite passes (239 tests; 161 before this work). I ran the app on the stand-in, and `/` and `/api/carbon/key` both answered. Port 8091 was already held by a process I didn't start, so I used 8093 and stopped my server afterwards.
I also drove the real page in headless Edge. Check read INTACT "Checked in your browser". Forge read CHANGED with the different-key reason. A damaged stamp read "a stamp on your device is damaged or forged".
## What changed
- **Spec:** Requirement 9 is in `requirements.md`. `design.md` has D1 word for word plus D2 to D8. `tasks.md` has task 9 with sub-tasks 9.1 to 9.10, all ticked.
- **F4, F8, F9:** `safe_json()` cleans every event before it is stored, hashed or sent. `canonical()` no longer has `default=str` and refuses NaN. Writing a receipt can no longer raise because of what the agent wrote. A test sends a lone surrogate through a real `reply_to_customer` call and gets its receipt.
- **F1:**
  - `Signer.from_env()` takes any key text and derives the seed as designed.
  - The app uses one process-wide signer.
  - `GET /api/carbon/key` publishes the key, and the footer shows it.
  - `verify(..., expected_key)` rejects a book signed with a different key.
- **F2, F5, F6:**
  - Every stamp's signature is checked, and a malformed stamp now fails closed.
  - The wrong-reason bug is fixed: a stamp whose position exists but whose fingerprint differs says "receipt #N no longer matches the stamp your device kept". Only a stamp beyond the book's end says "shorter".
  - Every SSE event now carries a signed stamp of the book at that moment, and `app.js` pins the first key and keeps every stamp in `localStorage`. With storage unavailable it keeps them in memory and says so.
- **F3:** `static/carbon_verify.js` runs the check in the browser and shows "Checked in your browser". Without Ed25519 it falls back to the server and shows "Checked by the server".
- **F7:** the CLI exits 0, 1 or 2, and takes `--key`.
- **D7:** "Try to forge a new book" and `POST /api/carbon/forge`.
- **D8:** the README "Limits we know about" now says all three limits.
- **D5:** `tests/test_carbon_parity.py` runs the JS check under node on a book of tricky content and compares its answers with Python's, word for word.
## Existing tests I had to change
- Three assertions now expect the new wording ("your device", "receipt #3 no longer matches…").
- One stamp in a test is now properly signed, because unsigned stamps are forged by the new rule.
## Things you might not expect
- **Approve and decline stamps:** the stamp from `approve()` and `decline()` in `core.py` is still the plain head, because an existing test pins its exact keys. The `/api/approve` and `/api/decline` routes add `public_key`.
- **Key order:** the cleaned event keeps the order the keys were written in, because an existing tamper test expects the first field. `canonical()` sorts by code point.
- **Server restart:** without `CARBON_COPY_KEY` a restart makes a new key, and the device then refuses new books until you press "Forget what this device trusts" on the Carbon copy tab. I added that button and noted it in the README.
- **Different-key and damaged-stamp results:** these carry no `first_bad`, so the stamp reads "CHANGED" rather than "CHANGED AT #n".
```
