# Kiro run: task 26 (what a first-time judge trips on: the last walk)

## Instructions given

```text
TASK 26: WHAT A FIRST-TIME JUDGE TRIPS ON (a last walk before submission: the live demo walked at phone, tablet and desktop width in light and dark, and a reader given only the public pages). Spec first (amend Requirement 10, "what a judge trips on", and add task 26), then build, with tests. Tasks 1 to 25 are done; do not undo them.

On the screen:
1. ON A PHONE THE ANSWER LANDS BELOW THE FOLD. At 375 x 812, "Next: try to forge the record" opens the Carbon copy tab at its top and the CHANGED stamp is off screen; the judge sees buttons, not the result. Whenever Check the book, Try to change one or Try to forge a new book writes its answer, bring #ccResult into view (smooth scroll, the stamp near the top of the window), at every width. Test it at 375 x 812.
2. THE LIVE DEMO NEVER SAYS WHAT IT IS ENTERED IN. Add one small line in the footer: "Built with Kiro for Kiroween 2026 · Code and the Kiro sessions: github.com/JosephCirello/carbon-copy" (a link), in the page's existing footer style.
3. "Recorded real run (replayed through PayPal now)" in the run-source options contradicts the stand-in label everywhere else. Say where it is replayed from what the server reports: "replayed through the PayPal stand-in now" on the stand-in, "through the PayPal sandbox now" on the sandbox. Check every other on-screen string that says "PayPal" without saying which one, the same way.

In the repository:
4. docs/kiro-sessions/README.md still says the carbon-attacker "was run twice"; it ran four times (records 10, 12, 16 and 17, and 23). Bring it in line, with what each run found.
5. The "No keys in the repo" hook's description says "Before the agent writes any file" but its trigger is PostFileSave. Make the description say what it does ("After each save...").
6. README, "Check the fingerprint yourself" carries a stray bullet ("No AI model decides a payment") that belongs elsewhere: move it where it belongs or remove the duplicate.
7. README says "Kiro wrote Carbon Copy" while the session records say the team wrote the first spec and steering and that some fixes were made by hand. Say it exactly: we wrote the first spec, the steering files and the hooks; Kiro wrote the code and the tests, task by task, from the spec; name the few changes made by hand (read them from docs/kiro-sessions/README.md and the commit history: commits whose message does not say "built by Kiro").
8. The picture 04_change_one_caught.jpg shows a device key 83d278dc..., not the hosted key 345c0cf4...: it was recorded on a local copy of the demo. Say so in its caption ("recorded on a local copy of the demo").
9. SHORTEN THE README WITHOUT LOSING A FACT. A reader said it repeats itself (the three demo clicks appear twice; the spec-first reason three times), the MCP bullet under "How Kiro built it" is about 300 words, and the visitor-and-run paragraph in Limits is very long. Keep every fact, number, limit and link; remove repetition; split the two long paragraphs into short bullets; plain words. Do not touch the first screen added by task 25 except to remove duplication below it. Every README count test (they compare the README with the repository) must still pass.

Follow every steering file. Do not touch receipts/measure.py, receipts/rules.py or results/. Run .venv\Scripts\python.exe -m pytest -q until everything passes. Report what you changed, the README's word count before and after, and the test count.
```

## What Kiro did and reported

```text
kiro-cli.exe : [INFO] [KRS] <-- GenerateAssistantResponseCommand done totalEvents=9
I'll start by looking at the repo layout and the existing spec.
[tool] Run Command
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
[tool] Write File
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
[tool] Run Command
[tool] status: Completed
[tool] Write File
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
Good catch by the test: another on-screen string. Let me find all of them.
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Completed
Task 26 is done and `.venv\Scripts\python.exe -m pytest -q` passes: 535 passed, 5 deselected (the `recorded` marker). That includes 16 new tests in `tests/test_carbon_round9.py`.
The README went from 7,211 to 7,103 words, a cut of only 108. I removed about 450 words of repetition, but the required additions (who wrote what, the task 26 text, the picture caption) took back most of it. A test now checks it stays under 7,211. Every README count test still passes. I did not touch `receipts/measure.py`, `receipts/rules.py` or `results/`.
**Spec first:** Requirement 10 now has items 10 to 15, a "Task 26" section is in `design.md`, and task 26 is in `tasks.md`. I counted the amendment under item 5 of the README's "spec changed" list instead of adding a nineteenth entry, as task 22 did.
**On the screen**
1. **Scroll:** *Check the book*, *Try to change one* and *Try to forge a new book* now scroll `#ccResult` into view, smoothly (instantly if the visitor prefers reduced motion). The margin is read from the sticky bar's height. A fixed margin hid the stamp under the 162 px phone bar, which the browser test caught. The test runs in real Chromium at 375×812, 768×1024 and 1280×800, light and dark, and I confirmed it fails with the scroll disabled.
2. **Footer:** it now has the "Built with Kiro for Kiroween 2026 · Code and the Kiro sessions: github.com/JosephCirello/carbon-copy" line, with the repository as a link.
3. **Which PayPal:** the run-source option now reads "(replayed through the PayPal stand-in now)" or "(…the PayPal sandbox now)", from what the server reports. Five other lines name it the same way:
   - the "Carbon Copy on" sub-title;
   - the approve-card text in two places;
   - the replay tag;
   - the ledger's "Why" column header.
   I left screens that already name which PayPal (the environment label, "PayPal here:" on the Carbon copy tab, each receipt's tech line). I also left the "replayed through Carbon Copy now" line beside the Run button, since it doesn't mention PayPal.
**In the repository**
4. `docs/kiro-sessions/README.md` now says the attacker ran four times (records 10, 12, 16 and 17, and 23), with what each run found. It also lists the by-hand commits.
5. The "No keys in the repo" hook description now starts "After each save…".
6. The stray bullet is out of the fingerprint section and now sits in "How it works".
7. The README now says we wrote the first spec, steering files and hooks, and Kiro wrote the code and tests task by task from the spec. It names the by-hand changes: the import of Receipts (`1d9b5fe`), the first spec, steering and hooks (`92e8580`), `requirements.txt`, `Dockerfile` and `render.yaml`, the README's link, commands, category line and pictures, the key scanner's skip list, and the session records.
8. The `04_change_one_caught.jpg` caption now says it was recorded on a local copy of the demo.
9. **Shortening:**
   - The three clicks are said once, on the first screen.
   - The spec-first reason is said once.
   - The MCP bullet and the Limits paragraph are now short bullets.
   - The Custom agent bullet now points to the numbered findings below it.
   - The table rows no longer repeat the bullets.
The README now says "tasks 1 to 26" and "26 tasks". I didn't add a session record 30 for task 26, because I didn't run Kiro CLI.
```
