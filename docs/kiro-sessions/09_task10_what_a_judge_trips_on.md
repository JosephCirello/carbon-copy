# Kiro run: task 10 (what a judge trips on)

## Instructions given

```text
TASK 10: WHAT A JUDGE TRIPS ON. A judge-style review of the live demo, the README and the repo against the Kiroween rules found the items below. Spec first: add Requirement 10 and task 10 (with sub-tasks) to the spec, update design.md, then build. Keep every existing test passing; add tests where behaviour changes. Do not touch receipts/measure.py, receipts/rules.py, results/ or render.yaml. Do not decide the contest category: leave one placeholder line in the README, "Category: (to be confirmed)".

10.1 ONE NAME, ONE MEANING. Today "Carbon Copy on/off" labels the old payment check (from Receipts) AND "Carbon Copy" is the new sealed book, so a judge cannot tell which part is new. Make the screen say: Carbon Copy = the whole product; inside it, "the check" stops a bad payment before PayPal (built on Receipts) and "the carbon copy" seals every move. Side-by-side labels become "Nothing checking" and "Carbon Copy on". The first banner reads: "Maya's AI agent pays her bills through PayPal. Carbon Copy checks each payment before it leaves (using Receipts, our earlier checker) and seals every move into a carbon-copy book nobody can quietly rewrite."
10.2 HONEST LABELS ON OLD MEASUREMENTS. The Results tab and the totals in Her book show Receipts' 19-model, 19-day measurement. Put one line at the top of the Results tab: "Measured by Receipts, the project Carbon Copy is built on (19 AI models, 19 business days, November 2026). The carbon copy itself is new and is not part of these numbers." Rename the tab "What Receipts measured".
10.3 A 30-SECOND PATH. A "Start here" strip at the top of the Watch tab with three numbered steps, each a button that does the step and moves the visitor on: (1) "Run Maya's day" (starts the replay), (2) "Decline the double payment on her phone" (opens the phone tab when the hold arrives), (3) "Try to forge the record" (opens the Carbon copy tab and presses Try to forge a new book). The current controls stay below for anyone who wants them.
10.4 THE CARBON COPY VISIBLE DURING THE RUN. On the Watch tab, beside "With Carbon Copy", a live counter "Carbon copies sealed: N" that rises as receipts are written, linking to the Carbon copy tab.
10.5 FALSE ALARMS ON SCREEN. Find out why (a) the AI's honest explanation is tagged "SAID: NO / SUSPICIOUS", (b) a receipt reads "The AI wrote (held)", and (c) the unchecked side reports "Honest work done: 1 of 1" after paying the bill twice. Fix the display where the label is wrong; where the label is right, add one plain line explaining it. Do not change the scoring in core.py or measure.py; this is display only. Write what you found into design.md.
10.6 PLAIN WORDS. One-line explanations, shown once near where each word first appears on the Carbon copy tab: fingerprint ("a short code computed from the receipt; change one letter and it changes"), stamp ("a sealed note your device keeps of how long the book was at that moment"), signing key ("the seal's owner; your device remembers the first one it sees and refuses any other"). Replace "vendor master" on screen with "Maya's list of suppliers".
10.7 THE TAB BAR. When the phone's count badge appears the tab bar overflows and hides "Carbon copy". Make all six tabs fit or scroll inside the bar with the active tab kept in view, at 375, 768 and 1280 pixels.
10.8 KIRO, SHOWN PROPERLY. Create (a) .kiro/settings/mcp.json registering Carbon Copy's own MCP server (receipts/mcp_server.py, run with the project's venv Python) so Kiro can call its tools; (b) .kiro/agents/carbon-attacker.json, a custom Kiro agent whose prompt is to attack the carbon-copy book (forge, rewrite, hide, cause false alarms) using the repo's own CLI and tests, reporting proven findings only. Read the Kiro docs in the repo's context or at kiro.dev for the exact file formats; if a format is uncertain, say so in your report rather than guessing silently.
10.9 README. Bring it in line: tasks 1 to 10 listed; the demo is on an always-on plan (no wake-up delay); the no-keys hook runs after each save; a "How Kiro built it" section answering each question the Kiroween rules ask: which Kiro surface (the Kiro CLI, headless, driven task by task from the spec, and why), spec-driven versus vibe coding, steering, each hook and what it did, property-based tests, MCP, the custom agent, and powers (say plainly if none were used). Leave a placeholder "Session records: docs/kiro-sessions/" for the build records the team will add.

Follow every steering file. Run .venv\Scripts\python.exe -m pytest -q until everything passes, then start the app (PAYPAL_MODE=standin) and load / once.
```

