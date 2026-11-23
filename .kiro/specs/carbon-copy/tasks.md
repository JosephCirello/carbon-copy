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
