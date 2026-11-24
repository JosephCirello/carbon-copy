# Kiro run: the custom agent carbon-attacker, third run (stopped by a network error before its report)

## Instructions given

```text
Third round. Rounds one and two attacked the book's format and the two checks (Python and static/carbon_verify.js); those findings are fixed or written down in the README's "Limits we know about". Do not repeat them. A measurement outside the repo has since replayed all 1,444 recorded runs in both arms (2,888 books, 45,571 receipts): every honest book reads intact, every one-receipt change, forgery under a new key, swap of two receipts and cut-off ending (with the device's stamp) is caught, and the browser and Python checks agree on all 11,552 checks. So spend no time on single-book format attacks.

Attack what is LEFT, as a dishonest operator, a curious second visitor, or a buggy AI agent. Use the app itself (start it with PAYPAL_MODE=standin and drive it with FastAPI's TestClient or httpx, two separate cookie jars for two visitors), the MCP server (python -m receipts.mcp_server, or the app's /mcp), and the command line. Throwaway keys only; write only in scratch_attacks/ (attack3_<name>.py). Look for:

1. WHO CAN SEE AND DO WHAT. Can visitor B read visitor A's book, holds, stamps or ledger, or approve or decline A's held payment, by guessing or reusing a session id (sid), a hold id or a replay line? Can the MCP session's holds be decided from the web, and is that what the README says?
2. THE CHECK'S OWN CODE. "Check the book" runs static/carbon_verify.js, which the same server sends. Show concretely what a dishonest operator could do with that (for example a page that always says INTACT), and check what an owner can do today to check the book WITHOUT trusting the server: does the downloaded file carry everything the command-line check needs (book, stamps, the key the device trusts)? Does `python -m receipts.carbon verify` on that download, from a fresh clone, reach the same answer as the page? If the device's stamps and pinned key cannot be exported, say so.
3. RECEIPTS THAT NEVER GET WRITTEN. Find any money move, owner tap or end-of-day report that reaches PayPal (the stand-in) or changes a hold WITHOUT its receipt in the book: errors and exceptions mid-call, the MCP path, an approve after a restart, two taps at once on the same hold (threads), approve and decline racing.
4. SIZE AND MEMORY. What does one visitor's huge event (a 5 MB tool argument, deep nesting, thousands of holds) do to the book, the page and the server? How many visitors and runs does the server keep, and what happens to the books and stamps it drops?

Report proven findings only, each with its scratch_attacks/attack3_*.py test, what you did, what happened, and what should have happened; then one line for each attack that was caught. Change nothing outside scratch_attacks/.
```

## What Kiro did and reported

