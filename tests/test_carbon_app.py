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
