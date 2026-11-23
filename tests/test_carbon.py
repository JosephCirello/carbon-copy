"""Unit tests for the carbon-copy receipt book (task 1: the book and the check).

No network, no keys on disk: every signer used here is generated in memory, and
the one test that exercises ``CARBON_COPY_KEY`` sets a freshly generated seed
through ``monkeypatch`` so no key is ever written to the repo.
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from receipts.carbon import (  # noqa: E402
    GENESIS,
    CarbonCopy,
    Signer,
    canonical,
    fingerprint,
    verify,
)


def _signer() -> Signer:
    """A fresh in-memory signer; never reads or writes the environment."""
    return Signer(Ed25519PrivateKey.generate())


def _book(*pairs) -> dict:
    """Build a book from ``(kind, event)`` pairs with one fresh in-memory signer."""
    carbon = CarbonCopy(_signer())
    for kind, event in pairs:
        carbon.append(kind, event)
    return carbon.book()


# Three events shaped like the ones Receipts emits; each carries its own ``t`` so
# the receipts' times are fixed and the tests are reproducible.
E1 = {"t": 1795462000.001, "type": "verdict", "tool": "create_payout", "decision": "HOLD",
      "amount": 1836.00, "invoice_number": "INV-BR-1197", "vendor": "Blue Ridge Finishes"}
E2 = {"t": 1795462000.002, "type": "paypal", "tool": "list_transactions",
      "backend": "stand-in", "result": {"total_items": 1}}
E3 = {"t": 1795462000.003, "type": "owner", "action": "approved", "hold_id": "abc12345"}


# ---- 1.1 canonical() and fingerprint() ------------------------------------------------------

def test_fingerprint_is_independent_of_key_order():
    a = fingerprint({"n": 1, "at": 1.5, "kind": "verdict", "event": {"b": 2, "a": 1}, "prev": "0" * 64})
    b = fingerprint({"prev": "0" * 64, "event": {"a": 1, "b": 2}, "kind": "verdict", "at": 1.5, "n": 1})
    assert a == b
    assert len(a) == 64


def test_canonical_sorts_keys_drops_spaces_and_keeps_unicode_as_utf8():
    assert canonical({"b": 1, "a": "café"}) == b'{"a":"caf\xc3\xa9","b":1}'
    # no \u escapes: the é is its own UTF-8 bytes, not \u00e9
    assert b"\\u" not in canonical({"k": "café"})


def test_fingerprint_is_stable_under_unicode_and_amounts():
    a = fingerprint({"k": "café", "v": "¥1,836.00", "emoji": "🪵"})
    b = fingerprint({"v": "¥1,836.00", "k": "café", "emoji": "🪵"})
    assert a == b


# ---- 1.2 Signer -----------------------------------------------------------------------------

def test_signer_uses_the_env_seed_when_set(monkeypatch):
    sk = Ed25519PrivateKey.generate()
    seed = sk.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    monkeypatch.setenv("CARBON_COPY_KEY", seed.hex())
    signer = Signer.from_env()
    expected_pub = sk.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    ).hex()
    assert signer.public_key_hex == expected_pub   # it signed with the env key, not a random one


def test_signer_generates_a_fresh_key_when_no_env(monkeypatch):
    monkeypatch.delenv("CARBON_COPY_KEY", raising=False)
    a = Signer.from_env()
    b = Signer.from_env()
    assert len(a.public_key_hex) == 64
    assert a.public_key_hex != b.public_key_hex   # two fresh random keys differ


def test_signer_hides_the_private_key(monkeypatch):
    sk = Ed25519PrivateKey.generate()
    seed = sk.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    monkeypatch.setenv("CARBON_COPY_KEY", seed.hex())
    signer = Signer.from_env()
    # gather everything reachable from the signer: its repr and every attribute's repr
    exposed = [repr(signer)]
    for name in dir(signer):
        try:
            exposed.append(repr(getattr(signer, name)))
        except Exception:
            pass
    text = "\n".join(exposed)
    assert seed.hex() not in text                       # the private seed never appears
    assert signer.public_key_hex != seed.hex()          # the public key is not the seed
    sig = signer.sign("00" * 32)                         # but signing still works
    assert isinstance(sig, str) and base64.b64decode(sig)  # and returns valid base64


# ---- 1.3 CarbonCopy.append / receipts / book ------------------------------------------------

def test_receipts_are_numbered_from_one_in_order():
    carbon = CarbonCopy(_signer())
    for i in range(3):
        carbon.append("verdict", {"t": 1795462000.001 + i, "x": i})
    assert [r["n"] for r in carbon.receipts()] == [1, 2, 3]


def test_first_receipt_links_to_zeros_and_each_later_one_to_the_previous_fingerprint():
    carbon = CarbonCopy(_signer())
    carbon.append("verdict", E1)
    carbon.append("paypal", E2)
    recs = carbon.receipts()
    assert recs[0]["prev"] == GENESIS == "0" * 64
    assert recs[1]["prev"] == recs[0]["fp"]


def test_append_strips_the_events_own_t_and_rounds_its_time_to_milliseconds():
    carbon = CarbonCopy(_signer())
    carbon.append("verdict", {"t": 1795462000.123456, "x": 1})
    rec = carbon.receipts()[0]
    assert "t" not in rec["event"]          # the event's own t is gone
    assert rec["at"] == 1795462000.123       # rounded to milliseconds
    assert rec["event"]["x"] == 1


def test_book_carries_the_public_key_and_the_receipts():
    carbon = CarbonCopy(_signer())
    carbon.append("verdict", E1)
    bk = carbon.book()
    assert set(bk.keys()) == {"public_key", "receipts"}
    assert len(bk["public_key"]) == 64
    assert len(bk["receipts"]) == 1


def test_changing_a_returned_copy_does_not_change_the_book():
    carbon = CarbonCopy(_signer())
    original_event = {"t": 1795462000.001, "amount": 100.0, "note": "first"}
    returned = carbon.append("verdict", original_event)

    # mutate the copy that append() handed back
    returned["event"]["amount"] = 999.0
    returned["n"] = 99
    returned["fp"] = "tampered"
    assert carbon.receipts()[0]["event"]["amount"] == 100.0
    assert carbon.receipts()[0]["n"] == 1
    assert carbon.receipts()[0]["fp"] != "tampered"

    # mutate the event the caller passed in, after the append
    original_event["amount"] = 888.0
    original_event["note"] = "changed-after"
    assert carbon.receipts()[0]["event"]["amount"] == 100.0
    assert carbon.receipts()[0]["event"]["note"] == "first"

    # mutate a snapshot from receipts()
    snap = carbon.receipts()
    snap[0]["event"]["amount"] = -1.0
    snap[0]["sig"] = "gone"
    assert carbon.receipts()[0]["event"]["amount"] == 100.0
    assert carbon.receipts()[0]["sig"] != "gone"

    # mutate a snapshot from book()
    bk = carbon.book()
    bk["receipts"][0]["event"]["amount"] = -2.0
    bk["public_key"] = "tampered"
    assert carbon.book()["receipts"][0]["event"]["amount"] == 100.0
    assert carbon.book()["public_key"] != "tampered"


# ---- 1.4 verify() ---------------------------------------------------------------------------

def test_verify_an_untouched_book_is_intact():
    book = _book(("verdict", E1), ("paypal", E2), ("owner", E3))
    assert verify(book) == {"intact": True, "count": 3}


def test_verify_survives_a_json_round_trip():
    # the stored and hashed times must stay the same number through JSON, on any machine
    book = _book(("verdict", E1), ("paypal", E2), ("owner", E3))
    roundtripped = json.loads(json.dumps(book))
    assert verify(roundtripped) == {"intact": True, "count": 3}


def test_verify_catches_a_receipt_whose_content_was_changed():
    book = _book(("verdict", E1), ("paypal", E2), ("owner", E3))
    book["receipts"][1]["event"]["tool"] = "create_refund"   # receipt 2's content no longer matches its fp
    out = verify(book)
    assert out["intact"] is False
    assert out["first_bad"] == 2
    assert out["why"] == "its content was changed"


def test_verify_catches_a_receipt_whose_link_to_the_previous_is_broken():
    book = _book(("verdict", E1), ("paypal", E2), ("owner", E3))
    book["receipts"][1]["prev"] = "f" * 64   # receipt 2 no longer links to receipt 1's fingerprint
    out = verify(book)
    assert out["intact"] is False
    assert out["first_bad"] == 2
    assert out["why"] == "its link to the receipt before was broken"


def test_verify_catches_a_receipt_whose_signature_does_not_match():
    book = _book(("verdict", E1), ("paypal", E2), ("owner", E3))
    # a real signature, but made with a different key -> valid base64, never verifies
    other = _signer()
    book["receipts"][1]["sig"] = other.sign(book["receipts"][1]["fp"])
    out = verify(book)
    assert out["intact"] is False
    assert out["first_bad"] == 2
    assert out["why"] == "its signature does not match"


def test_verify_catches_a_receipt_that_is_missing():
    book = _book(("verdict", E1), ("paypal", E2), ("owner", E3))
    del book["receipts"][1]   # remove receipt 2 (not the last), so the numbering gaps
    out = verify(book)
    assert out["intact"] is False
    assert out["first_bad"] == 2
    assert out["why"] == "a receipt is missing"


def test_verify_points_at_the_first_receipt_that_fails():
    book = _book(("verdict", E1), ("paypal", E2), ("owner", E3))
    # break receipt 3 only; receipts 1 and 2 are fine, so the first bad one is 3
    book["receipts"][2]["event"]["action"] = "declined"
    out = verify(book)
    assert out["intact"] is False
    assert out["first_bad"] == 3
