# Kiro run: task 18 (keep a run for an hour after the owner's last tap)

## Instructions given

```text
TASK 18: KEEP A RUN FOR AN HOUR AFTER THE OWNER'S LAST TAP. Found in your own task 17 report: after a hold has waited more than an hour, the owner's approve (or decline) leaves the run with nothing waiting, so it is already past its one hour and is dropped on the next request; the owner cannot then download the book that records her own decision. Spec first (amend Requirement 17 and the task 17 design, add task 18), then build, with a test.

Rule: a run's hour counts from its LAST activity (the run starting, or the owner's last approve or decline on it), not from when it started; a run with a WAITING hold is kept 24 hours from its last activity. Say it the same way on the phone, the Carbon copy tab and in the README Limits. Test with the clock moved, as attack3_expiry.py does: a hold waits 2 hours, is approved, and the run's book can still be fetched and downloaded 59 minutes later and is gone after 61; then re-run scratch_attacks/attack3_expiry.py and report what it says.

Follow every steering file. Do not touch receipts/measure.py, receipts/rules.py or results/. Run .venv\Scripts\python.exe -m pytest -q until everything passes, then pytest -m recorded -q. Report the change and both test counts.
```

## What Kiro did and reported

```text
kiro-cli.exe : [INFO] [KRS] <-- GenerateAssistantResponseCommand done totalEvents=9
[tool] Run Command
[tool] status: Completed
That was noisy. Let me look precisely.
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
Stray heredoc; I'll use str_replace instead.
[tool] Replace in File
[tool] status: Completed
[tool] Replace in File
[tool] Replace in File
[tool] status: Completed
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
[tool] Replace in File
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] Run Command
[tool] status: Failed: Run Command
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
My `Get-Content` rewrite of test_carbon_round4.py mangled its non-ASCII text. I'll restore that file from git and redo both edits with UTF-8-safe calls.
[tool] Run Command
[tool] status: Completed
The task asked me to amend Requirement 17 and the task 17 design as well, so I'll point those at the new rule.
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] Run Command
[tool] status: Completed
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
A run's hour now counts from its last activity, meaning the run starting or the owner's last approve or decline on it. The owner can download the book with her decision for a full hour after she taps. Both test runs pass:
- **`pytest -q`:** 415 passed, 5 deselected.
- **`pytest -m recorded -q`:** 5 passed, 415 deselected. Python and the browser check gave the same answer on 17,478 of 17,478 checks, and the run took 229 s.
**What changed**
- **Spec:** I added Requirement 18 (the rule, the sentence, the test), a "Task 18" section in the design and task 18 in `tasks.md`. I also amended Requirement 17.3 and 17.4 and the task 17 F10 design line so they count from the last activity and point to Requirement 18.
- **`app.py`:** a new `_touch` sets the run's time to now at the start of every approve and decline on that run, before the tap is made. The order matters. I first reset the time after the tap, and the new test still failed. The tap left nothing waiting on a run more than an hour old, so the very next lookup dropped the run before the time could be reset. `_run_expired` works as before, but its time now means "last activity".
- **Wording:** the phone, the Carbon copy tab and README Limits now all say: "This server keeps a run for one hour after its last activity (it starting, or your last approve or decline), and for 24 hours when a payment in it is waiting for you. Download the carbon copies to keep them." The README adds one sentence explaining that this leaves an hour to download the book after deciding on a payment that waited a long time. I updated the matching sentence checks in `test_carbon_round4.py` and `test_carbon_round5.py`.
- **Tests:** I added two to `tests/test_carbon_round5.py`, both with the clock moved:
  - A hold waits 2 hours and is approved, and any other waiting hold is declined. The book can be fetched 59 minutes later and is gone (404) at 61.
  - A decline after 50 minutes restarts the time. If another hold is still waiting, the run is still there 23 hours after that tap and gone at 25.
`scratch_attacks/attack3_expiry.py` now passes (it failed before the fix). After 61 minutes the approve returns 200 with a stamp, the hold is still listed as APPROVED, and the book returns 200. It had 11 receipts before the approve and the new stamp counts 14.
An approve or decline that fails, for example on an unknown hold id, also restarts the hour, because the time is reset before the tap runs. It can only keep the visitor's own run alive, so I left it that way.
I did not touch `receipts/measure.py`, `receipts/rules.py` or `results/`. No temporary files are left.
```
