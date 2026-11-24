# Design: the carbon-copy receipt book

## Overview

One new module, `receipts/carbon.py`, holds the book and the check. `Receipts.emit` (in `receipts/core.py`) already fires one event for every verdict, PayPal call, desk call, owner action, flagged word and report. The book hooks in there: one event, one receipt. Nothing about what Receipts decides changes.

## Data shape

```json
{
  "n": 7,
  "at_ms": 1795462000123,
  "kind": "verdict",
  "event": { "...": "the event exactly as emit() fired it, minus its own 't'" },
  "prev": "9f86d0…(64 hex)",
  "fp": "e3b0c4…(64 hex)",
  "sig": "base64 of the Ed25519 signature over bytes.fromhex(fp)"
}
```

- `fp = sha256(canonical({"n","at_ms","kind","event","prev"}))` (task 11 replaced `at` with `at_ms`; a receipt carries exactly `n, at_ms, kind, event, prev, fp, sig`)
- `canonical(x) = json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")` (task 9 replaced `default=str` with the cleaning step below; see "The check does not trust the server")
- `canonical()` first normalises the value: every float with no fractional part becomes an int, recursively through dicts and lists; tuples become lists; anything else JSON cannot hold goes through `str` as before. A browser writes 1836.0 as 1836, so without this the same number would give different bytes after a trip through `JSON.parse` and `JSON.stringify`.
- `append()` stores the NORMALISED event, so what is hashed is exactly what is stored and handed out. `verify()` normalises before hashing too, so books signed before this change still check out when they hold no whole-number floats.
- `at_ms` is the time in whole milliseconds since the epoch, a safe integer, so the stored value and the hashed value are the same number in every JSON tool (task 11, A1; `at` in seconds was replaced).
- The first receipt's `prev` is `"0" * 64`.

A book handed out is `{"public_key": "<hex>", "head": {...}, "receipts": [...]}`. The `head` is a signed count of the book:

```json
{"count": 7, "last_fp": "e3b0c4…(64 hex)", "sig": "base64 of the Ed25519 signature over bytes.fromhex(fingerprint({\"count\": 7, \"last_fp\": …}))"}
```

`count` is the number of receipts and `last_fp` is the fingerprint of the last receipt (64 zeros when the book is empty). `sig` is a signature over `bytes.fromhex(fingerprint({"count": N, "last_fp": …}))` made with the same key as the receipts. A hash chain cannot show when the last receipt (or the last several) has been deleted: every receipt left still links up, so `verify` would say *intact*. The signed head lets the check compare the promised `count` and `last_fp` to the receipts and catch the missing ones.

The signed head closes the end of the book, but it does not close the past: someone holding an *older* signed head can cut the book back to that older length and put the older head back, and the receipts left still link up and still match the older count. The owner's phone holds a copy of the head outside the book — handed over whenever the owner approves or declines a held payment — and `verify(book, stamps)` checks the book against those stamps. A stamp whose `count` is greater than the receipts the book now holds, or whose `last_fp` is not the fingerprint of the receipt at that position, means the book was cut back to an older state; `verify` answers *changed*.

## Components

### `Signer`
- `Signer.from_env()` reads `CARBON_COPY_KEY` (64 hex characters, an Ed25519 seed) or generates a fresh key in memory.
- `sign(fp_hex) -> str` and `public_key_hex -> str`. No method returns the private key.

### `CarbonCopy`
- `__init__(signer)`
- `append(kind, event) -> dict` builds, fingerprints, signs and stores one receipt; returns a copy.
- `receipts() -> list[dict]` returns deep copies.
- `book() -> dict` returns the public key, a signed `head` (the count and last fingerprint, signed), and the receipts.
- No update or delete method.

### `verify(book, stamps=None) -> dict`
Walks the receipts in order. For each: is `n` the next number; does `prev` equal the previous `fp`; does the recomputed fingerprint equal `fp`; does the signature verify against the public key. Stops at the first failure. Then it checks the `head`: its signature verifies, its `count` equals the number of receipts, and its `last_fp` equals the last receipt's fingerprint (64 zeros when empty). A book with no `head` is *changed* with the reason "the book has no signed count"; a `head` whose signature does not verify is *changed* with the reason "the book's signed count was changed"; a `head` whose `count` or `last_fp` does not match the receipts is *changed* with the reason "receipts are missing from the end of the book".

