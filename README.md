# Carbon Copy

Category: (to be confirmed)

Maya runs a nine-person furniture workshop. Her AI agent pays supplier bills through PayPal. One morning it tries to pay the same $1,836.00 bill to Blue Ridge Finishes twice. The check stops the second payment and asks Maya. She declines it.

Weeks later the books are questioned. The log that says she declined lives in the same system the AI runs on, so whoever controls that system can edit it to say she approved the payment. Nothing she holds can show otherwise.

**Two parts, one name.** Carbon Copy is the whole product. Inside it, *the check* stops a bad payment before it reaches PayPal (it comes from Receipts, see below), and *the carbon copy* seals every move into a book nobody can quietly rewrite (this is new). On screen, the two sides of the demo are "Nothing checking" and "Carbon Copy on".

Carbon Copy is the old carbon-copy receipt book for that AI. Every money move the AI tries, every decision the checker makes, every tap Maya makes and the AI's end-of-day report get a copy at the moment they happen. Each copy carries the fingerprint of the copy before it and is signed, so one changed copy shows exactly where the book was altered. Anyone holding the copies and the public key can check them, with no secret needed.

## Try it

- Hosted demo: **https://carbon-copy-ywv3.onrender.com** (it runs on the PayPal stand-in: no real money, no PayPal account). It runs on an always-on plan, so there is no wake-up delay.
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

Open http://127.0.0.1:8091. The *Start here* strip on the Watch tab is the 30-second path: *Run Maya's day*, then *Decline the double payment on her phone*, then *Try to forge the record*. Or press *Run the day* yourself and open the *Carbon copy* tab. *Check the book* says INTACT. *Try to change one* alters a copy of the book so it says Maya approved a payment she declined, and the check stamps it CHANGED at that receipt. The real book is never touched.

Run the tests (no network, no keys): `.venv\Scripts\python.exe -m pytest -q`

Check a downloaded book from the command line: `.venv\Scripts\python.exe -m receipts.carbon verify book.json [--stamps stamps.json]`. It exits 0 when intact, 1 when changed and 2 when the file could not be read. `--key <64 hex characters>` names the public key to trust: a book signed with any other key is changed. The file works as it is whether it is a bare book or the file *Download the carbon copies* writes: for that file the command uses the stamps and the trusted key inside it, unless you give `--stamps` or `--key`, which win.

Every screen that shows a PayPal result says whether it came from the PayPal sandbox or the stand-in that mirrors PayPal's API shapes. `PAYPAL_MODE=standin` forces the stand-in (the hosted demo does this). The default, `auto`, uses the sandbox when you have sandbox keys.

## What came from Receipts and what is new

