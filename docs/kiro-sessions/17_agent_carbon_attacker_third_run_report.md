# Kiro run: the same third run resumed (--resume) to write its report

## Instructions given

```text
Your run stopped with a network error (dispatch failure) before you wrote your report. Do not start over. Run every scratch_attacks/attack3_*.py you wrote (pytest -q -s -p no:cacheprovider), then write the report exactly as asked: proven findings only, each with its attack3 test, what you did, what happened and what should have happened; then one line per attack that was caught. Change nothing outside scratch_attacks/.
```

## What Kiro did and reported

```text
kiro-cli.exe : [tool] Running: cd ; $env:PAYPAL_MODE="standin"; Get-ChildItem 
scratch_attacks\attack3_*.py | Where-Object Name -ne 'attack3_common.py' | ForEach-Object { "=== " + $_.Nam...
[tool] status: Completed
# Third-round report
Every `attack3_*.py` was run with `pytest -q -s -p no:cacheprovider` on the stand-in with throwaway keys. A failing test means the attack worked, because each test asserts the behaviour that should have happened. I changed nothing outside `scratch_attacks/`. The helpers are in `attack3_common.py`, and the `probe3_*.py` files are my exploration scripts.
## Proven findings
**F1. The MCP path writes no carbon copy at all.** Test: `attack3_mcp_unrecorded.py`, 3 tests, all pass.
- **What I did:** I started the app with the hosted settings (`RECEIPTS_MCP_ON_PHONE=0`) and called `create_payout` through `/mcp/` as an anonymous client.
- **What happened:** The payout returned `SUCCESS`. A repeat call was decided by the checker. `web.MCP_RECEIPTS.carbon` is `None`, so no receipt exists for the verdict, the PayPal move or any owner tap. `/api/carbon` is empty for every visitor, and `?sid=mcp` returns 404.
- **What should have happened:** The README says every money move and every tap gets a copy. The MCP workspace is the one path with none, and the README doesn't say so.
**F2. With the default local config, any web visitor can decide the MCP holds, and nothing is sealed.** Same file.
- **What I did:** An MCP client asked to change Blue Ridge's payee to `evil@example.test`. A fresh cookie jar that had run nothing then called `/api/approve` with `session:"mcp"`.
- **What happened:** The approve returned 200 and the vendor master changed. The answer carried no `stamp`, and the visitor's book stayed empty. The next MCP `create_payout` to the new address was ALLOWED and `SUCCESS`.
- **What should have happened:** This is the `RECEIPTS_MCP_ON_PHONE=1` default, which the README's own run commands use. The README says nothing about it. The Dockerfile and `render.yaml` switch it off, but only `app.py` comments say why. Decisions on shared MCP holds should be sealed, or the README should state the exposure.
**F3. An honest book read while a run is writing can say CHANGED.** Tests: `attack3_book_race.py`, `attack3_book_race_app.py`.
- **Cause:** `CarbonCopy.book()` copies the receipts without the lock, then takes the signed head in a second locked step. A receipt appended between the two makes `head.count` larger than the receipts handed out.
- **Through the real app:** In the last run, 3 of 690 `GET /api/carbon?sid=` fetches during a replay failed. The earlier run failed 5 of 239. Each failure said "receipts are missing from the end of the book". I used six reader threads, so one page click has a much lower chance.
- **Library level:** 7 of 84 and 8 of 8 honest reads failed under heavy writing.
- **What should have happened:** Copy the receipts and compute the head under one lock.
**F5. A tap that changes a hold but leaves no receipt.** Test: `attack3_tap_lost.py::test_F5`.
- **What I did:** A payout for INV-BR-1197 with `amount:"1836 USD"` is HELD. The rule book reads that amount as unknown. I then POSTed `/api/approve`.
- **What happened:** The stand-in cannot parse the amount, and `_forward` raises only on `TypeError`, so a `ValueError` escapes. The response was HTTP 500. The hold is now APPROVED, with no result. PayPal moved nothing, and the book holds only the `verdict` receipt: no `owner` receipt and no stamp. A second tap returns "no such waiting hold", so Maya can no longer decline it either. The phone card for an APPROVED hold reads "Approved · sent to PayPal" with empty ids.
- **What should have happened:** Either seal the tap and its failure, or leave the hold WAITING so it can be retried.
- **Reach:** I built the session the way `_register` does, not through a live model. A live agent writing "1836 USD" would reach the same state.
**F6. The checker ALLOWs and sends a payout whose amount is `"NaN"`.** Test: `attack3_tap_lost.py::test_F6`.
- **What happened:** `money("NaN")` gives nan, every limit comparison is false, and the verdict is ALLOW. The stand-in returned `SUCCESS`.
- **What should have happened:** Block or hold a non-finite amount.
- **Scope:** This is in the rule book (Receipts code), outside what Carbon Copy changes.
**F4. A second visitor can erase the first visitor's runs, holds and books.** Test: `attack3_visitors.py::test_F4`.
- **What I did:** Visitor A replayed a run and had a waiting hold. Then 301 cookie-less `POST /api/policy` requests each created a visitor. The table is a 300-entry least-recently-used list.
- **What happened:** A's `/api/carbon?sid=` returned 404, A's `/api/approve` returned 404, and `/api/holds` returned `[]`.
- **What should have happened:** One client shouldn't be able to evict others. Options are not creating state for an unseen cookie, or a per-address cap.
**F7. The command-line check prints a plain "intact" when it had nothing to hold the book against.** Test: `attack3_check_code.py::test_F7`.
- **What I did:** I re-signed a book under a new key with `forge_demo`. I wrote a download with no stamps and no trusted key, as a second device would. Then I ran `python -m receipts.carbon verify` from a fresh `git clone`.
- **What happened:** Exit 0 with `intact (12 receipts)`. The page, on the same inputs, adds "can only compare the book with itself".
- **What should have happened:** The CLI should print the same caveat when the file has no trusted key or no stamps.
**F8. The page's check can be replaced by any script on the page.** Test: `attack3_check_code.py::test_F8_run`.
- **What I did:** I ran the real `carbon_verify.js` under node in a `vm` sandbox, then did what any other script could do: `window.CarbonVerify.verify = async b => ({intact:true,...})`.
- **What happened:** A forged book that read "signed with a different key" now reads `intact:true`. `app.js` looks up `window.CarbonVerify.verify` at click time. `index.html` loads AG Grid from jsDelivr with no `integrity=`. The file isn't frozen and is served by the same server, so an operator can serve a verifier that always says INTACT. The device's pinned key and stamps are same-origin localStorage, so they can be read or rewritten too.
- **What should have happened:** The README says the check runs in the browser, "never against what the server says". It should state that the verifying code itself comes from the server, and that the CLI on a saved download is the only check that doesn't depend on it.
- **Caveat:** This was node emulation, not a real browser.
**F9. The key an owner trusts has no source outside the server.** Tests: `attack3_check_code.py::test_F9` (two tests).
- **What happened:** I built a download from `forge_demo` with the forger's key as `trusted_key` and a matching stamp. The CLI exited 0 with "intact". The key in that file was `1c8378ea…`, while the owner's first-seen key was `bc677163…`. The README contains no public key to compare against.
- **What should have happened:** This is the trust-on-first-use limit the README already lists. The new part is that nothing out-of-band exists to check against, such as a key published in the README or repo.
**F10. After one hour the server drops a run, its waiting hold and its book.** Test: `attack3_expiry.py`.
- **What I did:** I moved a session's creation time back 61 minutes, since that is the only way to wait an hour in a test.
- **What happened:** `/api/approve` returned 404 "session expired", `/api/holds` returned `[]`, and `/api/carbon?sid=` returned 404. There is no receipt that the hold lapsed. The page does show "expired" for the hold.
- **What should have happened:** The README Limits mention only the 40-run cap. They should also say the one-hour expiry and the 300-visitor limit, and that a book not downloaded within the hour can't be fetched again.
**F11. `/mcp` keeps every argument forever and returns it all in one call.** Test: `attack3_size.py::test_F11`.
- **What happened:** 30 × 1 MB calls added about +36 MB of server memory. `receipts_holds` then returned 30 MB in one answer.
- **Limits:** A 5 MB body gets a 413, so 1 MB is the practical per-call size. There is no login, the workspace is shared, and only a restart clears it.
- **What should have happened:** Cap held and verdict history, or the size of stored arguments.
**F12. `POST /api/policy` stores `english` and `sources` of any size per visitor.** Test: `attack3_size.py::test_F12`.
- **What happened:** 10 fresh visitors × 4 MB added +40 MB, and every request returned 200. At the 300-visitor limit that is about 1.2 GB.
- **What should have happened:** Reject oversized policy text.
**F13. A deeply nested event breaks the stream to the page.** Test: `attack3_size.py::test_F13`.
- **What happened:** `app._data` catches only `ValueError`. With a 3,000-deep argument the generator raised `RecursionError` and delivered 0 chunks. The book sealed the same event without trouble.
- **What should have happened:** Send the sealed (cleaned) form, or catch `RecursionError`. Otherwise the page stops receiving stamps mid-run.
- **Reach:** I proved this at `_sse` function level. A live model would have to produce the nested argument.
## Caught
- **Cross-visitor reads and decisions** (`attack3_visitors.py`): B with A's exact sid and hold id gets 404 on book, approve, decline, tamper and forge. B sees no holds of A. The `mcp` session id is 404 in the hosted config.
- **Cookie value chosen by the client:** needs 24–64 URL-safe characters, and ids are random. Same chosen id means same visitor, by design. Not a break.
- **Download from a fresh clone:** it carries the book, the device's stamps for the run and the pinned key. The CLI and the page's `carbon_verify.js` agree on honest (intact), one receipt changed (receipt 12), forged under a new key and cut back to an older head (stamp). The CLI exits 0 or 1 to match.
- **What can't be exported:** The page exports only the stamps for the run on screen. The other 99 runs and the pinned key sit only in localStorage, with no export of them.
- **Two taps on one hold, and approve against decline** (`attack3_tap_race.py`): 0 contradictory results. That is 4,000 trials of each at the default thread-switch interval, plus the 300-trial rerun. Neither `approve` nor `decline` has a lock, so this is not proven safe.
- **Money moved with no result receipt:** a fuzz of `create_refund`, `accept_dispute_claim`, `create_payout` and `update_vendor_payee` with odd argument types found 0 cases of stand-in state changing without a `paypal` or `desk` receipt (`probe3_fuzz.py`).
- **Approve after a restart or expiry:** 404 "session expired", and no money moves.
- **Run and visitor caps:** 40 runs per visitor, 300 visitors. One run is about 0.14 MB in memory and its book 10 KB.
- **Tap cost on a large book:** `decline` on a 6,002-receipt book took 43 ms. An earlier 4,000-trial race run took about 30 minutes because each tap deep-copies the book, but a single tap is fine.
- **Very deep JSON to `/api/carbon/verify`:** depth 100,000 and above returns 400. Depth 1,000 returns a 500, and the server stays up (`probe3_size.py`).
```