Only when the book is intact on its own does it look at `stamps` — a list of the owner's phone stamps, each a signed head (`{"count", "last_fp", "sig"}`) handed to the phone when the owner tapped. A signed count inside the book can be cut back to an older signed count that still matches the receipts left; the phone holds a copy of the count the book reached, outside the book. If any stamp's `count` is greater than the number of receipts, or its `last_fp` is not the fingerprint of the receipt at that position, the book is *changed* with the reason "the book is shorter than a stamp the owner's phone already holds". The stamps are read only for their `count` and `last_fp`; their signatures are not re-checked here (task 9 reverses this: every stamp's signature is now checked, see below).
Returns `{"intact": true, "count": N}` or `{"intact": false, "count": N, "first_bad": n, "why": "<plain words>"}`.

### `tamper_demo(book, n=None) -> dict`
Deep-copies the book and changes one value in one receipt, runs `verify` on the copy and returns `n`, `field`, `before`, `after`, `say` (the change in plain words) and `result`. Never touches the real book.

Which receipt: when the book holds an owner action, THAT receipt (the latest "declined" if there is one, else the latest "approved"). A "declined" becomes "approved": a record edited afterwards to say the owner approved a payment she declined, the lie the product exists to catch. `say` then reads "We changed receipt #N in a copy of the book so it says Maya APPROVED the $1,836.00 payment to Blue Ridge Finishes. She declined it." The amount and payee come from the earlier verdict whose `id` equals the owner action's `hold_id` (the words "payment" alone when no such verdict is found). With no owner action it falls back to the amount of the latest money move (else another field), and `say` gives the real before and after: "We changed receipt #6 from $298.00 to $299.00 in a copy of the book." An explicit `n` changes that receipt as before.

### Command line
`python -m receipts.carbon verify path/to/book.json [--stamps path/to/stamps.json]` prints the result — *intact* with the count, or the first changed receipt in plain words — and exits 0 when intact, 1 when changed. When `--stamps` is given it loads the JSON list of the owner's phone stamps and passes them to `verify`. Files are opened as `utf-8-sig`, so a book saved with a byte-order mark (Windows PowerShell 5.1 and Notepad write one) is read too.

## Wiring

- `Receipts.__init__` takes an optional `carbon` argument; `emit()` appends every event to it before calling `on_event` (the receipt's `kind` is the event's `type`). When `carbon` is `None` every existing behaviour is unchanged.
- `Receipts.approve()` and `Receipts.decline()` return their result with the book's signed head — as it stands right after that tap is recorded — under the key `"stamp"`, so the owner's phone can hold it. Added only when `carbon` is set.
- `app.py` keeps one `CarbonCopy` per demo run and adds:
  - `GET /api/carbon` → the book
  - `POST /api/carbon/verify` → `verify(body)`
  - `POST /api/carbon/tamper` → `tamper_demo(current book)`
- The book download for the accountant gains two columns, *Receipt #* and *Fingerprint*.

## The screen

A *Carbon copy* tab, the sixth, after *Her book*, with the tooltip "Every move the AI made, sealed so nobody can quietly change it". It shows the current session's receipts, newest last. With no run yet it says: "Run Maya's day on the Watch tab first. Every move the AI makes will be copied here."

**No drawn pictures.** No wax seal image, no SVG, no line art. The verdict is a stamped word set in type: "INTACT" in green, or "CHANGED AT #7" (the first bad receipt) in red. The stamp is rotated about -6 degrees and has a double border, like a rubber stamp.

**The Halloween touch is type and colour only.** Dark paper background, receipt text in a faint carbon blue, and a typewriter face from Google Fonts: Special Elite for the receipts, the app's existing font for the buttons. Each receipt row is separated by a perforated dashed line.

**Plain words first.** Each row is one sentence an owner can read, built from the event. For example: "Held for Maya: a $1,836.00 payout to Ashwood Timber Co. for INV-AT-1142. Why: PayPal already shows a payment for this bill on its way." After the sentence come the receipt number, the time, and the first 10 characters of the fingerprint. A *Developer view* toggle shows the raw receipt JSON instead.

Three buttons:
- *Check the book* calls `POST /api/carbon/verify` and shows the stamp.
- *Try to change one* calls `POST /api/carbon/tamper` and shows the server's `say` sentence ("We changed receipt #7 in a copy of the book so it says Maya APPROVED the $1,836.00 payment to Blue Ridge Finishes. She declined it."), then shows the red stamp naming that receipt.
- *Download the carbon copies* saves a JSON file with the book and the phone's stamps.

On *Maya's phone*, after an approve or decline, one line: "Your phone kept stamp #N: the book had N receipts."

Server: every Receipts object the app builds (live runs and recorded replays) gets its own `CarbonCopy` with `Signer.from_env()`, kept with the session. The stamps returned by `approve()` and `decline()` are kept with the session and returned in the `/api/approve` and `/api/decline` responses. `GET /api/carbon?sid=` returns the book plus `stamps` and `source` ("live run" or "recorded run, replayed"). `POST /api/carbon/verify` takes `{"book", "stamps"}`. `POST /api/carbon/tamper?sid=` returns `tamper_demo` of a copy and never changes the real book.

The accountant's download from *Her book* gains *Receipt #* and *Fingerprint* columns, filled for rows from a session that has a book and blank for rows read from the recorded results files.
## Testing

- Unit tests for the canonical form, the first receipt, signing and each failure reason.
- Property-based tests (`hypothesis`): for any sequence of events, the untouched book is intact; changing any one field of any one receipt makes it *changed* at that receipt; deleting or swapping receipts is caught, including removing receipts from the end of the book.
- Unit tests for `tamper_demo` (it changes a copy, never the real book, and the check catches it) and for the command-line checker (it prints *intact* and exits 0, or the first changed receipt and exits 1, with and without `--stamps`).
- Unit tests for the owner's phone stamps: a book cut back to an older signed head is *changed* when a stamp the phone holds reaches further than the receipts, and *intact* when every stamp is satisfied.
- An integration test running one Receipts scenario on the stand-in with the book attached: the book is intact and holds one receipt per emitted event, and approving a hold returns a stamp that `verify` accepts.

## Polish round (task 7)

- **Name.** Every visitor-facing string says "Carbon Copy": page title, header wordmark, the phone's app name and notification header, empty states, the ledger's run labels ("Carbon Copy ON/OFF") and the CSV filename (`carbon_copy_*.csv`; the JSON download is `carbon_copies_*.json`). "Receipts" stays only where the README describes the base, and in module, class and field names. The header logo is the words "Carbon Copy" in Special Elite; the Receipts SVG logo and favicon are removed, and no drawn pictures replace them.
- **Change-one demo.** As in `tamper_demo` above.
- **No sideways scroll.** At every width from 375 to 1400 pixels `document.documentElement.scrollWidth` equals `window.innerWidth` on every tab. Long words and fingerprints wrap; the header wraps; only the tab bar scrolls, inside itself.
- **Hosted demo.** `render.yaml` sets `PAYPAL_MODE=standin`. The header badge and the Carbon copy source line read "PayPal stand-in (no real money, no PayPal account)". Locally `PAYPAL_MODE=auto` is unchanged.

## Which book the tab shows (task 8)

Found on the live demo: "Run the day" starts two replays for one visitor, one with Carbon Copy off (mode "observe") and one on (mode "enforce"). `GET /api/carbon` with no session took the visitor's most recently registered run, so whichever replay finished last decided the book. Online the OFF run finished last, so after Maya declined a payment the tab showed the OFF book, which has no owner action, and "Try to change one" fell back to the amount change.

- **Server.** `GET /api/carbon` and `POST /api/carbon/tamper` take an optional `mode` ("enforce" or "observe"; anything else is a 400) next to the optional `sid`. Choice order: `sid` if given; else the visitor's latest run of `mode` if given; else the visitor's latest ENFORCE run; else, only when there is no enforce run, the latest run of any mode. The choice reads each run's mode and never the order the replays finished in. The book response adds `mode` (the shown run's mode) and `has_twin` (true when the visitor also has a run of the other mode for the same day).
- **Screen.** When `has_twin` is true a small switch sits above the receipts: "Showing:" then two buttons, "Carbon Copy on (the run Maya saw)" and "Carbon Copy off (nothing checked it)". With no twin the switch is hidden. The source line names the shown run ("the run with Carbon Copy on" or "off"). Every call from the tab (`/api/carbon`, `/api/carbon/tamper`) passes the mode that is shown. Check and download use the book on screen.
- **Tests.** Both replays started in either order give the enforce book from `GET /api/carbon`; after a decline `tamper` on the default book says Maya approved what she declined; `mode=observe` returns the observe book; a bad mode is a 400.

## The check does not trust the server (task 9)

Two attack reviews broke the headline claim. A book re-signed under a new key read intact (the check used whatever key the book carried); the "phone stamps" lived in the server's session, so the server chose what the check compared against; "Check the book" asked the server; agent-written content (a lone surrogate, NaN, huge integers) either broke the write or changed on a browser round trip; a malformed stamp was skipped; a changed receipt inside the stamped part got the wrong reason; the command line exited 1 for an unreadable file; and the fingerprint recipe could not be reproduced outside this Python code. The fixes, in order of the findings (F1 to F9):

### D1. One canonical form that any JSON tool reproduces

ONE CANONICAL FORM THAT ANY JSON TOOL REPRODUCES. At append time the event is cleaned into a "safe JSON" form and that cleaned form is what is stored, hashed and handed out: dict keys and strings with lone surrogates replaced by U+FFFD; integers kept only when abs(n) <= 2**53 - 1, otherwise written as their decimal string; floats that are whole and within that range become ints; every other float (including NaN, Infinity, 298.5) becomes the string Python's repr gives; tuples become lists; any other type (Decimal, datetime, set, bytes, objects) becomes str(value) explicitly at clean time, so nothing reaches json.dumps that it would not handle; keys are sorted by Unicode code point. canonical() = json.dumps(cleaned, sort_keys=True, separators=(",", ":"), ensure_ascii=False). With only strings, safe integers, booleans, null, lists and dicts, the browser's JSON.stringify with code-point-sorted keys gives the same bytes.

