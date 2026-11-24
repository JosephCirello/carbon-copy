# Requirements: the carbon-copy receipt book

## Introduction

An AI agent pays a small business's bills through PayPal. Receipts (the base) already checks each money move before it reaches PayPal. This feature adds the carbon copy: a record of everything that happened that nobody, including the AI and including us, can quietly change afterwards, and a check anyone can run.

## Requirements

### Requirement 1: a copy of every event

**User story:** As the owner, I want a carbon copy of every money move the AI tried and every decision made about it, so that I can see later exactly what happened.

1. WHEN Receipts records a verdict (ALLOW, HOLD or BLOCK) THE SYSTEM SHALL append one carbon-copy receipt holding that verdict.
2. WHEN a call reaches PayPal or the business's own desk tools THE SYSTEM SHALL append one receipt holding the tool, its arguments and the result shown.
3. WHEN the owner approves or declines a held payment THE SYSTEM SHALL append one receipt holding the action and the hold it answers.
4. WHEN the agent files its end-of-day report THE SYSTEM SHALL append one receipt holding the report and the check of that report against PayPal.
5. WHEN the agent says something Receipts flags THE SYSTEM SHALL append one receipt holding the words and the flag.

### Requirement 2: what a receipt holds

1. EACH receipt SHALL hold: its number in the book (starting at 1), the time, the kind of event, the event itself, the fingerprint of the receipt before it (64 zeros for the first), its own fingerprint, and a signature over its own fingerprint.
2. A receipt's fingerprint SHALL be the SHA-256 of the canonical JSON of its number, time, kind, event and previous fingerprint.
3. THE SYSTEM SHALL produce the same fingerprint for the same receipt on any machine.
4. THE fingerprint SHALL be the same after the book passes through any standard JSON reader and writer, including a web browser's, which writes a whole-number float such as 1836.0 as 1836.

### Requirement 3: append only

1. THE SYSTEM SHALL offer no way to change or delete a receipt once written.
2. IF code asks the book for its receipts THEN THE SYSTEM SHALL hand back copies, so changing what was handed back cannot change the book.

### Requirement 4: the check

1. WHEN anyone runs the check on a book THE SYSTEM SHALL answer either *intact* with the number of receipts, or *changed* with the number of the first receipt that fails and the reason in plain words (its content was changed, its link to the receipt before was broken, its signature does not match, or a receipt is missing).
2. THE check SHALL need only the receipts and the public key; no secret.
3. IF any single byte of any receipt's event, number, time, kind or links is changed THEN the check SHALL answer *changed*.
4. IF a receipt is removed, or two are swapped THEN the check SHALL answer *changed*.
5. THE book SHALL carry a signed count of its receipts and the fingerprint of its last receipt, so that removing receipts from the END of the book — which the chain of links alone cannot show — is caught. IF the signed count is missing, or its signature does not match, or its count or last fingerprint does not match the receipts, THEN the check SHALL answer *changed* with the reason in plain words.
6. IF every receipt of an untouched book is checked THEN the check SHALL answer *intact*.

### Requirement 5: keys

1. IF `CARBON_COPY_KEY` is set THEN THE SYSTEM SHALL sign with the key it holds (a 32-byte Ed25519 seed in hex).
2. IF it is not set THEN THE SYSTEM SHALL generate a key in memory at start-up and SHALL NOT write it anywhere.
3. THE SYSTEM SHALL publish the public key with every book it hands out.

### Requirement 6: the owner can see it

1. THE web app SHALL have a *Carbon copy* screen listing the receipts in plain words, newest last, with each one's number and a short fingerprint.
2. THE screen SHALL have a *Check the book* button that runs the check in the browser's own request and shows *intact* or the first changed receipt.
3. THE screen SHALL have a *Try to change one* demo that alters a copy of one receipt (never the real book) and shows the check catching it, naming the receipt.
4. THE owner's book download (the accountant's spreadsheet) SHALL carry each row's receipt number and fingerprint.
5. A *Download the carbon copies* button SHALL hand over the whole book as a file with the public key, so the check can be run elsewhere.
6. THE screen SHALL show, by default, the book of the visitor's most recent run with Carbon Copy ON (mode "enforce"), whichever of the side-by-side runs finished last. Only when the visitor has no such run SHALL it show the most recent run of any mode.
7. WHEN the shown run has a twin with Carbon Copy OFF (mode "observe") for the same day, THE screen SHALL show a small switch above the receipts reading "Showing: Carbon Copy on (the run Maya saw)", with a second choice "Carbon Copy off (nothing checked it)". The source line SHALL name which run is shown.
8. *Check the book*, *Try to change one* and *Download the carbon copies* SHALL act on the book that is shown, so that after Maya declines a held payment the demo's change reads that she approved it.

### Requirement 7: the check runs anywhere

1. THE repository SHALL carry a command-line checker, `python -m receipts.carbon verify <book.json>`, that prints *intact* or the first changed receipt and exits 0 or 1.
2. THE command-line checker SHALL accept an optional list of the owner's phone stamps, `python -m receipts.carbon verify <book.json> --stamps <stamps.json>`, and apply the check in Requirement 8.

### Requirement 8: the owner's phone keeps the book's stamp

The signed count (the head) stops anyone quietly removing receipts from the end of the book, because the head still names a count the receipts no longer reach. But someone holding an *older* signed count can cut the book back to that older length and put the older count back, and the book still checks out: the receipts left still link up, and the older count matches them. The fix is a copy of the count kept outside the book, on the owner's phone.

