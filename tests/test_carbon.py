"""Unit tests for the carbon-copy receipt book (task 1: the book and the check).

No network, no keys on disk: every signer used here is generated in memory, and
the one test that exercises ``CARBON_COPY_KEY`` sets a freshly generated seed
through ``monkeypatch`` so no key is ever written to the repo.
"""
from __future__ import annotations

import base64
import json
import string
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hypothesis import assume, given, settings  # noqa: E402
import hypothesis.strategies as st  # noqa: E402

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from receipts.carbon import (  # noqa: E402
    GENESIS,
    CarbonCopy,
    Signer,
    canonical,
    fingerprint,
    tamper_demo,
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


def test_book_carries_the_public_key_signed_head_and_receipts():
    carbon = CarbonCopy(_signer())
    carbon.append("verdict", E1)
    bk = carbon.book()
    assert set(bk.keys()) == {"public_key", "head", "receipts"}
    assert len(bk["public_key"]) == 64
    assert len(bk["receipts"]) == 1
    # the signed head: a count, the last receipt's fingerprint, and a signature over them
    head = bk["head"]
    assert set(head.keys()) == {"count", "last_fp", "sig"}
    assert head["count"] == 1
    assert head["last_fp"] == bk["receipts"][0]["fp"]


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


# ---- 1.5 the signed head: catching receipts removed from the end ----------------------------
# A hash chain alone cannot show when the last receipt (or the last several) is
# deleted, because every receipt left still links up. The book now carries a signed
# count (the head); verify checks it after the receipts.

def test_the_head_counts_the_receipts_and_names_the_last_fingerprint():
    carbon = CarbonCopy(_signer())
    carbon.append("verdict", E1)
    carbon.append("paypal", E2)
    carbon.append("owner", E3)
    head = carbon.book()["head"]
    recs = carbon.receipts()
    assert head["count"] == 3
    assert head["last_fp"] == recs[-1]["fp"]            # the last receipt's fingerprint


def test_an_empty_book_has_a_head_counting_zero_and_linking_to_zeros():
    carbon = CarbonCopy(_signer())
    head = carbon.book()["head"]
    assert head["count"] == 0
    assert head["last_fp"] == GENESIS == "0" * 64         # no last receipt


def test_verify_catches_the_last_receipt_removed():
    book = _book(("verdict", E1), ("paypal", E2), ("owner", E3))
    del book["receipts"][2]   # remove the last receipt; the two left still link up
    out = verify(book)
    assert out["intact"] is False
    assert out["why"] == "receipts are missing from the end of the book"
    assert out["first_bad"] == 3                          # the head promised three


def test_verify_catches_the_last_several_receipts_removed():
    book = _book(("verdict", E1), ("paypal", E2), ("owner", E3))
    del book["receipts"][1:]   # remove receipts 2 and 3; receipt 1 still links to genesis
    out = verify(book)
    assert out["intact"] is False
    assert out["why"] == "receipts are missing from the end of the book"
    assert out["first_bad"] == 2


def test_verify_catches_every_receipt_removed_from_the_end():
    book = _book(("verdict", E1), ("paypal", E2), ("owner", E3))
    del book["receipts"][:]    # cut the whole book; the head still says three
    out = verify(book)
    assert out["intact"] is False
    assert out["why"] == "receipts are missing from the end of the book"
    assert out["first_bad"] == 1


def test_verify_reports_a_book_with_no_head():
    book = _book(("verdict", E1), ("paypal", E2), ("owner", E3))
    del book["head"]           # the receipts still link up, but the signed count is gone
    out = verify(book)
    assert out["intact"] is False
    assert out["why"] == "the book has no signed count"
    assert "first_bad" not in out                      # no one receipt is to blame


def test_verify_reports_an_empty_book_with_no_head():
    book = _book()
    del book["head"]
    out = verify(book)
    assert out["intact"] is False
    assert out["why"] == "the book has no signed count"


def test_verify_catches_a_head_whose_signature_does_not_match():
    book = _book(("verdict", E1), ("paypal", E2), ("owner", E3))
    del book["receipts"][2]                       # drop the last receipt
    book["head"]["count"] = 2                     # then lie that there were only two
    book["head"]["last_fp"] = book["receipts"][1]["fp"]
    out = verify(book)
    assert out["intact"] is False
    # the count block no longer carries a valid signature, so the forgery itself is caught
    assert out["why"] == "the book's signed count was changed"


def test_verify_catches_a_head_signed_by_a_different_key():
    book = _book(("verdict", E1), ("paypal", E2), ("owner", E3))
    head_fp = fingerprint({"count": book["head"]["count"], "last_fp": book["head"]["last_fp"]})
    book["head"]["sig"] = _signer().sign(head_fp)   # a valid signature, but the wrong key
    out = verify(book)
    assert out["intact"] is False
    assert out["why"] == "the book's signed count was changed"


def test_verify_catches_a_head_whose_count_is_wrong_but_last_fp_honest():
    book = _book(("verdict", E1), ("paypal", E2), ("owner", E3))
    book["head"]["count"] = 99                      # change only the count, leave the sig
    out = verify(book)
    assert out["intact"] is False
    assert out["why"] == "the book's signed count was changed"   # the sig no longer verifies


def test_an_empty_untouched_book_is_intact():
    book = _book()
    assert verify(book) == {"intact": True, "count": 0}


def test_the_head_survives_a_json_round_trip_and_still_checks_out():
    book = _book(("verdict", E1), ("paypal", E2), ("owner", E3))
    roundtripped = json.loads(json.dumps(book))
    assert verify(roundtripped) == {"intact": True, "count": 3}
    assert set(roundtripped["head"]) == {"count", "last_fp", "sig"}


# ---- 2 property-based tests (hypothesis) -----------------------------------------------------
# Fast enough for the on-save hook: max_examples about 100, no deadline. No network,
# no keys on disk; every signer is generated in memory.

# Events shaped like the ones Receipts emits, held as JSON values. Floats are finite
# (no NaN/inf) and ints stay inside JSON's safe range; canonical() handles any of these.
# "t" is left out of the top-level keys: in real use Receipts always sets "t" to the
# time and append() reads it as the receipt's time — stripping it is covered by the
# unit tests, so the property tests leave it out to keep the time a real number.
KINDS = ["verdict", "paypal", "desk", "owner", "say", "report"]
_JSON_VALUES = st.deferred(lambda: st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2 ** 53), max_value=2 ** 53),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=15),
    st.lists(_JSON_VALUES, max_size=4),
    st.dictionaries(st.text(min_size=1, max_size=6, alphabet=string.ascii_lowercase),
                   _JSON_VALUES, max_size=4),
))
_EVENT_KEYS = string.ascii_lowercase.replace("t", "")
_EVENTS = st.dictionaries(
    st.text(min_size=1, max_size=6, alphabet=_EVENT_KEYS),
    _JSON_VALUES, min_size=1, max_size=6,
)
_PAIRS = st.lists(st.tuples(st.sampled_from(KINDS), _EVENTS), max_size=8)