Notes on how this is built (F4, F8, F9):
- `safe_json(x)` in `receipts/carbon.py` is the cleaning step. `CarbonCopy.append()` runs the event through it, so what is stored is what is hashed. It cannot raise on any value an agent writes (nesting deeper than 100 levels is written as text). Two keys that clean to the same text keep the one with the larger cleaned value, so dict order never changes the bytes. The cleaned dict keeps the order the keys were written in; `canonical()` writes them sorted by code point.
- `canonical()` has no `default=` and refuses NaN (`allow_nan=False`): a value `safe_json` has not cleaned fails loudly instead of being hashed one way and sent another. It still turns whole floats into ints and tuples into lists, so values already in this shape hash the same as before.
- The one float left in a receipt is `at`, a finite time rounded to milliseconds. Python's `repr` and the browser's number text agree on such a number (no exponent form), so it needs no special rule.
- A receipt whose event holds a non-integer float or a huge number was not written by `append()`; its fingerprint is computed as given and a book that does not match what `append()` stored reads *changed*.
- The text escapes are the same in both languages: `"` and `\` and the control characters below U+0020 (`\b \f \n \r \t`, else `\u00xx` lower case); everything else, including U+007F, U+2028 and astral characters, stays as UTF-8.

### D2. A fixed, published key (F1)

`Signer.from_env()` accepts any `CARBON_COPY_KEY` string: 64 hex characters are the Ed25519 seed as before; any other text gives the seed `SHA-256(UTF-8 text)`, so a generated random value (Render's) works. With no key set it generates one in memory. `app.py` makes ONE signer for the process and every run's book uses it, so the footer's key is the key of every book. `GET /api/carbon/key` returns `{"public_key", "short", "temporary"}` where `short` is the first 16 hex characters. The footer prints "Signing key: <short>" linked to the full key, or "Signing key: temporary (changes on restart)".

### D3. The owner's device pins the key and keeps the stamps (F2)

A stamp is `{"count", "last_fp", "sig", "public_key"}`: the signed head plus the key that signed it. `CarbonCopy.stamp()` makes one. The server hands out stamps in two ways: `approve()` and `decline()` return one under `"stamp"` as before (the `/api/approve` and `/api/decline` routes add the `public_key`), and the server-sent event stream adds `"head"` (a stamp of the book at that moment) to every event it sends, so the device holds a stamp for every moment it saw. `static/app.js` keeps them in `localStorage`:

- `cc.pinned_key`: the full public key of the first stamp the device received (trust on first use). A button on the Carbon copy tab forgets it.
- `cc.stamps.<run id>`: every stamp received for that run, whole, without repeats.

Every `localStorage` access is in `try/catch`; with storage unavailable the device keeps them in memory and the screen says "This device cannot save stamps, so it keeps them only until you close this page."

### D4. The check runs in the browser (F2, F3, F5, F6)

`static/carbon_verify.js` has `verify(book, stamps, pinnedKey)` (async): the same canonical form, SHA-256 from `crypto.subtle.digest`, Ed25519 from `crypto.subtle.verify`; it returns the same answers with the same plain reasons as the Python check. It is loaded by the page and also exports its functions with `module.exports` so `node` can run it. `supportsEd25519()` tells the page whether the browser can verify Ed25519. "Check the book" runs it against the book on screen, the device's stamps for that run and the device's pinned key, and shows "Checked in your browser" under the stamp. With no Ed25519 in WebCrypto the screen says so and posts the book, the device's stamps and the pinned key to `POST /api/carbon/verify`, labelled "Checked by the server". With no pinned key yet the screen says the device has not seen the key and the check can only compare the book with itself.

Python `verify(book, stamps=None, expected_key=None)`, in this order:
1. IF `expected_key` is given and the book's `public_key` differs: *changed*, "it was signed with a different key than the one your device trusts".
2. The receipts and the signed head, as before, against that one key.
3. Every stamp is checked before any is compared: it must be an object whose `count` is a whole number (not a float, not text, not a boolean) of at least 0, whose `last_fp` and `sig` are text, and whose signature over `fingerprint({"count", "last_fp"})` verifies against the expected key (the book's key when none is given). Otherwise: *changed*, "a stamp on your device is damaged or forged". `stamps` that is neither empty nor a list is the same.
4. Then each stamp is compared with the book: `count` beyond the receipts gives "the book is shorter than a stamp your device already holds"; a position that exists with a different `last_fp` gives "receipt #N no longer matches the stamp your device kept" (`first_bad` is N in both).
A receipt that is not an object, or whose fields cannot be hashed, is *changed* at that receipt ("its content was changed"). `_signature_ok` reads base64 strictly. The different-key and damaged-stamp results name no receipt (no `first_bad`): the whole book or the device is at fault, and the screen's stamp then reads "CHANGED".

### D5. A parity test (F9)

`tests/test_carbon_parity.py`: when `node` is on the path, the test writes a book of tricky content (unicode, astral keys, 298.5, 2**60, 9007199254740993, NaN, a lone surrogate, nested lists) through `Receipts` with the book attached and checks that `static/carbon_verify.js` under node says intact on the untouched book, names the right receipt on a changed copy, rejects a key other than the pinned one and rejects a damaged stamp. It skips with a message when node is absent.

### D6. The command line (F7)

`python -m receipts.carbon verify <book.json> [--stamps <stamps.json>] [--key <hex>]`: exit 0 intact, 1 changed, 2 the file could not be read (missing, not UTF-8, not JSON, or not a book), with one plain line on standard error. `--key` is the public key to trust (64 hex characters; anything else is exit 2).

### D7. The demo shows the real attack

`POST /api/carbon/forge?sid=&mode=` (same choice of run as `tamper`) calls `forge_demo(book)`: a copy of the book with the change `tamper_demo` makes (Maya's decline flipped to approved), then every receipt rebuilt with its links and fingerprints and signed with a brand-new key, with a new signed head and the new public key. The response is `{"book", "n", "field", "say"}`. *Try to forge a new book* hands that book to the browser's own check with the device's stamps and pinned key, and the check rejects it with the different-key reason. The screen says: "We rewrote the whole book so it says Maya approved the payment, and re-sealed every page with a new key. Your device still holds the key it trusted and the stamps it saw, so the forgery is caught." With no pinned key yet, the button says the device has not seen the key and asks the visitor to run the day first.

### D8. The README says what it cannot do

"Limits we know about" says: the device must have seen the key first (trust on first use); anything after the last stamp the device saw can still be rewritten by whoever holds the key; the check proves the book was not changed, not that what was written was true.

### Server-sent events and NaN

`_sse` writes events with `allow_nan=False` and, when an event holds NaN or Infinity, writes it again with those values as text, so one such value cannot break the stream the browser reads.

## What a judge trips on (task 10)

Everything here is display, documentation and Kiro configuration. `receipts/measure.py`, `receipts/rules.py`, `receipts/core.py`'s scoring, `results/` and `render.yaml` are untouched.

### J1. One name, one meaning
"Carbon Copy" is the product. The part from Receipts is "the check" (stops a bad payment before PayPal); the new part is "the carbon copy" (seals every move). On the Watch tab the two sides are titled "Nothing checking" and "Carbon Copy on", the option reads "Side by side: Nothing checking / Carbon Copy on", and the banner is the sentence in Requirement 10.1. The Carbon copy tab's switch and the ledger's Run column say "Nothing checking" for the OFF run in the same way (the data values `observe` and `enforce` are unchanged).

### J2. The Results tab
Renamed "What Receipts measured". `loadResults()` puts the one line from Requirement 10.2 above the group buttons. The totals in *Her book* come from the same measurement; its heading line gets the same pointer.

### J3. The "Start here" strip
Three buttons at the top of the Watch tab, in `static/index.html`, wired in `static/app.js`:
1. *Run Maya's day* calls `runDay()`.
2. *Decline the double payment on her phone* sets a flag `PATH.phone = true`. `showOutcome()` and the hold poll look at it: when a hold is waiting, `showTab("owner")` runs once and the flag clears. If the run ends with no hold, the strip says so in one line.
3. *Try to forge the record* calls `showTab("carbon")`, waits for `loadCarbon()` and then clicks *Try to forge a new book*. With no book yet it says "Run Maya's day first" and does nothing else.
Each step shows as done once it is. The existing controls stay below.

### J4. The live counter
Every event the server streams carries `head` (the signed count after that event). `render()` already reads it for the device's stamps; for the run with Carbon Copy on it also sets `#sealed` to `head.count`. The counter is a link-styled button that calls `showTab("carbon")`, and it resets to 0 when a run starts.

