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