# ---- 2.1 any list of events gives an intact book ---------------------------------------------

@given(pairs=_PAIRS)
@settings(max_examples=100, deadline=None)
def test_property_any_sequence_of_events_is_intact(pairs):
    # an empty list is allowed, so the empty book (count 0, head linking to zeros) is covered
    assert verify(_book(*pairs)) == {"intact": True, "count": len(pairs)}


# ---- 2.2 changing any one field of any one receipt is caught at that receipt ----------------

def _new_value_for(field, old):
    """A strategy for a replacement value of one receipt field that differs from ``old``."""
    if field == "n":
        return st.integers(min_value=1, max_value=1000)
    if field == "at":
        return st.floats(allow_nan=False, allow_infinity=False)
    if field == "kind":
        return st.text(min_size=1, max_size=10)
    if field == "event":
        return _EVENTS
    if field in ("prev", "fp"):
        return st.text(alphabet="0123456789abcdef", min_size=64, max_size=64)
    return st.text(alphabet=string.ascii_letters + string.digits + "+/=", min_size=1, max_size=88)


@st.composite
def _book_one_field_and_new_value(draw):
    pairs = draw(st.lists(st.tuples(st.sampled_from(KINDS), _EVENTS), min_size=1, max_size=8))
    book = _book(*pairs)
    k = draw(st.integers(min_value=0, max_value=len(book["receipts"]) - 1))
    field = draw(st.sampled_from(["n", "at", "kind", "event", "prev", "fp", "sig"]))
    old = book["receipts"][k][field]
    new = draw(_new_value_for(field, old))
    assume(new != old)        # a real change, not a no-op
    return book, k, field, new


@given(plan=_book_one_field_and_new_value())
@settings(max_examples=100, deadline=None)
def test_property_changing_one_field_is_caught_at_that_receipt(plan):
    book, k, field, new = plan
    book["receipts"][k][field] = new
    out = verify(book)
    assert out["intact"] is False
    assert out["first_bad"] == k + 1          # the tampered receipt is the first to fail


# ---- 2.3 removing a receipt or swapping two is caught (including from the end) ---------------

@st.composite
def _book_and_index(draw, min_size):
    pairs = draw(st.lists(st.tuples(st.sampled_from(KINDS), _EVENTS),
                         min_size=min_size, max_size=8))
    book = _book(*pairs)
    k = draw(st.integers(min_value=0, max_value=len(book["receipts"]) - 1))
    return book, k


@given(plan=_book_and_index(min_size=1))
@settings(max_examples=100, deadline=None)
def test_property_removing_any_one_receipt_is_caught(plan):
    # any position: a middle gap fails the numbering; the last fails the signed head
    book, k = plan
    del book["receipts"][k]
    out = verify(book)
    assert out["intact"] is False
    assert out["first_bad"] == k + 1


@st.composite
def _book_and_drop(draw):
    pairs = draw(st.lists(st.tuples(st.sampled_from(KINDS), _EVENTS), min_size=1, max_size=8))
    book = _book(*pairs)
    drop = draw(st.integers(min_value=1, max_value=len(book["receipts"])))
    return book, drop


@given(plan=_book_and_drop())
@settings(max_examples=100, deadline=None)
def test_property_truncating_receipts_from_the_end_is_caught(plan):
    book, drop = plan
    total = len(book["receipts"])
    del book["receipts"][total - drop:]        # cut a suffix from the end
    out = verify(book)
    assert out["intact"] is False
    assert out["why"] == "receipts are missing from the end of the book"
    assert out["first_bad"] == len(book["receipts"]) + 1


@st.composite
def _book_and_two_indices(draw):
    pairs = draw(st.lists(st.tuples(st.sampled_from(KINDS), _EVENTS), min_size=2, max_size=8))
    book = _book(*pairs)
    n = len(book["receipts"])
    i = draw(st.integers(min_value=0, max_value=n - 1))
    j = draw(st.integers(min_value=0, max_value=n - 1))
    assume(i != j)
    return book, i, j


