# Kiro run: task 25 (the live MCP endpoint, and the README's first screen for a judge)

## Instructions given

```text
TASK 25: THE LIVE MCP ENDPOINT REFUSES EVERY CLIENT, AND THE README'S FIRST SCREEN FOR A JUDGE. Spec first (Requirement 20, design section "Task 25", task 25), then build, with tests. Tasks 1 to 24 are done; do not undo them.

1. THE HOSTED /mcp HAS NEVER ANSWERED A CLIENT. Measured 2026-11-24: POST https://carbon-copy-ywv3.onrender.com/mcp/ with an MCP initialize request answers HTTP 421 "Invalid Host header", while the same request to a local server answers 200. The MCP library's DNS-rebinding protection accepts only localhost hosts unless told otherwise. Fix it without turning the protection off: the allowed hosts (and origins) are localhost plus the host names in RECEIPTS_ALLOWED_HOSTS (comma-separated) plus RENDER_EXTERNAL_HOSTNAME when Render sets it (Render sets it automatically on every web service; check Render's docs to confirm the variable name before relying on it). Tests: an initialize with Host: carbon-copy-ywv3.onrender.com is accepted when that name is configured (either way), and a request with an unknown Host is still refused. Read the MCP Python SDK's own transport-security settings in the installed package to do it the supported way. The stdio server is unaffected.
2. README, THE FIRST SCREEN. Directly under the title and the one-line Kiroween line, add:
   a. a heading "Kiroween 2026: Resurrection" if the category is not already in a heading;
   b. "For judges, in 30 seconds": four or five short lines: what it is in one sentence; the three clicks on the live demo (Run Maya's day, decline on her phone, Try to forge the record); the three numbers (4 rounds of attacks by Kiro's own carbon-attacker agent; 38 weak spots it proved, each fixed or written down as a limit; 45,571 receipts from recorded AI runs changed one at a time, every change caught); the two links (live demo, video placeholder "Video: (link added at submission)");
   c. an "At a glance" row of four of the pictures in docs/images/ (01_two_sides.jpg, 02_maya_declines.jpg, 04_change_one_caught.jpg, 05_forgery_caught.jpg), each with a one-line caption saying what it shows, and 03 and 07 placed where the README already talks about the check and the attacker.
   Every number must be read from the repository (the recorded-runs test output in the README, the attacker reports in docs/kiro-sessions/ 10, 12, 17 and 23: 6 + 7 + 13 + 12). Keep the existing long sections below, unchanged except where a number they state is now wrong.
3. README, "How Kiro built it": open the section with a table, columns "Kiro feature | How we used it | Why it mattered", one row each for: Spec (1 spec: N requirements, N tasks, changed N times), Steering (3 files, what they fix), Hooks (3, in the current .kiro/hooks/*.json format), MCP (the project's own server, loaded by Kiro from .kiro/settings/mcp.json; the carbon-attacker used it), Custom agent (carbon-attacker: 4 runs, 38 proven findings), Property-based tests (hypothesis: what they generate and assert), Kiro CLI headless (every task one instruction, 29 recorded sessions or whatever the count is after this run). Counts read from the repository, not from this prompt. Then one short paragraph "Spec first, never vibe": the book and every money path went through the spec, every change started as a requirement, and why (money code: a change nobody wrote down is the bug the product exists to catch). Keep the existing bullets below the table.
4. README, "Point your own AI at it": a short section showing how to connect any MCP client to the live demo's https://carbon-copy-ywv3.onrender.com/mcp/ (a Kiro .kiro/settings/mcp.json snippet for a remote server, checked against Kiro's MCP docs for the exact remote-server field names, and the repo's own `python examples/mcp_client_demo.py https://carbon-copy-ywv3.onrender.com/mcp/`), what the AI will see (blocked, held, cleared), and how to pull the MCP book with the carbon_book tool and check it with `python -m receipts.carbon verify <file> --key-file HOSTED_KEY.txt`. Say plainly the workspace is shared by every visitor, the demo uses the PayPal stand-in (no money), and the limits (60 requests a minute, 256 KB a request, the 20 MB book).