1. WHEN the owner approves or declines a held payment THE SYSTEM SHALL hand the phone the book's signed head as it stands right after that tap is recorded.
2. THE check SHALL accept a list of such stamps and answer *changed*, with the reason "the book is shorter than a stamp the owner's phone already holds", if any stamp's count is greater than the book's receipts, or its last fingerprint is not the fingerprint of the receipt at that position.
3. THE check SHALL need only the receipts, the public key and the stamps; no secret.

### Requirement 9: the check does not trust the server

Two attack reviews showed the headline claim ("a changed copy is caught") could be broken by whoever runs the server, because the check trusted the book's own key, the server's stamps and the server's answer. Requirement 9 closes that. The owner's own device keeps the key it first saw and the stamps it received, and the check runs on the device.

1. THE book SHALL be written in ONE canonical form that any JSON tool reproduces: before a receipt is stored, its event is cleaned (lone surrogates in keys and text become U+FFFD; integers beyond 2^53 - 1 become their decimal text; whole floats within that range become integers; every other float, including NaN and Infinity, becomes the text Python's `repr` gives; tuples become lists; any other type becomes `str(value)`), and the cleaned form is what is stored, fingerprinted and handed out. Writing a receipt SHALL never raise because of what the agent wrote, and an action SHALL never happen without its receipt for that reason.
2. THE book SHALL read as intact after a trip through a browser's `JSON.parse` and `JSON.stringify`, whatever the agent wrote (emoji, astral-plane keys, 298.5, 2^60, 9007199254740993, NaN, a lone surrogate, nested lists), and `GET /api/carbon` SHALL answer for every such book.
3. WHEN `CARBON_COPY_KEY` is set to any text THE SYSTEM SHALL sign with a key derived from it: the text itself when it is 64 hex characters, otherwise the SHA-256 of the text. THE app SHALL publish the public key at `GET /api/carbon/key` and print a short form in the page footer; with no key set the footer SHALL say the key is temporary.
4. THE owner's device SHALL pin the public key of the first stamp it receives (trust on first use) and keep every stamp it receives whole (count, last fingerprint, signature, public key), per run, in the browser's own storage, in memory with a notice on screen when storage is unavailable. A stamp arrives with every approve and decline and with every event of a run.
5. THE check SHALL take the key the device trusts. A book signed with a different key SHALL be *changed*, with the reason "it was signed with a different key than the one your device trusts".
6. THE check SHALL verify every stamp's signature against the key the device trusts (the book's own key when none is given). A stamp that is malformed (a count that is not a whole number, a text that is not text, not an object) or whose signature fails SHALL make the result *changed*, with the reason "a stamp on your device is damaged or forged".
7. A stamp whose position exists in the book but whose fingerprint does not match SHALL give "receipt #N no longer matches the stamp your device kept". Only a stamp whose count is beyond the end of the book SHALL give "the book is shorter than a stamp your device already holds".
8. THE *Check the book* button SHALL run the check in the browser, with the browser's own SHA-256 and Ed25519, against the book, the device's stamps and the device's pinned key, and say "Checked in your browser". IF the browser has no Ed25519 THEN the screen SHALL say so and ask the server, with the device's stamps and key, and say "Checked by the server".
9. THE command-line checker SHALL exit 0 when the book is intact, 1 when it is changed and 2 when the file could not be read (a plain message, never a traceback), and SHALL accept `--key <hex>` for the key to trust.
10. THE demo SHALL show the real attack: *Try to forge a new book* gives the browser a copy of the book with Maya's decline flipped to approved and every receipt re-signed with a brand-new key, and the browser's own check SHALL reject it, naming the different key.
11. THE README SHALL say plainly what the check cannot do: the device must have seen the key first, anything after the last stamp the device saw can still be rewritten by whoever holds the key, and the check proves the book was not changed, not that what was written was true.

### Requirement 10: what a judge trips on

A judge-style review of the live demo, the README and the repository against the Kiroween rules found nine things a visitor trips on. None of them changes what Receipts decides or what the book records; they are about what the screen says and what the repository shows.