@given(plan=_book_and_two_indices())
@settings(max_examples=100, deadline=None)
def test_property_swapping_two_receipts_is_caught(plan):
    book, i, j = plan
    book["receipts"][i], book["receipts"][j] = book["receipts"][j], book["receipts"][i]
    out = verify(book)
    assert out["intact"] is False
    assert out["first_bad"] == min(i, j) + 1


# ---- 8 the owner's phone keeps the book's stamp -----------------------------------------------
# A signed count inside the book can be cut back to an older signed count that still
# matches the receipts left; the owner's phone holds a copy of the head outside the
# book, and verify(book, stamps) checks the book against those stamps.

def _head_at(signer, count, last_fp):
    """A valid signed head at a given count — the shape the owner's phone holds."""
    return {"count": count, "last_fp": last_fp,
            "sig": signer.sign(fingerprint({"count": count, "last_fp": last_fp}))}


def test_verify_with_no_stamps_behaves_as_before():
    book = _book(("verdict", E1), ("paypal", E2), ("owner", E3))
    assert verify(book) == {"intact": True, "count": 3}
    assert verify(book, stamps=None) == {"intact": True, "count": 3}
    assert verify(book, stamps=[]) == {"intact": True, "count": 3}


def test_verify_accepts_stamps_when_the_book_reaches_every_one():
    signer = _signer()
    carbon = CarbonCopy(signer)
    for i in range(5):
        carbon.append("verdict", {"t": 1795462000.001 + i, "amount": 100 + i, "invoice": f"INV-{i}"})
    book = carbon.book()
    recs = carbon.receipts()
    stamp3 = _head_at(signer, 3, recs[2]["fp"])    # the phone saw the book at 3
    stamp5 = book["head"]                           # the phone saw the book at 5 (the current head)
    assert verify(book, stamps=[stamp3, stamp5]) == {"intact": True, "count": 5}


def test_a_stamp_reaching_past_a_truncated_book_is_caught():
    # someone cuts the book back to 3 receipts and puts back an older signed head at 3;
    # the phone holds a stamp at 5, which the truncated book no longer reaches
    signer = _signer()
    carbon = CarbonCopy(signer)
    for i in range(5):
        carbon.append("verdict", {"t": 1795462000.001 + i, "amount": 100 + i})
    recs = carbon.receipts()
    truncated = {"public_key": signer.public_key_hex, "head": _head_at(signer, 3, recs[2]["fp"]),
                 "receipts": recs[:3]}
    # the truncated book is intact on its own — the older head matches the three receipts
    assert verify(truncated) == {"intact": True, "count": 3}
    # but the phone's stamp at 5 reaches past it
    stamp5 = _head_at(signer, 5, recs[4]["fp"])
    out = verify(truncated, stamps=[stamp5])
    assert out["intact"] is False
    assert out["why"] == "the book is shorter than a stamp your device already holds"
    assert out["first_bad"] == 5


def test_a_stamp_whose_last_fp_is_not_the_receipt_at_that_position_is_caught():
    signer = _signer()
    carbon = CarbonCopy(signer)
    for i in range(5):
        carbon.append("verdict", {"t": 1795462000.001 + i, "amount": 100 + i})
    book = carbon.book()
    recs = carbon.receipts()
    # a stamp at count 3 that claims the wrong last fingerprint (receipt 3 differs)
    bad_stamp = _head_at(signer, 3, recs[4]["fp"])
    out = verify(book, stamps=[bad_stamp])
    assert out["intact"] is False
    assert out["why"] == "receipt #3 no longer matches the stamp your device kept"   # the book is NOT shorter (task 9, F6)
    assert out["first_bad"] == 3


def test_any_one_of_several_stamps_is_enough_to_flag_a_short_book():
    signer = _signer()
    carbon = CarbonCopy(signer)
    for i in range(5):
        carbon.append("verdict", {"t": 1795462000.001 + i, "amount": 100 + i})
    recs = carbon.receipts()
    truncated = {"public_key": signer.public_key_hex, "head": _head_at(signer, 2, recs[1]["fp"]),
                 "receipts": recs[:2]}
    stamp2 = _head_at(signer, 2, recs[1]["fp"])    # satisfied (the book is at 2)
    stamp4 = _head_at(signer, 4, recs[3]["fp"])    # reaches past the truncated book
    out = verify(truncated, stamps=[stamp2, stamp4])
    assert out["intact"] is False
    assert out["why"] == "the book is shorter than a stamp your device already holds"


def test_a_stamp_at_the_books_own_count_is_accepted():
    # approving a hold hands the phone the head as it stands; that stamp must be accepted
    signer = _signer()
    carbon = CarbonCopy(signer)
    for i in range(3):
        carbon.append("verdict", {"t": 1795462000.001 + i, "amount": 100 + i})
    book = carbon.book()
    stamp = book["head"]
    assert verify(book, stamps=[stamp]) == {"intact": True, "count": 3}


def test_an_empty_book_with_a_stamp_at_zero_is_intact():
    signer = _signer()
    book = CarbonCopy(signer).book()
    stamp = _head_at(signer, 0, GENESIS)             # a stamp is signed (task 9): an unsigned one is forged
    assert verify(book, stamps=[stamp]) == {"intact": True, "count": 0}


# ---- 3 tamper_demo ---------------------------------------------------------------------------

