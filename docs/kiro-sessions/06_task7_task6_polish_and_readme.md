# Kiro run: task 7 and task 6 (polish, README)

## Instructions given

```text
Polish round, from a human click-through of the running app. Update design.md and tasks.md first (add these as task 7 with sub-tasks), then build. Keep every existing test passing; add tests where a behaviour changes.

7.1 NAME. The product is Carbon Copy. Everywhere a visitor reads it (page title, header wordmark, the phone's app name and notification header, empty states, the JSON download's filename), say "Carbon Copy" instead of "Receipts". Keep the Receipts name only where the README and code describe the base it is built on, and in Python module and class names (do not rename receipts/ or the Receipts class). The header logo image belongs to Receipts: replace it with the words "Carbon Copy" set in the Special Elite typewriter face. No drawn pictures, no SVG objects.

7.2 THE CHANGE-ONE DEMO TELLS THE REAL LIE. tamper_demo() should, when the book holds an owner action, change THAT receipt: an owner "declined" becomes "approved". That is the exact lie the product exists to catch: a record edited afterwards to say the owner approved a payment she declined. The screen then reads, in plain words: "We changed receipt #N in a copy of the book so it says Maya APPROVED the $1,836.00 payment to Blue Ridge Finishes. She declined it." (use the real amount and payee from the hold the action answers), then the red stamp. If the book has no owner action, fall back to the current amount change, worded with the real before and after values. Tests for both paths; the real book must stay intact after either.

7.3 NO SIDEWAYS SCROLL. At 800 pixels wide the Carbon copy tab's text runs off the right edge (the source line and the change-one sentence are cut) and the header badge is clipped. At every width from 375 to 1400 pixels, document.documentElement.scrollWidth must equal window.innerWidth on every tab. Long words and fingerprints wrap or break; the tab bar may scroll inside itself but the page may not.

7.4 THE HOSTED DEMO USES THE STAND-IN. In render.yaml set PAYPAL_MODE=standin for the service, and make the header badge and the Carbon copy source line say "PayPal stand-in (no real money, no PayPal account)". Locally PAYPAL_MODE=auto keeps working as before.

THEN task 6 from tasks.md: README.md rewritten for Carbon Copy, plain words first. Open with one person and one loss: Maya's AI agent tries to pay a $1,836.00 bill twice; afterwards, the record could be edited to say she approved it. Then what Carbon Copy does in three sentences, then "Try it" (the hosted demo link placeholder, the run commands with no keys), then "What came from Receipts and what is new" (the first commit 1d9b5fe imported Receipts unchanged from github.com/JosephCirello/receipts, built 2026-11-08 to 11-11 inside the Kiroween period; everything after it is new), then "How Kiro built it" (which spec, steering files, hooks and tasks exist, what each hook did during the build, how the spec changed twice when gaps were found: the signed count, the phone's stamp, and the browser round-trip rule after a false alarm), then "Limits we know about" (the stand-in mirrors PayPal's API shapes; the book proves nothing was changed after it was written, not that what was written was true; a book cut back to an OLDER signed count is caught only when the owner's phone holds a later stamp), then the Potestas footer that is already at the bottom of the current README. No Claude co-author lines anywhere.

Follow every steering file. Run .venv\Scripts\python.exe -m pytest -q until everything passes. Do not touch receipts/measure.py, receipts/rules.py or results/.
```

## What Kiro did and reported

```text
kiro-cli.exe : [INFO] [KRS] <-- GenerateAssistantResponseCommand done totalEvents=10
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
Now the rename edits.
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
The first script fell back to msedge; do the same here.
[tool] Run Command
[tool] status: Completed
[tool] Read File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] status: Failed
[tool] Run Command
[tool] status: Completed
[tool] Write File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
Tasks 7.1 to 7.4 and the README (task 6) are done, and all 154 tests pass. I haven't committed anything. `design.md` and `tasks.md` were updated before the code.
I did check the running app in Edge. There was no sideways scroll on any of the six tabs at the 12 widths I tried, from 375 to 1400 pixels. I could not click through an owner decline in the browser, because the replay I tried had no held payment to decline. The "declined becomes approved" sentence is covered only by the new unit tests, not seen on screen.
- **7.1 Name:** Every visitor-facing "Receipts" now says "Carbon Copy". That covers the page title, the phone's app name and notification header, the empty states, the ledger's run labels ("Carbon Copy ON/OFF") and the ledger CSV filename. The JSON download was already `carbon_copies_*.json`. The header logo is now the words "Carbon Copy" in Special Elite, with no drawn picture. The old SVG logo is gone from the page and from the phone card, and I deleted `static/favicon.svg` since it was the Receipts logo. The favicon link is now an empty `data:,`, so the tab shows no icon. I did not rename `receipts/`, the `Receipts` class or data fields like `receipts_off`.
- **7.2 Change-one demo:** When the book holds an owner action, `tamper_demo()` changes that receipt. It prefers the latest "declined" and turns it into "approved". It returns a plain-words `say` sentence, which the screen shows before the red stamp, for example: "We changed receipt #2 in a copy of the book so it says Maya APPROVED the $1,836.00 payment to Blue Ridge Finishes. She declined it." The amount and payee come from the hold that action answers. If the book only has "approved" actions, it flips one to "declined" and says so. With no owner action it falls back to the amount change, worded with the real before and after values. The real book stays intact on every path, and new tests cover both.
- **7.3 No sideways scroll:** Long words and fingerprints now wrap, the header wraps, and only the tab bar scrolls inside itself.
- **7.4 Hosted demo:** `render.yaml` already had `PAYPAL_MODE=standin`, so I left it, and a test now checks it stays. The header badge now reads "PayPal stand-in (no real money, no PayPal account)". The Carbon copy source line already said this, so it is unchanged. Locally `auto` works as before.
- **README:** Rewritten in the order you gave, ending with the Potestas footer copied unchanged. The hosted demo link is a placeholder. There are no co-author lines.
- **Hook descriptions:** I have no log of what the hooks did during the build. The README says what each hook is set to do, not what it caught.
- **Spec changes:** You said the spec changed twice, then listed three gaps (signed count, phone's stamp, browser round-trip rule). The README says three times.
- **Task 6:** I ticked it in `tasks.md`.
```