1. ONE NAME, ONE MEANING. THE screen SHALL use "Carbon Copy" for the whole product only. Inside it, "the check" SHALL mean the part that stops a bad payment before PayPal (built on Receipts) and "the carbon copy" SHALL mean the sealed book. THE side-by-side labels SHALL read "Nothing checking" and "Carbon Copy on". THE first banner SHALL read: "Maya's AI agent pays her bills through PayPal. Carbon Copy checks each payment before it leaves (using Receipts, our earlier checker) and seals every move into a carbon-copy book nobody can quietly rewrite."
2. HONEST LABELS ON OLD MEASUREMENTS. THE Results tab SHALL be named "What Receipts measured" and SHALL open with the line: "Measured by Receipts, the project Carbon Copy is built on (19 AI models, 19 business days, November 2026). The carbon copy itself is new and is not part of these numbers."
3. A 30-SECOND PATH. THE Watch tab SHALL open with a "Start here" strip of three numbered buttons, each doing its step and moving the visitor on: (1) "Run Maya's day" starts the replay; (2) "Decline the double payment on her phone" opens the phone tab when the hold arrives; (3) "Try to forge the record" opens the Carbon copy tab and presses *Try to forge a new book*. THE existing controls SHALL stay below the strip.
4. THE CARBON COPY VISIBLE DURING THE RUN. THE Watch tab SHALL show, beside the "Carbon Copy on" side, a live counter "Carbon copies sealed: N" that rises as receipts are written and links to the Carbon copy tab.
5. FALSE ALARMS ON SCREEN. THE display SHALL not say more than the data means. (a) The AI's words are tagged by a pattern reader that cannot tell a refusal from a suspicion, so the tag SHALL read "SAID: NO" (not "SUSPICIOUS") and carry one plain line saying it is a pattern match on the AI's words and not a verdict. (b) A receipt for the AI's words SHALL say what the pattern found ("it said no", "it said it would hold or verify") and not a bare "(held)", which reads as if the AI's words were held. (c) THE end-of-day line "Honest work done: N of M" SHALL carry one plain line saying it counts only the bills and refunds that were right to do, so a payment the AI should not have made is counted apart, under risky money moves. Scoring in `core.py` and `measure.py` SHALL NOT change.
6. PLAIN WORDS. THE Carbon copy tab SHALL explain, once, near where each first appears: *fingerprint* ("a short code computed from the receipt; change one letter and it changes"), *stamp* ("a sealed note your device keeps of how long the book was at that moment"), *signing key* ("the seal's owner; your device remembers the first one it sees and refuses any other"). "Vendor master" SHALL NOT appear on any screen; it reads "Maya's list of suppliers".
7. THE TAB BAR. WHEN the phone's count badge shows, all six tabs SHALL stay reachable at 375, 768 and 1280 pixels: they fit, or scroll inside the bar with the active tab kept in view.
8. KIRO, SHOWN PROPERLY. THE repository SHALL carry `.kiro/settings/mcp.json` registering Carbon Copy's own MCP server, started with the project's virtual-environment Python, and `.kiro/agents/carbon-attacker.json`, a custom Kiro agent that attacks the book (forge, rewrite, hide, cause false alarms) using the repository's own command line and tests and reports only findings it proved. THE MCP server SHALL be startable over stdio by `python -m receipts.mcp_server`.
9. README. THE README SHALL list tasks 1 to 10, say the demo runs on an always-on plan, say the no-keys hook runs after each save, carry a "How Kiro built it" section that answers each question the Kiroween rules ask (the Kiro surface and why, spec-driven versus vibe coding, steering, each hook and what it did, property-based tests, MCP, the custom agent, powers), a "Category: (to be confirmed)" line and a "Session records: docs/kiro-sessions/" line.
*Amended by task 26 (a last walk before submission: the live demo at phone, tablet and desktop width in light and dark, and a reader given only the public pages).*

10. THE ANSWER LANDS IN VIEW. WHEN *Check the book*, *Try to change one* or *Try to forge a new book* has written its answer into `#ccResult`, THE page SHALL scroll it into view, smoothly (at once when the visitor asked for reduced motion), with the stamp near the top of the window and below the sticky bar, at every width. At 375 x 812 the CHANGED stamp SHALL be on screen after "Next: try to forge the record".
11. WHAT THE DEMO IS ENTERED IN. THE page footer SHALL carry one more line in its existing style: "Built with Kiro for Kiroween 2026 · Code and the Kiro sessions: github.com/JosephCirello/carbon-copy", the repository name being a link.
12. WHICH PAYPAL. EVERY line on screen that says where the demo sends money or reads records SHALL name the PayPal the server reports: "the PayPal stand-in" or "the PayPal sandbox". The run-source option reads "Recorded real run (replayed through the PayPal stand-in now)" on the stand-in and "(replayed through the PayPal sandbox now)" on the sandbox. Lines on a screen that already names which one (the environment label, the Carbon copy tab's "PayPal here", each receipt's tech line) are left as they are.
13. THE SESSION RECORDS ARE TRUE. `docs/kiro-sessions/README.md` SHALL say the `carbon-attacker` agent ran four times (records 10, 12, 16 and 17, and 23) and what each run found.
14. A HOOK SAYS WHAT IT DOES. A hook's description SHALL match its trigger: the "No keys in the repo" hook runs on PostFileSave, so it says "After each save".
15. THE README SAYS WHO DID WHAT, ONCE. THE README SHALL say: we wrote the first spec, the steering files and the hooks; Kiro wrote the code and the tests, task by task, from the spec; and name the few changes made by hand. THE fingerprint recipe's section SHALL hold only the recipe. THE caption of the picture `04_change_one_caught.jpg` SHALL say it was recorded on a local copy of the demo (its device key is not the hosted key). THE README SHALL say each fact once (the three demo clicks, the spec-first reason) and keep every number, limit and link; no count test SHALL need to change.


### Requirement 11: what our own attacker found

The custom Kiro agent `carbon-attacker` attacked the book and proved five ways to hide a change or raise a false alarm, one documented limit of the cleaning, and one failure to load its tools. Requirement 11 closes them. Each has a test in `tests/`; the attacker's own reproductions live in `scratch_attacks/` (git ignores it).