def test_tamper_demo_changes_a_copy_not_the_real_book():
    carbon = CarbonCopy(_signer())
    carbon.append("verdict", {"t": 1795462000.001, "amount": 1836.00, "invoice": "INV-BR-1197"})
    carbon.append("paypal", {"t": 1795462000.002, "tool": "list_transactions", "result": {"total_items": 1}})
    book_before = carbon.book()

    demo = tamper_demo(book_before)

    assert carbon.book() == book_before                       # the real book is untouched
    assert carbon.receipts()[0]["event"]["amount"] == 1836.00
    # the only receipt with an amount is receipt 1, so that is the one changed
    assert demo["n"] == 1
    assert demo["field"] == "amount"
    assert demo["before"] == 1836.00
    assert demo["after"] == 1837.0
    assert demo["result"]["intact"] is False
    assert demo["result"]["first_bad"] == 1
    assert demo["result"]["why"] == "its content was changed"


def test_tamper_demo_can_target_a_chosen_receipt():
    carbon = CarbonCopy(_signer())
    carbon.append("verdict", {"t": 1795462000.001, "amount": 100.0})
    carbon.append("verdict", {"t": 1795462000.002, "amount": 200.0})
    book = carbon.book()
    demo = tamper_demo(book, n=2)
    assert demo["n"] == 2
    assert demo["field"] == "amount"
    assert demo["before"] == 200.0
    assert demo["after"] == 201.0
    assert demo["result"]["first_bad"] == 2
    assert carbon.book() == book                               # the real book is untouched


def test_tamper_demo_falls_back_to_another_event_field_when_there_is_no_amount():
    carbon = CarbonCopy(_signer())
    carbon.append("paypal", {"t": 1795462000.001, "tool": "list_transactions", "result": {"total_items": 1}})
    book = carbon.book()
    demo = tamper_demo(book)
    assert demo["n"] == 1
    assert demo["field"] == "tool"                             # no amount, so the first event field
    assert demo["result"]["intact"] is False
    assert demo["result"]["first_bad"] == 1


def test_tamper_demo_returns_intact_for_an_empty_book():
    book = _book()
    demo = tamper_demo(book)
    assert demo["n"] is None
    assert demo["field"] is None
    assert demo["result"] == {"intact": True, "count": 0}


def test_tamper_demo_never_mutates_the_book_passed_in():
    carbon = CarbonCopy(_signer())
    carbon.append("verdict", {"t": 1795462000.001, "amount": 100.0})
    book = carbon.book()
    snapshot = json.loads(json.dumps(book))
    tamper_demo(book)
    tamper_demo(book, n=1)
    assert book == snapshot


# ---- 3 the command-line checker ---------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent


def _run_cli(book_path, stamps_path=None):
    args = [sys.executable, "-m", "receipts.carbon", "verify", str(book_path)]
    if stamps_path:
        args += ["--stamps", str(stamps_path)]
    return subprocess.run(args, capture_output=True, text=True, cwd=str(ROOT))


def test_cli_prints_intact_and_exits_zero_for_a_good_book(tmp_path):
    book = _book(("verdict", E1), ("paypal", E2), ("owner", E3))
    p = tmp_path / "book.json"
    p.write_text(json.dumps(book), encoding="utf-8")
    proc = _run_cli(p)
    assert proc.returncode == 0
    assert "intact" in proc.stdout
    assert "3" in proc.stdout


def test_cli_prints_the_first_changed_receipt_and_exits_one(tmp_path):
    book = _book(("verdict", E1), ("paypal", E2), ("owner", E3))
    book["receipts"][1]["event"]["tool"] = "create_refund"   # receipt 2's content no longer matches its fp
    p = tmp_path / "book.json"
    p.write_text(json.dumps(book), encoding="utf-8")
    proc = _run_cli(p)
    assert proc.returncode == 1
    assert "receipt 2" in proc.stdout
    assert "its content was changed" in proc.stdout


def test_cli_applies_the_stamps_and_flags_a_short_book(tmp_path):
    signer = _signer()
    carbon = CarbonCopy(signer)
    for i in range(5):
        carbon.append("verdict", {"t": 1795462000.001 + i, "amount": 100 + i})
    recs = carbon.receipts()
    truncated = {"public_key": signer.public_key_hex, "head": _head_at(signer, 3, recs[2]["fp"]),
                 "receipts": recs[:3]}
    stamp5 = _head_at(signer, 5, recs[4]["fp"])
    bp = tmp_path / "book.json"
    sp = tmp_path / "stamps.json"
    bp.write_text(json.dumps(truncated), encoding="utf-8")
    sp.write_text(json.dumps([stamp5]), encoding="utf-8")
    assert _run_cli(bp).returncode == 0                          # without stamps the truncated book looks intact
    proc = _run_cli(bp, sp)                                       # with stamps the phone catches the rollback
    assert proc.returncode == 1
    assert "the book is shorter than a stamp your device already holds" in proc.stdout


# ---- whole-number floats survive a browser round trip ----------------------------------------

def _browser_like(x):
    """What a browser does to a book: JSON.parse then JSON.stringify writes 1836.0 as 1836."""
    def whole_to_int(v):
        if isinstance(v, float):
            return int(v) if v.is_integer() else v
        if isinstance(v, dict):
            return {k: whole_to_int(w) for k, w in v.items()}
        if isinstance(v, list):
            return [whole_to_int(w) for w in v]
        return v
    return whole_to_int(json.loads(json.dumps(x)))


def test_a_whole_number_float_survives_a_browser_round_trip():
    event = {"type": "verdict", "decision": "HOLD", "amount": 1836.0, "fee": 298.5}
    book = _book(("verdict", event))
    assert book["receipts"][0]["event"]["amount"] == 1836.0
    sent = _browser_like(book)
    assert sent["receipts"][0]["event"]["amount"] == 1836
    assert isinstance(sent["receipts"][0]["event"]["amount"], int)
    assert verify(sent) == {"intact": True, "count": 1}


