# Tasks: the carbon-copy receipt book

- [x] 1. The book and the check (`receipts/carbon.py`)
  - [x] 1.1 `canonical()` and `fingerprint()` as in the design, with unit tests for key order and unicode
  - [x] 1.2 `Signer` with `from_env()`, `sign()`, `public_key_hex`; a test that no attribute or repr exposes the private key
  - [x] 1.3 `CarbonCopy.append()`, `receipts()`, `book()`; tests for numbering, the first `prev`, and that changing a returned copy does not change the book
  - [x] 1.4 `verify()` with all four failure reasons in plain words; one unit test per reason
  - _Requirements: 2, 3, 4, 5_

- [x] 2. Property-based tests (`tests/test_carbon.py`, hypothesis)
  - [x] 2.1 Any list of events gives an intact book
  - [x] 2.2 Changing any one field of any one receipt is caught at that receipt
  - [x] 2.3 Removing a receipt (including from the end) or swapping two is caught
  - _Requirements: 4_

- [x] 3. `tamper_demo()` and the command-line checker (`python -m receipts.carbon verify <file>`)
  - _Requirements: 6.3, 7, 8_

- [x] 4. Wire the book into Receipts
  - [x] 4.1 `Receipts(carbon=...)`; `emit()` appends every event
  - [x] 4.2 Integration test: one scenario on the stand-in gives an intact book with one receipt per event
  - _Requirements: 1, 8_

- [x] 5. The app
  - [x] 5.1 `GET /api/carbon`, `POST /api/carbon/verify`, `POST /api/carbon/tamper`, with tests
  - [x] 5.2 The *Carbon copy* tab: the receipt list in plain words, *Check the book*, *Try to change one*, *Download the carbon copies*
  - [x] 5.3 Receipt number and fingerprint columns in the accountant's download
  - _Requirements: 6_

- [x] 6. README and Kiro write-up sections for Carbon Copy, disclosing the Receipts base

- [x] 7. Polish round from a human click-through
  - [x] 7.1 Name: "Carbon Copy" everywhere a visitor reads it; wordmark in Special Elite, no drawn logo
  - [x] 7.2 `tamper_demo()` flips an owner "declined" to "approved" and says so in plain words, with a fallback for books with no owner action; tests for both paths
  - [x] 7.3 No sideways scroll from 375 to 1400 pixels on every tab
  - [x] 7.4 Hosted demo on the stand-in (`PAYPAL_MODE=standin` in `render.yaml`); badge and source line say so

- [x] 8. The Carbon copy tab shows the ON run's book by default (bug from the live demo: the OFF run finished last and was shown)
  - [x] 8.1 design.md and requirements.md (Requirement 6.6 to 6.8)
  - [x] 8.2 `GET /api/carbon` and `POST /api/carbon/tamper` take an optional `mode`; default is the latest enforce run, with no dependence on finishing order
  - [x] 8.3 The switch and the mode on every call in `static/app.js`
  - [x] 8.4 Tests in `tests/test_carbon_app.py`
  - _Requirements: 6_

- [x] 9. The check does not trust the server (two attack reviews, findings F1 to F9)
  - [x] 9.1 Spec first: Requirement 9, this design and these tasks
  - [x] 9.2 `safe_json()` and the new `canonical()` (F4, F8, F9); `append()` cleans before it stores; tests for surrogates, NaN, huge ints, 2**60, 298.5, key order for astral characters, Decimal/datetime/set/bytes
  - [x] 9.3 `Signer.from_env()` takes any key text; one signer per app; `GET /api/carbon/key`; footer (F1)
  - [x] 9.4 `verify(book, stamps, expected_key)`: key pinning, every stamp's signature, malformed stamps, the two stamp reasons (F1, F2, F5, F6); `stamp()` with the public key
  - [x] 9.5 Command line: exit 0, 1, 2 and `--key` (F7)
  - [x] 9.6 `static/carbon_verify.js` and the browser check; the device pins the key and keeps the stamps from approve, decline and every event; fall back to the server with a label (F2, F3)
  - [x] 9.7 `forge_demo()`, `POST /api/carbon/forge` and the *Try to forge a new book* button (D7)
  - [x] 9.8 `tests/test_carbon_parity.py` under node (D5)
  - [x] 9.9 README "Limits we know about" (D8)
  - [x] 9.10 Full test run, then start the app on the stand-in and call `/` and `/api/carbon/key`
  - _Requirements: 9_

