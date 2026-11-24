# Kiro run: the custom agent carbon-attacker, first run

## Instructions given

```text
kiro-cli chat --agent carbon-attacker --no-interactive --trust-all-tools

Attack the carbon-copy book as your instructions say. Start by checking whether the carbon-copy MCP tools are available to you and say so. Then try at least these, each as a scratch_attacks/attack_<name>.py test: re-sign a forged book under a new key and check it against the device's pinned key and stamps; cut the last receipts and re-sign the head; make the browser check (static/carbon_verify.js under node) and the Python check disagree on any book; make an honest book read changed. Report proven findings only, plus one line for each attack that was caught.
```

## What Kiro did and reported

```text
kiro-cli.exe : [INFO] [KRS] <-- GenerateAssistantResponseCommand done totalEvents=9
The carbon-copy MCP tools aren't available to me. The resource catalogue lists no tools, and I only have file, shell and code tools. I'll use the Python API and CLI instead. First I'll read the docs and the code.
[tool] List Directory
[tool] status: Failed: Invalid input for file_search — explanation: expected string, received undefined
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Read File
[tool] Read File
[tool] status: Completed
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Write File
[tool] status: Completed
[tool] Write File
[tool] status: Completed
[tool] Write File
[tool] status: Completed
[tool] Write File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
I found no way to forge a book that reads intact, and no way to hide a change under a pinned key plus stamps. I did prove four smaller flaws. All 13 tests pass, so each attack either behaved as described below or was caught.
**MCP tools:** the carbon-copy MCP tools are not available to me. I used the Python API, the CLI and node instead. I changed nothing outside `scratch_attacks/`. I used only throwaway in-memory keys and wrote no key to any file.
Reproduce everything with:
`.venv\Scripts\python.exe -m pytest scratch_attacks/attack_resign_newkey.py scratch_attacks/attack_cut_tail.py scratch_attacks/attack_disagree.py -q -s`
## Proven findings
**1. The browser check calls an honest book changed (false alarm).**
- **Test:** `attack_disagree.py::test_honest_book_with_huge_event_time_reads_changed_in_browser`.
- **What I did:** I wrote a book with `CarbonCopy.append("note", {"t": 1e21, ...})`, then ran both checks on it after a JSON round trip.
- **What the checks said:** Python said `intact`. The browser said `{'intact': False, 'first_bad': 1, 'why': 'its content was changed'}`.
- **Cause:** `at` is a float that does not go through `safe_json`. Python's `normalise` turns it into the integer `1000000000000000000000`. JavaScript writes it as `1e+21`, so the fingerprints differ.
- **Should have said:** intact in both.
- **Reach:** `Receipts.emit` overwrites `t` with `time.time()` (`receipts/core.py:45`), so the running app cannot produce this. It only happens when `append` is called directly.
**2. Python reads a malformed "receipts" field as an empty book, and the browser rejects it.**
- **Test:** `test_receipts_field_that_is_not_a_list_python_treats_as_empty`.
- **What I did:** I took a genuine empty signed book and set `"receipts"` to `{}`, `0`, `""` or `false`.
- **What the checks said:** Python said `intact (0 receipts)`. The browser said "this is not a carbon-copy book we can read".
- **Cause:** `book.get("receipts") or []` in Python lets any falsy value through as an empty list.
- **Should have said:** changed, as the browser does.
- **Limit:** the signed head must still say 0 and no stamp may be newer, so this cannot hide lost receipts.
**3. Fields outside the fingerprint can be added to a receipt, and both checks say intact.**
- **Test:** `test_extra_unsigned_fields_are_ignored_by_both`.
- **What I did:** I added `"approved_by": "maya"` and `"note": "Maya approved this by phone"` to a receipt, and `"verdict": "approved"` to the top level of the book.
- **What the checks said:** both said `intact (6 receipts)`, with the device's stamp and key in force.
- **Should have said:** changed, or the extra fields should be rejected. This is only harmful if some screen or export shows those fields.
- **Not checked:** I did not look at whether any screen does.
**4. The signature text can be altered and the book still reads intact.**
- **Test:** `test_signature_text_can_be_changed_and_still_reads_intact`.
- **What I did:** I changed the last base64 character of a receipt's `sig`. The 4 spare bits give 15 other encodings of the same signature.
- **What the checks said:** both said `intact` for all 15.
- **Should have said:** changed. `sig` is not covered by `fp`, so two files with different bytes pass as the same book.
**5. Different events get the same fingerprint (smaller; this is the documented cleaning).**
- **Test:** `test_event_values_that_collide`.
- **What I did:** I appended pairs of events through `append` and compared the fingerprints.
- **What the checks said:** these pairs match: `298.5` and `"298.5"`, `2**60` and `"1152921504606846976"`, `Decimal("5.10")` and `"5.10"`, and `NaN` and `"nan"`.
- **Consequence:** the book cannot show whether an amount was a number or a text.
**6. A bad public key with spaces: Python and browser disagree (needs no pinned key).**
- **Test:** `test_public_key_with_spaces_python_and_browser_disagree`.
- **What I did:** I put spaces between the hex pairs of the book's `public_key` and ran both checks with no key pinned, as the CLI does without `--key`.
- **What the checks said:** Python said `intact`. The browser said "its signature does not match".
- **Cause:** Python's `bytes.fromhex` ignores spaces. The browser's hex parser rejects them.
- **Should have said:** changed in both.
## Tried and caught
- **Re-sign under a new key:** a forged book with Maya's decline flipped to approved and re-signed under a new key was caught against the pinned key. It was also caught against stamps alone, because the stamp signatures fail. The browser agreed in both cases (`attack_resign_newkey.py`).
- **Rewrite under the real key:** a key holder who rewrites a receipt and re-links the whole chain was caught by the stamp ("receipt #6 no longer matches the stamp your device kept").
- **Cut the tail without re-signing the head:** caught as missing receipts.
- **Cut the tail and re-sign the head:** caught when the device holds a later stamp. Cutting to empty and re-signing was also caught.
- **Cut back to the last stamp:** a book cut back to exactly the last stamp, or one receipt past it, reads intact. This is the README's documented limit, so I do not count it as a finding.
I did not try reorder, duplicate, or replay of an older book beyond the stamp and cut cases above.
```