def test_canonical_gives_the_same_bytes_for_1836_and_1836_point_0():
    assert canonical({"a": 1836.0, "b": (1, 2.0)}) == canonical({"a": 1836, "b": [1, 2]})
    assert canonical({"a": 298.5}) == b'{"a":298.5}'


@given(pairs=_PAIRS)
@settings(max_examples=100, deadline=None)
def test_property_any_book_survives_the_browser_round_trip(pairs):
    book = _book(*pairs)
    assert verify(_browser_like(book)) == {"intact": True, "count": len(pairs)}


def test_the_command_line_reads_a_book_saved_with_a_byte_order_mark(tmp_path):
    book = _book(("verdict", E1), ("owner", E3))
    p = tmp_path / "book.json"
    p.write_text(json.dumps(book), encoding="utf-8-sig")
    assert p.read_bytes().startswith(b"\xef\xbb\xbf")
    done = _run_cli(p)
    assert done.returncode == 0 and "intact" in done.stdout


# ---- 7.2 the change-one demo tells the real lie ------------------------------------------------

def _book_with_owner_action(action: str):
    carbon = CarbonCopy(_signer())
    carbon.append("verdict", {"t": 1795462000.001, "id": "abc12345", "decision": "HOLD", "amount": 1836.0,
                              "tool": "create_payout", "args": {"vendor": "Blue Ridge Finishes", "amount": 1836.0}})
    carbon.append("owner", {"t": 1795462000.002, "type": "owner", "action": action, "hold_id": "abc12345"})
    return carbon


def test_tamper_demo_turns_a_declined_into_an_approved_and_says_so():
    carbon = _book_with_owner_action("declined")
    before = carbon.book()
    demo = tamper_demo(before)
    assert (demo["n"], demo["field"], demo["before"], demo["after"]) == (2, "action", "declined", "approved")
    assert demo["say"] == ("We changed receipt #2 in a copy of the book so it says Maya APPROVED the $1,836.00 "
                           "payment to Blue Ridge Finishes. She declined it.")
    assert demo["result"]["intact"] is False and demo["result"]["first_bad"] == 2
    assert carbon.book() == before and verify(carbon.book())["intact"] is True


def test_tamper_demo_turns_an_approved_into_a_declined_when_nothing_was_declined():
    demo = tamper_demo(_book_with_owner_action("approved").book())
    assert demo["after"] == "declined" and "Maya DECLINED the $1,836.00 payment to Blue Ridge Finishes" in demo["say"]
    assert demo["result"]["first_bad"] == 2


def test_tamper_demo_without_an_owner_action_says_the_real_before_and_after():
    carbon = CarbonCopy(_signer())
    carbon.append("verdict", {"t": 1795462000.001, "amount": 298.0})
    before = carbon.book()
    demo = tamper_demo(before)
    assert demo["say"] == "We changed receipt #1 from $298.00 to $299.00 in a copy of the book."
    assert demo["result"]["first_bad"] == 1 and carbon.book() == before


def test_visitors_read_carbon_copy_not_receipts():
    root = Path(__file__).resolve().parent.parent
    html = (root / "static" / "index.html").read_text(encoding="utf-8")
    assert "<title>Carbon Copy</title>" in html and '<div class="name">Carbon Copy</div>' in html
    assert "<svg" not in html.split("</header>")[0]
    assert "PAYPAL_MODE\n        value: standin" in (root / "render.yaml").read_text(encoding="utf-8").replace("\r\n", "\n")


# ---- 9 the check does not trust the server (task 9) ------------------------------------------------------------
import copy  # noqa: E402
import datetime  # noqa: E402
import decimal  # noqa: E402
import hashlib  # noqa: E402
import math  # noqa: E402

import pytest  # noqa: E402

from receipts.carbon import forge_demo, safe_json  # noqa: E402

WHY_KEY = "it was signed with a different key than the one your device trusts"
WHY_BAD_STAMP = "a stamp on your device is damaged or forged"


def _stamp_book(count=5):
    signer = _signer()
    carbon = CarbonCopy(signer)
    for i in range(count):
        carbon.append("verdict", {"t": 1795462000.001 + i, "amount": 100 + i})
    return signer, carbon


# F4 / D1: the safe JSON form --------------------------------------------------------------------------------

def test_safe_json_replaces_lone_surrogates_in_text_and_keys():
    assert safe_json("a\ud83db") == "a\ufffdb"
    assert safe_json({"k\udfff": ["\ud800"]}) == {"k\ufffd": ["\ufffd"]}
    assert safe_json("😀") == "😀"                                  # a real astral character is kept


def test_safe_json_keeps_safe_integers_and_writes_the_rest_as_text():
    assert safe_json(2 ** 53 - 1) == 2 ** 53 - 1 and safe_json(-(2 ** 53 - 1)) == -(2 ** 53 - 1)
    assert safe_json(2 ** 53) == str(2 ** 53)
    assert safe_json(9007199254740993) == "9007199254740993"
    assert safe_json(True) is True and safe_json(None) is None


def test_safe_json_floats():
    assert safe_json(1836.0) == 1836 and isinstance(safe_json(1836.0), int)
    assert safe_json(float(2 ** 60)) == repr(float(2 ** 60))        # whole but out of range: text
    assert safe_json(298.5) == "298.5"
    assert safe_json(float("nan")) == "nan" and safe_json(float("inf")) == "inf" and safe_json(float("-inf")) == "-inf"
    assert safe_json(-0.0) == 0


