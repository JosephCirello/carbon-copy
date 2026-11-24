# Kiro run: task 11 (what our own attacker found)

## Instructions given

```text
TASK 11: WHAT OUR OWN ATTACKER FOUND. The custom Kiro agent carbon-attacker (.kiro/agents/carbon-attacker.json) attacked the book and proved the findings below, each with a test in scratch_attacks/ (git ignores that folder; read the tests there, they are the reproductions). Spec first: add Requirement 11 and task 11 (with sub-tasks) to the spec, update design.md, then build. Every fix gets a test in tests/. Keep every existing test passing. Do not touch receipts/measure.py, receipts/rules.py, results/ or render.yaml.

A1. A receipt's time is not cleaned like the event: an "at" of 1e21 is normalised by Python to an integer and written by JavaScript as 1e+21, so the two checks disagree (reachable only through append() called directly). Fix: store "at" as an integer number of milliseconds since the epoch ("at_ms"), cleaned like everything else; the screen formats it. Keep reading old books that carry "at" seconds only if that is simple; otherwise say in the design that books from before task 11 are not readable.
A2. Python reads a "receipts" field that is not a list ({}, 0, "", false) as an empty book and says intact; the browser rejects it. Fix: both checks answer changed with the reason "this is not a carbon-copy book we can read" for any book whose shape is wrong.
A3. Fields outside the seal can be added to a receipt ("approved_by": "maya", "note": "Maya approved this by phone") and both checks say intact. Fix: a receipt must carry exactly the sealed keys (n, at_ms, kind, event, prev, fp, sig); any other key makes it changed with the reason "receipt #N carries something outside its seal". At the top level the check reads only public_key, head and receipts; the screen and every export show only those.
A4. The signature text is malleable: changing the last base64 character gives 15 other encodings that decode to the same signature, and both checks say intact. Fix: a signature must be canonical base64 (decode, re-encode, and the text must match exactly; standard alphabet, padded); otherwise changed with the reason "its signature does not match". Same rule for the head's and every stamp's signature, in Python and in static/carbon_verify.js.
A5. A public key with spaces between the hex pairs passes in Python (bytes.fromhex ignores spaces) and fails in the browser. Fix: a key is exactly 64 lowercase hex characters in both checks; anything else is changed with a plain reason.
A6. Different values seal the same (298.5 and "298.5"; 2**60 and "1152921504606846976"; Decimal("5.10") and "5.10"; NaN and "nan"). This is the documented cleaning. Keep it, and add one line to the README's Limits: "Amounts that are not whole numbers are sealed as text, so the book shows the value, not whether the AI wrote it as a number or as text."
A7. MCP DID NOT LOAD. The attacker reported "The carbon-copy MCP tools aren't available to me". Find out why .kiro/settings/mcp.json is not loaded by the Kiro CLI (check the current Kiro CLI docs for where a workspace MCP config lives and how an agent includes it; check whether the relative venv path or the server's start-up fails), fix it, and prove it: run `kiro-cli mcp list` (or the documented equivalent) and paste what it prints into your report, and have a test start the server the same way Kiro does. If you cannot make Kiro load it, say so plainly in the README's "How Kiro built it" instead of claiming MCP was used.
A8. Update the carbon-attacker agent's prompt to name the six findings above as already fixed, so its next run looks for new shapes.

Run .venv\Scripts\python.exe -m pytest -q until everything passes, and run every test in scratch_attacks/ (they should now show the attacks caught; report any that still pass).
```

## What Kiro did and reported

