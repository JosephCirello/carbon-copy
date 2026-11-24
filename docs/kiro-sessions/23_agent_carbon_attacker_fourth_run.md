# Kiro run: the custom agent carbon-attacker, fourth run (on tasks 15 to 18)

## Instructions given

```text
Fourth round, on the finished build. Rounds one to three are fixed or written down in the README's "Limits we know about" (read it first, and read Requirements 15 to 18). Do not repeat them, and do not re-attack the book's format: tests/test_carbon_recorded_runs.py already replays all 1,444 recorded runs (2,888 books) and catches every one-receipt change.

Attack the NEW code of tasks 15 to 18, as a dishonest operator, an anonymous MCP client, a second visitor or a buggy AI agent. Start the app with PAYPAL_MODE=standin (and once with RECEIPTS_BEHIND_PROXY=1) and drive it over real HTTP; throwaway keys only; write only in scratch_attacks/ (attack4_<name>.py). Look for:

1. THE MCP BOOK AND ITS GUARD. Can a money move through /mcp or the stdio server still happen without a receipt (errors mid-call, a refused call, the 20 MB cap reached mid-call, the phone approving an MCP hold)? Can the 256 KB body limit or the 60-a-minute limit be stepped around (chunked bodies, compressed bodies, many small calls, batched JSON-RPC, X-Forwarded-For with RECEIPTS_BEHIND_PROXY=1 and without)? Does carbon_book's book verify intact with the command line and verify.html?
2. THE OWNER'S TAP. After task 15 an approve writes "approved" before forwarding and then "sent" or "not_sent". Find any order of events where the book and what PayPal (the stand-in) did disagree: a forward that succeeds but raises after, a timeout, two taps, approve on a hold whose argument was cut, the NaN rule and refunds with and without amounts.
3. verify.html AND --key-file. Can a download be made that verify.html calls INTACT while the command line with --key-file HOSTED_KEY.txt calls CHANGED, or the reverse? Does verify.html really make no network request (check its CSP and every tag)? Does it handle a hostile download (huge, deeply nested, script in a field) without running anything from the file?
4. THE CLOCK AND THE VISITOR TABLE. Can a second visitor or one address keep runs alive forever, push other visitors out despite task 16's rules, or make another visitor's hold lapse? Does the 24-hour rule hold when a run has several holds?

Report proven findings only, each with its scratch_attacks/attack4_*.py test, what you did, what happened, and what should have happened; then one line for each attack that was caught. Change nothing outside scratch_attacks/.
```

## What Kiro did and reported