def test_safe_json_turns_every_other_type_into_text_and_tuples_into_lists():
    assert safe_json((1, (2, 3))) == [1, [2, 3]]
    assert safe_json(decimal.Decimal("1.10")) == "1.10"
    assert safe_json(datetime.date(2026, 1, 2)) == "2026-01-02"
    assert safe_json(b"ab") == "b'ab'" and safe_json({"x"}) == "{'x'}"
    assert safe_json({1: "a", None: "b"}) == {"1": "a", "None": "b"}


def test_safe_json_does_not_change_its_input_and_survives_a_cycle():
    original = {"a": [1.5, {"b": (1,)}]}
    snapshot = copy.deepcopy(original)
    safe_json(original)
    assert original == snapshot
    loop: list = []
    loop.append(loop)
    json.dumps(safe_json({"loop": loop}))                           # finishes, and the result is plain JSON


def test_keys_that_clean_to_the_same_text_give_the_same_bytes_in_either_order():
    a = safe_json({"k\ud800": 1, "k\udfff": 2})
    b = safe_json({"k\udfff": 2, "k\ud800": 1})
    assert a == b == {"k\ufffd": 2}


def test_the_example_from_the_review_lone_surrogate_in_a_reply_is_written_and_checked():
    carbon = CarbonCopy(_signer())
    receipt = carbon.append("desk", {"t": 1795462000.001, "tool": "reply_to_customer",
                                     "args": {"to": "a@b.c", "body": "hello \ud83d"}})
    assert receipt["event"]["args"]["body"] == "hello \ufffd"
    assert verify(carbon.book()) == {"intact": True, "count": 1}
    json.dumps(carbon.book(), ensure_ascii=False).encode("utf-8")   # can be sent as UTF-8


def test_nan_and_infinity_are_written_and_the_book_is_valid_json():
    carbon = CarbonCopy(_signer())
    carbon.append("verdict", {"t": 1795462000.001, "amount": float("nan"), "x": [float("inf"), float("-inf")]})
    book = carbon.book()
    text = json.dumps(book, allow_nan=False)                        # Starlette refuses NaN: there is none
    assert verify(json.loads(text)) == {"intact": True, "count": 1}


def test_a_time_that_is_not_a_finite_number_falls_back_to_now():
    carbon = CarbonCopy(_signer())
    for bad in (float("nan"), float("inf"), "later", None, True):
        r = carbon.append("verdict", {"t": bad, "amount": 1})
        assert math.isfinite(r["at"]) and r["at"] > 1_000_000_000


@pytest.mark.parametrize("number", [9007199254740993, 2 ** 60, float(2 ** 60), 2 ** 53, -(2 ** 63), 298.5, 1e-7, 1e22])
def test_big_numbers_survive_a_browser_round_trip(number):
    carbon = CarbonCopy(_signer())
    carbon.append("verdict", {"t": 1795462000.001, "amount": number})
    roundtrip = json.loads(json.dumps(carbon.book(), allow_nan=False))
    assert verify(roundtrip) == {"intact": True, "count": 1}


def test_canonical_orders_keys_by_code_point_not_by_utf16_unit():
    # U+FFFF sorts before U+10000 by code point; by UTF-16 unit (a browser's default) the astral key would come first
    assert canonical({"\U00010000": 1, "\uffff": 2}) == '{"\uffff":2,"\U00010000":1}'.encode("utf-8")


def test_canonical_refuses_what_it_would_have_to_guess_at():
    for odd in (decimal.Decimal("1"), datetime.date(2026, 1, 1), {1, 2}, b"x"):
        with pytest.raises(TypeError):
            canonical({"v": odd})
    for bad in (float("nan"), float("inf")):
        with pytest.raises(ValueError):
            canonical({"v": bad})


def test_every_type_an_agent_could_write_is_stored_as_what_is_hashed_and_sent():
    carbon = CarbonCopy(_signer())
    r = carbon.append("verdict", {"t": 1795462000.001, "d": decimal.Decimal("2.50"), "when": datetime.datetime(2026, 1, 2, 3, 4),
                                  "s": {"a"}, "b": b"\x00", "o": object, "t2": (1, 2)})
    assert all(isinstance(v, (str, list)) for v in r["event"].values())
    assert verify(json.loads(json.dumps(carbon.book()))) == {"intact": True, "count": 1}


def test_the_fingerprint_recipe_is_the_plain_one_anyone_can_redo():
    # The recipe from the README, written out with nothing but json and hashlib.
    carbon = CarbonCopy(_signer())
    r = carbon.append("say", {"t": 1795462000.001, "text": "café 😀", "n": 7, "ok": True, "none": None, "list": [1, ["x"]],
                              "\U00010000": "astral", "\uffff": "bmp"})
    payload = {"n": r["n"], "at": r["at"], "kind": r["kind"], "event": r["event"], "prev": r["prev"]}
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == r["fp"]


# D2: the key ------------------------------------------------------------------------------------------------

def test_a_key_that_is_64_hex_characters_is_the_seed(monkeypatch):
    seed = Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    monkeypatch.setenv("CARBON_COPY_KEY", seed.hex().upper())
    assert Signer.from_env().public_key_hex == Signer(Ed25519PrivateKey.from_private_bytes(seed)).public_key_hex


@pytest.mark.parametrize("text", ["correct horse battery staple", "ünïcode ☕", "abc123", "0" * 63, "g" * 64, " " + "a" * 64])
def test_any_other_key_text_gives_the_seed_sha256_of_it(monkeypatch, text):
    monkeypatch.setenv("CARBON_COPY_KEY", text)
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    assert Signer.from_env().public_key_hex == Signer(Ed25519PrivateKey.from_private_bytes(seed)).public_key_hex
    assert Signer.from_env().public_key_hex == Signer.from_env().public_key_hex      # fixed
    assert Signer.from_env().temporary is False


