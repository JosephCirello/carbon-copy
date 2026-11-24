# Kiro run: task 16 (a check that does not need to trust us, and honest limits)

## Instructions given

```text
TASK 16: A CHECK THAT DOES NOT NEED TO TRUST US, AND HONEST LIMITS (findings F4, F7, F8, F9, F10, F11, F12 of the third carbon-attacker round, plus a measurement of every recorded run). Spec first (Requirement 16, design section "Task 16", task 16), then build, with tests. Task 15 is done; do not undo it.

1. F8, THE CHECK'S OWN CODE COMES FROM THE SERVER. "Check the book" runs static/carbon_verify.js, which the same server sends, and app.js looks up window.CarbonVerify.verify at click time, so any script on the page (or an operator serving a different file) can make a forgery read INTACT. Three fixes:
   a. In the page: capture the verify function once when carbon_verify.js loads and freeze window.CarbonVerify (Object.freeze), so a later assignment cannot replace it; pin the third-party AG Grid script to its exact version with a Subresource Integrity hash (integrity= and crossorigin=), computed from the file jsDelivr serves for that version.
   b. A STANDALONE CHECKER that does not come from the server: `verify.html`, one self-contained file (no network, nothing loaded from anywhere) with the browser check inlined, that the owner saves once from GitHub, opens from their own disk, and drops a downloaded book file onto. It reads the download's book, stamps and trusted key and shows INTACT or CHANGED with the reason, exactly as the page does. Build it with a script (tools/build_verify.py) that inlines static/carbon_verify.js byte for byte; a test fails if verify.html's inlined code differs from static/carbon_verify.js. Publish verify.html's SHA-256 in the README and test that the README's hash matches the file.
   c. README, "Limits we know about": say plainly that the in-page check runs code our server sends, so a dishonest operator could send a check that lies; the two checks that do not depend on us are the command line from a fresh clone and verify.html saved from GitHub, each on a downloaded file.
2. F9, NOTHING OUTSIDE THE SERVER SAYS WHICH KEY TO TRUST. Publish the hosted demo's public key in the README and in a file `HOSTED_KEY.txt` at the repository root: 345c0cf441241146d896623a4dc08bc3a7c0f004c60975e2d072382552a9f6e1 (read it back from https://carbon-copy-ywv3.onrender.com/api/carbon/key before writing it; if it differs, use what the server says and say so). The command line takes `--key-file HOSTED_KEY.txt`; verify.html shows the key the download trusts beside the published one and says whether they match.
3. F7, THE COMMAND LINE SAYS A BARE "intact" WHEN IT HAD NOTHING TO HOLD THE BOOK AGAINST. When the file carries no trusted key and none is given, or no stamps, print the same caveat the page prints ("This file has no key from your device, so the check can only compare the book with itself." / "...no stamp, so it cannot tell whether the end of the book was rewritten.") on the line after the verdict. Exit codes stay 0, 1, 2.
4. F10, A RUN AND ITS HELD PAYMENT VANISH FROM THE SERVER AFTER ONE HOUR. Keep the hour, but: the phone and the Carbon copy tab SHALL say, while a run is kept, "This server keeps a run for one hour. Download the carbon copies to keep them." and when a hold lapses, its card says it lapsed and was never sent to PayPal. README Limits SHALL state the one hour, the 40 runs per visitor and the visitor limit.
5. F4, ONE CLIENT CAN PUSH EVERY OTHER VISITOR OUT. 301 cookie-less requests evict every visitor, runs and holds included. Fix: a request that carries no visitor cookie and does not start a run SHALL NOT create a visitor (POST /api/policy with no cookie answers without keeping anything, or with a 400 asking to load the page first, whichever the page does not need); when the table is full, drop the least recently seen visitor that has NO waiting hold and no run younger than an hour, and only then anyone; cap new visitors per client address (X-Forwarded-For's first address on Render, else the socket) at 30 per 10 minutes, answering 429 in plain words past it.
6. F11, /mcp KEEPS EVERY ARGUMENT FOREVER. Keep at most the last 200 holds and 500 verdicts in the MCP workspace (the book keeps everything; the book is the record), store an argument over 64 KB in the history as its first 64 KB plus "(cut: N bytes)", and give receipts_holds a limit (default 50, newest first).
7. F12, POLICY TEXT OF ANY SIZE IS KEPT PER VISITOR. Refuse `english` over 20,000 characters and `sources` over 200 entries or 2,000 characters each, with 413 and a plain message.
8. THE BOOK ON EVERY RECORDED RUN. A measurement outside the repo (reference: <build-logs>\scale_check.py and scale_check2.py, read them) replayed all 1,444 recorded runs in both arms: 2,888 books, 45,571 receipts, every honest book intact, every one-receipt change (all 45,571, one at a time) caught at that receipt, every forgery, swap and cut-off ending caught with the device's stamp, browser and Python agreeing on every check. Bring that into the repository as tests/test_carbon_recorded_runs.py, marked `recorded` (registered in pytest config, skipped by the default run, run by a separate CI step `pytest -m recorded -q`), replaying exactly as /api/replay does and asserting all of it, the browser half through node in batches. Then add one short README section "What we measured on the book" with the numbers your test prints on the final build, and a line in Limits: a book of 10,000 receipts takes about 6 seconds to check in a browser and 50,000 about 30 (measured: 1,000 0.4 s in Python; 10,000 4 s Python, 6.5 s browser; 50,000 20 s Python, 31 s browser); real runs' books hold 7 to 153 receipts.

Follow every steering file. Do not touch receipts/measure.py, receipts/rules.py or results/. Run .venv\Scripts\python.exe -m pytest -q until everything passes, then `pytest -m recorded -q`, then every scratch_attacks/attack3_*.py covering F4, F7, F8, F9, F10, F11, F12, and report what each says now. Report what you changed, both test counts, the numbers the recorded-runs test printed, and anything you could not fix.
```

