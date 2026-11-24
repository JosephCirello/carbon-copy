# Kiro run: the custom agent carbon-attacker, second run (MCP loaded)

## Instructions given

```text
kiro-cli chat --agent-engine v2 --agent carbon-attacker --no-interactive --trust-all-tools

Second round. Your first run's six findings are fixed (receipt times in milliseconds, wrong-shaped books, fields outside the seal, non-canonical base64 signatures, keys with spaces; the value-versus-text sealing is documented and out of scope). First list the carbon-copy MCP tools you can see and call one of them on a fresh run, and say what it returned. Then look for NEW shapes only: reorder or duplicate receipts; replay an older book or an older stamp against a newer one; a stamp from one run used against another run's book; a book whose head is valid but whose receipts were swapped for another run's; anything that makes the browser check (static/carbon_verify.js under node) and the Python check disagree; anything on screen or in an export that shows data the seal does not cover. Each as a scratch_attacks/attack2_<name>.py test. Report proven findings only, plus one line for each attack that was caught.
```

## What Kiro did and reported

```text
I'll start with the MCP check: a read-only call to two of the tools, plus a look at the repo layout.
kiro-cli.exe : [tool] Running: @carbon-copy/receipts_holds
[tool] Running: @carbon-copy/list_recent_orders
[tool] Reading listing carbon-copy
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
The MCP tools work. Next I'll read the code under attack.
[tool] Reading carbon.py:1, carbon_verify.js:1, attack_common.py:1, attack_disagree.py:1
[tool] status: Completed
Now the server routes, the export and the Carbon copy tab on screen.
[tool] Running: Select-String -Path app.py -Pattern 'carbon|export|download|csv|accountant|stamp' 
-CaseSensitive:$false | ForEach-Object { "$($_.LineNumber): $($_.Line.Trim())" }
[tool] Running: Select-String -Path static\app.js -Pattern 'carbon|Fingerprint|Receipt #|stamp|pinned|localStorage' 
-CaseSensitive:$false | ForEach-Object { "$($_.LineNumber): $($_.Line.Trim().Substring(0...
[tool] status: Completed
[tool] status: Completed
[tool] Reading app.py:96-135, app.py:251-330, app.py:481-700
[tool] status: Completed
[tool] Reading app.js:6-67, app.js:216-255, app.js:291-330, app.js:475-644
[tool] status: Completed
[tool] Running: Select-String -Path receipts\core.py -Pattern 'carbon|emit\(|"verdict"|def approve|def decline|def 
_decide|stamp' | ForEach-Object { "$($_.LineNumber): $($_.Line.Trim())" }
[tool] status: Completed
[tool] Reading core.py:21-195
[tool] status: Completed
[tool] Reading app.py:337-416, core.py:176-235
[tool] status: Completed
[tool] Running: Select-String -Path tests\test_carbon_app.py -Pattern 'TestClient|def _run|replay|def 
test_.*download|trusted_key|bookParts' | Select-Object -First 30 | ForEach-Object { "$($_.LineNumber):...
[tool] status: Completed
[tool] Reading test_carbon_app.py:21-70, test_carbon_app.py:441-480
[tool] status: Completed
[tool] Reading test_carbon_app.py:1-22
[tool] status: Completed
[tool] Creating attack2_common.py
[tool] status: Completed
[tool] Creating attack2_download_cli.py
[tool] status: Completed
[tool] Running: .venv\Scripts\python.exe -m pytest scratch_attacks/attack2_download_cli.py -q -s -x 2>&1 | 
Select-Object -Last 25
[tool] status: Completed
[tool] Running: .venv\Scripts\python.exe -m pytest scratch_attacks/attack2_download_cli.py -q -s -x 2>&1 | 
Select-String 'exit 1'
[tool] status: Completed
[tool] Creating attack2_disagree.py
[tool] status: Completed
[tool] Running: .venv\Scripts\python.exe -m pytest scratch_attacks/attack2_disagree.py -q -s 2>&1 | Select-String 
'python:|passed|failed|FAILED|Error'
[tool] status: Completed
[tool] Creating attack2_cli_crash.py
[tool] Creating attack2_replay_mix.py
[tool] status: Completed
[tool] status: Completed
[tool] Running: .venv\Scripts\python.exe -m pytest scratch_attacks/attack2_cli_crash.py 
scratch_attacks/attack2_replay_mix.py -q -s 2>&1 | Select-String 'exit |passed|failed|FAILED|^\{'
[tool] status: Completed
[tool] Running: cd scratch_attacks; ..\.venv\Scripts\python.exe -c " import sys; sys.path.insert(0,'..') import json 
from receipts.core import Receipts from receipts.carbon import CarbonCopy, Signer, veri...
[tool] status: Completed
[tool] Running: $env:PAYPAL_MODE='standin'; .venv\Scripts\python.exe -c " import sys, json from receipts.core import 
Receipts from receipts.carbon import CarbonCopy, Signer, verify from cryptography.hazma...
[tool] status: Completed
[tool] Running: $env:PAYPAL_MODE='standin'; .venv\Scripts\python.exe -c " import sys, json from receipts.core import 
Receipts from receipts.carbon import CarbonCopy, Signer, verify from cryptography.hazma...
[tool] status: Completed
[tool] Creating attack2_screen_claims.py
[tool] status: Completed
[tool] Running: $env:PAYPAL_MODE='standin'; .venv\Scripts\python.exe -m pytest 
scratch_attacks/attack2_screen_claims.py -q -s 2>&1 | Select-String 'approve returned|kinds:|owner event|page 
sentence|mode:|...
[tool] status: Completed
[tool] Running: Select-String -Path receipts\paypal.py -Pattern 'def create_refund|def accept_dispute_claim|def 
create_payout|def update_vendor|"error"|raise ' | Select-Object -First 40 | ForEach-Object {...
[tool] status: Completed
[tool] Running: cd ; $py = @' import re p = 
"scratch_attacks/attack2_screen_claims.py" s = open(p, encoding="utf-8").read() start = 
s.index("@pytest.mark.skipif(NODE is N...
[tool] status: Completed
[tool] Running: cd ; $py = @' p = "scratch_attacks/attack2_screen_claims.py" s = 
open(p, encoding="utf-8").read() s = s.replace('h1 = r.call("create_refund", {"capture_id...
[tool] status: Completed
[tool] Creating attack2_device_forgets.py
[tool] status: Completed
[tool] Running: .venv\Scripts\python.exe -m pytest scratch_attacks/attack2_device_forgets.py -q -s 2>&1 | 
Select-String 'stamps the device|forged run0|passed|failed|Error'
[tool] status: Completed
I proved eight problems, none of which lets someone forge a book that reads intact. The two with the most weight are the owner-approval sentence (finding 3) and the cut-short stamp store (finding 6). I did not look for a real Ed25519, hash or chain hole beyond the tries listed under "Tried and caught".
**MCP tools.** I could see all 12 carbon-copy tools: `accept_dispute_claim`, `create_payout`, `create_refund`, `get_dispute`, `get_order`, `get_shipment_tracking`, `list_recent_orders`, `list_transactions`, `list_vendors`, `payments_book`, `receipts_holds` and `update_vendor_payee`. I called two read-only ones on a fresh run. `receipts_holds` returned `[]`. `list_recent_orders` returned five orders, such as `TNA51YRGF6JGXJP6D` (Walnut side table, $180.00).
**Disclosure:** one exploratory script ran with `PAYPAL_MODE` unset. `make_paypal` then started the PayPal sandbox MCP subprocess ("Mode: Sandbox"). The one call it made was a payout to a vendor not in the master, and the vendor-master rule blocked it before anything was forwarded. No money move was attempted. I can't rule out that the rule check made a read-only lookup to the sandbox. Every later run used `PAYPAL_MODE=standin`.
In each test the assertion states what the product should do. A FAILED line is a finding.
## Proven findings
1. **The file the Download button writes can't be read by the README's command-line check.**
   - **What I did:** I replayed a run through the app and built the file exactly as `bookParts()` in `app.js` does: `{book, stamps, trusted_key}`. I ran `python -m receipts.carbon verify <file> --key <public key>`.
   - **What the check said:** exit 1, `receipt 1: this is not a carbon-copy book we can read`.
   - **What it should say:** intact, exit 0. The book inside the file is intact, and `verify()` called on `parts["book"]` agrees.
   - **Repro:** `.venv\Scripts\python.exe -m pytest scratch_attacks/attack2_download_cli.py -s`
2. **The command-line check prints a traceback on a deeply nested file.**
   - **What I did:** I gave it a book file, then a `--stamps` file, each holding 200,000 nested `[`.
   - **What it said:** exit 1 with a `RecursionError` traceback.
   - **What it should say:** exit 2 and one plain line, as the README promises ("never a traceback").
   - **Repro:** `pytest scratch_attacks/attack2_cli_crash.py -s -k "C1 or C2"`. The lone-surrogate case (C3) is handled correctly.
3. **The Carbon copy screen says "It went to PayPal" when PayPal refused.**
   - **What I did:** I held two $265 refunds on one capture and approved both. PayPal refused the second with `REFUND_AMOUNT_EXCEEDED`.
   - **Evidence:** both the sealed owner receipt and the sealed paypal receipt carry that error. The book reads intact.
   - **What the page's own `ccSentence` (extracted from `app.js` and run under node) says:** "Maya approved a held payment. It went to PayPal." and "Sent to PayPal…: create refund." Neither mentions the refusal.
   - **What it should say:** that PayPal said no.
   - **Repro:** `pytest scratch_attacks/attack2_screen_claims.py -s -k E1`
   - **Caveat:** my node harness uses a stub for `PP_NAME`, so the backend name in the paypal sentence differs slightly from the real page. The owner sentence is not affected.
4. **The two checks disagree on three inputs.** Python and the browser check (under node) give different answers in each case. All three are in `scratch_attacks/attack2_disagree.py`.
   - **B1:** a trusted key written in capitals, with stamps. Python says intact. The browser says "a stamp on your device is damaged or forged", because it doesn't lower-case the key before checking stamps. The page itself always lower-cases, so this only affects direct callers of `CarbonVerify.verify`.
   - **B2:** a genuine, validly signed stamp whose count is written `6.0`. Python says "damaged or forged", because `_whole` rejects floats. The browser says intact.
   - **B3 (hides a change):** a receipt written with `kind: null`, which `CarbonCopy.append(None, …)` allows. If its `kind` key is deleted, Python still says intact because `r.get("kind")` is None. The browser says "its content was changed". Receipts itself never writes a null kind, so this is low severity.
   - **Repro:** `pytest scratch_attacks/attack2_disagree.py -s -k "B1 or B2 or B3"`
5. **The screen's header labels and the Receipt # / Fingerprint columns sit next to data the seal doesn't cover.**
   - **E2:** the Carbon copy header ("the run with Carbon Copy on", "(a recorded run…)") reads `CC.mode` and `CC.source` from `/api/carbon`. Neither is sealed. I flipped them to `enforce` and `live run` on an observe run. The check still said intact, and the sealed verdict receipts still say `observe`. This test passes because it asserts today's behaviour.
   - **E3:** a ledger row from `_ledger_from(..., book=book)` gets the verdict's `receipt_n` and `fp`. Its `model`, `scenario` and `when` appear in no receipt.
   - **Repro:** `pytest scratch_attacks/attack2_screen_claims.py -s -k "E2 or E3"`
6. **The device keeps stamps for 12 runs, the server keeps 40, and a rewritten older book then reads intact.**
   - **What I did:** I ran the page's own device-store code under node with a stub `localStorage`. After 14 runs, the stamps for runs 0 and 1 were gone (`DEV_MAX_RUNS = 12`).
   - **Attack:** I rewrote run 0 as the key holder would: Maya's decline flipped to approved, everything re-signed with the real key, new head.
   - **With its stamp:** "receipt #2 no longer matches the stamp your device kept".
   - **After the device dropped the stamp:** `{'intact': True, 'count': 2}`.
   - **Mitigation and what's new:** the page does add "kept no stamp for this run" under INTACT. The README's Limits don't mention this eviction.
   - **Repro:** `pytest scratch_attacks/attack2_device_forgets.py -s`
7. **A stale copy of the book plus a later honest stamp reads CHANGED (D13).**
   - **What I did:** I took a book snapshot mid-run, appended one more receipt, then checked the snapshot against the newer stamp. Both Python and the browser check said "receipt #… no longer matches / shorter than a stamp".
   - **What it should say:** the check can't tell a stale copy from a cut-back book. The page should re-fetch before checking.
   - **What's proven and what isn't:** I proved this at the check level. `app.js` checks the cached `CC` without re-fetching. I did not reproduce it in a browser.
   - **Repro:** `pytest scratch_attacks/attack2_replay_mix.py -s -k D13`
## Tried and caught (asserted changed, in `attack2_replay_mix.py` and `attack2_disagree.py`, run under both checks)
- Swapped two receipts (D1).
- Swapped two receipts and renumbered them (D2).
- Duplicated a receipt (D3).
- Duplicated and renumbered it, with the head count edited (D4).
- Put another run's receipts under this run's valid head, same key (D5).
- Checked another run's book against this run's stamp (D7).
- Checked an older book against a newer stamp (D8).
- Checked a book against another run's stamp with the same count (D12).
- Rewrote a receipt's signature as `S+L` in the receipt (B4) and in the head (B5). Both checks reject it.
## Behaviour that matches the documented limits (asserted intact)
- Another genuine run, same key, presented as this run with no stamp for it (D6).
- An older stamp against a newer book (D9).
- A book cut back to a length that matches the device's newest stamp (D10).
- A count-0 stamp (D11).
Every test is in `scratch_attacks/`, in the `attack2_*.py` files.
```