Follow every steering file. Do not touch receipts/measure.py, receipts/rules.py or results/. If verify.html or HOSTED_KEY.txt change, rebuild with tools/build_verify.py and update the README hash. Keep the README count tests passing (they compare the README with the repository). Run .venv\Scripts\python.exe -m pytest -q until everything passes. Report what you changed, the test count, and the exact allowed-hosts behaviour.
```

## What Kiro did and reported

```text
kiro-cli.exe : [INFO] [KRS] <-- GenerateAssistantResponseCommand done totalEvents=9
I'll start by looking at the repo and spec.
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] Fetch URL
[tool] Fetch URL
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
RENDER_EXTERNAL_HOSTNAME is confirmed. Next I'll check Kiro's remote-server fields and its hook format.
[tool] Fetch URL
[tool] status: Completed
[tool] Fetch URL
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Fetch URL
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
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Write File
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
[tool] Read File
[tool] status: Completed
[tool] Replace in File
[tool] status: Completed
Now the session record (29) and its index entry.
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Completed
The spec text landed in the repo root, so I'll append it to the real spec files and delete the stray ones.
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Completed
The hosted `/mcp` fix and the README changes are in. The full suite passes: 519 passed, 5 deselected. The deselected tests are the `recorded` ones, which the default run skips. I did not run `pytest -m recorded`.
I could not test against the live Render URL from here. The fix is tested locally. A fresh process that imports `app` with only `RENDER_EXTERNAL_HOSTNAME` or only `RECEIPTS_ALLOWED_HOSTS` set answers `/mcp/` with 200 for `carbon-copy-ywv3.onrender.com` and 421 for another host. I did not run `examples/mcp_client_demo.py` against a server, so the "what the AI sees" lines in the README rest on that script's header comment.
**Allowed-hosts behaviour**
- The MCP library's DNS-rebinding protection stays on, set through its own `TransportSecuritySettings`. The code is `allowed_host_names()` and `transport_security()` in `receipts/mcp_server.py`, and `app.py` passes the settings when it mounts `/mcp`.
- **Allowed hosts:** `127.0.0.1`, `localhost` and `[::1]` on any port, plus every name in `RECEIPTS_ALLOWED_HOSTS` (comma-separated) and `RENDER_EXTERNAL_HOSTNAME`. Each configured name is allowed with and without a port.
- **Allowed origins:** the same names as `https://` and `http://`, with and without a port, plus the localhost origins.
- **Cleaning:** names are lower-cased and de-duplicated. A pasted URL is cut to its host. Wildcards, spaces and paths are ignored.
- **Refusals:** any other Host gets 421. A foreign Origin on an allowed host gets 403. With nothing configured, only localhost works, as before.
- **Render's variable:** I confirmed in Render's docs that `RENDER_EXTERNAL_HOSTNAME` is set on web services to the onrender.com name.
- **`render.yaml`:** it now also sets `RECEIPTS_ALLOWED_HOSTS=carbon-copy-ywv3.onrender.com`, so the hosted demo doesn't rely on one variable.
- **stdio:** the stdio server is unaffected.
**Spec**
- I added Requirement 20, design section "Task 25" and task 25 (with sub-tasks) to the spec files.
- The spec text first landed in the repo root by mistake. I moved it into the spec files and deleted the strays.
**README**
- **First screen:**
  - the "Kiroween 2026: Resurrection" heading and "For judges, in 30 seconds";
  - the "At a glance" table of pictures 01, 02, 04 and 05, each with a caption;
  - picture 03 under "How it works" and picture 07 under the Custom agent bullet. I viewed 07 for its caption.
- **Numbers:**
  - **Attacker findings:** I counted 6, 7, 13 and 12 findings in reports 10, 12, 17 and 23, which makes 38. Report 12's own summary says "eight", but it lists seven. I used 7, matching the existing README.
  - **Receipts:** 45,571 comes from "What we measured on the book".
- **"How Kiro built it" table:** it comes before the old bullets and has the seven rows you listed, followed by the "Spec first, never vibe" paragraph. Counts are read from the repo:
  - 20 requirements, 25 tasks, changed 18 times;
  - 3 steering files;
  - 3 hooks in 2 files (the existing files already use the current `hooks`/`trigger` format);
  - 29 recorded sessions.
- **"Point your own AI at it":** the Kiro remote snippet uses `url`, per Kiro's MCP docs. It also covers the demo client, blocked/held/cleared, `carbon_book` with `verify ... --key-file HOSTED_KEY.txt`, the shared workspace, the stand-in and the limits.
- **Counts and spec changes:**
  - I updated the existing counts to 20 requirements, tasks 1 to 25 and 29 runs.
  - I added item 18 to the "spec changed" list, so it now says "eighteen times", and reworded the "not an eighteenth" note in item 17.
- **Not touched:** `verify.html` and `HOSTED_KEY.txt` are unchanged, so no rebuild or hash update was needed. `receipts/measure.py`, `receipts/rules.py` and `results/` are also untouched.
**Session record**
- I wrote `docs/kiro-sessions/29_task25_hosted_mcp_and_the_judges_first_screen.md` and linked it from the sessions README. That record is my own summary, not a copied Kiro CLI log, so replace it if you re-run this task headless.
**Tests**
- New `tests/test_carbon_round8.py` covers the allowed-hosts behaviour above and the README numbers.
- Three older tests pinned "seventeen times". They now call a new `assert_spec_changes_match` in `tests/readme_counts.py`, which compares the README's word with the length of the list under it.
```
