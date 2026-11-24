# Carbon Copy

Maya runs a nine-person furniture workshop. Her AI agent pays supplier bills through PayPal. One morning it tries to pay the same $1,836.00 bill to Blue Ridge Finishes twice. The check stops the second payment and asks Maya. She declines it.

Weeks later the books are questioned. The log that says she declined lives in the same system the AI runs on, so whoever controls that system can edit it to say she approved the payment. Nothing she holds can show otherwise.

Carbon Copy is the old carbon-copy receipt book for that AI. Every money move the AI tries, every decision the checker makes, every tap Maya makes and the AI's end-of-day report get a copy at the moment they happen. Each copy carries the fingerprint of the copy before it and is signed, so one changed copy shows exactly where the book was altered. Anyone holding the copies and the public key can check them, with no secret needed.

## Try it

- Hosted demo: **https://carbon-copy-ywv3.onrender.com** (it runs on the PayPal stand-in: no real money, no PayPal account). On Render's free plan the first visit after a quiet spell can take about a minute to wake.
- On your machine, no keys needed:

Windows (PowerShell):

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8091
```

macOS or Linux:

```
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8091
```

Open http://127.0.0.1:8091, press *Run the day* on the Watch tab, then open the *Carbon copy* tab. *Check the book* says INTACT. *Try to change one* alters a copy of the book so it says Maya approved a payment she declined, and the check stamps it CHANGED at that receipt. The real book is never touched.

Run the tests (no network, no keys): `.venv\Scripts\python.exe -m pytest -q`

Check a downloaded book from the command line: `.venv\Scripts\python.exe -m receipts.carbon verify book.json [--stamps stamps.json]`. It exits 0 when intact, 1 when changed and 2 when the file could not be read. `--key <64 hex characters>` names the public key to trust: a book signed with any other key is changed.

Every screen that shows a PayPal result says whether it came from the PayPal sandbox or the stand-in that mirrors PayPal's API shapes. `PAYPAL_MODE=standin` forces the stand-in (the hosted demo does this). The default, `auto`, uses the sandbox when you have sandbox keys.

## What came from Receipts and what is new

Carbon Copy is built on [Receipts](https://github.com/JosephCirello/receipts), our earlier open-source checker that sits between an AI agent and PayPal and checks PayPal's own records before money moves. Receipts was built from 2026-11-08 to 2026-11-11, inside the Kiroween period. The first commit here, `1d9b5fe`, imported Receipts unchanged from github.com/JosephCirello/receipts at `abc470c`. Everything after that commit is new:

- `receipts/carbon.py`: the book, the signer, the check and the change-one demo.
- `Receipts.emit()` appends every event to the book, and `approve()` and `decline()` hand the owner's phone a stamp. What Receipts decides did not change. `receipts/measure.py`, `receipts/rules.py` and `results/` are as imported.
- The *Carbon copy* tab, the server routes `/api/carbon`, `/api/carbon/key`, `/api/carbon/verify`, `/api/carbon/tamper` and `/api/carbon/forge`, the phone's stamp line, and the Receipt # and Fingerprint columns in the accountant's download.
- The command-line checker and the tests in `tests/test_carbon*.py`, including property tests with `hypothesis`.
- The renaming and the polish round (task 7 in the spec).

The Python package is still called `receipts` and the main class `Receipts`. The measurement of 19 AI models on 19 business days belongs to Receipts and is described in its repository.

## How it works

- A receipt is `{n, at, kind, event, prev, fp, sig}`. `fp` is SHA-256 over canonical JSON (sorted keys, no spaces, UTF-8) of the other fields. `sig` is an Ed25519 signature over the fingerprint.
- `prev` is the previous receipt's `fp` (64 zeros for the first). The book is append-only: there is no update or delete function.
- The book also carries a signed count (the number of receipts and the last fingerprint). That catches receipts cut from the end.
- The owner's device keeps stamps: copies of the signed count, taken when she approves or declines and with every event it sees during a run. The first stamp also pins the public key (trust on first use). *Check the book* runs in the browser (`static/carbon_verify.js`, with the browser's own SHA-256 and Ed25519) against the book, the device's stamps and the device's key, never against what the server says.
- The signing key comes from `CARBON_COPY_KEY`: 64 hex characters are the Ed25519 seed, any other text is hashed with SHA-256 into one. With none set it is generated in memory at start-up and the page footer says it is temporary. It never leaves the server process and is never written to a file, log or error message. The public key is at `/api/carbon/key` and in the footer. Checking needs only the receipts, the public key and the stamps.
- `forge` demo: *Try to forge a new book* rebuilds the whole book with Maya's decline flipped to approved, re-signed with a brand-new key, and shows the browser's check rejecting it.

### Check the fingerprint yourself, with any JSON tool

Before a receipt is stored its event is cleaned into one form every JSON tool reproduces: lone surrogates in text and keys become U+FFFD; integers beyond 2^53 - 1 become their decimal text; whole floats in that range become integers; every other float (298.5, NaN, Infinity) becomes the text Python's `repr` gives; tuples become lists; any other type (Decimal, date, set, bytes) becomes `str(value)`. Then:

```python
payload = {"n": n, "at": at, "kind": kind, "event": event, "prev": prev}
text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
fp = hashlib.sha256(text.encode("utf-8")).hexdigest()
```

In a browser, `JSON.stringify` with keys sorted by Unicode code point (not UTF-16 unit) gives the same text. `sig` is the Ed25519 signature, in base64, over the 32 bytes of `fp`.
- No AI model decides a payment. A model may propose; plain code decides ALLOW, HOLD or BLOCK.

## How Kiro built it

Kiro wrote Carbon Copy from a spec, with the rules fixed in steering files and two hooks watching the work. Work went in task by task, one commit per task or pair of tasks.

- **Spec** (`.kiro/specs/carbon-copy/`): `requirements.md` (9 requirements), `design.md` and `tasks.md` (tasks 1 to 9).
- **Steering** (`.kiro/steering/`): `money-rules.md` (no model decides a payment; the book is append-only; checking needs no secret; keys never enter the repo; same input gives the same fingerprint; no real money; Receipts' measurement stays untouched), `product.md` (who Carbon Copy is for and the plain-words rule for every screen) and `tech.md` (Python 3.13, FastAPI, plain HTML, JavaScript and CSS, Ed25519, the test commands).
- **Hooks** (`.kiro/hooks/`):
  - *Run the tests when Python changes*: each time a `.py` file is saved it runs the whole suite, so a broken check shows up at once.
  - *Keep the book append-only*: each time `receipts/carbon.py` is saved it asks Kiro whether any code path now edits, reorders or deletes a receipt, or lets a model's output become a verdict, and to remove it if so.
  - *No keys in the repo*: each time a file is saved it runs `tools/no_keys.py`, which refuses a file that looks like it holds a private key or seed.
- **Tasks**: 1 the book and the check; 2 property tests; 3 the change-one demo and command-line checker; 4 wiring into Receipts; 5 the app; 6 this README; 7 the polish round after a human click-through; 9 the check stops trusting the server, after two attack reviews.

The spec changed when gaps were found, four times:

1. **The signed count.** A hash chain cannot show that the last receipts were deleted, since every receipt left still links up. The book now carries a signed count and the check compares it to the receipts.
2. **The phone's stamp.** A book can be cut back to an older length with its older signed count put back. The owner's phone now keeps a stamp outside the book, and a book shorter than a stamp is reported as changed.
3. **The browser round-trip rule.** A false alarm: a book that went through a browser failed its own check, because a browser writes 1836.0 as 1836 and the bytes changed. Whole-number floats are now normalised before hashing, so a book that passes through `JSON.parse` and `JSON.stringify` still checks out.
4. **The check trusted the server.** Two attack reviews re-signed a book under a new key and flipped Maya's decline to approved, and it read intact; the stamps lived on the server; "Check the book" asked the server. Requirement 9 and task 9 moved the stamps and the key to the owner's device, moved the check into the browser, made the fingerprint reproducible with any JSON tool and made every stamp's signature count.

## Limits we know about

- The stand-in mirrors PayPal's API shapes. It is not PayPal. The hosted demo uses it, so no real or sandbox PayPal order is created there.
- **The device has to have seen the key first.** The check trusts the key the device pinned from the first stamp it received (trust on first use). A device that has never seen the book has nothing to hold a forgery up against, and a first visit to a forged copy would pin the forger's key. A server restart without `CARBON_COPY_KEY` makes a new temporary key, and the device then rightly refuses the new books until it is told to forget the old key.
- **Anything after the last stamp the device saw can still be rewritten by whoever holds the key.** Stamps cover every moment the device was watching, not the time it was closed. A book cut back or rewritten beyond the device's last stamp is not caught by that device.
- **The check proves the book was not changed, not that what was written was true.** If the AI said it paid a bill and the book records that, the check shows the record is as written. It cannot show the payment happened. For that, Receipts compares the AI's report with PayPal's own records.
- A book cut back to an OLDER signed count is caught only when the owner's device holds a later stamp.
- Browsers without Ed25519 in WebCrypto fall back to the server's check, with the device's stamps and key. The screen says so.
- Carbon Copy records what Receipts decides. It does not change it.

License: MIT.

---

### Potestas AI

**[Potestas AI](https://potestasai.com)** tests what AI agents do, not what they say, and publishes the evidence.

- **Putting an AI agent in front of money, patients or customers?** [See the screening](https://potestasai.com/screening) or [book a 30-minute call](https://calendly.com/joseph-cirello-potestasai).
- **Free book:** [Your AI Is Safe. Says Who?](https://potestasai.com/book)
- **What we find, as we find it:** [potestasai.com/findings](https://potestasai.com/findings)