1. A RECEIPT'S TIME IS CLEANED LIKE THE EVENT (A1). A receipt SHALL carry its time as `at_ms`, a whole number of milliseconds since the epoch, between 0 and 2^53 - 1. WHEN the event's own time is missing, not a finite number or outside that range THEN THE SYSTEM SHALL use the current time. `at_ms` is sealed in place of `at`. THE screen formats it. Books written before task 11 carry `at` in seconds and are NOT readable (the design says why).
2. A BOOK OF THE WRONG SHAPE IS CHANGED (A2). WHEN the book is not an object, or its `receipts` is not a list (an object, a number, text, false, null or missing), THEN BOTH checks (Python and `static/carbon_verify.js`) SHALL answer *changed* with the reason "this is not a carbon-copy book we can read".
3. A RECEIPT CARRIES EXACTLY ITS SEAL (A3). A receipt SHALL carry exactly the keys `n`, `at_ms`, `kind`, `event`, `prev`, `fp`, `sig`. WHEN it carries any other key THEN BOTH checks SHALL answer *changed*, at that receipt, with the reason "receipt #N carries something outside its seal". At the top level the checks SHALL read only `public_key`, `head` and `receipts`; the screen and every export of the book SHALL show only those three.
4. A SIGNATURE HAS ONE WRITTEN FORM (A4). A signature (a receipt's, the head's, a stamp's) SHALL be canonical base64: standard alphabet, padded, and the text SHALL equal the re-encoding of what it decodes to. Otherwise BOTH checks SHALL answer *changed* with the reason "its signature does not match" (the head's and a stamp's keep their own reasons).
5. A KEY HAS ONE WRITTEN FORM (A5). A public key SHALL be exactly 64 lowercase hex characters. WHEN the book's key is anything else THEN BOTH checks SHALL answer *changed* with the reason "its public key is not written the way a key must be".
6. THE README SAYS WHAT THE CLEANING DOES (A6). Different values that clean to the same text (298.5 and "298.5", 2^60 and its digits, Decimal("5.10") and "5.10", NaN and "nan") stay as they are, and the README's Limits SHALL say: "Amounts that are not whole numbers are sealed as text, so the book shows the value, not whether the AI wrote it as a number or as text."
7. KIRO LOADS THE MCP SERVER (A7). THE repository SHALL show, with `kiro-cli mcp list` output in the report, that the workspace `.kiro/settings/mcp.json` is read, and a test SHALL start the server the way Kiro does (the command and arguments from `mcp.json`, started in the workspace folder, speaking MCP over stdio). THE agent file SHALL load in Kiro CLI's default headless engine as well as the newer one. IF Kiro cannot be made to load it THEN the README's "How Kiro built it" SHALL say so plainly.
8. THE ATTACKER KNOWS WHAT IS FIXED (A8). THE `carbon-attacker` prompt SHALL name findings A1 to A6 as already fixed so its next run looks for new shapes.


### Requirement 12: what our own attacker found, second round

The custom Kiro agent `carbon-attacker` ran again and proved seven more things, plus one problem with its own prompt. Requirement 12 closes them. Each has a test in `tests/`; the attacker's reproductions live in `scratch_attacks/attack2_*.py` (git ignores it).

1. THE DOWNLOAD READS ON THE COMMAND LINE (C1). `python -m receipts.carbon verify <file>` SHALL accept a bare book and the file "Download the carbon copies" writes (`{book, stamps, trusted_key}`). WITH the download shape it SHALL use the file's `stamps` and `trusted_key`, unless `--stamps` or `--key` is given: the flags win.
2. NO TRACEBACK, EVER (C2). Any failure to read or parse either file (missing, not UTF-8, not JSON, nested too deeply) SHALL give exit 2 and one plain line on standard error.
3. THE SCREEN SAYS WHEN PAYPAL SAID NO (C3). WHEN a sealed result carries an error THEN the sentence for that receipt SHALL say PayPal refused it, with PayPal's reason in plain words ("PayPal refused it: the refund is more than what is left on that payment"), and SHALL NOT say "It went to PayPal".
4. BOTH CHECKS GIVE ONE ANSWER (C4). (B1) Keys SHALL be compared lower-cased in both, stamps included. (B2) A stamp's `count` SHALL be a JSON integer in both: `6.0` is damaged. (B3) A receipt's `kind` SHALL be a non-empty text, `append()` SHALL refuse anything else, and a receipt SHALL carry all seven sealed keys (exactly those): a missing key is *changed* in both.
5. THE RUN IS SEALED (C5). Every run's book SHALL start with a receipt of kind `run` holding `mode`, `source` (`live` or `recorded`), `scenario` and `model`. THE Carbon copy header and every label about the run SHALL be built only from that receipt; THE ledger SHALL take model, scenario and time from it. The unsealed `mode` and `source` fields MAY stay in the API response for routing, and the screen SHALL NOT display them.
6. THE DEVICE REMEMBERS MORE RUNS (C6). THE device SHALL keep stamps for 100 runs. WHEN it kept none for the run on screen THEN the line "kept no stamp for this run" SHALL sit directly beside the verdict. THE README's Limits SHALL say, in plain words, that once a run's stamps are dropped to make room a rewrite of that run is no longer caught.
7. THE CHECK USES THE CURRENT BOOK (C7). "Check the book", "Try to change one", "Try to forge a new book" and "Download the carbon copies" SHALL fetch the current book first, so a copy held since the tab was opened never meets a later honest stamp.
8. THE ATTACKER STAYS ON THE STAND-IN (C8). THE `carbon-attacker` prompt SHALL require every command it runs to set `PAYPAL_MODE=standin`, forbid it ever to start the PayPal sandbox, and name findings C1 to C7 as fixed so a third run looks elsewhere.


### Requirement 13: an honest book after a local restart

A human click-through found that on a machine with no `CARBON_COPY_KEY`, running the day, restarting the server and running the day again makes "Check the book" say CHANGED ("it was signed with a different key than the one your device trusts") on an honest book, with no explanation. The hosted demo has a fixed key and never does this.

1. THE VERDICT STAYS (D1). A key that differs from the one the device trusts SHALL still be *changed*, with the same reason, in both checks. A key change SHALL NOT be excused automatically, because an attacker could claim a restart.
2. THE SCREEN EXPLAINS A TEMPORARY KEY (D2). WHEN the book's key differs from the device's trusted key AND `/api/carbon/key` says `temporary` is true, THEN the screen SHALL show under the verdict: "This server makes a new temporary signing key every time it starts. If you restarted it yourself, that is why the key changed: press 'Forget what this device trusts' and run the day again. The hosted demo uses a fixed key, so this never happens there."
3. A FIXED KEY SAYS NOTHING EXTRA (D3). WHEN the server's key is not temporary, or the keys match, or the device trusts no key yet, the screen SHALL show nothing extra.
4. THE FOOTER STAYS (D4). The footer keeps "Signing key: temporary (changes on restart)".
5. THE README SAYS HOW TO AVOID IT (D5). "Try it" SHALL show, before the run commands, how to set a fixed `CARBON_COPY_KEY` (PowerShell and macOS/Linux) and one sentence on why.
6. TESTS (D6). A test SHALL cover the function that decides (`restart_note` in `receipts/carbon.py` and its twin in `static/carbon_verify.js`) and the `/api/carbon/key` values it reads, for a temporary and a fixed key.


### Requirement 14: "Try to change one" is checked in the browser too

On the Carbon copy tab, "Check the book" and "Try to forge a new book" were checked in the browser and said "Checked in your browser". "Try to change one" printed the server's answer under "Checked by the server", which contradicts the claim that the check runs on the owner's side.

1. THE ENDPOINT RETURNS THE COPY (E1). `POST /api/carbon/tamper` SHALL return, besides `n`, `field`, `before`, `after`, `say` and `result`, the changed copy as `book` (`public_key`, `head`, `receipts`, the shape `/api/carbon/forge` returns). The real book SHALL never be touched.
2. THE BROWSER CHECKS IT (E2). THE page SHALL run the changed copy through `checkOnDevice()` and show that result and `ccWhere(...)`, so it says "Checked in your browser". Only a browser with no Ed25519 SHALL fall back to the server (Requirement 9.8). The server's `result` SHALL stay in the response for the command line and tests, and the screen SHALL NOT show it.
3. THE VERDICT STAYS (E3). For Maya's book the verdict SHALL stay CHANGED AT #N, N being the receipt holding her decline. The browser and Python SHALL give the same `intact`, `first_bad` and `why` for the changed copy.
4. TESTS (E4). A test SHALL cover the endpoint returning the book, the book being changed exactly at `n` and failing `verify()` with the response's own reason, the real book still intact afterwards, and the node parity test over the changed copy.
5. README (E5). THE README SHALL say which buttons are checked where.


### Requirement 15: every money move gets its receipt, on every path

The third attacker round (findings F1, F2, F3, F5, F6, F13, F14) found money moves with no receipt, taps nobody sealed, and an honest book read as changed.

1. THE MCP WORKSPACE HAS ITS BOOK (F1). THE object behind every MCP tool SHALL write its own book, signed by the app's one signer (the stdio server: its own signer from `CARBON_COPY_KEY` or made in memory), opened by a sealed `run` receipt (mode enforce, source live, the MCP workspace's scenario, model "mcp client"). Every verdict, PayPal or desk call and owner tap on an MCP hold SHALL be sealed as on the web path. An MCP tool `carbon_book` SHALL return that book (`public_key`, `head`, `receipts`), and the README SHALL say how to check it with the command line.
2. THE MCP HOLDS ARE NOT OPEN TO EVERY VISITOR (F2). `RECEIPTS_MCP_ON_PHONE` SHALL default to off in `app.py`, as in the Dockerfile and `render.yaml`. WHEN it is on, a tap on an MCP hold SHALL write the owner receipt into the MCP book and return its stamp, and the README SHALL say in one line that with it on anyone who can open the page can decide the MCP holds, so it is for your own machine only.
3. AN HONEST BOOK IS NEVER READ AS CHANGED (F3). `CarbonCopy.book()` SHALL take the receipts and the signed head under one hold of the lock, so `head.count` always equals the number of receipts handed out, whatever is being written.
4. THE OWNER'S TAP IS ALWAYS SEALED (F5). `approve` SHALL write the owner receipt "approved" BEFORE it forwards, then a receipt with PayPal's answer or the error in plain words. A forward that fails SHALL leave the hold approved with the reason, the phone SHALL say "Approved, but PayPal did not take it: <reason>", and the API SHALL answer 200 with the error and the stamp, never a 500. `approve` and `decline` SHALL share one lock per `Receipts` object, so two taps at once on one hold cannot both act.
5. A BAD AMOUNT IS BLOCKED (F6). A payout or refund whose amount is not a finite, non-negative number of dollars (NaN, infinity, a negative, or text the rule book cannot read as money) SHALL be BLOCKED, with the reason "the amount is not a number of dollars". This is the one change allowed in `receipts/rules.py`. A test SHALL re-score every recorded run in `results/episodes.jsonl` and `results/frontier` with the rules before and after the change, in memory, and assert every verdict is identical. `results/` is not touched.
6. ONE EVENT NEVER ENDS THE STREAM (F13). WHEN an event cannot be written as JSON as it is (a very deep tool argument, NaN), `_data` SHALL send it in its cleaned form (`safe_json`); WHEN even that fails it SHALL send a short placeholder event. No event SHALL end the stream to the page.
7. A TAP DOES NOT COPY THE BOOK (F14). `approve` and `decline` SHALL take the book's head with the cheap `head()`, not by copying the book.
8. TESTS. Each fix SHALL have its own test in `tests/`.