def test_with_no_key_set_the_key_is_temporary_and_the_short_form_is_16_hex(monkeypatch):
    monkeypatch.delenv("CARBON_COPY_KEY", raising=False)
    s = Signer.from_env()
    assert s.temporary is True and s.short_key == s.public_key_hex[:16] and len(s.short_key) == 16


def test_the_key_text_never_appears_in_the_signer_repr(monkeypatch):
    monkeypatch.setenv("CARBON_COPY_KEY", "a-very-secret-sentence")
    s = Signer.from_env()
    assert "secret" not in repr(s) and "secret" not in str(s.public_key_hex)


# F1 / D4: the key the device trusts ---------------------------------------------------------------------------

def test_a_book_re_signed_under_a_new_key_reads_intact_alone_but_changed_against_the_trusted_key():
    carbon = _book_with_owner_action("declined")
    book = carbon.book()
    forged = forge_demo(book)["book"]
    assert forged["receipts"][1]["event"]["action"] == "approved"
    assert verify(forged) == {"intact": True, "count": 2}               # alone, the forgery is perfect
    out = verify(forged, expected_key=book["public_key"])               # against the key the device trusts it is not
    assert out["intact"] is False and out["why"] == WHY_KEY
    assert verify(book, expected_key=book["public_key"]) == {"intact": True, "count": 2}
    assert verify(book, expected_key=book["public_key"].upper()) == {"intact": True, "count": 2}


def test_the_forgery_does_not_touch_the_real_book():
    carbon = _book_with_owner_action("declined")
    before = carbon.book()
    out = forge_demo(before)
    assert carbon.book() == before and out["n"] == 2 and "APPROVED" in out["say"] and "declined" in out["say"]
    assert out["book"]["public_key"] != before["public_key"]
    assert forge_demo(CarbonCopy(_signer()).book())["book"] is None


# F2 / F5: the stamps are checked, malformed ones fail closed ----------------------------------------------

def test_a_stamp_with_a_made_up_signature_is_forged():
    signer, carbon = _stamp_book()
    book = carbon.book()
    stamp = {**book["head"], "sig": "AAAA"}
    out = verify(book, stamps=[stamp])
    assert out["intact"] is False and out["why"] == WHY_BAD_STAMP


def test_a_stamp_signed_by_another_key_is_forged_even_if_the_book_key_is_not_pinned():
    signer, carbon = _stamp_book()
    other = _signer()
    stamp = _head_at(other, 5, carbon.receipts()[4]["fp"])
    assert verify(carbon.book(), stamps=[stamp])["why"] == WHY_BAD_STAMP
    assert verify(carbon.book(), stamps=[stamp], expected_key=signer.public_key_hex)["why"] == WHY_BAD_STAMP


def test_a_stamp_is_checked_against_the_trusted_key_not_the_books_own():
    signer, carbon = _stamp_book()
    other = _signer()
    forged = forge_demo(carbon.book())["book"]                          # signed under a new key, stamps by the real key
    stamp = carbon.stamp()
    assert verify(forged, stamps=[stamp])["why"] == WHY_BAD_STAMP        # no pinned key: the book's key rejects the stamp
    assert verify(forged, stamps=[stamp], expected_key=other.public_key_hex)["why"] == WHY_KEY


@pytest.mark.parametrize("breakage", [
    lambda s: {**s, "count": float(s["count"])},         # 5.0
    lambda s: {**s, "count": str(s["count"])},           # "5"
    lambda s: {**s, "count": True},
    lambda s: {**s, "count": -1},
    lambda s: {**s, "count": None},
    lambda s: {**s, "last_fp": 7},
    lambda s: {**s, "sig": None},
    lambda s: {k: v for k, v in s.items() if k != "sig"},
    lambda s: json.dumps(s),                              # a JSON string instead of an object
    lambda s: [s],
    lambda s: None,
])
def test_a_malformed_stamp_makes_the_book_changed(breakage):
    signer, carbon = _stamp_book()
    out = verify(carbon.book(), stamps=[breakage(carbon.stamp())], expected_key=signer.public_key_hex)
    assert out["intact"] is False and out["why"] == WHY_BAD_STAMP


def test_a_cut_back_book_cannot_hide_behind_a_malformed_stamp():
    signer, carbon = _stamp_book()
    recs = carbon.receipts()
    cut = {"public_key": signer.public_key_hex, "head": _head_at(signer, 3, recs[2]["fp"]), "receipts": recs[:3]}
    stamp = carbon.stamp()
    assert verify(cut, stamps=[{**stamp, "count": 5.0}])["intact"] is False
    assert verify(cut, stamps=[stamp])["why"] == "the book is shorter than a stamp your device already holds"


def test_stamps_that_are_not_a_list_make_the_book_changed():
    signer, carbon = _stamp_book()
    for bad in (carbon.stamp(), "stamp", 5):
        assert verify(carbon.book(), stamps=bad)["why"] == WHY_BAD_STAMP
    assert verify(carbon.book(), stamps=[]) == {"intact": True, "count": 5}
    assert verify(carbon.book(), stamps=None) == {"intact": True, "count": 5}


def test_a_stamp_carries_the_public_key_that_signed_it():
    signer, carbon = _stamp_book()
    s = carbon.stamp()
    assert set(s) == {"count", "last_fp", "sig", "public_key"} and s["public_key"] == signer.public_key_hex
    assert verify(carbon.book(), stamps=[s], expected_key=s["public_key"]) == {"intact": True, "count": 5}


