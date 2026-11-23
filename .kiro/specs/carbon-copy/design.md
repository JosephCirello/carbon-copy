# Design: the carbon-copy receipt book

## Overview

One new module, `receipts/carbon.py`, holds the book and the check. `Receipts.emit` (in `receipts/core.py`) already fires one event for every verdict, PayPal call, desk call, owner action, flagged word and report. The book hooks in there: one event, one receipt. Nothing about what Receipts decides changes.

## Data shape

```json
{
  "n": 7,
  "at": 1795462000.123,
  "kind": "verdict",
  "event": { "...": "the event exactly as emit() fired it, minus its own 't'" },
  "prev": "9f86d0…(64 hex)",
  "fp": "e3b0c4…(64 hex)",
  "sig": "base64 of the Ed25519 signature over bytes.fromhex(fp)"
}
```

- `fp = sha256(canonical({"n","at","kind","event","prev"}))`
- `canonical(x) = json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")`
- `at` is rounded to milliseconds before hashing, so the stored value and the hashed value are the same number.
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

Only when the book is intact on its own does it look at `stamps` — a list of the owner's phone stamps, each a signed head (`{"count", "last_fp", "sig"}`) handed to the phone when the owner tapped. A signed count inside the book can be cut back to an older signed count that still matches the receipts left; the phone holds a copy of the count the book reached, outside the book. If any stamp's `count` is greater than the number of receipts, or its `last_fp` is not the fingerprint of the receipt at that position, the book is *changed* with the reason "the book is shorter than a stamp the owner's phone already holds". The stamps are read only for their `count` and `last_fp`; their signatures are not re-checked here (a stamp is an assertion the phone holds, and a false one fails closed — it says *changed*).
Returns `{"intact": true, "count": N}` or `{"intact": false, "count": N, "first_bad": n, "why": "<plain words>"}`.

### `tamper_demo(book, n=None) -> dict`
Deep-copies the book, changes one value in one receipt's event (the amount if there is one), runs `verify` on the copy and returns the before/after values and the result. Never touches the real book.

### Command line
`python -m receipts.carbon verify path/to/book.json [--stamps path/to/stamps.json]` prints the result — *intact* with the count, or the first changed receipt in plain words — and exits 0 when intact, 1 when changed. When `--stamps` is given it loads the JSON list of the owner's phone stamps and passes them to `verify`.

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
- *Try to change one* calls `POST /api/carbon/tamper` and says in plain words what was changed in a copy ("We changed receipt #7 from $1,836.00 to $18.36 in a copy of the book"), then shows the red stamp naming that receipt.
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