## What Kiro did and reported

```text
kiro-cli.exe : [INFO] [KRS] <-- GenerateAssistantResponseCommand done totalEvents=9
I'll start by looking at the repo.
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] Run Command
[tool] status: Completed
[tool] status: Completed
[tool] Read File
[tool] status: Completed
[tool] Read File
[tool] status: Completed
[tool] Run Command
[tool] Run Command
[tool] status: Completed
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
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
[tool] Run Command
[tool] status: Completed
[tool] Read File
[tool] status: Completed
[tool] Run Command
[tool] Run Command
[tool] status: Completed
[tool] status: Completed
[tool] Read File
[tool] status: Completed
[tool] Read File
[tool] status: Completed
[tool] Read File
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
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Replace in File
[tool] status: Completed
[tool] Replace in File
[tool] status: Completed
[tool] Replace in File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
The diff has no code that edits, deletes or reorders receipts, and the carbon tests pass. Next is the page: freeze the check and pin AG Grid.
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
[tool] Write File
[tool] status: Completed
[tool] Write File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
Expected: that test posts with no cookie. I'll update it to load the page first.
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
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Write File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
Now I'll start the recorded run in the background and write the other tests while it runs.
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Write File
[tool] Run Command
[tool] status: Completed
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Write File
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Failed: Run Command
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
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
Task 16 is built and both test runs pass. Two of the attacks you listed still fail: the F11 memory growth and the F10 server expiry. Nothing is committed, and I did not touch `receipts/measure.py`, `receipts/rules.py` or `results/`.
**What changed**
- **F8 (the check's own code):**
  - The page now freezes `window.CarbonVerify` and captures it once at load, and AG Grid is pinned to 32.3.3 with a SHA-384 hash and `crossorigin`.
  - `verify.html` is a self-contained page built by `tools/build_verify.py`, with `static/carbon_verify.js` inlined byte for byte. It carries a CSP that blocks all connections.
  - The README publishes its SHA-256, `668be87ddb4687ee192d4bfa801d7328087aad7b71ca67b618d77a2ffed03194`. Tests check both the inlined code and that hash.
  - Limits now say the in-page check runs code our server sends.
- **F9 (which key to trust):**
  - I read the hosted key back from the server and it matched yours. It is in `HOSTED_KEY.txt` and the README.
  - The command line takes `--key-file`, and giving it with `--key` exits 2.
  - `verify.html` shows the key a download trusts beside the published one and says whether they match.
- **F7 (bare "intact"):** the command line prints the page's two caveats after the verdict, and exit codes are unchanged. When both are missing it prints both lines.
- **F10 (the hour):**
  - The phone and the Carbon copy tab show "This server keeps a run for one hour…".
  - A lapsed card now says it lapsed and was never sent to PayPal.
  - Limits state the hour, the 40 runs and the 300 visitors.
- **F4 (visitor flooding):**
  - A policy POST with no cookie answers 400 and creates nothing.
  - When the table is full, visitors with a waiting hold or a run under an hour old are dropped last. The visitor just created is never the one dropped.
  - New visitors are capped at 30 per 10 minutes per address, then 429. Behind Render it reads the first `X-Forwarded-For` address, switched on by a new `RECEIPTS_BEHIND_PROXY=1` in `render.yaml`. Without that flag the header is ignored, so rotating it buys nothing.
- **F11 (/mcp):** the workspace keeps the last 200 holds and 500 verdicts, cuts arguments over 64 KB with `(cut: N bytes)`, and `receipts_holds` takes `limit` (default 50, newest first). The book keeps everything.
- **F12 (policy size):** `english` over 20,000 characters, more than 200 `sources`, or a source over 2,000 characters now gets a 413.
- **Recorded runs:** the replay test is `tests/test_carbon_recorded_runs.py`, with the `recorded` marker registered in a new `pytest.ini`. The default run skips it and CI has a separate `pytest -m recorded -q` step. The README has "What we measured on the book" and the large-book timings in Limits.
**Changes you did not ask for**
- `receipts/core.py`: `approve` refuses a hold whose argument was cut, so a truncated payee cannot be sent to PayPal.
- `tests/conftest.py`: clears the new per-address count between tests.
- Two older tests (`test_carbon_app.py`, `test_app_visitors.py`) were updated, because they asserted "no 64-hex key in the README" and posted policy with no cookie.
**Tests**
- Default run: 403 passed, 5 deselected. That includes 28 new tests in `tests/test_carbon_round4.py`, which run `verify.html` itself under node.
- `pytest -m recorded -q`: 5 passed in 226 s.
**What the recorded-runs test printed**
```
recorded runs: 1444; books (both arms): 2888; receipts: 45,571 (7 to 153 per book)
honest books intact: 2888 of 2888 (and 2888 after a JSON round trip)
one-receipt changes caught at that receipt: 45,571 of 45,571; named another receipt: 0; missed: 0
tamper_demo / forged and re-signed / two swapped / cut off with the real key, caught: 2888 / 2888 / 2888 / 2888
browser (node) and Python gave the same answer on 17,478 of 17,478 checks; different: 0
```
**What each `attack3_*` script says now**
I ran these against a clone of the working tree, because the check-code script clones HEAD and would otherwise test the old code.
- **F4:** the 301 cookieless POSTs now get 400, so the script stops there. The first visitor's book survives, and my own test covers that.
- **F7:** the script passes, because the command line now prints the caveat.
- **F8:** the script's precondition (no integrity hash, nothing frozen) is gone, so it fails before its swap step. My node test shows a later assignment does nothing.
- **F9, key published:** the script fails because the README now has the key, on purpose.
- **F9, operator key:** still true. The command line accepts a book signed with the key in its own file unless you pass `--key-file HOSTED_KEY.txt`, which rejects it.
- **F10:** the script still fails. The server drops the run and its hold after an hour, as the spec kept. It says so now, but the hold is still gone.
- **F11:** it prints +39 MB for 30 MB sent, so it still fails, and I could not fix this. The book keeps every argument in memory, and you ruled that the book keeps everything. Capping request size on `/mcp` would fix it; I did not add that.
- **F12:** a 4 MB policy now gets 413 (10 of 10), with memory up 1 MB.
- **`attack3_mcp_unrecorded`:** two tests still fail. They assert the Task 15 holes that are already closed.
**Left for you**
- `verify.html` is built from `HOSTED_KEY.txt` and `static/carbon_verify.js`. If either changes, run `tools/build_verify.py` and update the README hash, or the hash test fails.
- Nothing is committed. I deleted `scratch_attacks/fresh_clone`, a scratch clone the attack scripts recreate.
```
