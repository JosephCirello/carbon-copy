# Kiro run: task 22 (rules saved before a run; one lock for the tap and the agent)

## Instructions given

```text
TASK 22: TWO THINGS TASK 21 LEFT. Spec first (amend Requirement 19 and the task 21 design, add task 22), then build, with tests. Task 21 is done; do not undo it.

1. SAVING RULES BEFORE A RUN MUST KEEP WORKING. Task 21 item 11 made POST /api/policy answer 400 for a visitor the server does not hold, so someone who opens the page and goes straight to "Her rules" cannot save until they have run a day. A judge will do exactly that. Use the signed cookie you suggested: when the page is loaded, the server sets the visitor cookie to a random id plus an HMAC over it (key: a secret made at start-up, or derived from CARBON_COPY_KEY's text with a fixed label so restarts of the hosted demo keep accepting it; never the signing key itself, never written anywhere), and creates NOTHING. Any request with a VALID signed cookie may create its visitor on first use (policy save, a run, a tap), still counted against the per-address limit on new visitors; a made-up or unsigned cookie is treated as no cookie (400 for a policy save, as now). The flood test of task 16 and attack4_visitor_cookie.py must still hold; add a test that a fresh page load followed by a policy save works with no run, and one that a hand-written cookie is refused.
2. THE INSTANT BETWEEN THE TAP'S LOOK AND ITS SEND. Task 21 left in the README Limits: a payment the AI itself sends for the same invoice between the tap's re-check and the tap's forward is not seen. Close it: the owner's approve (re-check plus forward) and the agent's own money moves (the check plus the forward in Receipts.call) take the SAME per-run lock, so one cannot happen in the other's gap. For the MCP workspace, the same lock covers MCP tool calls and phone taps on MCP holds. Test with threads: an approve and an agent payout for the same invoice started together, thousands of times; exactly one pays every time. Then remove that line from the README Limits.

Follow every steering file. Do not touch receipts/measure.py, receipts/rules.py or results/. Keep the README's counts true (task 22; the spec-change count only if this is a new change rather than an amendment, say which you chose). Run .venv\Scripts\python.exe -m pytest -q until everything passes, then pytest -m recorded -q, then scratch_attacks/attack4_visitor_cookie.py and attack4_tap.py. Report what you changed and both test counts.
```

## What Kiro did and reported

```text
kiro-cli.exe : [INFO] [KRS] <-- GenerateAssistantResponseCommand done totalEvents=8
I'll start by looking at the repo and the spec.
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] Run Command
[tool] status: Completed
[tool] status: Completed
[tool] Read File
[tool] Read File
[tool] status: Completed
[tool] status: Completed
Now Receipts core.
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
[tool] Write File
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
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
Now the recorded run and the two attack scripts.
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
Both changes are in: rules can be saved straight after loading the page, and the owner's approve and the agent's own payments now share one lock. The full suite passes with 503 tests. `pytest -m recorded -q` passes with 5 tests. Both attack scripts pass (3 tests). I did not run the validation sub-agent, and I did not touch `receipts/measure.py`, `receipts/rules.py` or `results/`.
**Spec first.** I amended Requirement 19 rather than adding a new one. Item 11 is reworded for the signed cookie and item 13 is new (the lock); the test item is now 14. I added "Task 22" to the design and task 22 to `tasks.md`. The spec-change count stays at seventeen, with a sentence under item 17 saying task 22 is part of it. Requirements stay at 19 and tasks are now 1 to 22.
**1. Saving rules before a run**
- **The cookie.** The cookie is now `<id>.<HMAC-SHA256 tag>`. The page load sets it and creates nothing.
- **The key.** It comes from `CARBON_COPY_KEY`'s text with a fixed label, so restarts of the hosted demo keep accepting cookies, or from memory if that variable is unset. It is never the signing key and is never written anywhere.
- **Who can create a visitor.** A rules save with a valid signed cookie creates its visitor and counts against the 30-per-10-minutes address limit. A made-up, unsigned or wrongly signed cookie is treated as no cookie, so the save gets 400 as before.
- **Taps.** A tap does not create a visitor. A tap with no run behind it has nothing to approve and answers 404, so creating a visitor would only use memory.
- **Existing code.** The visitor-table key is now the whole signed cookie value, so the existing visitor-table tests still work.
**2. The instant between the tap's look and its send**
- **The lock.** `Receipts` now has one lock, `run_lock` (it replaces `_tap_lock`, and is re-entrant). `call` holds it for a money move from check to forward, and `approve` and `decline` hold it too. Reads take no lock.
- **MCP.** The MCP tools and the phone's taps on MCP holds act on the same `Receipts` object, so the same lock covers them.
- **Scope.** The change in `core.py` is only the lock, not the scoring.
- **README.** I removed the gap sentence from the Limits and retitled that item "The owner's tap looks again."
**Tests**
- **New file.** `tests/test_carbon_round7.py` has 25 tests.
- **Cookie tests.** A page load then a rules save with no run works. Nine kinds of hand-written cookie are refused. Rules saves count against the address limit. A flood of made-up cookies pushes no one out.
- **Race tests.** The thousands-of-races test runs 2,500 approve-versus-agent-payout races on one invoice, and exactly one pays every time. A control run with the lock removed and a slow send pays twice, so the test can detect a missing lock.
- **Updated tests.** Three older tests asserted the old "400 until a run" behaviour. I updated `test_f4_a_policy_request_with_no_cookie_keeps_nothing` in `test_carbon_round4.py` and a test in `test_carbon_round6.py`. I also updated `test_unticking_a_rule_changes_only_that_visitors_runs` in `test_app_visitors.py`, and the "tasks 1 to 21" README pins in two tests.
**Test counts**
| Run | Result |
|---|---|
| `pytest -q` | 503 passed, 5 deselected |
| `pytest -m recorded -q` | 5 passed |
| `attack4_visitor_cookie.py` and `attack4_tap.py` | 3 passed |
`scratch_attacks/attack3_tap_lost.py` (an older script) sets an unsigned cookie by hand, so it no longer works as written. I left it alone.
```
