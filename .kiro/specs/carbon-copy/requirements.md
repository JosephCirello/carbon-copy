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

### Requirement 7: the check runs anywhere

1. THE repository SHALL carry a command-line checker, `python -m receipts.carbon verify <book.json>`, that prints *intact* or the first changed receipt and exits 0 or 1.
2. THE command-line checker SHALL accept an optional list of the owner's phone stamps, `python -m receipts.carbon verify <book.json> --stamps <stamps.json>`, and apply the check in Requirement 8.

### Requirement 8: the owner's phone keeps the book's stamp

The signed count (the head) stops anyone quietly removing receipts from the end of the book, because the head still names a count the receipts no longer reach. But someone holding an *older* signed count can cut the book back to that older length and put the older count back, and the book still checks out: the receipts left still link up, and the older count matches them. The fix is a copy of the count kept outside the book, on the owner's phone.

1. WHEN the owner approves or declines a held payment THE SYSTEM SHALL hand the phone the book's signed head as it stands right after that tap is recorded.
2. THE check SHALL accept a list of such stamps and answer *changed*, with the reason "the book is shorter than a stamp the owner's phone already holds", if any stamp's count is greater than the book's receipts, or its last fingerprint is not the fingerprint of the receipt at that position.
3. THE check SHALL need only the receipts, the public key and the stamps; no secret.