Carbon Copy is built on [Receipts](https://github.com/JosephCirello/receipts), our earlier open-source checker that sits between an AI agent and PayPal and checks PayPal's own records before money moves. Receipts was built from 2026-11-08 to 2026-11-11, inside the Kiroween period. The first commit here, `1d9b5fe`, imported Receipts unchanged from github.com/JosephCirello/receipts at `abc470c`. Everything after that commit is new:

- `receipts/carbon.py`: the book, the signer, the check and the change-one demo.
- `Receipts.emit()` appends every event to the book, and `approve()` and `decline()` hand the owner's phone a stamp. What Receipts decides did not change. `receipts/measure.py`, `receipts/rules.py` and `results/` are as imported.
- The *Carbon copy* tab, the server routes `/api/carbon`, `/api/carbon/key`, `/api/carbon/verify`, `/api/carbon/tamper` and `/api/carbon/forge`, the phone's stamp line, and the Receipt # and Fingerprint columns in the accountant's download.
- The command-line checker and the tests in `tests/test_carbon*.py`, including property tests with `hypothesis`.
- The renaming and the polish round (task 7 in the spec).
- Our own attacker's findings (task 11): a receipt seals `at_ms` (whole milliseconds), carries exactly its seven sealed keys, and its signatures and key have one written form; a book of the wrong shape is *changed*; the agent file loads in Kiro CLI's default headless engine.
- The review round (task 10): one name for each part, the *What Receipts measured* tab with its own label, the *Start here* strip, the live count of carbon copies, plain-word explanations, the tab bar, the Kiro configuration in `.kiro/settings/mcp.json` and `.kiro/agents/carbon-attacker.json`, and `python -m receipts.mcp_server`.

The Python package is still called `receipts` and the main class `Receipts`. The measurement of 19 AI models on 19 business days (November 2026) belongs to Receipts and is described in its repository. The *What Receipts measured* tab and the totals in *Her book* show it. The carbon copy itself is new and is not part of those numbers.

## How it works

- A receipt is exactly `{n, at_ms, kind, event, prev, fp, sig}`, and the check refuses a receipt that carries any other key. `at_ms` is the time as a whole number of milliseconds since the epoch. `fp` is SHA-256 over canonical JSON (sorted keys, no spaces, UTF-8) of the other fields. `sig` is an Ed25519 signature over the fingerprint, written as canonical base64 (the one spelling the signer wrote). A public key is exactly 64 lowercase hex characters. The check reads only `public_key`, `head` and `receipts`.
- `prev` is the previous receipt's `fp` (64 zeros for the first). The book is append-only: there is no update or delete function.
- The book also carries a signed count (the number of receipts and the last fingerprint). That catches receipts cut from the end.
- The owner's device keeps stamps: copies of the signed count, taken when she approves or declines and with every event it sees during a run. The first stamp also pins the public key (trust on first use). *Check the book* runs in the browser (`static/carbon_verify.js`, with the browser's own SHA-256 and Ed25519) against the book, the device's stamps and the device's key, never against what the server says.
- The signing key comes from `CARBON_COPY_KEY`: 64 hex characters are the Ed25519 seed, any other text is hashed with SHA-256 into one. With none set it is generated in memory at start-up and the page footer says it is temporary. It never leaves the server process and is never written to a file, log or error message. The public key is at `/api/carbon/key` and in the footer. Checking needs only the receipts, the public key and the stamps.
- `forge` demo: *Try to forge a new book* rebuilds the whole book with Maya's decline flipped to approved, re-signed with a brand-new key, and shows the browser's check rejecting it.

### Check the fingerprint yourself, with any JSON tool

Before a receipt is stored its event is cleaned into one form every JSON tool reproduces: lone surrogates in text and keys become U+FFFD; integers beyond 2^53 - 1 become their decimal text; whole floats in that range become integers; every other float (298.5, NaN, Infinity) becomes the text Python's `repr` gives; tuples become lists; any other type (Decimal, date, set, bytes) becomes `str(value)`. Then:

```python
payload = {"n": n, "at_ms": at_ms, "kind": kind, "event": event, "prev": prev}
text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
fp = hashlib.sha256(text.encode("utf-8")).hexdigest()
```

In a browser, `JSON.stringify` with keys sorted by Unicode code point (not UTF-16 unit) gives the same text. `sig` is the Ed25519 signature, in base64, over the 32 bytes of `fp`.
- No AI model decides a payment. A model may propose; plain code decides ALLOW, HOLD or BLOCK.

## How Kiro built it

Kiro wrote Carbon Copy from a spec, with the rules fixed in steering files and three hooks watching the work. Work went in task by task, one commit per task or pair of tasks. This section answers the questions the Kiroween rules ask.

