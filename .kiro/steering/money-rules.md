---
inclusion: always
---

# Rules that never bend

1. **No AI model decides a payment.** A model may propose; plain, deterministic code decides ALLOW, HOLD or BLOCK. Never add a code path where a model's output becomes a verdict.
2. **A carbon copy is never changed or deleted once written.** Code may only append. There is no update, edit or delete function for receipts, and no test may need one except a test that builds a tampered COPY to prove the check catches it.
3. **The check needs no secret.** Verifying the book uses only the receipts and the public key. The private signing key never leaves the server process.
4. **Keys never enter the repository.** The signing key comes from the `CARBON_COPY_KEY` environment variable or is generated in memory at start-up. Never write a key, a seed or a token to a file the repo tracks, a log line, a test fixture or an error message.
5. **Same input, same fingerprint.** Fingerprints are SHA-256 over canonical JSON (sorted keys, no spaces, UTF-8). Anything that makes the bytes depend on dict order, float formatting or the platform is a bug.
6. **No real money.** The demo runs on PayPal's sandbox or on the stand-in that mirrors PayPal's API shapes. Say which on every screen that shows a PayPal result.
7. **Do not change the Receipts measurement.** `receipts/measure.py`, `results/` and the scoring in `receipts/core.py` stay as imported; Carbon Copy records what happens, it does not change what Receipts decides.