### J5. False alarms: what was found
Found by replaying the page's own default (glm-5.3 on "Crossed in the mail") and reading the events.
- **(a) "SAID: NO / SUSPICIOUS" on the AI's honest explanation.** Cause: `words.classify()` is a set of regular expressions. Its REFUSED set matches "will not", "I will not retry", "violate ... rule", and also "suspicious", "fraud". The AI had written: "Paying again would violate rule 3 ... so I will not retry." That is an honest explanation of why it did not pay twice, and "NO" is true, but "SUSPICIOUS" was never in it. The label claimed more than the pattern means. **Fix (display):** the tag reads "SAID: NO", with one line under the first one: "A word pattern marked this: the AI's words include a refusal. It is a pattern match, not a judgement of the AI." The pattern and the scoring are unchanged (a tag only matters to the score when the AI then makes a move the rules stop, and here it did not).
- **(b) A receipt reading "The AI wrote (held)".** Cause: `ccSentence()` printed the marker `HELD` in brackets. `HELD` means the words read as a promise to hold or verify. A reader takes "(held)" to mean the AI's message was held. **Fix:** `HELD` reads "(it said it would hold or verify)" and `REFUSED` reads "(it said no)". The receipt's data is unchanged: the book still stores the marker as written.
- **(c) "Honest work done: 1 of 1" on the side with nothing checking, after the bill was paid twice.** Cause: `legit_expected` for this day is one move, the Hollis Freight bill (INV-HF-0936), and the AI did it, so 1 of 1 is correct. Paying Blue Ridge a second time is not honest work; it is counted apart as a risky move (`trap_attempts`), which the same line reports. The label was right and a reader took it to mean "nothing went wrong". **Fix:** the line gains a second sentence: "Honest work counts only the bills that were right to pay. A payment that should not have been made is counted apart, as a risky money move."

### J6. Plain words
On the Carbon copy tab, one line each, shown once under the buttons (`#ccWords`): fingerprint, stamp, signing key, in the words of Requirement 10.6. The fingerprint line sits above the receipt list (where fingerprints first show), the other two sit with the device line (where stamps and the key first show). The `list_vendors` label on the Watch tab reads "Opened Maya's list of suppliers". The model-facing tool descriptions in `receipts/desk.py` and the recorded runs are not screen text and stay as they are.

### J7. The tab bar
`.tabs` is a single row that scrolls sideways inside itself at every width (`overflow-x: auto; max-width: 100%; min-width: 0`), the header lets it shrink (`flex: 1 1 auto; min-width: 0`), and `showTab()` calls `scrollIntoView({inline: "nearest", block: "nearest"})` on the active button so it is never hidden. The badge no longer widens the Phone tab beyond its text.

### J8. Kiro configuration
- `.kiro/settings/mcp.json`: `mcpServers.carbon-copy` with `command` `.venv\Scripts\python.exe` and `args` `["-m", "receipts.mcp_server"]`. No `env`, no key.
- `receipts/mcp_server.py` gains `if __name__ == "__main__"` that builds the server and runs it over stdio, so a client can start it. Nothing else in the file changes.
- `.kiro/agents/carbon-attacker.json`: JSON profile with `name`, `description`, `prompt`, `tools`, `permissions` (read, a narrow set of shell commands, write only under a scratch folder that git ignores) and `includeMcpJson`. Format taken from kiro.dev/docs/custom-agents/configuration-reference. The prompt tells it to attack with `python -m receipts.carbon verify` and `pytest`, to work on copies, never to edit `receipts/` or the real book, and to report only findings it reproduced, with the command that shows each.

### J9. README
Lists tasks 1 to 10, says the demo is on an always-on plan, says the no-keys hook runs after each save, adds "How Kiro built it" with one answer per question the Kiroween rules ask, and the two placeholders.

### Tests
`tests/test_carbon_app.py` gains tests that read the page and the script as shipped (labels, banner, six tabs, "Start here" buttons, counter, no "vendor master", the Results line and name, the plain-word lines), that the two Kiro files parse and point at files that exist, that no Kiro file or README line holds a key, and that `python -m receipts.mcp_server` answers an MCP `initialize` over stdio. A node-run test of the marker wording is not added: the wording lives in two small pure functions (`markerTag`, `markerWords`) that the page tests read as text.


## What our own attacker found (task 11)

The custom Kiro agent `carbon-attacker` attacked the book and proved the findings below. Each has a reproduction in `scratch_attacks/` (git ignores that folder) and, since task 11, a test in `tests/` that builds the same attack and expects the check to catch it. Nothing here changes what Receipts decides.

### A1. The receipt's time is cleaned like the event
Cause: `append()` sealed `at` as a float rounded to milliseconds. An event time of `1e21` is a whole float, so Python's `normalise()` turned it into the integer `1000000000000000000000` before hashing, while JavaScript writes the same number as `1e+21`. The two checks hashed different bytes. It was reachable only by calling `append()` with such a time, not through the web app.

Fix: the receipt carries `at_ms`, a whole number of milliseconds since the epoch. `_receipt_time_ms(t)` takes the event's `t` (seconds), multiplies by 1000, rounds, and accepts the result only when it is between 0 and 2^53 - 1; anything else (missing, text, NaN, a boolean, 1e21, a negative time) becomes the current time. So the sealed time is always a safe integer that every JSON tool writes the same way. The check also refuses an `at_ms` that is not such a number (`_time_ok`), even when someone with the key signed it; a whole float such as `5.0` still reads as `5`, as a browser reads it. The screen formats `at_ms` (`new Date(r.at_ms)`).

Old books: a receipt from before task 11 carries `at` in seconds and no `at_ms`. Reading both would need two fingerprint recipes and two key sets in both checks, for a demo book that lives in memory for one visit. We chose the simpler course: **books from before task 11 are not readable.** They read as *changed* (the `at` key is outside the seven sealed keys, A3). The README's Limits says so.

### A2. A book of the wrong shape is changed
Cause: Python read `book.get("receipts") or []`, so `{}`, `0`, `""` and `false` became an empty book and read *intact*; the browser rejected them.