- **Which Kiro surface, and why.** The Kiro CLI, headless. Each task in `tasks.md` was handed to it as one instruction, in order, with the spec and the steering files as its only source of truth. The reason: a task is a unit that can be run, tested and committed on its own, and no one has to sit in a chat for it.
- **Spec-driven, not vibe coding.** `.kiro/specs/carbon-copy/` holds `requirements.md` (11 requirements), `design.md` and `tasks.md` (tasks 1 to 11). Every task from 8 on began by writing its requirement and design into the spec, then building. The spec changed when gaps were found, six times (below).
- **Steering** (`.kiro/steering/`): `money-rules.md` (no model decides a payment; the book is append-only; checking needs no secret; keys never enter the repo; same input gives the same fingerprint; no real money; Receipts' measurement stays untouched), `product.md` (who Carbon Copy is for, and the plain-words rule for every screen) and `tech.md` (Python 3.13, FastAPI, plain HTML, JavaScript and CSS, Ed25519, the test commands, where new code and tests go). They apply to every task.
- **Hooks** (`.kiro/hooks/`):
  - *Run the tests when Python changes*: after each save of a `.py` file it runs the whole suite (`pytest -q -x`), so a broken check shows up at once.
  - *Keep the book append-only*: after each save of `receipts/carbon.py` it asks Kiro whether any code path now edits, reorders or deletes a receipt, or lets a model's output become a verdict, and to remove it if so.
  - *No keys in the repo*: after each save of any file it runs `tools/no_keys.py`, which fails when a file looks like it holds a private key, a seed or a provider token. It needs no keys and no network, and it runs after each save.
- **Property-based tests.** `tests/test_carbon.py` uses `hypothesis`: any list of events gives an intact book; changing any one field of any one receipt is caught at that receipt; removing any one receipt, cutting receipts off the end or swapping two is caught; any book survives a trip through the browser's `JSON.parse` and `JSON.stringify`. `tests/test_carbon_parity.py` runs the browser's check under `node` against the same books. The suite runs with no network and no keys.
- **MCP.** Two uses. The app mounts Receipts' own MCP server at `/mcp`: the same PayPal tool names as PayPal's server, with every money move checked first. Since task 10 that server also starts over stdio with `python -m receipts.mcp_server`, and `.kiro/settings/mcp.json` registers it as `carbon-copy`. Tasks 1 to 9 did not use MCP. Task 11 checked that Kiro really loads it, because the attacker reported "The carbon-copy MCP tools aren't available to me". With Kiro CLI 3.5.0 on Windows: the workspace file `.kiro/settings/mcp.json` is the right place and is read (`kiro-cli mcp list` shows `carbon-copy` under the default agent); the relative `.venv\Scripts\python.exe` works because Kiro starts the server from the workspace folder; the server connects in about three seconds and lists twelve tools. We found two reasons the attacker could still see none, and could not see inside its own session to say which one it hit. First, the agent file used only the newer `permissions` field, which Kiro CLI's default headless engine (`kiro-cli chat --no-interactive`) does not load ("Mode 'carbon-attacker' not found"); the file now also carries the older `allowedTools` and `toolsSettings`, and loads in both engines. Second, a one-shot headless run on the newer engine (`--agent-engine v3`) starts its first turn before the server has connected, so the tools appear a few seconds late; the attacker's prompt now says to look again before giving up. `tests/test_carbon_app.py` starts the server the way Kiro does, from the command and arguments in `mcp.json`.
- **Custom agent.** `.kiro/agents/carbon-attacker.json` is an agent whose whole job is to attack the book: forge it, rewrite it, hide a change, cause a false alarm, using `python -m receipts.carbon verify` and `pytest`, on copies only, and to report only what it proved. It may write only to `scratch_attacks/`, which git ignores. Its first run found five ways to hide a change or raise a false alarm, one documented limit of the cleaning, and the MCP problem above; task 11 fixed them, each with a test in `tests/`, and the agent's prompt now lists them as already fixed so its next run looks for new shapes. Its second run found seven more (the download the command line could not read, a traceback, a screen saying "went to PayPal" when PayPal refused, three disagreements between the browser and Python, a run header the seal did not cover, the device forgetting old runs, a stale copy read against a newer stamp); task 12 fixed them with tests, and the prompt now says every command it runs sets `PAYPAL_MODE=standin`.
- **Powers.** None were used. There is no power installed or referenced in this repository.
- **Not confirmed.** The shell patterns in the agent's permissions (and the older regex form beside them) have not been exercised in a recorded run; if they do not match on your machine, change that one line. A one-shot headless run of the attacker on the newer engine can still start before the MCP server has connected, as described above.
- **Session records:** docs/kiro-sessions/ (the build records the team will add).
- **Tasks**: 1 the book and the check; 2 property tests; 3 the change-one demo and command-line checker; 4 wiring into Receipts; 5 the app; 6 this README; 7 the polish round after a human click-through; 8 the Carbon copy tab shows the run Maya saw; 9 the check stops trusting the server, after two attack reviews; 10 what a judge trips on (a review against the Kiroween rules); 11 what our own attacker found.

The spec changed when gaps were found, six times:

1. **The signed count.** A hash chain cannot show that the last receipts were deleted, since every receipt left still links up. The book now carries a signed count and the check compares it to the receipts.
2. **The phone's stamp.** A book can be cut back to an older length with its older signed count put back. The owner's phone now keeps a stamp outside the book, and a book shorter than a stamp is reported as changed.
3. **The browser round-trip rule.** A false alarm: a book that went through a browser failed its own check, because a browser writes 1836.0 as 1836 and the bytes changed. Whole-number floats are now normalised before hashing, so a book that passes through `JSON.parse` and `JSON.stringify` still checks out.
4. **The check trusted the server.** Two attack reviews re-signed a book under a new key and flipped Maya's decline to approved, and it read intact; the stamps lived on the server; "Check the book" asked the server. Requirement 9 and task 9 moved the stamps and the key to the owner's device, moved the check into the browser, made the fingerprint reproducible with any JSON tool and made every stamp's signature count.
5. **The screen said more than the data meant.** A review against the Kiroween rules found labels that claimed too much: "SAID: NO / SUSPICIOUS" on an AI's honest explanation (the word pattern only finds a refusal, never a suspicion), "(held)" on a receipt about the AI's words, and "Honest work done: 1 of 1" read as "nothing went wrong" after a bill was paid twice (it counts only the bills that were right to pay; the double payment is counted apart). Requirement 10 fixed the wording and left the scoring as it was. `design.md` has what was found.
6. **Our own attacker found six things.** The custom agent attacked the book. A receipt's time was not cleaned like the event (1e21 gave a false alarm in the browser); a `receipts` field that was not a list read as an empty book in Python; extra fields beside a receipt's seal ("approved_by") were ignored by both checks; a signature could be spelled 16 ways; a key with spaces passed in Python only; and the agent's MCP tools did not load. Requirement 11 and task 11 fixed them. Books written before task 11 carry `at` (seconds) and are not readable any more. `design.md` has the reasoning.
## Limits we know about

- The stand-in mirrors PayPal's API shapes. It is not PayPal. The hosted demo uses it, so no real or sandbox PayPal order is created there.
- **The device has to have seen the key first.** The check trusts the key the device pinned from the first stamp it received (trust on first use). A device that has never seen the book has nothing to hold a forgery up against, and a first visit to a forged copy would pin the forger's key. A server restart without `CARBON_COPY_KEY` makes a new temporary key, and the device then rightly refuses the new books until it is told to forget the old key.
- **Anything after the last stamp the device saw can still be rewritten by whoever holds the key.** Stamps cover every moment the device was watching, not the time it was closed. A book cut back or rewritten beyond the device's last stamp is not caught by that device.
- **The check proves the book was not changed, not that what was written was true.** If the AI said it paid a bill and the book records that, the check shows the record is as written. It cannot show the payment happened. For that, Receipts compares the AI's report with PayPal's own records.
- **The device forgets old runs.** It keeps the stamps of the last 100 runs. Once a run's stamps have been dropped to make room for newer runs, a rewrite of that run by whoever holds the key reads intact. The screen says "This device kept no stamp for this run" right under the verdict when that is so; download a run's carbon copies if you want to keep it checkable. (The server keeps only the last 40 runs of a visit.)
- A book cut back to an OLDER signed count is caught only when the owner's device holds a later stamp.
- Browsers without Ed25519 in WebCrypto fall back to the server's check, with the device's stamps and key. The screen says so.
- Amounts that are not whole numbers are sealed as text, so the book shows the value, not whether the AI wrote it as a number or as text.
- Books written before task 11 (receipts with `at` in seconds) are not readable by the new check; it says they were changed.
- Carbon Copy records what Receipts decides. It does not change it.

License: MIT.

---

### Potestas AI

**[Potestas AI](https://potestasai.com)** tests what AI agents do, not what they say, and publishes the evidence.

- **Putting an AI agent in front of money, patients or customers?** [See the screening](https://potestasai.com/screening) or [book a 30-minute call](https://calendly.com/joseph-cirello-potestasai).
- **Free book:** [Your AI Is Safe. Says Who?](https://potestasai.com/book)
- **What we find, as we find it:** [potestasai.com/findings](https://potestasai.com/findings)
