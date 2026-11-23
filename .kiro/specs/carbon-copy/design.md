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

A book handed out is `{"public_key": "<hex>", "receipts": [...]}`.

## Components

### `Signer`
- `Signer.from_env()` reads `CARBON_COPY_KEY` (64 hex characters, an Ed25519 seed) or generates a fresh key in memory.
- `sign(fp_hex) -> str` and `public_key_hex -> str`. No method returns the private key.

### `CarbonCopy`
- `__init__(signer)`
- `append(kind, event) -> dict` builds, fingerprints, signs and stores one receipt; returns a copy.
- `receipts() -> list[dict]` returns deep copies.
- `book() -> dict` returns the public key and the receipts.
- No update or delete method.

### `verify(book) -> dict`
Walks the receipts in order. For each: is `n` the next number; does `prev` equal the previous `fp`; does the recomputed fingerprint equal `fp`; does the signature verify against the public key. Stops at the first failure.
Returns `{"intact": true, "count": N}` or `{"intact": false, "count": N, "first_bad": n, "why": "<plain words>"}`.

### `tamper_demo(book, n=None) -> dict`
Deep-copies the book, changes one value in one receipt's event (the amount if there is one), runs `verify` on the copy and returns the before/after values and the result. Never touches the real book.

### Command line
`python -m receipts.carbon verify path/to/book.json` prints the result and exits 0 when intact, 1 when changed.

## Wiring

- `Receipts.__init__` takes an optional `carbon` argument; `emit()` appends every event to it before calling `on_event`.
- `app.py` keeps one `CarbonCopy` per demo run and adds:
  - `GET /api/carbon` → the book
  - `POST /api/carbon/verify` → `verify(body)`
  - `POST /api/carbon/tamper` → `tamper_demo(current book)`
- The book download for the accountant gains two columns, *Receipt #* and *Fingerprint*.

## The screen

A *Carbon copy* tab styled as a carbon-paper receipt book (a Halloween touch: faint blue carbon on dark paper, a wax seal when the book checks out, a torn seal when it does not). Each row: number, time, a plain sentence (*"Held: payout of $1,836.00 to Ashwood Timber, invoice INV-AT-1142. PayPal already shows a payment for it on its way."*), short fingerprint. Two buttons: *Check the book*, *Try to change one*. A *Download the carbon copies* link.

## Testing

- Unit tests for the canonical form, the first receipt, signing and each failure reason.
- Property-based tests (`hypothesis`): for any sequence of events, the untouched book is intact; changing any one field of any one receipt makes it *changed* at that receipt; deleting or swapping receipts is caught.
- An integration test running one Receipts scenario on the stand-in with the book attached: the book is intact and holds one receipt per emitted event.