Fix: both checks require the book to be an object whose `receipts` is a list. Anything else, including a missing `receipts`, is *changed* with `count` 0, `first_bad` 1 and the reason "this is not a carbon-copy book we can read".

### A3. A receipt carries exactly its seal
Cause: the fingerprint covers five fields and the signature covers the fingerprint, so a key added beside them (`"approved_by": "maya"`) changed nothing the check looked at.

Fix: a receipt's keys must be a subset of `n, at_ms, kind, event, prev, fp, sig` (`SEALED_KEYS`). Any other key makes the book *changed* at that receipt with "receipt #N carries something outside its seal", where N is the receipt's position in the book. A sealed key that is missing already fails the content or signature check. At the top level the checks read only `public_key`, `head` and `receipts`; a key beside them is not read and does not change the answer, because it is not part of the book. What is shown or exported is cut to those parts: `public_book()` copies a book with only the three parts and only the seven keys in each receipt, `tamper_demo` and `forge_demo` build their copies through it, `book()` hands out exactly the three, and the screen's developer view prints a receipt's sealed keys only (`sealedOnly` in `static/app.js`).

### A4. A signature has one written form
Cause: a 64-byte signature is 88 base64 characters whose last character carries four unused bits, so 16 texts decode to the same bytes. Python's `b64decode(validate=True)` and the browser's `atob` both accept all 16.

Fix: `_signature_ok` decodes, re-encodes and requires the text to equal the re-encoding (standard alphabet, padded, no spaces or line breaks). `static/carbon_verify.js` does the same with `atob` and `btoa`. The rule applies to a receipt's, the head's and every stamp's signature, and each keeps its own reason ("its signature does not match", "the book's signed count was changed", "a stamp on your device is damaged or forged").

### A5. A key has one written form
Cause: `bytes.fromhex` ignores spaces, so a key written as `"d7 5a 98 ..."` verified in Python; the browser's hex reader did not.

Fix: a book's `public_key` must match `[0-9a-f]{64}` in both checks, otherwise *changed* with "its public key is not written the way a key must be". This is checked before the key the device trusts is compared. The key the device trusts may still be given in capitals; it is lower-cased before the comparison.

### A6. Different values that seal the same: kept, and said so
`298.5` and `"298.5"`, `2**60` and `"1152921504606846976"`, `Decimal("5.10")` and `"5.10"`, `NaN` and `"nan"` all clean to the same text, so they seal to the same fingerprint. That is the cleaning of design D1, which exists so that every JSON tool reproduces the bytes. It stays. The README's Limits gets one line: "Amounts that are not whole numbers are sealed as text, so the book shows the value, not whether the AI wrote it as a number or as text." A test pins the behaviour so any change is a decision.

### A7. Why the attacker did not see the MCP tools
Checked on Windows with Kiro CLI 3.5.0, against kiro.dev/docs/mcp/configuration and kiro.dev/docs/custom-agents/configuration-reference.

- Location and loading are right. A workspace server lives in `<workspace>/.kiro/settings/mcp.json`, and an agent includes it with `"includeMcpJson": true`. `kiro-cli mcp list` shows `carbon-copy` under the default agent, and `kiro-cli mcp status --name carbon-copy` shows the command and a 120000 ms timeout.
- The relative command is not the problem. Started from the workspace folder, `.venv\Scripts\python.exe -m receipts.mcp_server` connects (about 2.8 seconds as Kiro measures it, of which roughly one second is Python importing the `mcp` package) and lists the twelve tools. Replacing it with an absolute path changed nothing.
- Cause 1: the agent file held only the newer `permissions` field, which makes it "v3-only". `kiro-cli chat --no-interactive` runs the older engine unless `--agent-engine v3` is given, and that engine answers "Mode 'carbon-attacker' not found" (`kiro-cli agent upgrade --dry-run .kiro/agents` called the file "v3-only"). Removing `permissions` made it load; so did adding the older fields.
- Cause 2: on the newer engine in a one-shot headless run, the first turn starts before the MCP server has connected, so the first catalogue of tools is empty. The tools appear after the connect (a later turn lists all twelve).
- Fix: the agent file is written in the form both engines load: the newer `tools` and `permissions` plus the older `allowedTools` and `toolsSettings` (shell commands as regular expressions, write paths as globs), the same limits written twice. A test checks that the two agree. The prompt tells the attacker that the carbon-copy tools can take a few seconds to connect and to look again before saying they are missing.
- Proof: `kiro-cli mcp list` output is in the task 11 report; `kiro-cli chat --agent-engine v2 --agent carbon-attacker` lists the twelve tools and calls `receipts_holds`; a test starts the server from the command and arguments in `mcp.json`, from the workspace folder, and performs the MCP handshake. We could not see inside the attacker's own session, so we cannot say which of the two causes it hit; both reproduce its message.

### A8. The attacker knows what is fixed
The prompt lists A1 to A6 in plain words as already fixed and says to look for new shapes.

### Tests
`tests/test_carbon.py` holds the unit and property tests for A1 to A6 (every spelling of a signature, every key form, extra keys by property, event times by property). `tests/test_carbon_parity.py` builds each attack once and runs it through both checks under node, requiring the same answer and *changed* for every attack. `tests/test_carbon_app.py` holds the checks of the spec, README, agent file and the MCP start-up.


## Task 12: what our own attacker found, second round (C1 to C8)

Nothing here changes what Receipts decides (`receipts/measure.py`, `receipts/rules.py`, `results/` and the scoring in `core.py` stay as they are).

### C1. The download reads on the command line
Cause: the page writes `{"book", "stamps", "trusted_key"}`; the command read the file as a book and found no `receipts`.
Fix: `read_check_file(parsed)` in `receipts/carbon.py` returns `(book, stamps, key)`. A dict with a `book` object and no `receipts` of its own is the download shape; anything else is a bare book. The command uses the download's `stamps` and `trusted_key` unless `--stamps` or `--key` is given. A `trusted_key` that is not 64 hex characters is exit 2 (same rule as `--key`). A test builds the file the way `bookParts()` in `static/app.js` builds it.

### C2. No traceback
Cause: `json.loads` on a file nested 200,000 levels raises `RecursionError`, which is not a `ValueError`.
Fix: reading and parsing either file catches every `Exception` and prints one line, `could not read the file: <name> is not a book we can read`, exit 2.

### C3. PayPal said no
Cause: `ccSentence` said "It went to PayPal" for every approval and "Sent to PayPal" for every PayPal receipt, whatever the sealed result held.
Fix: the sentence function reads the sealed `result`. With an `error` (a text, or an object with `message`, or `details[0].issue`) it says "PayPal refused it: <reason>". Known codes have plain words (`REFUND_AMOUNT_EXCEEDED` is "the refund is more than what is left on that payment"); an unknown code is shown lower-cased with spaces; a timeout says PayPal did not answer in time. The words come from the sealed receipt, so they are as sealed as the receipt.

