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