# F6: the right reason -----------------------------------------------------------------------------------------

def test_a_changed_receipt_inside_the_stamped_part_is_named_for_what_it_is():
    signer, carbon = _stamp_book()
    recs = carbon.receipts()
    stamp3 = _head_at(signer, 3, recs[2]["fp"])
    # a book of the same length where receipt 3 was rewritten and the rest re-chained and re-signed with the SAME key
    # (someone who holds the key): every receipt is valid, the stamp no longer matches
    rewritten = CarbonCopy(signer)
    for i, r in enumerate(recs):
        rewritten.append(r["kind"], {"t": r["at"], **({"amount": 999} if i == 2 else r["event"])})
    book = rewritten.book()
    assert verify(book) == {"intact": True, "count": 5}
    out = verify(book, stamps=[stamp3])
    assert out["intact"] is False and out["first_bad"] == 3
    assert out["why"] == "receipt #3 no longer matches the stamp your device kept"
    assert "shorter" not in out["why"]


def test_only_a_stamp_beyond_the_end_says_shorter():
    signer, carbon = _stamp_book()
    recs = carbon.receipts()
    cut = {"public_key": signer.public_key_hex, "head": _head_at(signer, 4, recs[3]["fp"]), "receipts": recs[:4]}
    out = verify(cut, stamps=[_head_at(signer, 5, recs[4]["fp"])])
    assert out["why"] == "the book is shorter than a stamp your device already holds" and out["first_bad"] == 5


# robustness of verify itself ------------------------------------------------------------------------------------

@pytest.mark.parametrize("junk", [None, [], "book", 5, {"receipts": "x"}, {"receipts": [None]}, {"receipts": [5, "a"]},
                                  {"receipts": [{"n": 1}]}])
def test_verify_fails_closed_on_junk(junk):
    out = verify(junk) if not isinstance(junk, dict) else verify({**junk, "public_key": "00"})
    assert out["intact"] is False and out["why"]


def test_a_receipt_holding_nan_or_a_date_is_changed_not_a_crash():
    carbon = CarbonCopy(_signer())
    carbon.append("verdict", {"t": 1795462000.001, "amount": 1})
    book = carbon.book()
    for bad in (float("nan"), datetime.date(2026, 1, 1)):
        broken = copy.deepcopy(book)
        broken["receipts"][0]["event"]["amount"] = bad
        assert verify(broken)["why"] == "its content was changed" and verify(broken)["first_bad"] == 1


# F7 / D6: the command line ------------------------------------------------------------------------------------

def test_cli_exits_two_with_a_plain_message_when_the_file_cannot_be_read(tmp_path):
    missing = _run_cli(tmp_path / "nope.json")
    assert missing.returncode == 2 and "could not read" in missing.stderr and "Traceback" not in missing.stderr
    junk = tmp_path / "junk.json"
    junk.write_text("not json at all", encoding="utf-8")
    assert _run_cli(junk).returncode == 2
    binary = tmp_path / "binary.json"
    binary.write_bytes(b"\xff\xfe\x00\x80\x81")
    done = _run_cli(binary)
    assert done.returncode == 2 and "Traceback" not in done.stderr
    notbook = tmp_path / "list.json"
    notbook.write_text("[1, 2]", encoding="utf-8")
    assert _run_cli(notbook).returncode == 2


def test_cli_exits_two_when_the_stamps_file_cannot_be_read(tmp_path):
    bp = tmp_path / "book.json"
    bp.write_text(json.dumps(_book(("verdict", E1))), encoding="utf-8")
    done = _run_cli(bp, tmp_path / "no_stamps.json")
    assert done.returncode == 2 and "Traceback" not in done.stderr


def test_cli_still_exits_one_for_a_changed_book_and_zero_for_an_intact_one(tmp_path):
    book = _book(("verdict", E1), ("owner", E3))
    good = tmp_path / "good.json"
    good.write_text(json.dumps(book), encoding="utf-8")
    book["receipts"][0]["event"]["amount"] = 1
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(book), encoding="utf-8")
    assert _run_cli(good).returncode == 0 and _run_cli(bad).returncode == 1


def test_cli_key_pins_the_expected_key(tmp_path):
    book = _book(("verdict", E1))
    bp = tmp_path / "book.json"
    bp.write_text(json.dumps(book), encoding="utf-8")
    right = subprocess.run([sys.executable, "-m", "receipts.carbon", "verify", str(bp), "--key", book["public_key"]],
                           capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent)
    assert right.returncode == 0 and "intact" in right.stdout
    wrong = subprocess.run([sys.executable, "-m", "receipts.carbon", "verify", str(bp), "--key", "ab" * 32],
                           capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent)
    assert wrong.returncode == 1 and WHY_KEY in wrong.stdout
    bad_key = subprocess.run([sys.executable, "-m", "receipts.carbon", "verify", str(bp), "--key", "not-hex"],
                             capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent)
    assert bad_key.returncode == 2 and "Traceback" not in bad_key.stderr


def test_cli_stamps_with_a_forged_signature_exit_one(tmp_path):
    signer, carbon = _stamp_book()
    bp, sp = tmp_path / "book.json", tmp_path / "stamps.json"
    bp.write_text(json.dumps(carbon.book()), encoding="utf-8")
    sp.write_text(json.dumps([{**carbon.stamp(), "sig": "AAAA"}]), encoding="utf-8")
    done = _run_cli(bp, sp)
    assert done.returncode == 1 and WHY_BAD_STAMP in done.stdout