```text
I'll start by reading the repo layout and the spec for Requirements 15 to 18.
kiro-cli.exe : [tool] Reading listing carbon-copy, listing carbon-copy
[tool] Running: git status --short | Select-Object -First 20; git log --oneline | Select-Object -First 8
[tool] status: Completed
[tool] status: Completed
[tool] Reading mcp_server.py:1, app.py:1
[tool] status: Completed
[tool] Reading core.py:1
[tool] status: Completed
[tool] Reading carbon.py:1-520
[tool] status: Completed
[tool] Reading carbon.py:521
[tool] status: Completed
[tool] Reading verify.html:1, HOSTED_KEY.txt:1
[tool] status: Completed
[tool] Running: $env:PAYPAL_MODE="standin"; Select-String -Path receipts\rules.py -Pattern "def money|def 
note_paid|def check|HOLD|NaN|isfinite" | Select-Object -First 60; Select-String -Path receipts\pay...
[tool] Running: Select-String -Path .kiro\specs\carbon-copy\requirements.md -Pattern "^#+ " | Select-Object -Last 14; 
Select-String -Path tests\test_carbon_round5.py,tests\test_carbon_app.py -Pattern "/mc...
[tool] status: Completed
[tool] status: Completed
[tool] Reading requirements.md:151-210, rules.py:41-70, rules.py:136-165, paypal.py:171-320
[tool] status: Completed
[tool] Running: Get-Content render.yaml; Select-String -Path README.md -Pattern "idle|3 hours|three hours" | 
Select-Object -First 5; .venv\Scripts\python.exe -c "import httpx,sys;print(httpx.__version__)"...
[tool] status: Completed
[tool] Reading attack3_common.py:61, attack3_mcp_unrecorded.py:1
[tool] status: Completed
[tool] Creating attack4_common.py
[tool] status: Completed
[tool] Creating attack4_mcp_race.py
[tool] status: Completed
[tool] Running: $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest scratch_attacks/attack4_mcp_race.py -q 
-s -p no:cacheprovider 2>&1 | Select-Object -Last 40
[tool] status: Completed
[tool] Creating attack4_mcp_limits.py
[tool] status: Completed
[tool] Running: $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest scratch_attacks/attack4_mcp_limits.py 
-q -s -p no:cacheprovider 2>&1 | Select-Object -Last 50
[tool] status: Completed
[tool] Running: $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest scratch_attacks/attack4_mcp_limits.py 
-q -s -p no:cacheprovider -k "xff_is_ignored or removes_the_60" 2>&1 | Select-String -P...
[tool] status: Completed
[tool] Running: Get-Content Dockerfile | Select-String -Pattern "CMD|uvicorn|FORWARDED|ENV|EXPOSE"; 
.venv\Scripts\python.exe -c "import uvicorn;print(uvicorn.__version__)"
[tool] status: Completed
[tool] Running: $code = @' import os, sys, socket, subprocess, time, requests os.environ["PAYPAL_MODE"]="standin" 
sys.path.insert(0, "scratch_attacks") from attack4_common import THROWAWAY, free_port, ROO...
[tool] status: Completed
[tool] Running: Select-String -Path receipts\paypal.py -Pattern "def _money" -Context 0,6 | Select-Object -First 3; 
Get-Content receipts\rules.py | Select-Object -Skip 176 -First 90; Select-String -Path s...
[tool] status: Completed
[tool] Running: Select-String -Path receipts\desk.py -Pattern "def update_vendor_payee|def call_vendor|def |\*\*" | 
Select-Object -First 30; Select-String -Path receipts\rules.py -Pattern "payout_approval...
[tool] status: Completed
[tool] Running: Get-Content receipts\rules.py | Select-Object -Skip 276 -First 40
[tool] status: Completed
[tool] Creating attack4_tap.py
[tool] status: Completed
[tool] Running: $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest scratch_attacks/attack4_tap.py -q -s -p 
no:cacheprovider 2>&1 | Select-String -Pattern "hold 2|first tap|sealed|second call|t...
[tool] status: Completed
[tool] Creating attack4_tap_timeout.py
[tool] status: Completed
[tool] Running: $env:PAYPAL_MODE="standin"; $env:CARBON_COPY_KEY="a4-"+[guid]::NewGuid().ToString("N"); 
.venv\Scripts\python.exe -m pytest scratch_attacks/attack4_tap_timeout.py -q -s -p no:cacheprovider ...
[tool] status: Completed
[tool] Creating attack4_server.py
[tool] status: Completed
[tool] Creating attack4_clock.py
[tool] status: Completed
[tool] Running: $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest scratch_attacks/attack4_clock.py -q -s 
-p no:cacheprovider 2>&1 | Select-String -Pattern "waiting holds|after 6.7|Maya's|firs...
[tool] status: Completed
[tool] Editing attack4_clock.py
[tool] Running: $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest scratch_attacks/attack4_clock.py -q -s 
-p no:cacheprovider -k default_table 2>&1 | Select-String -Pattern "one real|passed|fa...
[tool] status: Completed
[tool] status: Completed
[tool] Editing attack4_clock.py
[tool] Running: $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest scratch_attacks/attack4_clock.py -q -s 
-p no:cacheprovider -k default_table 2>&1 | Select-String -Pattern "one real|passed|fa...
[tool] status: Completed
[tool] status: Completed
[tool] Running: Select-String -Path tests\*.py -Pattern "verify.html" | Select-Object -First 8; Select-String -Path 
tests\test_carbon_round5.py,tests\test_carbon_round4.py -Pattern "__checkText" | Select-...
[tool] status: Completed
[tool] Reading test_carbon_round4.py:96-205
[tool] status: Completed
[tool] Creating attack4_verify_html.py
[tool] Running: $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest scratch_attacks/attack4_verify_html.py 
-q -s -p no:cacheprovider 2>&1 | Select-Object -Last 60 | ForEach-Object { if ($_.Leng...
[tool] status: Completed
[tool] status: Completed
[tool] Running: $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest scratch_attacks/attack4_verify_html.py 
-q -s -p no:cacheprovider -k "forged_download or hostile" 2>&1 | Select-String -Patter...
[tool] status: Completed
[tool] status: Failed
[tool] Running: $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest scratch_attacks/attack4_mcp_book.py -q 
-s -p no:cacheprovider 2>&1 | Select-Object -Last 25 | ForEach-Object { if ($_.Length ...
[tool] status: Completed
My write call dropped its path, so I'm re-issuing it.
[tool] Creating attack4_mcp_book.py
[tool] Running: $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest scratch_attacks/attack4_mcp_book.py -q 
-s -p no:cacheprovider 2>&1 | Select-Object -Last 25 | ForEach-Object { if ($_.Length ...
[tool] status: Completed
[tool] status: Completed
[tool] status: Failed
[tool] Running: $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest scratch_attacks/attack4_mcp_phone.py -q 
-s -p no:cacheprovider 2>&1 | Select-Object -Last 14 | ForEach-Object { if ($_.Length...
[tool] status: Completed
Same mistake: the path was missing. I'll re-issue the write with it.
[tool] Creating attack4_mcp_phone.py
[tool] Running: $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest scratch_attacks/attack4_mcp_phone.py -q 
-s -p no:cacheprovider 2>&1 | Select-Object -Last 14 | ForEach-Object { if ($_.Length...
[tool] status: Completed
[tool] status: Completed
[tool] status: Failed
[tool] Running: $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest 
scratch_attacks/attack4_visitor_cookie.py -q -s -p no:cacheprovider 2>&1 | Select-Object -Last 8 | ForEach-Object { if 
($_.Le...
[tool] status: Completed
[tool] Creating attack4_visitor_cookie.py
[tool] Running: $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest 
scratch_attacks/attack4_visitor_cookie.py -q -s -p no:cacheprovider 2>&1 | Select-Object -Last 8 | ForEach-Object { if 
($_.Le...
[tool] status: Completed
[tool] status: Completed
[tool] Running: $code = @' """Round 4, attack 2b: without RECEIPTS_BEHIND_PROXY a spoofed X-Forwarded-For must not 
change the address the limit counts. Uvicorn itself trusts X-Forwarded-For from 127.0.0.1...
[tool] Editing attack4_mcp_limits.py
[tool] status: Completed
[tool] status: Completed
[tool] Running: git diff --stat; git diff --ignore-all-space --ignore-cr-at-eol --stat
[tool] status: Completed
Round four found twelve problems, and each reproduces with a test in `scratch_attacks/`. Eight more attacks were caught.
Each finding test asserts the behavior the README or requirements promise, so a **failing** test is a confirmed finding. Run any one with:
`$env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest scratch_attacks/<file>.py::<test> -q -s`
I used throwaway keys and the stand-in only, started the app over real HTTP, and started it once with `RECEIPTS_BEHIND_PROXY=1`. I wrote only inside `scratch_attacks/`. I did not run the repo's own test suite. `git status` also shows `.kiro/specs/carbon-copy/tasks.md` and `tests/test_carbon_round3.py` as modified, and I didn't touch them. The tree was clean when I started.
## Findings
**1. The owner's tap pays a bill twice, with both approvals sealed.**
- *Test:* `attack4_tap.py::test_two_holds_for_one_bill_both_approved_pays_it_twice`.
- *What I did:* I sent a $9,000 payout for `INV-AT-9501` through `/mcp` twice. Both calls were held, because nothing was paid yet for the duplicate rule to match. I approved both holds over HTTP, with `RECEIPTS_MCP_ON_PHONE=1` only so the script could tap.
- *What happened:* two `SUCCESS` payouts and two sealed `sent` receipts. `approve` forwards the held arguments and never re-runs the rules.
- *Should have:* the second tap re-checks the invoice and refuses, or its card warns that the bill is already paid or waiting.
- *Same cause:* `test_a_waiting_hold_is_approved_after_the_same_bill_was_paid_another_way`. A $9,000 hold stays waiting, a $900 payout for the same invoice is allowed, then the tap on the old hold also returns `SUCCESS`.
- *Note:* this predates tasks 15 to 18, but task 15 rewrote `approve`.
**2. The book can say `not_sent` when PayPal took the payment.**
- *Test:* `attack4_tap_timeout.py`. It runs in-process because the stand-in cannot time out.
- *What I did:* I wrapped the stand-in's `create_payout` so it moves the money and then raises `TimeoutError`, as a read timeout would.
- *What happened:* the book holds `approved` and then `not_sent` with error "read timed out". PayPal's history shows the payout as `SUCCESS` at $9,000. The phone says "did not go to PayPal".
- *Should have:* an exception after the request left should be sealed as "no answer, may have been sent", not "not sent".
**3. `X-Forwarded-For` spoofing removes both address limits on the hosted configuration.**
- *Tests:* `attack4_mcp_limits.py::test_a_spoofed_first_forwarded_for_removes_the_60_a_minute_limit_behind_the_proxy` and `…removes_the_30_new_visitors_limit_behind_the_proxy`.
- *What I did:* I ran with `RECEIPTS_BEHIND_PROXY=1`, as `render.yaml` sets it. The app reads the first entry of the header, which a client writes.
- *What happened:*
  - One fixed address got 10 `429`s out of 70 requests. 300 requests with a different first entry got 0.
  - 34 new visitors from one address hit the 30-visitor limit. 120 spoofed ones were never refused.
- *Should have:* the limit counts the entry the proxy added (the last one), or a configured number of trusted hops.
- *Assumption:* I tested the app's reading of the header. I did not test Render's proxy, and I assume it appends the real address to the end, as proxies normally do.
**4. Read-only MCP tools keep growing the book past the cap.**
- *Test:* `attack4_mcp_limits.py::test_read_only_tools_keep_growing_the_book_past_its_cap`.
- *What I did:* I set `RECEIPTS_MCP_BOOK_MB=0.3`, which is only the documented knob lowered so the test is fast. The money tool was refused, as designed. Then I made 12 more `get_order` calls with 200 KB arguments.
- *What happened:* the book reached 3.0 MB, ten times the cap. Every call seals its full argument.
- *Should have:* "the MCP book stops at 20 MB" is false for read-only tools. At 20 MB each call can add up to about 250 KB (more than 600 KB with the seals counted twice), and finding 3 removes the request limit.
**5. A waiting payment is forgotten after 3 hours of silence, not 24.**
- *Test:* `attack4_clock.py::test_a_waiting_hold_is_kept_24_hours_but_the_visitor_is_forgotten_after_3`.
- *What I did:* I moved the clock forward on a running server. A hold was waiting. A request at 2.5 h still saw it. Then I sent no request for 3.5 h.
- *What happened:* the hold was gone and the book returned `404`, at 6 h in all. `_visitor` drops any visitor idle for `RECEIPTS_VISITOR_IDLE_HOURS`, which defaults to 3, before it looks at the 24-hour rule.
- *Should have:* a visitor with a waiting hold survives idle time up to 24 hours.
- *Scope:* this applies when no request arrives for 3 hours, such as a closed tab or a sleeping phone.
**6. New visitors push out a visitor whose payment is waiting.**
- *Tests:* `attack4_clock.py::test_ten_new_visitors_push_out_a_visitor_whose_hold_is_waiting` and `test_default_table_of_300_is_filled_by_one_address_behind_the_proxy_and_maya_is_pushed_out`.
- *What I did:* I filled the table with visitors that each had a run younger than an hour. The first test used `RECEIPTS_MAX_VISITORS=10`. The second used the default 300 and one real address with a spoofed first `X-Forwarded-For` entry (see finding 3). In both, Maya's hold was waiting and she was idle.
- *What happened:* her waiting hold was gone in both. The rule drops the least recently seen visitor with no hold and no young run, "and only then anyone". A young run protects exactly as much as a waiting hold does, so the least recently seen visitor goes, which is the idle owner.
- *Should have:* a waiting hold ranks above a young run.
**7. A tap on a hold that does not exist keeps a run alive indefinitely.**
- *Test:* `attack4_clock.py::test_bogus_taps_keep_a_run_alive_forever`.
- *What I did:* `/api/decline` calls `_touch` before it checks the hold id. I declined a nonexistent hold every 50 minutes for about 6.7 hours.
- *What happened:* the run, with nothing waiting, was still served (`200`). An identical run left alone was `404` after an hour. Such runs also count as "young" in finding 6.
- *Should have:* only a tap that decides a real waiting hold counts as activity.
**8. The 40-run cap drops a run that has a waiting payment.**
- *Test:* `attack4_clock.py::test_the_40_run_cap_drops_a_run_with_a_waiting_hold`.
- *What I did:* one visitor started a run with a hold, then 40 more.
- *What happened:* the oldest run, and its waiting hold, were silently dropped.
- *Should have:* it drops the oldest run with nothing waiting. The page starts two runs per click, so this takes 20 clicks.
**9. `verify.html` shows a green INTACT where the command line with `--key-file HOSTED_KEY.txt` says CHANGED.**
- *Test:* `attack4_verify_html.py::test_a_forged_download_is_INTACT_on_the_page_and_CHANGED_on_the_command_line`.
- *What I did:* I built a download from `forge_demo`, signed under a new key, with that key written as `trusted_key`.
- *What happened:* the page's big stamp says INTACT, with a smaller note that the key does not match the published one. The command line says CHANGED ("signed with a different key").
- *Should have:* the repo's own test pins the INTACT word, so this is documented behavior. The headline should not be green when the trusted key is not the published key.
**10. `verify.html` and the command line disagree on two kinds of hostile file.**
- *Test:* `attack4_verify_html.py::test_stamps_written_as_text_page_reads_them_as_a_list_command_line_does_not`.
  - *What I did:* I wrote `stamps` as a string: `"[]"`, `"null"`, or a real stamp list written as text.
  - *What happened:* the page reads each as a list and says INTACT. The command line says CHANGED.
  - *Effect:* weak. The page only ever ignores or uses the stamps.
- *Test:* `attack4_verify_html.py::test_a_whole_number_past_2_53_is_read_by_the_page_as_another_number`.
  - *What I did:* the key holder signs an event holding `9007199254740992`, and the file text says `…993`.
  - *What happened:* JavaScript rounds both to the same number and says INTACT. Python reads `…993` exactly and says CHANGED.
  - *Effect:* it needs the signing key, so it gives an outsider nothing. It is still a case where the two checks differ, and the page is the lenient one.
**11. A cookie the server never issued creates a visitor without a run.**
- *Test:* `attack4_visitor_cookie.py`.
- *What happened:* `POST /api/policy` with no cookie returns `400`. With `Cookie: receipts_visitor=AAAA…` (30 characters) it returns `200` and makes a visitor. Requirement 16.7 says it must not.
- *Effect:* small. These visitors are unprotected, so they are evicted first, but they still use the address's allowance.
**12. A payout of `-0.0` or `0` is allowed and shows as paid.**
- *Seen in:* `attack4_mcp_book.py` output. Payouts for `INV-AT-9709` and `INV-AT-9710` returned `SUCCESS` and appear in PayPal's transaction list.
- *Should have:* the NaN rule allows "non-negative", so zero passes. I did not test whether this later blocks the real payment of that invoice.
## Tried and caught
- **Concurrent duplicate payouts through `/mcp`.** 16 simultaneous calls for one invoice gave 1 payout and 15 stopped (`attack4_mcp_race.py`).
- **Batched JSON-RPC.** An array of 40 tool calls was rejected with `400`, so it cannot bypass the request limit.
- **Oversize bodies.** A 300 KB chunked body got `413`. A gzip body and a lying `Content-Length` were refused, and no tool ran (`attack4_mcp_limits.py::test_body_limit_chunked_gzip_and_lying_length`).
- **`X-Forwarded-For` without the proxy flag.** A non-loopback peer sending spoofed headers still got 30 `429`s out of 90 (`attack4_xff_noproxy.py`). Uvicorn itself trusts the header from `127.0.0.1`, so test this from another address.
- **Bad amounts.** NaN, Infinity and `[5]` were blocked or refused. `"1e2"` was paid as $100, which matches what the book recorded.
- **The MCP book and the checkers.** After mixed traffic (allowed, blocked, held, NaN, a 100 KB memo, errors), `carbon_book` verified intact in the command line and in `verify.html`. PayPal's invoice list matched the sealed `paypal` receipts exactly (`attack4_mcp_book.py`).
- **The phone's tap on MCP holds.** A hold with a cut argument was refused with no receipt written. Two simultaneous taps gave one payout. A tap at the cap got `409`, and a decline still wrote its receipt (`attack4_mcp_phone.py`).
- **Hostile downloads in `verify.html`.** Seven cases (script in fields, 150,000 levels deep, 20 MB text, `__proto__` keys) were never INTACT, threw nothing, and only `textContent` is used. The CSP is `default-src 'none'`.
I did not attack the stdio server or test the 24-hour rule on a run with several holds. Finding 5 already breaks the 24-hour rule for a single hold.
```
