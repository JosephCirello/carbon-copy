# Kiro run: task 17 (the two findings task 16 left open)

## Instructions given

```text
TASK 17: THE TWO FINDINGS TASK 16 LEFT OPEN (F10 and F11 of the third carbon-attacker round). Spec first (Requirement 17, design section "Task 17", task 17), then build, with tests. Tasks 15 and 16 are done; do not undo them.

1. F11, ONE ANONYMOUS MCP CLIENT CAN GROW THE SERVER'S MEMORY WITHOUT LIMIT. /mcp has no login and one shared workspace whose book keeps every argument (rightly: the book keeps everything). Bound it without ever letting money move unrecorded:
   a. Refuse an /mcp request body over 256 KB with 413 and a plain message, before any tool runs.
   b. Limit MCP calls per client address (the same address rule as task 16's visitor limit, RECEIPTS_BEHIND_PROXY) to 60 per minute, 429 past it.
   c. Cap the MCP workspace's book at 20 MB of sealed receipts (measure the stored JSON as it grows, cheaply). Past the cap, every MCP tool that would move money or change a payee REFUSES with a plain message ("This demo's MCP book is full; restart the server to start a new one.") and nothing is forwarded; read-only tools and carbon_book still answer. Fail closed: a money move never happens without its receipt.
   d. Test each: a 300 KB body gets 413; the 61st call in a minute gets 429; with the cap set small in the test, a payout past it is refused, nothing reaches the stand-in, and the book still verifies intact.
2. F10, A HELD PAYMENT VANISHES AFTER ONE HOUR. Keep a run that still has a WAITING hold for 24 hours instead of one (memory per run is about 0.14 MB, and runs per visitor stay capped at 40); a run with nothing waiting keeps the one hour. The phone and the Carbon copy tab say which applies ("This server keeps a run with a payment waiting for you for 24 hours, and any other run for one hour. Download the carbon copies to keep them."). README Limits say both numbers and that the hosted demo also loses everything on a restart. Test both times with the clock moved, as attack3_expiry.py does.

Follow every steering file. Do not touch receipts/measure.py, receipts/rules.py or results/. Run .venv\Scripts\python.exe -m pytest -q until everything passes, then pytest -m recorded -q, then scratch_attacks/attack3_size.py (F11) and attack3_expiry.py (F10), and report what each says now. If verify.html or HOSTED_KEY.txt would change, rebuild with tools/build_verify.py and update the README hash. Report what you changed, both test counts, and anything you could not fix.
```

## What Kiro did and reported

```text
kiro-cli.exe : [INFO] [KRS] <-- GenerateAssistantResponseCommand done totalEvents=11
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
[tool] Replace in File
[tool] Replace in File
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
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Failed: Run Command
That test pins the old README wording, which Task 17 replaces on purpose. I'll update the test.
[tool] Run Command
[tool] Run Command
[tool] status: Completed
[tool] status: Completed
Now the two attack scripts.
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
F10 and F11 are fixed, and the full suite and the recorded-runs test pass. I did not edit `receipts/measure.py`, `receipts/rules.py` or `results/`. `verify.html` and `HOSTED_KEY.txt` are unchanged, so the README hash stands.
**Tests**
- `pytest -q`: 413 passed, 5 deselected. I changed one older test in `test_carbon_round4.py`, because it pinned the old README wording and the new wording replaces it.
- `pytest -m recorded -q`: 5 passed. The browser check and Python agreed on 17,478 of 17,478 cases, and every change was caught.
- The new tests are in `tests/test_carbon_round5.py`, and I added a clear of the MCP rate counter to `conftest.py`.
**F11, /mcp memory**
- A new ASGI middleware, `McpGuard` in `app.py`, refuses any /mcp body over 256 KB with 413 before a tool runs. This holds even when the client declares no length.
- It also limits each client address to 60 requests a minute and returns 429 past that. It uses the same address rule as the visitor limit. I count every HTTP request to /mcp, so a client's handshake messages count toward the 60 along with its tool calls.
- `CarbonCopy.size_bytes()` is new and counts the stored JSON as each receipt is appended. It only reads the book.
- At 20 MB (`RECEIPTS_MCP_BOOK_MB`), `create_refund`, `accept_dispute_claim`, `create_payout` and `update_vendor_payee` refuse with "This demo's MCP book is full; restart the server to start a new one." and forward nothing. Read-only tools and `carbon_book` still answer.
- I also made the phone's approval of an MCP hold refuse with 409 when the book is full, because an approval sends money. Declining still works.
- A refusal writes no receipt, since a refusal that wrote one would still let a client grow the book. One call can pass the cap by its own receipts, by at most about 256 KB.
**F10, held payments**
- A run with a WAITING hold is now kept for 24 hours, and any other run for one hour. The 40 runs per visitor cap is unchanged, and the visitor-eviction rule uses the new times.
- The phone, the Carbon copy tab and the README Limits all give both numbers and say the hosted demo also loses everything on a restart. The README also states the /mcp limits.
- The spec (Requirement 17, design "Task 17", task 17) is written.
**Attack scripts**
- `attack3_size.py` F11: it now fails at its first call, because its 1 MB arguments get 413 ("That request is too large for this demo (the limit is 256 KB). Nothing was done."). The memory growth it measured can no longer happen. I left the script unchanged, and it also cannot reach the cap.
- `attack3_expiry.py` F10: the payment is no longer lost. After 61 minutes the hold was still there and the approve call returned 200. The script then fails on its last assertion, because that approval leaves the run with nothing waiting, so the run has passed its one hour and is dropped on the next request.
- Dropping the run straight after the owner's tap is what the rule says, but the owner then cannot download that run's book. I did not change this, and it is your call.
I could not run the hosted demo, so none of this is checked on Render.
```
