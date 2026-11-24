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

- [ ] 7. Polish round from a human click-through
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
