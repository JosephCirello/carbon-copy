"""Task 13: the note for an honest book after a local restart (words only; the verdict is untouched)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from receipts.carbon import RESTART_NOTE, CarbonCopy, Signer, restart_note, verify, WHY_KEY  # noqa: E402

A, B = "a" * 64, "b" * 64


def test_the_note_appears_for_a_temporary_key_that_changed():
    assert restart_note(B, A, True) == RESTART_NOTE
    assert restart_note(B.upper(), A, True) == RESTART_NOTE
    assert "Forget what this device trusts" in RESTART_NOTE and "hosted demo uses a fixed key" in RESTART_NOTE


def test_nothing_extra_for_a_fixed_key_or_a_matching_key_or_no_trusted_key():
    assert restart_note(B, A, False) is None
    assert restart_note(B, A, None) is None
    assert restart_note(A, A.upper(), True) is None
    assert restart_note(B, None, True) is None


def test_the_verdict_is_the_same_whatever_the_key_says():
    carbon = CarbonCopy(Signer(Ed25519PrivateKey.generate()))
    carbon.append("pay", {"amount": 1})
    out = verify(carbon.book(), None, A)
    assert out["intact"] is False and out["why"] == WHY_KEY


def test_the_key_endpoint_gives_the_value_the_note_reads(monkeypatch):
    from fastapi.testclient import TestClient
    import app as web
    for temporary in (True, False):
        monkeypatch.setattr(web, "SIGNER", Signer(Ed25519PrivateKey.generate(), temporary=temporary))
        got = TestClient(web.app).get("/api/carbon/key").json()
        assert got["temporary"] is temporary
        assert (restart_note(got["public_key"], A, got["temporary"]) is not None) is temporary


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on the path")
def test_the_page_function_gives_the_same_answers():
    script = f"""const v = require("./static/carbon_verify.js");
console.log(JSON.stringify([v.restartNote("{B}", "{A}", true), v.restartNote("{B}", "{A}", false),
  v.restartNote("{A}", "{A}", true), v.restartNote("{B}", null, true)]));"""
    got = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, encoding="utf-8", check=True, cwd=ROOT).stdout)
    assert got == [RESTART_NOTE, None, None, None]