### C4. One answer from both checks
- B1: the browser used the trusted key as the user typed it when it checked stamps; it now lower-cases it, as Python does.
- B2: a browser cannot tell `6.0` from `6` once JSON is parsed. `CarbonVerify.parseStamps(text)` parses with the reviver's `context.source` and turns a `count` written as anything but a plain integer into a marker that is not a number, so the stamp is damaged; `verify` accepts stamps as such text too. Python rejects a float `count` as before. The page reads stamps from storage through `parseStamps`.
- B3: `kind` must be a non-empty text in both checks and in `append()` (which raises `ValueError`; the book is never left holding a receipt the check calls changed). A receipt must carry all seven keys: a missing `n`, `at_ms`, `kind`, `event`, `prev` or `fp` is *changed*; a missing `sig` is "its signature does not match". Python's `r.get` read a missing key and a null as the same thing; both checks now test presence.

### C5. The run is sealed
Cause: the header and the ledger read `mode`, `source`, scenario and model from fields beside the book, not sealed by anything.
Fix: `run_event(...)` builds `{"mode", "source", "scenario", "title", "model", "started"}` and `app._register` appends it, as kind `run`, before anything else is written to the book. `run_of(receipts)` returns the event of receipt 1 when it is of kind `run`. The page's header, the switch's pressed state and the receipt sentence for `run` read receipt 1 only; the ledger takes model, scenario and time (`started`) from it, and leaves them blank when a book has no run receipt. A book without a `run` receipt is described as "a run this book does not describe".

### C6. The device remembers 100 runs
`DEV_MAX_RUNS` is 100 (about 15 KB of stamps per run, so about 1.5 MB of the 5 MB a browser gives a page). The server keeps 40 runs per visitor, which is unchanged. The "kept no stamp for this run" line now sits directly under the verdict stamp, in warning style. The README's Limits explains the eviction.

### C7. The current book
`refreshBook()` in `static/app.js` fetches `/api/carbon?sid=<run>` and replaces the page's copy before each of the four buttons acts. If the server no longer has the run the button says so and stops.

### C8. The attacker's prompt
The prompt says every command sets `PAYPAL_MODE=standin`, never starts the sandbox, and lists C1 to C7 as fixed. The permission rules keep their shape.

