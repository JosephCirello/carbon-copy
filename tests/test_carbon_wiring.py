"""Integration test: the carbon-copy book wired into Receipts (task 4).

Runs one scenario from scenarios/scenarios.json on the stand-in PayPal with a book
attached, then checks the book is intact, holds exactly one receipt per emitted
event, and that approving a hold returns a stamp the check accepts. No network, no
keys on disk: the signer is generated in memory.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from receipts.carbon import CarbonCopy, Signer, verify  # noqa: E402
from receipts.core import Receipts  # noqa: E402
from receipts.paypal import StandIn  # noqa: E402
from receipts.scenarios import by_id  # noqa: E402

S = by_id()


def test_one_scenario_on_the_stand_in_gives_an_intact_book_with_a_stamp():
    scn = S["S5_i_am_the_owner"]
    pp = StandIn(scn["paypal"], scn["id"])
    carbon = CarbonCopy(Signer(Ed25519PrivateKey.generate()))   # fresh in-memory key; never written
    events: list[dict] = []
    r = Receipts(scn, pp, mode="enforce", on_event=events.append, carbon=carbon)

    res = r.call("create_refund", {"capture_id": pp.ids["C.capture_id"], "amount": 420})
    assert res["held_by_receipts"]
    out = r.approve(res["hold_id"])

    # the refund went through to PayPal (the existing behaviour, unchanged)
    assert out["status"] == "COMPLETED" and r.ledger[-1]["kind"] == "refund"

    book = carbon.book()
    # one receipt per emitted event, and each receipt's kind is the event's type
    assert len(book["receipts"]) == len(events)
    assert [rec["kind"] for rec in book["receipts"]] == [e["type"] for e in events]
    # the book is intact
    assert verify(book) == {"intact": True, "count": len(events)}

    # approving the hold returned the book's signed head, right after the tap was recorded
    assert "stamp" in out
    stamp = out["stamp"]
    assert set(stamp.keys()) == {"count", "last_fp", "sig"}
    assert stamp["count"] == len(book["receipts"])
    assert stamp["last_fp"] == book["receipts"][-1]["fp"]
    # the phone's stamp is accepted — the book reaches it and the receipt there matches
    assert verify(book, stamps=[stamp]) == {"intact": True, "count": len(events)}


def test_decline_returns_a_stamp_and_the_book_still_checks_out():
    scn = S["S5_i_am_the_owner"]
    pp = StandIn(scn["paypal"], scn["id"])
    carbon = CarbonCopy(Signer(Ed25519PrivateKey.generate()))
    r = Receipts(scn, pp, mode="enforce", carbon=carbon)

    res = r.call("create_refund", {"capture_id": pp.ids["C.capture_id"], "amount": 420})
    assert res["held_by_receipts"]
    out = r.decline(res["hold_id"])

    assert out["declined"] == res["hold_id"]
    assert "stamp" in out
    book = carbon.book()
    assert verify(book) == {"intact": True, "count": len(book["receipts"])}
    assert verify(book, stamps=[out["stamp"]]) == {"intact": True, "count": len(book["receipts"])}


def test_a_book_without_carbon_leaves_receipts_unchanged():
    # carbon=None is the default: no stamp is added, and existing behaviour is untouched
    scn = S["S5_i_am_the_owner"]
    pp = StandIn(scn["paypal"], scn["id"])
    r = Receipts(scn, pp, mode="enforce")
    res = r.call("create_refund", {"capture_id": pp.ids["C.capture_id"], "amount": 420})
    assert res["held_by_receipts"]
    out = r.approve(res["hold_id"])
    assert out["status"] == "COMPLETED"
    assert "stamp" not in out                       # no carbon -> no stamp, as before
