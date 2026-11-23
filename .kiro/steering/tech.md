---
inclusion: always
---

# Tech

- Python 3.13, FastAPI, Uvicorn. Front end is plain HTML, CSS and JavaScript in `static/` (no build step) with AG Grid from a CDN.
- Crypto: the `cryptography` package, Ed25519 for signatures, `hashlib.sha256` for fingerprints.
- Tests: `pytest`, plus `hypothesis` for property-based tests. Tests run with no network and no keys: `.venv\Scripts\python.exe -m pytest -q`.
- Run the app: `.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8091`.
- New code for Carbon Copy goes in `receipts/carbon.py`, its tests in `tests/test_carbon.py`. Keep functions small and pure where possible so the property tests can reach them.
- Windows is the development machine: use `pathlib`, never hard-coded `/` paths, and open files with an explicit `encoding="utf-8"`.