```text
kiro-cli.exe : [INFO] [KRS] <-- GenerateAssistantResponseCommand done totalEvents=10
I'll start by looking at the repo layout and the spec.
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] Read File
[tool] status: Completed
[tool] Read File
[tool] status: Completed
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] Fetch URL
[tool] status: Completed
[tool] status: Completed
[tool] Fetch URL
[tool] status: Completed
[tool] Fetch URL
[tool] status: Completed
[tool] Fetch URL
[tool] status: Completed
[tool] Fetch URL
[tool] status: Completed
[tool] Fetch URL
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Fetch URL
[tool] Fetch URL
[tool] status: Completed
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Read File
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
It's installed but not on PATH. I'll call it by full path.
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
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Write File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Write File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Write File
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Failed: Run Command
Expected: these tests encode the old `at` shape. I'll update them to the new one. First the full list of failures.
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Completed
[tool] Write File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Write File
[tool] status: Completed
[tool] Write File
[tool] status: Completed
[tool] Write File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Write File
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
[tool] Write File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Write File
[tool] status: Completed
[tool] Write File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Write File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Replace in File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
Task 11 is finished: A1 to A6 and A8 are fixed, and A7 is fixed for the headless engine. The full suite passes (292 tests, up from 254), and I did not touch `receipts/measure.py`, `receipts/rules.py`, `results/` or `render.yaml`.
**Spec.** Requirement 11 and task 11 (11.1 to 11.10) are added, and design.md has a new section "What our own attacker found (task 11)". The `at` to `at_ms` change is also noted in design.md's data-shape block.
**Fixes** (Python in `receipts/carbon.py`, browser in `static/carbon_verify.js`, tested in both):
- **A1.** A receipt now seals `at_ms`, whole milliseconds between 0 and 2^53−1. Anything else becomes the current time, and the check refuses a bad `at_ms` even if someone with the key signed it. The screen formats `at_ms`. Books from before task 11 are not readable: they read as changed, and the design and README Limits say so.
- **A2.** Both checks answer changed with "this is not a carbon-copy book we can read" when the book isn't an object or its `receipts` isn't a list. A missing `receipts` field counts as the wrong shape too.
- **A3.** A receipt must carry exactly its seven sealed keys. Any other key gives "receipt #N carries something outside its seal". The check reads only `public_key`, `head` and `receipts`. A new `public_book()` strips everything else from the demo books, and the screen's developer view prints sealed keys only.
- **A4.** A signature must be canonical base64. This covers receipt, head and stamp signatures, and each keeps its own reason text.
- **A5.** A book's public key must be exactly 64 lowercase hex characters, otherwise changed with "its public key is not written the way a key must be". The key the device trusts may still be given in capitals.
- **A6.** The cleaning is unchanged. The README Limits now carries your sentence, and a test pins the behaviour.
- **A8.** The attacker's prompt lists A1 to A6 as already fixed and says to look for new shapes.
**A7.** The workspace `.kiro/settings/mcp.json` is the right place, and Kiro reads it. The relative `.venv` path works because Kiro starts the server from the workspace folder. I could not see inside the attacker's own session, so I can't say which of two causes it hit. Both reproduce its message:
1. **Agent file didn't load.** The agent file used only the newer `permissions` field, which `kiro-cli chat --no-interactive` (headless, older engine by default) does not load. It answered "Mode 'carbon-attacker' not found". The file now carries both the new and old fields, and loads in both engines. A test checks that the two forms agree.
2. **First turn started too early.** On the newer engine (`--agent-engine v3`), a one-shot headless run starts its first turn before the server has connected, about 2.8 seconds. Slowness in Python's `mcp` import is part of that and can't be removed. The prompt now tells the attacker to look again before giving up. This can still happen on a one-shot run of that engine, and the README says so.
I confirmed it with `kiro-cli chat --agent-engine v2 --agent carbon-attacker`: it listed all twelve tools and called `receipts_holds`. A new test starts the server from the `mcp.json` command from the workspace folder and does the handshake. The README's "How Kiro built it" is rewritten with these facts.
`kiro-cli mcp list` prints:
```
🤖 default:
  kiro_default
    • carbon-copy  .venv\Scripts\python.exe
📄 workspace:
  carbon-attacker
    • carbon-copy  .venv\Scripts\python.exe [legacy]
  kiro_help
    (empty)
  kiro_planner
    (empty)
```
Before the agent change, `carbon-attacker` was missing from the workspace list.
**Existing tests I had to change.** Five tests in `tests/test_carbon.py` and one README check in `tests/test_carbon_app.py` asserted the old `at` field or "tasks 1 to 10". I updated them to the new format and kept their intent.
**scratch_attacks/.**
- **A1 to A5 are caught.** The five attack tests in `attack_disagree.py` now fail, which means the attack no longer works.
- **Still passing, as expected.** `test_event_values_that_collide` passes because it is A6, which I kept on purpose. The four tests in `attack_cut_tail.py` and the three in `attack_resign_newkey.py` assert that the check catches the attack. One of the cut-tail tests documents the known limit about changes after the device's last stamp.
- **Edited.** I changed `"at": r["at"]` to `"at_ms": r["at_ms"]` in the `attack_resign_newkey.py` helper so it builds the new receipt format.
- **Cleaned up.** I removed the leftover `tmp*` folders and my own temp files.
The shell patterns in the agent's permissions (the regex form for the older engine) have not been exercised in a recorded run. The README says so under "Not confirmed".
The post-save hook check on `receipts/carbon.py` came out clean. Only `append()` writes to the book. `public_book()` and `_change_one()` work on copies.
```