### Tests
`tests/test_carbon_round2.py` holds a test for each of C1 to C8 (the CLI through `subprocess`, the page's own functions under node).


## Task 13: an honest book after a local restart

`restart_note(book_key, trusted_key, temporary)` in `receipts/carbon.py` is plain code with no model: it returns the explanation text (`RESTART_NOTE`) only when `temporary is True`, `trusted_key` is set and the two keys differ (compared lower-cased), else `None`. `static/carbon_verify.js` carries the same function (`restartNote`) and the same text. `verify()` is not changed, so the verdict is the same as before. On "Check the book" the page reads `/api/carbon/key` (`temporary`) and puts the note under the verdict; if that request fails it shows nothing. The footer is unchanged. The README's "Try it" gains a fixed-key line. Tests are in `tests/test_carbon_restart.py`.


## Task 14: "Try to change one" is checked in the browser too

`tamper_demo()` in `receipts/carbon.py` now also returns `book`, the deep copy it changed (None for an empty book); `/api/carbon/tamper` passes it through with the fields it returned before. The server's `result` stays for the command line and tests. The `#ccTamper` handler in `static/app.js` runs `t.book` through `checkOnDevice()` (the device's stamps and pinned key, the browser's SHA-256 and Ed25519) and shows `ccStamp(got.out)`, the reason and `ccWhere(got.where)`, as the forge button does; with no Ed25519 `checkOnDevice` falls back to the server as before. The changed copy keeps every old signature, so both checks stop at the same receipt with "its content was changed"; a parity test over the copy keeps it so. Nothing in `verify()` changed.


## Task 15: every money move gets its receipt, on every path

**F1, the MCP book.** `receipts.mcp_server.build(register, on_event, signer)` makes a `CarbonCopy(signer)` (the stdio start passes `Signer.from_env()`, `app.py` passes `SIGNER`, so one process has one key), seals `run_event("enforce", "live", "MCP_workspace", "mcp client")` as receipt 1, and gives the book to `Receipts(carbon=...)`. `emit()` then seals every verdict, PayPal or desk call and owner tap. The new tool `carbon_book` returns `carbon.book()` as JSON. The README shows saving that answer and running `python -m receipts.carbon check`.

**F2, the phone.** `RECEIPTS_MCP_ON_PHONE` defaults to `"0"` in `app.py`. When it is `"1"` the MCP `Receipts` is listed in `_sessions()` as before; its `approve` and `decline` now seal into the MCP book and return the stamp (`_with_key` adds the public key). The README says in one line that this is for your own machine only.

**F3, one lock.** `CarbonCopy.book()` copies the receipts and signs the head inside one `with self._lock`. `receipts()` also takes the lock. `head()` is the public cheap head.

**F5, the tap.** Per `Receipts` object one `threading.Lock` (`_tap_lock`) guards `approve` and `decline` from the check of WAITING to the last receipt. `approve` sets the hold to APPROVED, seals `owner` / `approved`, forwards inside `try`, and seals a second `owner` receipt: `sent` with PayPal's answer (a refusal PayPal sent is an answer and is sealed as it came), or `not_sent` with the error in plain words when the forward raised. The hold's `result` carries `error` when PayPal did not take it. The answer is the result plus `stamp`, the stamp taken after the last receipt. The phone reads `result.error` and says "Approved, but PayPal did not take it: <reason>". The tamper and forge demos still act on `approved` / `declined` only.

**F6, the amount.** `rules.amount_problem(x)` returns the plain reason or `None` (finite, not negative, readable). `RuleBook.check` uses it for `create_payout` and `create_refund` (a refund with no amount means the whole balance and is not checked): a bad amount gives one BLOCK finding `AMOUNT_NOT_A_NUMBER` and skips that tool's other checks, which would compare NaN or `None`. `money()` is unchanged. The proof test patches `amount_problem` to "always fine" for the old rules and re-scores every recorded run with both, comparing each verdict whole.

**F13, the stream.** `_data` tries `json.dumps(ev, allow_nan=False)`, on any error `json.dumps(safe_json(ev))`, on any error a placeholder `{"type": "unshown", "msg": ...}` that keeps the event's `head` when it is plain. The ordinary form is tried first so the page keeps amounts as numbers; the cleaned form is the fallback.

**F14.** `approve` and `decline` take `carbon.head()`.

Tests are in `tests/test_carbon_round3.py`.


## Task 16: a check that does not need to trust us, and honest limits

**F8, the check's code.** `static/carbon_verify.js` ends with `Object.freeze(api)` and defines `root.CarbonVerify` as a read-only, non-writable property, so a later assignment does nothing. `static/app.js` begins with `const CHECK = window.CarbonVerify`, and every use reads `CHECK`. The AG Grid `<script>` has `integrity="sha384-..."` and `crossorigin="anonymous"`. `tools/build_verify.py` reads `static/carbon_verify.js` as bytes and writes `verify.html`, a template with that code placed between `<script>` tags (the code holds no `</script>`; the builder refuses if it does) and a small page script of its own. The page has no `src`, `href` or `@import` that leaves the file. A dropped file is read with `FileReader`, parsed as the CLI parses it (the download `{book, stamps, trusted_key}` or a bare book), checked with `CarbonVerify.verify`, and shown as INTACT or CHANGED with the reason and the two notes about no key and no stamp. `HOSTED_KEY` is written into the page by the builder beside a line "The key this download trusts" and a match or no-match sentence.

**F9, the published key.** `HOSTED_KEY.txt` holds the 64 hex characters and a line saying where they came from. `python -m receipts.carbon verify <file> --key-file HOSTED_KEY.txt` reads the first 64-hex word. `--key` and `--key-file` together exit 2.

**F7, the caveats.** `caveats(trusted_key, stamps)` in `receipts/carbon.py` returns the two sentences as the page prints them. The command line prints them after the verdict line, intact or changed (on standard output, exit code unchanged), both when both are missing.

**F10.** `static/index.html` carries the one-hour sentence on the phone and the Carbon copy tab; `expiredCard` says the payment lapsed and was never sent to PayPal.

**F4, the visitors.** `VisitorCookie` still issues a cookie, but a visitor object is created only by `_visitor(request, create=True)`, called by `/api/run` and `/api/replay`; `POST /api/policy` uses `_visitor(request)` and answers 400 when there is none. A request is a new visitor when it carries no valid cookie; `_admit(request)` counts new visitors per client address in a 10-minute window (30), answering 429. Eviction: `_make_room()` drops, oldest first, a visitor with no WAITING hold and no run younger than an hour; only when there is none does it drop the oldest.

**F11, MCP.** After every tool call `mcp_server` trims the history: `r.verdicts[-500:]`, `r.holds[-200:]`, and an argument string over 64 KB becomes its first 64 KB plus `(cut: N bytes)` with `cut` set on the hold. `Receipts.approve` refuses a hold with `cut`. The book is untouched. `receipts_holds(limit=50)` returns the newest first.

**F12.** `set_policy` checks sizes before `_validate`, 413.

**The recorded runs.** `tests/test_carbon_recorded_runs.py` replays through `make_paypal` and `Receipts(... carbon=CarbonCopy(SIGNER))` as `replay()` does in `app.py`, declines every hold as the owner, and runs the checks of the outside measurement. It prints its numbers.

Tests are in `tests/test_carbon_round4.py` and `tests/test_carbon_recorded_runs.py`.

## Task 17: the two findings task 16 left open

**F11.** `CarbonCopy` keeps a running count of the stored JSON (`size_bytes()`, added to as each receipt is appended; it reads the book, never changes it). `McpGuard`, a plain ASGI middleware in `app.py` on paths under `/mcp`, counts requests per client address (`_client_address`, the visitor limit's rule) over 60 seconds (429, `Retry-After`), then reads the body up to 256 KB + 1 byte (413 past it, with or without a declared length) and replays it unchanged to the MCP app. In `receipts/mcp_server.py` each of `create_refund`, `accept_dispute_claim`, `create_payout` and `update_vendor_payee` first asks `full(tool)`: when `size_bytes()` is at or past `r.mcp_cap_bytes` (20 MB, env `RECEIPTS_MCP_BOOK_MB`) it returns `blocked_by_receipts` with the book-full sentence and does not call `Receipts.call`. `POST /api/approve` for the MCP workspace answers 409 with the same sentence. A refusal writes no receipt (a refusal that wrote one would let a client keep growing the book); the check is made before the call, so one call can pass the cap by its own receipts, at most about 256 KB of arguments.

**F10.** `_run_expired(s, now)`: a run is over one hour after its last activity, or 24 hours after it when a hold in it is still WAITING (amended by Task 18: the time counts from the run starting or the owner's last approve or decline, not from the start alone). `_visitor` and `_holds_something` use it. The two sentences on the phone and the Carbon copy tab, and the README Limits, give both times.

Tests are in `tests/test_carbon_round5.py`.

## Task 18: the hour counts from the last activity

`s["t"]` of a run (in `Visitor.sessions`) now means its last activity, not its start. It is set when the run starts and again in `_keep_stamp` each time an approve or decline hands back a stamp (a tap that wrote a receipt). `_run_expired(s, now)` is unchanged in form: over `SESSION_MAX_AGE_S` since `t` is over, unless a hold is WAITING, then `HOLD_MAX_AGE_S`. The sentence on the phone and the Carbon copy tab (`static/index.html`) and the README Limits use the Requirement 18 wording. Tests are in `tests/test_carbon_round5.py`.

## Task 21: the fourth attacker round's twelve findings

**1. The tap looks again.** `Receipts.approve` calls `_tap_problem(hold)` first: `rules.check(tool, args, None, None)` run again against PayPal's records as they are now. It refuses when a finding is a BLOCK, or has a code in `SINCE_HOLD_CODES` (`ALREADY_PAID_IN_PAYPAL`, `PAYMENT_IN_FLIGHT`, `NEAR_DUPLICATE_BILL`, `SPLIT_UNDER_LIMIT`, `REFUND_WHILE_DISPUTED`) that the hold was not already held for (`_hold_codes`, kept beside `holds` so the hold's own shape is unchanged). The reason is a plain sentence ("INV-AT-9501 was paid while this was waiting") or the finding's own words. If the records cannot be read, nothing is sealed and nothing sent, and the answer asks the owner to tap again. Otherwise "approved" is sealed, then either "refused_at_tap" (hold status stays APPROVED, its result carries `refused_at_tap` and the reason) or the forward. `hold_notes(hold)` gives the words for the card before the tap (another waiting hold for the same invoice; "If you approve this now it will be refused: ..."); `/api/holds` adds them as `notes` to a WAITING hold. The second look and the forward happen under the tap lock; task 22 closes the gap that was left between them (see Task 22).

**2. A send that may have left.** `_forward` already turns a refusal PayPal answered, and a TypeError for bad arguments, into an answer. In `approve`, a `ValueError` or `TypeError` that escapes is the client refusing its own arguments: sealed "not_sent". Any other exception: before the send, `_paypal_before` notes what PayPal's records show for this payment (the payout ids for the invoice, the capture's refunded total, the dispute's status, the vendor's email); after it, "no_answer" is sealed, `_look_up` reads the same records (`payout_records`, `capture_record`, `dispute_record`) and what changed since is sealed: "sent" (with PayPal's id, the money recorded in the run's ledger as for any send) or "not_found". A lookup that itself fails seals "lookup_failed" and says to check PayPal before approving again.

**3. The address.** `_client_address` takes `X-Forwarded-For`'s entries and, when `RECEIPTS_BEHIND_PROXY=1`, the one at `-PROXY_HOPS` (`RECEIPTS_PROXY_HOPS`, default 1); fewer entries than hops, or none, give the socket's address.

**4. The cap.** `full(tool)` in `receipts/mcp_server.py` no longer looks at the tool's name: every tool except `carbon_book` asks it first.

**5 and 6. The table.** `_visitor` drops an idle visitor only when `_has_waiting_hold` is false. `_make_room` ranks each visitor by `_keep_rank`: 0 nothing kept (no run that is not over), 1 only runs, 2 a payment waiting; it drops the least recently seen of rank 0, else of rank 1, else of rank 2.

**7. A tap on nothing.** `/api/approve` and `/api/decline` call `_touch` only when `_is_waiting(r, hold_id)`; then the tap decides.

**8. The run cap.** `_register` drops the oldest run with nothing waiting, never the one being registered; only when every other run has a waiting payment, the oldest of them.

**9 and 10. verify.html.** The page trusts `PUBLISHED` unless the switch `useFileKey` is ticked, and says "signed with a different key than the published one" for the key reason. `carbon_verify.js` adds `hasUnsafeInteger(text)` (steps over strings, reads every other run of digits as a number, true for a whole number past 2^53 - 1; no regex runs unless a 16-digit run exists) and `WHY_BIG_NUMBER`; the page checks the raw text after it parses. `receipts/carbon.py` has the same words and `load_json_text`, which reads a file with `parse_int` noting any whole number past 2^53 - 1 without ever turning a long text into a number; the command line says CHANGED with `WHY_BIG_NUMBER`, exit 1. A `stamps` value that is text is passed to `verify` as a non-list on the page, as Python reads it.

**11. Visitors.** `_visitor(..., create=True, may_start=False)` returns None for a visitor not held, whatever the cookie. The page's "Use these rules" shows the server's words when the rules were not kept. Amended by task 22: see Task 22, section 1.

**12. Zero.** `amount_problem` refuses `a <= 0` with "the amount is not a positive number of dollars". `tests/test_carbon_round3.py` re-scores every recorded run (results/episodes.jsonl and results/frontier) with the rules before task 15, as task 15 left them and as now; every verdict is identical.

Tests are in `tests/test_carbon_round6.py`.

## Task 22: saving rules before a run, and the instant between the tap's look and its send

**1. A signed visitor cookie.** VisitorCookie (the ASGI middleware) now reads the cookie as <id>.<tag>, where id is secrets.token_urlsafe(32) and 	ag is the URL-safe base64 of HMAC-SHA256(COOKIE_KEY, id) without padding. COOKIE_KEY is made once at start-up: hashlib.sha256(b"carbon-copy visitor cookie v1" + CARBON_COPY_KEY text) when that variable is set (so the hosted demo's restarts keep accepting cookies it issued), else secrets.token_bytes(32). It is a different value from the signing key, is never the signing key, and is never written to a file, a log or an error. The tag is compared with hmac.compare_digest. A cookie with no valid tag (made up, unsigned, tag for another id, other key) is treated as no cookie. Whether a request that carries no valid cookie is handed a new signed one is unchanged: the response sets it. Setting a cookie creates no Visitor. / is the page load that hands one out (any request without a valid cookie does, as before).

_visitor(request, create=True) creates a visitor only for an id whose cookie was valid (scope[VISITOR_SCOPE_KEY] is set by the middleware only for an id that either came in signed, or was issued on this very request). POST /api/policy calls it with create=True (a rules save is allowed to make the visitor); a request that came in with NO valid cookie of its own (the id was issued on this request: ISSUED_SCOPE_KEY) still gets 400, since the browser cannot have loaded the page. Creation is counted by _admit_new_visitor, so the per-address limit of 30 new visitors per 10 minutes holds for rules saves too. GET requests, eset, holds, the book and the ledger still create nothing (create=False).

**2. One lock per run.** Receipts has un_lock, a 	hreading.RLock (the old _tap_lock, renamed and made re-entrant, because an event handler that runs inside call may itself tap). call holds it for the whole of a money tool (the rules check, the verdict, the hold or the forward); pprove holds it for its second look and its forward; decline holds it as before. Because the agent's check and its forward are one step under the lock, and the tap's look and forward are one step under the same lock, whichever starts second sees the first one's payment in the records and the rules refuse it. The MCP server's tools call .call and the phone's taps on MCP holds call .approve on the same Receipts, so one lock covers both. A non-money tool (a read) does not take the lock.

Tests are in 	ests/test_carbon_round7.py.


## Task 25: the hosted /mcp answers a client, and the README's first screen

**1. The cause.** `MCPServer.streamable_http_app(..., host="127.0.0.1")` turns DNS-rebinding protection on for localhost only when `transport_security` is None and the host is a loopback address. A request to the hosted demo carries `Host: carbon-copy-ywv3.onrender.com`, which is not in that list, so the library answers 421 before any tool runs.

**2. The fix, the supported way.** `mcp.server.transport_security.TransportSecuritySettings` has `enable_dns_rebinding_protection`, `allowed_hosts` and `allowed_origins`; an allowed entry matches exactly, or as `name:*` for any port. `receipts/mcp_server.py` has `allowed_host_names(env)` (names from `RECEIPTS_ALLOWED_HOSTS`, split on commas, then `RENDER_EXTERNAL_HOSTNAME`; lower-cased, de-duplicated; a pasted URL is cut to its host; an entry with a wildcard, space or other odd character is dropped) and `transport_security(env)` (protection on; hosts `127.0.0.1:*`, `localhost:*`, `[::1]:*` and each name with and without `:*`; origins the localhost ones and each name as `https://` and `http://`, with and without `:*`). `app.py` passes `transport_security()` when it mounts /mcp. `render.yaml` also sets `RECEIPTS_ALLOWED_HOSTS` to the hosted name, so the hosted demo does not depend on one variable alone. The protection is never turned off; with nothing configured the behaviour is the one before (localhost only).

**3. Tests.** `tests/test_carbon_round8.py`: the pure functions; an initialize through a real streamable-HTTP app built with the settings (accepted for the configured name through either variable, refused for another Host with 421, a foreign Origin refused 403, localhost with a port still accepted); and a fresh process that imports `app` with the variable set and talks to `/mcp/` through its middleware.

**4. The README.** The first screen, the table, "Point your own AI at it" and the updated counts are in the README; numbers are read from the repository: the attacker findings from the four reports in `docs/kiro-sessions/` (10, 12, 17, 23), the receipts count from "What we measured on the book", the counts of requirements, tasks, hooks, steering files and session records from the repository's files. Tests compare them (`tests/test_carbon_round8.py` and `tests/readme_counts.py`).

## Task 26: what a first-time judge trips on (amends Requirement 10)

**1. The scroll.** `static/app.js` has `showAnswer()`: when `#ccResult` has content it sets `scroll-margin-top` to the sticky bar's height plus 12 pixels and calls `scrollIntoView({ block: "start" })`, smooth unless `prefers-reduced-motion` is set. `answered(fn)` wraps the three button handlers so it runs after each one finishes, whatever path it took (an answer, or a plain "nothing to change yet"). `static/style.css` carries a default `scroll-margin-top` for `.cc-result`. On the tall phone bar (162 px at 375 wide) a fixed margin put the stamp under the bar, so the margin is read from the bar.

**2. The footer.** One more line in `.foot`, in the same style, with the repository link (`rel="noopener"`).

**3. Which PayPal.** `ppSay("the" | "poss")` returns "the PayPal stand-in" or "the PayPal sandbox" (and the possessive) from `META.paypal_mode`, which comes from `/api/meta`. Static text in `index.html` that names PayPal carries `data-pp` and is filled in at boot; the run-source option, the side's sub-title, the replay tag and the ledger's "Why" header call `ppSay`. Screens that already name which one are left alone.

**4. The repository.** The words in `docs/kiro-sessions/README.md`, the hook description and the README, as Requirement 10 items 13 to 15 say. The README's word count goes down; every count test still compares the README with the repository.

**5. Tests.** `tests/test_carbon_round9.py`: the wording; and a real Chromium (Playwright; skipped when none is installed) at 375 x 812, 768 x 1024 and 1280 x 800, light and dark, driving the demo against a local server on the stand-in: the stamp is under the sticky bar, on screen and in the top part of the window after each of the three buttons.