```text
I'll start by reading the repo layout and the code paths that matter: the app, the carbon module and the MCP server.
kiro-cli.exe : [tool] Reading listing carbon-copy
[tool] status: Completed
Next, app.py, the MCP server and the Receipts core, since those hold the session, hold and emit logic.
[tool] Reading app.py:1, mcp_server.py:1
[tool] status: Completed
Now core.py, where holds, approve, decline and emit live.
[tool] Reading core.py:1, Dockerfile:1, render.yaml:1
[tool] status: Completed
[tool] Reading carbon.py:1-520
[tool] status: Completed
Next I'll look at how the page downloads the book and keeps the device's stamps and pinned key, in app.js and index.html.
[tool] Running: cd ; Select-String -Path static\app.js,static\index.html -Pattern 
'localStorage|sessionStorage|trusted_key|Download|download|carbon_verify|integrity|stamp...
[tool] Running: cd ; Select-String -Path receipts\carbon.py -Pattern '^def |^class 
|__main__|argparse|stamps|trusted' | Select-Object -Skip 40 | ForEach-Object { "{0}: {1...
[tool] status: Completed
[tool] status: Completed
[tool] Reading app.js:6-80, app.js:581-705
[tool] status: Completed
Next I'll check what the spec and README promise about the MCP path and the book, so I can compare it with the code.
[tool] Running: cd ; Select-String -Path README.md,.kiro\specs\carbon-copy\*.md 
-Pattern 'MCP|/mcp|every money move|every move|MCP_ON_PHONE|restart|memory|keeps only|100 ...
[tool] status: Completed
The tests already cover cross-visitor holds and the MCP phone toggle. I'll reuse the harness from the earlier attack files and the visitor tests.
[tool] Reading attack2_common.py:1, test_app_visitors.py:1-90
[tool] status: Completed
I'll check the environment (versions, node, httpx) and start the app on a local port with a throwaway key, so I can drive `/mcp` over real HTTP.
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -c "import 
mcp,fastapi,httpx,sys;print(sys.version.split()[0],getattr(mcp,'__version__',None),fa...
[tool] status: Completed
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; Test-Path .venv\Scripts\python.exe; 
.venv\Scripts\python.exe -m pip list 2>&1 | Select-String -Pattern 'mcp|fastapi|httpx...
[tool] status: Completed
The venv ships `httpx2` and `requests`, so I'll use `requests` against a live uvicorn for the MCP path. First a probe of the MCP session handshake and the first tool calls.
[tool] Creating attack3_common.py
[tool] Creating probe3_mcp.py
[tool] status: Completed
[tool] status: Completed
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe 
scratch_attacks\probe3_mcp.py 2>&1 | Select-Object -First 30
[tool] status: Completed
The MCP path works and a fresh web visitor sees the MCP hold. Next I'll check whether a web tap on it writes any receipt or stamp, and whether it can steer later payouts.
[tool] Creating probe3_mcp.py
[tool] status: Completed
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe 
scratch_attacks\probe3_mcp.py 2>&1 | Select-Object -First 30
[tool] status: Completed
[tool] Creating attack3_mcp_unrecorded.py
[tool] status: Completed
One assertion in that file is meaningless, so I'm removing it before running.
[tool] Editing attack3_mcp_unrecorded.py
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest 
scratch_attacks/attack3_mcp_unrecorded.py -q -s -p no:cacheprovider 2>&1 | Select-Obje...
[tool] status: Completed
[tool] status: Completed
My own test bug (the dummy dict has no `head` key). I'm simplifying that loop.
[tool] Editing attack3_mcp_unrecorded.py
[tool] status: Completed
That edit added another junk line. I'm removing it.
[tool] Editing attack3_mcp_unrecorded.py
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest 
scratch_attacks/attack3_mcp_unrecorded.py -q -s -p no:cacheprovider 2>&1 | Select-Obje...
[tool] status: Completed
[tool] status: Completed
[tool] Creating attack3_book_race.py
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest 
scratch_attacks/attack3_book_race.py -q -s -p no:cacheprovider 2>&1 | Select-Object -L...
[tool] status: Completed
[tool] status: Completed
[tool] status: Failed
The race is real at library level, but that writer runs at an unrealistic pace. I'll try it through the real app, with readers hitting `/api/carbon` while a recorded replay writes.
[tool] Creating attack3_book_race_app.py
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest 
scratch_attacks/attack3_book_race_app.py -q -s -p no:cacheprovider 2>&1 | Select-Objec...
[tool] status: Completed
[tool] status: Completed
[tool] status: Failed
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest 
scratch_attacks/attack3_visitors.py -q -s -p no:cacheprovider 2>&1 | Select-Object -La...
[tool] status: Completed
The file write failed because I left out the path. I'm resending it.
[tool] Creating attack3_visitors.py
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest 
scratch_attacks/attack3_visitors.py -q -s -p no:cacheprovider 2>&1 | Select-Object -La...
[tool] status: Completed
[tool] status: Completed
[tool] Editing attack3_common.py
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest 
scratch_attacks/attack3_visitors.py -q -s -p no:cacheprovider 2>&1 | Select-Object -La...
[tool] status: Completed
[tool] status: Completed
[tool] Creating attack3_tap_race.py
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest 
scratch_attacks/attack3_tap_race.py -q -s -p no:cacheprovider 2>&1 | Select-Object -La...
[tool] status: Completed
[tool] status: Completed
[tool] Running: cd ; (Get-Content scratch_attacks\attack3_tap_race.py) -replace 
'^TRIALS = 4000','TRIALS = 300 # the 4000-trial run found 0 (about 30 minutes: every tap d...
[tool] status: Completed
[tool] Reading paypal.py:256-330
[tool] status: Completed
Next, `rules.note_paid` and the vendor lookup, to find an argument that makes `_forward` raise after PayPal has already moved money.
[tool] Running: cd ; Select-String -Path receipts\rules.py -Pattern 'def 
note_paid|def money|def vendor|paid_set|self.paid' -Context 0,6 | Select-Object -First 8 | ForEac...
[tool] status: Completed
[tool] Creating probe3_args.py
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe 
scratch_attacks\probe3_args.py 2>&1 | Select-Object -Last 30
[tool] status: Completed
[tool] status: Completed
[tool] Creating probe3_args2.py
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe 
scratch_attacks\probe3_args2.py 2>&1 | Select-Object -Last 40
[tool] status: Completed
[tool] status: Completed
[tool] Creating attack3_tap_lost.py
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest 
scratch_attacks/attack3_tap_lost.py -q -s -p no:cacheprovider 2>&1 | Select-Object -La...
[tool] status: Completed
[tool] status: Completed
Both tests fail as intended. I'll pull the printed line to confirm the HTTP status and the hold state.
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest 
scratch_attacks/attack3_tap_lost.py -q -s -p no:cacheprovider 2>&1 | Select-String -Pa...
[tool] status: Completed
F5 confirmed. Next I'll check what the phone prints for a hold in that state.
[tool] Running: cd ; (Get-Content static\app.js)[412..420] | ForEach-Object { 
$_.Substring(0,[Math]::Min(420,$_.Length)) }
[tool] status: Completed
The phone would show "Approved · sent to PayPal" with an empty id for that hold. Next, Q2. I'll find where the page keeps stamps during a run, so I can rebuild its download exactly.
[tool] Running: cd ; Select-String -Path static\app.js -Pattern 'deviceKeep\(' | 
ForEach-Object { "{0}: {1}" -f $_.LineNumber,$_.Line.Trim().Substring(0,[Math]::Min(200,$...
[tool] status: Completed
[tool] Running: cd ; Get-Content scratch_attacks\attack_common.py | Select-Object 
-Skip 28; Select-String -Path static\carbon_verify.js -Pattern 'freeze|window\.CarbonVer...
[tool] status: Completed
[tool] Reading carbon.py:687-736
[tool] status: Completed
[tool] Creating attack3_check_code.py
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest 
scratch_attacks/attack3_check_code.py -q -s -p no:cacheprovider 2>&1 | Select-String -...
[tool] status: Completed
[tool] status: Completed
[tool] Running: cd ; git clone --quiet . scratch_attacks\fresh_clone 2>&1 | 
Select-Object -First 5; git status --short | Select-Object -First 5
[tool] status: Completed
[tool] Running: cd ; Get-ChildItem scratch_attacks\fresh_clone -Force | 
Select-Object -First 8 | ForEach-Object Name; git -C scratch_attacks\fresh_clone log --oneline -1 ...
[tool] status: Completed
The earlier clone left only a `.git` folder. I'll remove that scratch directory (mine) and re-clone with the error visible.
[tool] Running: cd ; Remove-Item -Recurse -Force scratch_attacks\fresh_clone; git 
clone . scratch_attacks\fresh_clone 2>&1 | Select-Object -First 12
[tool] status: Completed
The clone is complete now. I'm making the fixture reuse a complete clone instead of re-cloning.
[tool] Editing attack3_check_code.py
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest 
scratch_attacks/attack3_check_code.py -q -s -p no:cacheprovider 2>&1 | Select-String -...
[tool] status: Completed
[tool] status: Completed
[tool] Running: cd ; (Get-Content scratch_attacks\attack3_check_code.py -Raw) 
-replace "fs.readFileSync\(process.argv\[1\], 'utf8'\), ctx\)","fs.readFileSync(process.argv...
[tool] status: Completed
[tool] Creating probe3_size.py
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe 
scratch_attacks\probe3_size.py 2>&1 | Select-Object -Last 20
[tool] status: Completed
[tool] status: Completed
Two harness problems. The venv `python.exe` is a launcher, so my RSS number came from the wrong process. The 5 MB MCP response also wasn't JSON, so I'll look at what came back.
[tool] Creating probe3_size2.py
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe 
scratch_attacks\probe3_size2.py 2>&1 | Select-Object -Last 12
[tool] status: Completed
[tool] status: Completed
[tool] Editing attack3_common.py
[tool] Creating probe3_size.py
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe 
scratch_attacks\probe3_size.py 2>&1 | Select-Object -Last 20
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] Creating probe3_size3.py
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe 
scratch_attacks\probe3_size3.py 2>&1 | Select-Object -Last 8
[tool] status: Completed
[tool] status: Completed
Per-run memory is small (about 0.14 MB per run, 10 KB per book), so the 40-run cap holds up. Next, what happens to a run after the 1-hour server expiry, and whether the README says so.
[tool] Running: cd ; Select-String -Path 
README.md,.kiro\specs\carbon-copy\*.md,static\index.html,static\app.js -Pattern 'hour|expire|EXPIRED_TEXT' | 
ForEach-Object { "{0...
[tool] Creating attack3_expiry.py
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest 
scratch_attacks/attack3_expiry.py -q -s -p no:cacheprovider 2>&1 | Select-String -Patt...
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] Creating probe3_fuzz.py
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe 
scratch_attacks\probe3_fuzz.py 2>&1 | Select-Object -Last 25
[tool] status: Completed
[tool] status: Completed
[tool] Creating attack3_size.py
[tool] Running: cd ; $env:PAYPAL_MODE="standin"; .venv\Scripts\python.exe -m pytest 
scratch_attacks/attack3_size.py -q -s -p no:cacheprovider 2>&1 | Select-String -Patter...
[tool] status: Completed
[tool] status: Completed
Error: Internal error (code -32603): Encountered an error in the response stream: An unknown error occurred: dispatch 
failure
```