- [x] 10. What a judge trips on (a judge-style review against the Kiroween rules)
  - [x] 10.1 Spec first: Requirement 10, design section "What a judge trips on", these tasks
  - [x] 10.2 One name, one meaning: banner, "Nothing checking" / "Carbon Copy on", the check versus the carbon copy
  - [x] 10.3 Honest labels: the Results tab is "What Receipts measured", with its one line on top
  - [x] 10.4 "Start here" strip: three buttons that do the step and move on
  - [x] 10.5 Live counter "Carbon copies sealed: N" on the Watch tab
  - [x] 10.6 False alarms: find the cause of each (written in design.md), fix the wrong labels, explain the right one
  - [x] 10.7 Plain words on the Carbon copy tab; "vendor master" gone from the screen
  - [x] 10.8 Tab bar: six tabs reachable at 375, 768 and 1280 pixels with the active tab in view
  - [x] 10.9 `.kiro/settings/mcp.json`, `.kiro/agents/carbon-attacker.json`, stdio start for `receipts/mcp_server.py`
  - [x] 10.10 README brought in line
  - [x] 10.11 Tests for what changed; full run; start the app on the stand-in and load `/`
  - _Requirements: 10_


- [x] 11. What our own attacker found (findings A1 to A8 from the `carbon-attacker` agent)
  - [x] 11.1 Spec first: Requirement 11, design section "What our own attacker found", these tasks
  - [x] 11.2 A1: `at_ms` (whole milliseconds, cleaned), sealed in place of `at`; the screen formats it; old books are not readable
  - [x] 11.3 A2: a book whose shape is wrong is *changed* in both checks
  - [x] 11.4 A3: a receipt carries exactly its seven keys; the checks read only `public_key`, `head`, `receipts`; the screen and exports show only those
  - [x] 11.5 A4: canonical base64 for every signature, in Python and in `static/carbon_verify.js`
  - [x] 11.6 A5: a key is exactly 64 lowercase hex characters in both checks
  - [x] 11.7 A6: one line in the README's Limits
  - [x] 11.8 A7: find why Kiro did not load the MCP server, fix it, run `kiro-cli mcp list`, add a test that starts the server the way Kiro does, and write the truth in "How Kiro built it"
  - [x] 11.9 A8: the attacker's prompt names A1 to A6 as fixed
  - [x] 11.10 Tests in `tests/` for every fix; the full run; every file in `scratch_attacks/` run and reported
  - _Requirements: 11_

- [x] 12. What our own attacker found, second round (findings C1 to C8)
  - [x] 12.1 Spec first: Requirement 12, design section "Task 12", these tasks
  - [x] 12.2 C1: the command line reads the download's shape (flags win)
  - [x] 12.3 C2: any failure to read or parse a file is exit 2 with one plain line
  - [x] 12.4 C3: the screen says when PayPal refused, with its reason in plain words
  - [x] 12.5 C4: B1 key case, B2 integer count, B3 kind and exact keys, the same in Python and in the browser
  - [x] 12.6 C5: a sealed `run` receipt first in every book; the header, switch and ledger read from it
  - [x] 12.7 C6: the device keeps 100 runs; the "no stamp" line beside the verdict; README Limits
  - [x] 12.8 C7: the four buttons fetch the current book first
  - [x] 12.9 C8: the attacker's prompt (stand-in only; C1 to C7 fixed)
  - [x] 12.10 Tests in `tests/` for every fix; the full run; every `scratch_attacks/attack2_*.py` run and reported
  - _Requirements: 12_

- [x] 13. An honest book after a local restart
  - [x] 13.1 Spec first: Requirement 13, design section "Task 13", these tasks
  - [x] 13.2 `restart_note` in Python and in the page, the note under the verdict, nothing for a fixed key
  - [x] 13.3 README "Try it": set a fixed key
  - [x] 13.4 Tests for a temporary and a fixed key; the full run
  - _Requirements: 13_

