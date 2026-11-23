# Tasks: the carbon-copy receipt book

- [x] 1. The book and the check (`receipts/carbon.py`)
  - [x] 1.1 `canonical()` and `fingerprint()` as in the design, with unit tests for key order and unicode
  - [x] 1.2 `Signer` with `from_env()`, `sign()`, `public_key_hex`; a test that no attribute or repr exposes the private key
  - [x] 1.3 `CarbonCopy.append()`, `receipts()`, `book()`; tests for numbering, the first `prev`, and that changing a returned copy does not change the book
  - [x] 1.4 `verify()` with all four failure reasons in plain words; one unit test per reason
  - _Requirements: 2, 3, 4, 5_

- [ ] 2. Property-based tests (`tests/test_carbon.py`, hypothesis)
  - [ ] 2.1 Any list of events gives an intact book
  - [ ] 2.2 Changing any one field of any one receipt is caught at that receipt
  - [ ] 2.3 Removing a receipt or swapping two is caught
  - _Requirements: 4_

- [ ] 3. `tamper_demo()` and the command-line checker (`python -m receipts.carbon verify <file>`)
  - _Requirements: 6.3, 7_

- [ ] 4. Wire the book into Receipts
  - [ ] 4.1 `Receipts(carbon=...)`; `emit()` appends every event
  - [ ] 4.2 Integration test: one scenario on the stand-in gives an intact book with one receipt per event
  - _Requirements: 1_

- [ ] 5. The app
  - [ ] 5.1 `GET /api/carbon`, `POST /api/carbon/verify`, `POST /api/carbon/tamper`, with tests
  - [ ] 5.2 The *Carbon copy* tab: the receipt list in plain words, *Check the book*, *Try to change one*, *Download the carbon copies*
  - [ ] 5.3 Receipt number and fingerprint columns in the accountant's download
  - _Requirements: 6_

- [ ] 6. README and Kiro write-up sections for Carbon Copy, disclosing the Receipts base
