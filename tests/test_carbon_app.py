"""The carbon-copy book through the web app (task 5.1): FastAPI's TestClient, the stand-in PayPal, recorded runs.

No model, no network, no keys: each run's signer is generated in memory.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DAY, MODEL = "S14_crossed_in_the_mail", "glm-5.3"


@pytest.fixture(scope="module")
def web():
    before = os.environ.get("PAYPAL_MODE")
    os.environ["PAYPAL_MODE"] = "standin"
    import app as web_app
    yield web_app
    if before is None:
        os.environ.pop("PAYPAL_MODE", None)
    else:
        os.environ["PAYPAL_MODE"] = before


@pytest.fixture()
def client(web):
    from fastapi.testclient import TestClient
    web.VISITORS.clear()
    return TestClient(web.app)


def replay(client) -> str:
    rows = client.get("/api/recorded", params={"scenario": DAY, "model": MODEL}).json()
    pick = sorted((r for r in rows if r["mode"] == "enforce"), key=lambda r: -(r["attempts"] or 0))[0]
    res = client.get("/api/replay", params={"line": pick["line"], "speed": 100})
    assert res.status_code == 200 and '"type": "done"' in res.text
    return client.get("/api/holds").json()[0]["session"]


def test_no_run_yet_gives_an_empty_book(client):
    got = client.get("/api/carbon")
    assert got.status_code == 200 and got.json()["receipts"] == [] and got.json()["source"] is None
    assert client.get("/api/carbon", params={"sid": "nope"}).status_code == 404
    assert client.post("/api/carbon/tamper").status_code == 404


def test_an_untouched_book_verifies_intact(client):
    sid = replay(client)
    book = client.get("/api/carbon", params={"sid": sid}).json()
    assert book["source"] == "recorded run, replayed" and book["stamps"] == [] and book["receipts"]
    out = client.post("/api/carbon/verify", json={"book": book, "stamps": book["stamps"]}).json()
    assert out == {"intact": True, "count": len(book["receipts"])}


def test_tamper_says_changed_where_it_changed_and_the_real_book_stays_intact(client):
    sid = replay(client)
    before = client.get("/api/carbon", params={"sid": sid}).json()
    t = client.post("/api/carbon/tamper", params={"sid": sid}).json()
    assert t["result"]["intact"] is False and t["result"]["first_bad"] == t["n"]
    after = client.get("/api/carbon", params={"sid": sid}).json()
    assert after["receipts"] == before["receipts"]
    assert client.post("/api/carbon/verify", json={"book": after, "stamps": []}).json()["intact"] is True


def test_a_phone_stamp_round_trips(client):
    sid = replay(client)
    hold = next(h for h in client.get("/api/holds").json() if h["status"] == "WAITING")
    done = client.post("/api/approve", json={"session": sid, "hold_id": hold["id"]}).json()
    stamp = done["stamp"]
    book = client.get("/api/carbon", params={"sid": sid}).json()
    assert book["stamps"] == [stamp] and stamp["count"] <= len(book["receipts"])
    assert client.post("/api/carbon/verify", json={"book": book, "stamps": book["stamps"]}).json()["intact"] is True
    # a book cut back to before the tap no longer satisfies the stamp the phone holds
    cut = {**book, "receipts": book["receipts"][: stamp["count"] - 1]}
    assert client.post("/api/carbon/verify", json={"book": cut, "stamps": book["stamps"]}).json()["intact"] is False


def test_a_decline_stamp_is_kept_too(client):
    sid = replay(client)
    hold = next(h for h in client.get("/api/holds").json() if h["status"] == "WAITING")
    done = client.post("/api/decline", json={"session": sid, "hold_id": hold["id"]}).json()
    assert "stamp" in done
    assert client.get("/api/carbon", params={"sid": sid}).json()["stamps"] == [done["stamp"]]


def test_a_file_that_is_not_a_book_fails_closed(client):
    out = client.post("/api/carbon/verify", json={"book": {"receipts": "x"}, "stamps": []}).json()
    assert out["intact"] is False


def _browser_like(x):
    """JSON.parse then JSON.stringify in a browser: a whole-number float 1836.0 comes back as 1836."""
    import json

    def whole_to_int(v):
        if isinstance(v, float):
            return int(v) if v.is_integer() else v
        if isinstance(v, dict):
            return {k: whole_to_int(w) for k, w in v.items()}
        if isinstance(v, list):
            return [whole_to_int(w) for w in v]
        return v
    return whole_to_int(json.loads(json.dumps(x)))


def test_a_book_sent_through_a_browser_still_verifies_intact(client):
    sid = replay(client)
    book = client.get("/api/carbon", params={"sid": sid}).json()
    sent = _browser_like(book)
    out = client.post("/api/carbon/verify", json={"book": sent, "stamps": sent["stamps"]}).json()
    assert out == {"intact": True, "count": len(book["receipts"])}


# ---- which book the tab shows (task 8) ----------------------------------------------------------------------
def _lines(client):
    rows = client.get("/api/recorded", params={"scenario": DAY, "model": MODEL}).json()
    return sorted((r for r in rows if r["mode"] == "enforce"), key=lambda r: -(r["attempts"] or 0))[0]["line"]


def _start_both(client, order):
    """Start the two side-by-side replays for one visitor; the first named finishes first."""
    line = _lines(client)
    for mode in order:
        res = client.get("/api/replay", params={"line": line, "speed": 100, "mode": mode})
        assert res.status_code == 200 and '"type": "done"' in res.text


@pytest.mark.parametrize("order", [("enforce", "observe"), ("observe", "enforce")])
def test_the_default_book_is_the_enforce_run_whichever_finished_last(client, order):
    _start_both(client, order)
    book = client.get("/api/carbon").json()
    assert book["mode"] == "enforce" and book["has_twin"] is True
    off = client.get("/api/carbon", params={"mode": "observe"}).json()
    assert off["mode"] == "observe" and off["has_twin"] is True and off["session"] != book["session"]
    assert client.get("/api/carbon", params={"mode": "enforce"}).json()["session"] == book["session"]


@pytest.mark.parametrize("order", [("enforce", "observe"), ("observe", "enforce")])
def test_after_a_decline_tamper_on_the_default_book_says_approved_instead_of_declined(client, order):
    _start_both(client, order)
    hold = next(h for h in client.get("/api/holds").json() if h["status"] == "WAITING")
    assert client.post("/api/decline", json={"session": hold["session"], "hold_id": hold["id"]}).status_code == 200
    t = client.post("/api/carbon/tamper").json()
    assert "APPROVED" in t["say"] and "She declined it" in t["say"] and t["result"]["intact"] is False
    assert client.get("/api/carbon").json()["session"] == hold["session"]


def test_observe_book_has_no_owner_action_and_the_off_tamper_acts_on_it(client):
    _start_both(client, ("enforce", "observe"))
    off = client.get("/api/carbon", params={"mode": "observe"}).json()
    assert all(r["kind"] != "owner" for r in off["receipts"])
    t = client.post("/api/carbon/tamper", params={"mode": "observe"}).json()
    assert t["result"]["intact"] is False and "declined" not in t["say"]


def test_with_only_an_observe_run_the_default_falls_back_to_it(client):
    line = _lines(client)
    client.get("/api/replay", params={"line": line, "speed": 100, "mode": "observe"})
    book = client.get("/api/carbon").json()
    assert book["mode"] == "observe" and book["has_twin"] is False
    assert client.get("/api/carbon", params={"mode": "enforce"}).json()["receipts"] == []


def test_a_bad_mode_is_refused(client):
    assert client.get("/api/carbon", params={"mode": "sideways"}).status_code == 400
    assert client.post("/api/carbon/tamper", params={"mode": "sideways"}).status_code == 400


# ---- task 9: the check does not trust the server ----------------------------------------------------------------
def _events(text):
    import json
    return [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]


def test_the_key_endpoint_publishes_the_key_every_book_is_signed_with(client, web):
    key = client.get("/api/carbon/key").json()
    assert key["public_key"] == web.SIGNER.public_key_hex and key["short"] == key["public_key"][:16] and len(key["public_key"]) == 64
    assert key["temporary"] is web.SIGNER.temporary
    sid = replay(client)
    assert client.get("/api/carbon", params={"sid": sid}).json()["public_key"] == key["public_key"]
    again = replay(client)                                    # a second run is signed with the same key
    assert client.get("/api/carbon", params={"sid": again}).json()["public_key"] == key["public_key"]


def test_the_key_endpoint_has_no_secret_in_it(client):
    text = client.get("/api/carbon/key").text
    assert set(client.get("/api/carbon/key").json()) == {"public_key", "short", "temporary"} and "seed" not in text


def test_every_event_of_a_run_carries_a_stamp_the_device_can_keep(client):
    rows = client.get("/api/recorded", params={"scenario": DAY, "model": MODEL}).json()
    line = sorted((r for r in rows if r["mode"] == "enforce"), key=lambda r: -(r["attempts"] or 0))[0]["line"]
    res = client.get("/api/replay", params={"line": line, "speed": 100})
    events = _events(res.text)
    assert events and all("head" in e for e in events)
    heads = [e["head"] for e in events]
    assert all(set(h) == {"count", "last_fp", "sig", "public_key"} for h in heads)
    assert [h["count"] for h in heads] == sorted(h["count"] for h in heads) and heads[-1]["count"] > 3
    sid = next(e["session"] for e in events if e["type"] == "session")
    book = client.get("/api/carbon", params={"sid": sid}).json()
    key = client.get("/api/carbon/key").json()["public_key"]
    # the device's own stamps, from the event stream alone, are satisfied by the real book and pin the real key
    out = client.post("/api/carbon/verify", json={"book": book, "stamps": heads, "expected_key": key}).json()
    assert out == {"intact": True, "count": len(book["receipts"])}
    # and they catch a book cut back to an earlier moment, with that moment's own signed head put back in the book
    earlier = next(h for h in heads if h["count"] < len(book["receipts"]))
    cut = {"public_key": book["public_key"], "receipts": book["receipts"][: earlier["count"]],
           "head": {k: earlier[k] for k in ("count", "last_fp", "sig")}}
    assert client.post("/api/carbon/verify", json={"book": cut, "stamps": [], "expected_key": key}).json()["intact"] is True
    out = client.post("/api/carbon/verify", json={"book": cut, "stamps": heads, "expected_key": key}).json()
    assert out["intact"] is False and out["why"] == "the book is shorter than a stamp your device already holds"


def test_a_rewrite_after_the_last_server_stamp_is_caught_by_the_stamps_the_device_saw(client):
    # F2: the stamps the device kept itself (from the event stream) cover the whole run, so a rewrite of the end is caught
    import json
    rows = client.get("/api/recorded", params={"scenario": DAY, "model": MODEL}).json()
    line = sorted((r for r in rows if r["mode"] == "enforce"), key=lambda r: -(r["attempts"] or 0))[0]["line"]
    events = _events(client.get("/api/replay", params={"line": line, "speed": 100}).text)
    sid = next(e["session"] for e in events if e["type"] == "session")
    book = client.get("/api/carbon", params={"sid": sid}).json()
    stamps = [e["head"] for e in events]
    assert stamps[-1]["count"] == len(book["receipts"])
    from receipts.carbon import forge_demo
    forged = forge_demo(book)["book"]                               # a whole new book under a new key
    key = book["public_key"]
    assert client.post("/api/carbon/verify", json={"book": forged, "stamps": stamps, "expected_key": key}).json()["why"] \
        == "it was signed with a different key than the one your device trusts"
    bad = [{**stamps[-1], "sig": "AAAA"}]
    assert client.post("/api/carbon/verify", json={"book": book, "stamps": bad, "expected_key": key}).json()["why"] \
        == "a stamp on your device is damaged or forged"
    assert json.dumps(stamps)                                       # plain JSON


def test_approve_and_decline_stamps_carry_the_key(client, web):
    sid = replay(client)
    hold = next(h for h in client.get("/api/holds").json() if h["status"] == "WAITING")
    stamp = client.post("/api/decline", json={"session": sid, "hold_id": hold["id"]}).json()["stamp"]
    assert stamp["public_key"] == web.SIGNER.public_key_hex
    book = client.get("/api/carbon", params={"sid": sid}).json()
    assert client.post("/api/carbon/verify", json={"book": book, "stamps": [stamp], "expected_key": stamp["public_key"]}).json()["intact"] is True


def test_verify_takes_the_devices_stamps_and_key_and_fails_closed_on_junk(client):
    sid = replay(client)
    book = client.get("/api/carbon", params={"sid": sid}).json()
    wrong = client.post("/api/carbon/verify", json={"book": book, "stamps": [], "expected_key": "ab" * 32}).json()
    assert wrong["intact"] is False and wrong["why"] == "it was signed with a different key than the one your device trusts"
    for junk in ("a stamp", 5, {"count": 1}, [None], ["x"], [{"count": "5"}]):
        out = client.post("/api/carbon/verify", json={"book": book, "stamps": junk}).json()
        assert out["intact"] is False and out["why"] == "a stamp on your device is damaged or forged"


def test_forge_gives_a_book_that_reads_intact_alone_and_changed_against_the_trusted_key(client):
    from receipts.carbon import verify
    sid = replay(client)
    hold = next(h for h in client.get("/api/holds").json() if h["status"] == "WAITING")
    decline = client.post("/api/decline", json={"session": sid, "hold_id": hold["id"]}).json()
    real = client.get("/api/carbon", params={"sid": sid}).json()
    got = client.post("/api/carbon/forge", params={"sid": sid}).json()
    forged = got["book"]
    assert got["say"] and "approved" in got["say"].lower() and "declined" in got["say"].lower()
    assert forged["receipts"][got["n"] - 1]["event"]["action"] == "approved"
    assert forged["public_key"] != real["public_key"] and len(forged["receipts"]) == len(real["receipts"])
    assert verify(forged)["intact"] is True                                      # a perfect forgery on its own
    out = verify(forged, stamps=[decline["stamp"]], expected_key=real["public_key"])
    assert out["intact"] is False and out["why"] == "it was signed with a different key than the one your device trusts"
    assert client.get("/api/carbon", params={"sid": sid}).json()["receipts"] == real["receipts"]   # the real book is untouched


def test_forge_with_no_run_is_a_404_and_a_bad_mode_is_a_400(client):
    assert client.post("/api/carbon/forge").status_code == 404
    assert client.post("/api/carbon/forge", params={"mode": "x"}).status_code == 400


def test_a_book_holding_nan_a_lone_surrogate_and_huge_numbers_is_served_and_intact(client):
    import json
    sid = replay(client)
    from app import VISITORS
    carbon = next(s["carbon"] for v in VISITORS.values() for s in v.sessions.values() if s["sid"] == sid)
    carbon.append("say", {"text": "hi \ud83d", "amount": float("nan"), "big": [9007199254740993, 2 ** 60, float(2 ** 60), 298.5]})
    res = client.get("/api/carbon", params={"sid": sid})
    assert res.status_code == 200
    book = json.loads(res.text)
    out = client.post("/api/carbon/verify", json={"book": book, "stamps": []}).json()
    assert out == {"intact": True, "count": len(book["receipts"])}


def test_an_event_holding_nan_does_not_break_the_stream(web):
    import json
    text = web._data({"type": "say", "amount": float("nan"), "list": [float("inf")], "text": "ok"})
    assert json.loads(text) == {"type": "say", "amount": "nan", "list": ["inf"], "text": "ok"}
    assert json.loads(web._data({"a": 1.5, "b": 2})) == {"a": 1.5, "b": 2}               # a normal event is left as it is