## What Kiro did and reported

```text
kiro-cli.exe : [INFO] [KRS] <-- GenerateAssistantResponseCommand done totalEvents=11
I'll start by looking at the repo layout and the spec.
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
[tool] Fetch URL
[tool] status: Completed
[tool] status: Completed
[tool] Run Command
[tool] Fetch URL
[tool] status: Completed
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
[tool] status: Completed
Fix the README to match those tests and drop the unverified IDE sentence.
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
My test expectation was wrong (the code's output is the better one). Fix the test.
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] Read File
[tool] status: Failed: Read File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
Task 10 is built. The full suite passes (254 tests, 15 of them new, in `tests/test_carbon_app.py`). The app is running on the stand-in at http://127.0.0.1:8091, and `/` returns 200. I did not touch `receipts/measure.py`, `receipts/rules.py`, `results/` or `render.yaml`.
I added Requirement 10, task 10 with sub-tasks, and a "What a judge trips on" section in `design.md` before building.
**What changed on screen (10.1 to 10.8)**
- **Names:** the first banner is your sentence. The side-by-side labels are now "Nothing checking" and "Carbon Copy on".
- **Results tab:** it is renamed "What Receipts measured" and opens with your line. The ledger got a matching pointer above its totals.
- **Start here:** three buttons run the 30-second path. I tested it in a headless browser at 375, 768 and 1280 pixels, from the replay through to "CHANGED … different key".
- **Phone step:** I added a "Next: try to forge the record" button on the phone tab after a decline. Without it, step 3 would be hidden behind the Watch tab.
- **Counter:** "Carbon copies sealed: N" rises as receipts are written (it reached 10 in the test run) and links to the Carbon copy tab.
- **Plain words:** the fingerprint, stamp and signing-key lines are on the Carbon copy tab.
- **Suppliers wording:** "vendor master" is gone from the screen. `rules.py` produces that phrase and I can't edit it, so the page rewrites it to "Maya's list of suppliers" when it draws the text.
- **Tab bar:** it scrolls inside itself and keeps the active tab in view. At 768 pixels all six tabs fit even with the phone badge showing. At 375 the bar scrolls.
**False alarms (10.5), written up in `design.md`**
- **"SAID: NO / SUSPICIOUS":** the AI's honest explanation was "…would violate rule 3… I will not retry". A word-pattern reader marks that as a refusal. It never detects suspicion, so the tag now reads "SAID: NO" with one plain line saying it is a word pattern.
- **"The AI wrote (held)":** "held" was the marker name printed in brackets. It now reads "(it said it would hold or verify)" or "(it said no)".
- **"Honest work done: 1 of 1":** the label was right. The only honest job that day was the Hollis Freight bill, and the double payment to Blue Ridge is counted apart as a risky move. I added a line explaining that. Scoring is unchanged.
**Kiro (10.8) and README (10.9)**
- **`.kiro/settings/mcp.json`:** it registers `carbon-copy`, started with the venv Python as `-m receipts.mcp_server`. That file had no way to start over stdio, so I added a small `__main__` to it. A test starts it and lists its tools.
- **`.kiro/agents/carbon-attacker.json`:** it attacks only copies of books. It may write only to `scratch_attacks/`, which git ignores, and it is denied writes to `receipts/`, `tests/`, `static/`, `results/` and `.kiro/`.
- **README:** it lists tasks 1 to 10, says the demo is on an always-on plan, and says the no-keys hook runs after each save. A new "How Kiro built it" section answers each Kiroween question, and both placeholders are in.
- **README claims I couldn't check:** I wrote "none used" for Powers because the repo has none. I wrote that the attacker agent has no recorded run because I found none. Please check both against what you know.
**Kiro formats I could not confirm**
- I wrote both Kiro files to the docs at kiro.dev/docs/custom-agents/configuration-reference, but I never loaded them in Kiro.
- The relative `.venv\Scripts\python.exe` in `mcp.json` assumes Kiro starts the server from the workspace folder.
- The shell permission patterns in the agent assume Kiro matches them as written.
- The README says this plainly.
```