- [x] 14. "Try to change one" is checked in the browser too
  - [x] 14.1 Spec first: Requirement 14, design section "Task 14", these tasks
  - [x] 14.2 `tamper_demo` and `/api/carbon/tamper` return the changed copy as `book`
  - [x] 14.3 The page checks it with `checkOnDevice()` and shows "Checked in your browser"
  - [x] 14.4 Tests: endpoint, exact change, same reason, real book intact, node parity; the full run
  - [x] 14.5 README: which buttons are checked where
  - _Requirements: 14_


- [x] 15. Every money move gets its receipt, on every path (findings F1, F2, F3, F5, F6, F13, F14)
  - [x] 15.1 Spec first: Requirement 15, design section "Task 15", these tasks
  - [x] 15.2 F1: the MCP workspace's own book, signed by the app's signer, the `carbon_book` tool, the same on stdio
  - [x] 15.3 F2: MCP holds on the phone default to off; a tap seals into the MCP book
  - [x] 15.4 F3: `book()` takes receipts and head under one lock
  - [x] 15.5 F5: the tap is always sealed; a failed forward is shown truthfully; one lock for taps
  - [x] 15.6 F6: a bad amount is BLOCKED; proof that no recorded verdict changes
  - [x] 15.7 F13: one event never ends the stream
  - [x] 15.8 F14: the cheap head on a tap
  - [x] 15.9 README; tests in `tests/` for every fix; the full run; every `scratch_attacks/attack3_*.py` run and reported
  - _Requirements: 15_


- [x] 16. A check that does not need to trust us, and honest limits (findings F4, F7, F8, F9, F10, F11, F12, and the book on every recorded run)
  - [x] 16.1 Spec first: Requirement 16, design section "Task 16", these tasks
  - [x] 16.2 F8: the page captures and freezes the check; AG Grid is pinned with an integrity hash; `verify.html` built by `tools/build_verify.py`; README hash and Limits
  - [x] 16.3 F9: `HOSTED_KEY.txt`, `--key-file`, `verify.html` shows the published key beside the trusted one
  - [x] 16.4 F7: the command line prints the same caveats as the page
  - [x] 16.5 F10: the one-hour notices on the phone and the Carbon copy tab, the lapsed card, README Limits
  - [x] 16.6 F4: no visitor without a cookie unless a run starts; eviction spares waiting holds and young runs; 30 new visitors per address per 10 minutes
  - [x] 16.7 F11: the MCP workspace keeps 200 holds and 500 verdicts, cuts an argument over 64 KB, `receipts_holds` takes a limit
  - [x] 16.8 F12: policy text size limits with 413
  - [x] 16.9 The recorded-runs test (`recorded` marker, its own CI step) and the README section "What we measured on the book"
  - [x] 16.10 Tests in `tests/` for every fix; both runs; every `scratch_attacks/attack3_*.py` run and reported
  - _Requirements: 16_

- [x] 17. The two findings task 16 left open (F10, F11)
  - [x] 17.1 Spec first: Requirement 17, design section "Task 17", this task
  - [x] 17.2 F11: 256 KB body limit (413), 60 requests a minute per address (429), 20 MB MCP book cap that refuses money tools and phone approvals, fails closed
  - [x] 17.3 F10: 24 hours for a run with a waiting hold, one hour otherwise; the sentence on the phone and the Carbon copy tab; README Limits
  - [x] 17.4 Tests in `tests/test_carbon_round5.py`; both runs; `attack3_size.py` and `attack3_expiry.py` run and reported
  - _Requirements: 17_

- [x] 18. Keep a run for an hour after the owner's last tap
  - [x] 18.1 Spec first: Requirement 18, design section "Task 18", this task
  - [x] 18.2 A tap that returns a stamp sets the run's last-activity time; the sentence on the phone, the Carbon copy tab and README Limits
  - [x] 18.3 Tests in `tests/test_carbon_round5.py` with the clock moved; both runs; `attack3_expiry.py` re-run and reported
  - _Requirements: 18_

- [x] 19. The README's "How Kiro built it" in line with tasks 14 to 18 (documentation only)
  - [x] 19.1 Every count in the section read from the spec and the session records: requirements, tasks, runs of the attacker, session records, spec changes
  - [x] 19.2 The task list extended to 19 and the spec changes since the eighth written up
  - [x] 19.3 The attacker's three runs described with the numbers in its own reports
  - [x] 19.4 The README tests that pin the counts updated; the full run
  - _Requirements: none (documentation, kept true as task 6 did)_
