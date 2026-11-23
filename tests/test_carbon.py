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
    assert out["why"] == "the book is shorter than a stamp the owner's phone already holds"
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
    assert out["why"] == "the book is shorter than a stamp the owner's phone already holds"
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
    assert out["why"] == "the book is shorter than a stamp the owner's phone already holds"


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
    book = _book()
    stamp = {"count": 0, "last_fp": GENESIS, "sig": ""}
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
    assert "the book is shorter than a stamp the owner's phone already holds" in proc.stdout


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