### Requirement 16: a check that does not need to trust us, and honest limits

The third attacker round also found that the in-page check is code the server sends (F8), that nothing outside the server says which key to trust (F9), that the command line says a bare "intact" when it had nothing to hold the book against (F7), that a run and its held payment vanish after an hour with no word (F10), that one client can push every other visitor out (F4), and that /mcp (F11) and the rules (F12) keep text of any size. A measurement outside the repository also replayed every recorded run through the book.

1. THE PAGE'S CHECK CANNOT BE SWAPPED AT CLICK TIME (F8a). `static/carbon_verify.js` SHALL freeze `window.CarbonVerify` (`Object.freeze`) and `static/app.js` SHALL capture the check once when the page loads, not look it up at click time. The AG Grid script SHALL carry `integrity` (SHA-384 of the file jsDelivr serves for the pinned version) and `crossorigin`.
2. A CHECK THAT DOES NOT COME FROM THE SERVER (F8b). `verify.html` at the repository root SHALL be one self-contained file (no network, nothing loaded from anywhere) with `static/carbon_verify.js` inlined byte for byte, built by `tools/build_verify.py`. The owner saves it from GitHub, opens it from disk and drops a downloaded book file on it. It SHALL read the download's book, stamps and trusted key and show INTACT or CHANGED with the reason, with the same notes the page prints when there is no key or no stamp. A test SHALL fail if the inlined code differs from `static/carbon_verify.js`. The README SHALL publish the SHA-256 of `verify.html`, and a test SHALL check it against the file.
3. THE LIMIT IS SAID (F8c). The README's "Limits we know about" SHALL say that the in-page check runs code the server sends, so a dishonest operator could send a check that lies, and that the two checks that do not depend on us are the command line from a fresh clone and `verify.html` saved from GitHub, each on a downloaded file.
4. THE KEY TO TRUST IS PUBLISHED OUTSIDE THE SERVER (F9). The hosted demo's public key SHALL be in the README and in `HOSTED_KEY.txt` at the repository root, read back from the hosted server before it was written. The command line SHALL take `--key-file <path>` (the first 64-hex word in the file; `--key` and `--key-file` together are an error, exit 2). `verify.html` SHALL show the key the download trusts beside the published one and say whether they match.
5. NO BARE "intact" (F7). WHEN the file carries no trusted key and none is given, or carries no stamps, the command line SHALL print the page's caveat on the line after the verdict: "This file has no key from your device, so the check can only compare the book with itself." or "This file has no stamp, so it cannot tell whether the end of the book was rewritten." Exit codes stay 0, 1 and 2.
6. THE HOUR IS SAID (F10). While a run is kept, the phone and the Carbon copy tab SHALL say "This server keeps a run for one hour. Download the carbon copies to keep them." WHEN a hold has lapsed its card SHALL say it lapsed and was never sent to PayPal. The README's Limits SHALL state the one hour, the 40 runs per visitor and the visitor limit.
7. ONE CLIENT CANNOT PUSH THE OTHERS OUT (F4). A request that carries no visitor cookie and does not start a run SHALL NOT create a visitor: `POST /api/policy` with no cookie answers 400 asking to load the page first. WHEN the table is full the server SHALL drop the least recently seen visitor that has no waiting hold and no run younger than an hour, and only then anyone. New visitors SHALL be capped at 30 per 10 minutes per client address (the first `X-Forwarded-For` address when `RECEIPTS_BEHIND_PROXY=1`, else the socket's), answering 429 in plain words past it.
8. /mcp DOES NOT KEEP EVERYTHING (F11). The MCP workspace SHALL keep at most the last 200 holds and 500 verdicts (its book keeps everything). An argument over 64 KB SHALL be kept in the history as its first 64 KB plus "(cut: N bytes)", and a hold with a cut argument cannot be approved. `receipts_holds` SHALL take `limit` (default 50), newest first.
9. POLICY TEXT HAS A SIZE (F12). `POST /api/policy` SHALL answer 413 with a plain message for `english` over 20,000 characters, for `sources` over 200 entries, or for a source over 2,000 characters.
10. THE BOOK ON EVERY RECORDED RUN. `tests/test_carbon_recorded_runs.py`, marked `recorded`, SHALL replay every recorded run in both arms as `/api/replay` does and assert: every honest book intact (Python, and after a JSON round trip); every one-receipt change caught at that receipt; every forgery, swap and cut-off ending caught with the device's stamp; the browser check (node, in batches) agreeing with Python on every case. The default run SHALL skip it; CI SHALL run it as its own step (`pytest -m recorded -q`). The README SHALL have a short section "What we measured on the book" with the numbers the test printed, and Limits SHALL give the time a large book takes to check.
11. TESTS. Each fix SHALL have its own test in `tests/`.

### Requirement 17: the two findings task 16 left open (F10, F11)

The third attacker round found that one anonymous client of /mcp, which has no login and one shared workspace whose book keeps every argument, could grow the server's memory without limit (F11), and that a held payment vanished after one hour (F10).

1. /mcp IS BOUNDED (F11). A request body over 256 KB SHALL get 413 with a plain message before any tool runs (a body with no declared length is held to the same limit). One client address (the rule of the visitor limit: first `X-Forwarded-For` when `RECEIPTS_BEHIND_PROXY=1`, else the socket's) SHALL be allowed 60 /mcp requests a minute, 429 past it.
2. THE MCP BOOK HAS A CAP, AND FAILS CLOSED (F11). The MCP workspace's book SHALL be measured as it grows (stored JSON, counted per receipt). At 20 MB (`RECEIPTS_MCP_BOOK_MB`) every MCP tool that would move money or change a payee SHALL refuse with "This demo's MCP book is full; restart the server to start a new one." and forward nothing; so SHALL the phone's approval of an MCP hold. Read-only tools and `carbon_book` SHALL still answer. A money move SHALL never happen without its receipt.
3. A WAITING HOLD KEEPS ITS RUN 24 HOURS (F10). A run with a WAITING hold SHALL be kept for 24 hours after its last activity; any other run for one hour after its last activity. Its last activity is the run starting or the owner's last approve or decline on it (amended by Requirement 18). Runs per visitor stay capped at 40.
4. THE TIMES ARE SAID. The phone and the Carbon copy tab SHALL say the sentence of Requirement 18.2 (amended by Requirement 18). The README's Limits SHALL give both numbers, say the hosted demo also loses everything on a restart, and state the /mcp limits.
5. TESTS. Each limit SHALL have its own test in `tests/test_carbon_round5.py`, with the clock moved for the two times.

### Requirement 18: a run is kept from its LAST activity (found in the task 17 report)

After a hold waited more than an hour, the owner's approve or decline left the run with nothing waiting and already older than an hour, so the next request dropped it and she could not download the book of her own decision.

1. THE HOUR COUNTS FROM THE LAST ACTIVITY. A run's last activity is the run starting or the owner's last approve or decline on it. A run SHALL be kept for one hour after its last activity, and for 24 hours after it when a hold in it is WAITING.
2. SAID THE SAME WAY EVERYWHERE. The phone, the Carbon copy tab and the README's Limits SHALL say: "This server keeps a run for one hour after its last activity (it starting, or your last approve or decline), and for 24 hours when a payment in it is waiting for you. Download the carbon copies to keep them."
3. TEST. With the clock moved: a hold waits 2 hours, is approved, and the run's book can be fetched 59 minutes later and is gone after 61. scratch_attacks/attack3_expiry.py is re-run and reported.

### Requirement 19: the fourth attacker round's twelve findings

The fourth run of the `carbon-attacker` agent found twelve things (proofs in `scratch_attacks/attack4_*.py`): the owner's tap could pay a bill twice and said "not sent" when PayPal had taken the money, two address limits and the visitor table could be defeated by a spoofed or made-up header or cookie, a read-only MCP tool kept the book growing past its cap, a waiting payment could be forgotten after three hours or pushed out by newcomers or by the run cap, a tap on nothing kept a run alive, `verify.html` called a forged book intact and disagreed with the command line, and a payout of 0 was allowed.

1. THE TAP LOOKS AGAIN (finding 1). `approve` SHALL, before anything is forwarded, run the rules that depend on what has been paid since the hold was made (the duplicate-invoice check, a payment on its way, a near-duplicate, a split, a dispute opened, and any rule that would now BLOCK it) against PayPal's records as they are now. WHEN the payment would no longer pass, nothing SHALL be forwarded: the owner receipt "approved" SHALL be sealed, then "refused_at_tap" with the reason in plain words ("INV-AT-9501 was paid while this was waiting"), and the phone SHALL show that reason. BEFORE the tap, the hold's card SHALL say when another hold for the same invoice is waiting, or when the payment would now be refused (for instance the invoice has been paid since).
2. "not_sent" IS ONLY FOR A SEND THAT NEVER LEFT (finding 2). An error raised because the client refused its own arguments (ValueError, TypeError) SHALL be sealed "not_sent". Any other exception while forwarding (a timeout, a dropped connection) SHALL be sealed "no_answer" ("PayPal did not answer; it may have been sent"); PayPal's records SHALL then be looked up (the lookup the duplicate check uses) and what they show SHALL be sealed: "sent" with PayPal's id, or "not_found". The phone SHALL say which.
3. THE ADDRESS IS THE ONE THE PROXY ADDED (finding 3). Behind the proxy (`RECEIPTS_BEHIND_PROXY=1`) the client address SHALL be the last entry of `X-Forwarded-For`, or with `RECEIPTS_PROXY_HOPS` (default 1) the n-th entry counting from the right, never the first entry, which the client writes. Both limits (60 /mcp requests a minute, 30 new visitors per 10 minutes) SHALL use it.
4. A READ-ONLY MCP TOOL IS NOT FREE (finding 4). Past the book's cap EVERY MCP tool SHALL refuse except `carbon_book`.
5. A WAITING PAYMENT IS NOT FORGOTTEN FOR IDLENESS (finding 5). The visitor idle drop SHALL NOT drop a visitor with a WAITING hold before that hold's 24 hours are up.
6. NEWCOMERS DO NOT PUSH OUT A WAITING PAYMENT (finding 6). WHEN the visitor table is full the server SHALL drop first a visitor with nothing kept at all, then a visitor with only runs (each time the least recently seen), and a visitor with a WAITING hold only when no one else is left.
7. A TAP ON NOTHING IS NOT ACTIVITY (finding 7). Only an approve or decline of a hold that exists and is WAITING SHALL restart a run's clock. The hold SHALL be checked first, then the clock restarted, then the tap decided (Requirement 18's order).
8. THE RUN CAP SPARES A WAITING PAYMENT (finding 8). WHEN a visitor has more than 40 runs the server SHALL drop the oldest run with nothing waiting, and a run with a waiting hold only when every other kept run has one.
9. verify.html CHECKS AGAINST THE PUBLISHED KEY (finding 9). By default `verify.html` SHALL trust the published key (`HOSTED_KEY.txt`, built in), as the command line does with `--key-file HOSTED_KEY.txt`, so a book signed with another key reads CHANGED ("it was signed with a different key than the published one"). A visible switch, "Use the key in this file instead (for a book from your own server)", SHALL check against the file's key and say plainly that this is only as good as where the file came from.
10. THE PAGE AND THE COMMAND LINE AGREE (finding 10). (a) `stamps` written as text, not a list, SHALL read CHANGED in both, with the same reason. (b) A whole number past plus or minus 2^53 - 1 anywhere in a book file SHALL read CHANGED in both, with the same reason, because the book never seals one (it writes them as text). The page SHALL read the number as written in the file, not as JavaScript rounds it.
11. A COOKIE THE SERVER NEVER ISSUED MAKES NO VISITOR (finding 11; amended by task 22). A request that does not start a run SHALL NOT create a visitor on the strength of an unsigned or made-up cookie. When the page is loaded the server SHALL set the visitor cookie to a random id plus an HMAC-SHA256 over it, and SHALL create NOTHING. The HMAC key is made in memory at start-up, or, when CARBON_COPY_KEY is set, derived from that text with a fixed label (so a restart of the hosted demo keeps accepting cookies it issued); it is never the signing key itself and is never written anywhere. A request that carries a VALID signed cookie MAY create its visitor on first use (a rules save, a run, a tap), and that creation SHALL count against the per-address limit on new visitors (30 in 10 minutes). A made-up, unsigned or wrongly signed cookie SHALL be treated as no cookie: POST /api/policy answers 400, asking to load the page first, and keeps nothing; the page SHALL NOT say the rules are in force when they were not kept. Saving rules right after loading the page, before any run, SHALL work.
12. A PAYOUT OF ZERO IS NOT A PAYMENT (finding 12). A payout or a refund whose amount is zero or below SHALL be BLOCKED ("the amount is not a positive number of dollars"); a refund with no amount (a full refund) stays allowed. This is the one change allowed in `receipts/rules.py` in this requirement, and every recorded verdict SHALL be shown to be identical under the old and the new rules.
13. THE INSTANT BETWEEN THE TAP'S LOOK AND ITS SEND IS CLOSED (task 22; closes the gap named in finding 1). The owner's approve (the second look and the forward) and the agent's own money moves (the check and the forward in Receipts.call) SHALL take the SAME per-run lock, so neither can happen in the other's gap: of an approve and an agent payout for the same invoice started together, exactly one SHALL pay. For the MCP workspace the same lock SHALL cover the MCP tool calls and the phone's taps on MCP holds. The README's Limits SHALL no longer name this gap.
14. TESTS. Each fix SHALL have its own test in `tests/test_carbon_round6.py` (findings 1 to 12) or `tests/test_carbon_round7.py` (task 22: items 11 and 13).


### Requirement 20: the hosted /mcp answers a client, and the README's first screen is for a judge

Measured 2026-11-24: `POST https://carbon-copy-ywv3.onrender.com/mcp/` with an MCP initialize request answered HTTP 421 "Invalid Host header", while the same request to a local server answered 200. The MCP library's DNS-rebinding protection accepts only localhost Host and Origin values unless it is told more. The hosted /mcp had never answered a client.

1. THE ALLOWED HOSTS ARE SET, THE PROTECTION STAYS ON. The app SHALL pass the MCP library's own `TransportSecuritySettings` to the /mcp app with `enable_dns_rebinding_protection=True`. Its allowed hosts SHALL be localhost (`127.0.0.1`, `localhost`, `[::1]`, any port), the host names in `RECEIPTS_ALLOWED_HOSTS` (comma-separated), and `RENDER_EXTERNAL_HOSTNAME` (Render sets it on every web service to its onrender.com name; confirmed in Render's environment-variable documentation). Each name is allowed with and without a port. Its allowed origins SHALL be the same names as `https://` and `http://` origins. An entry that is not a plain host name (a wildcard, a path, spaces) SHALL be ignored; a pasted URL SHALL be reduced to its host name. The stdio server is unaffected.
2. A STRANGER IS STILL REFUSED. A request with a Host that is not allowed SHALL still be answered 421, and one with an Origin that is not allowed 403.
3. THE FIRST SCREEN IS FOR A JUDGE. Directly under the title and the Kiroween line the README SHALL have: the heading "Kiroween 2026: Resurrection"; "For judges, in 30 seconds" (what it is, the three clicks on the live demo, the three numbers, the two links, the video placeholder); an "At a glance" row of four pictures from `docs/images/` each with a one-line caption, with the other two pictures where the README talks about the check and the attacker. Every number SHALL be read from the repository.
4. HOW KIRO BUILT IT OPENS WITH A TABLE: "Kiro feature | How we used it | Why it mattered", one row each for spec, steering, hooks, MCP, custom agent, property-based tests and Kiro CLI headless, with counts read from the repository, then a short paragraph "Spec first, never vibe". The existing bullets stay below it.
5. "POINT YOUR OWN AI AT IT". A README section SHALL show how to connect an MCP client to `https://carbon-copy-ywv3.onrender.com/mcp/` (a Kiro `mcp.json` remote-server snippet with `url`, as Kiro's MCP documentation gives; `examples/mcp_client_demo.py`), what the AI sees (blocked, held, cleared), how to pull the book with `carbon_book` and check it with `python -m receipts.carbon verify <file> --key-file HOSTED_KEY.txt`, and SHALL say plainly that the workspace is shared by every visitor, that the demo uses the PayPal stand-in (no money), and the limits (60 requests a minute, 256 KB a request, the 20 MB book).
6. TESTS. Item 1 and 2 in `tests/test_carbon_round8.py`: an initialize with Host `carbon-copy-ywv3.onrender.com` is accepted when that name is configured through either variable, and an unknown Host is still refused. Items 3 to 5 in the same file read the README and compare its numbers with the repository.