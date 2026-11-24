"""Task 17: the two findings task 16 left open (F10 a held payment vanishing after an hour, F11 /mcp memory).

The stand-in PayPal, no network, no keys: signers are made in memory.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from receipts import mcp_server  # noqa: E402
from receipts.carbon import CarbonCopy, Signer, verify  # noqa: E402

README = (ROOT / "README.md").read_text(encoding="utf-8")
KEEP = ("This server keeps a run for one hour after its last activity (it starting, or your last approve or decline), and for 24 hours when a payment in it is waiting for you. "
        "Download the carbon copies to keep them.")
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
    web._NEW_BY_ADDRESS.clear()
    web._MCP_CALLS.clear()
    yield TestClient(web.app, raise_server_exceptions=False)
    web.VISITORS.clear()
    web._MCP_CALLS.clear()


def run_with_hold(client) -> str:
    rows = client.get("/api/recorded", params={"scenario": DAY, "model": MODEL}).json()
    line = sorted((r for r in rows if r["mode"] == "enforce"), key=lambda r: -(r["attempts"] or 0))[0]["line"]
    text = client.get("/api/replay", params={"line": line, "speed": 100}).text
    assert [h for h in client.get("/api/holds").json() if h["status"] == "WAITING"]
    return next(json.loads(ln[5:])["session"] for ln in text.splitlines() if ln.startswith("data:") and '"type": "session"' in ln)


def age_runs(web, seconds: float) -> None:
    for v in web.VISITORS.values():
        for s in v.sessions.values():
            s["t"] -= seconds


# ---- F10: 24 hours with a payment waiting, one hour otherwise ---------------------------------------------------

def test_f10_a_run_with_a_waiting_payment_is_kept_past_an_hour_and_can_still_be_approved(web, client):
    sid = run_with_hold(client)
    age_runs(web, web.SESSION_MAX_AGE_S + 60)
    assert client.get("/api/carbon", params={"sid": sid}).status_code == 200
    hold = [h for h in client.get("/api/holds").json() if h["status"] == "WAITING"][0]
    assert client.post("/api/approve", json={"session": sid, "hold_id": hold["id"]}).status_code == 200


def test_f10_it_goes_after_24_hours(web, client):
    sid = run_with_hold(client)
    age_runs(web, 23 * 3600)
    assert client.get("/api/carbon", params={"sid": sid}).status_code == 200
    age_runs(web, 2 * 3600)
    assert client.get("/api/carbon", params={"sid": sid}).status_code == 404
    assert not client.get("/api/holds").json()


def test_f10_a_run_with_nothing_waiting_still_goes_after_an_hour(web, client):
    sid = run_with_hold(client)
    for h in client.get("/api/holds").json():
        if h["status"] == "WAITING":
            assert client.post("/api/decline", json={"session": sid, "hold_id": h["id"]}).status_code == 200
    age_runs(web, web.SESSION_MAX_AGE_S - 60)
    assert client.get("/api/carbon", params={"sid": sid}).status_code == 200
    age_runs(web, 120)
    assert client.get("/api/carbon", params={"sid": sid}).status_code == 404


def test_task18_the_hour_counts_from_the_owners_last_tap(web, client):
    sid = run_with_hold(client)
    age_runs(web, 2 * 3600)                                    # the payment waits 2 hours
    hold = [h for h in client.get("/api/holds").json() if h["status"] == "WAITING"][0]
    assert client.post("/api/approve", json={"session": sid, "hold_id": hold["id"]}).status_code == 200
    for h in client.get("/api/holds").json():                  # decide any other waiting payment too: nothing waits now
        if h["status"] == "WAITING":
            assert client.post("/api/decline", json={"session": sid, "hold_id": h["id"]}).status_code == 200
    age_runs(web, 59 * 60)
    book = client.get("/api/carbon", params={"sid": sid})
    assert book.status_code == 200 and book.json()["receipts"]   # the book that records her decision can be fetched
    age_runs(web, 2 * 60)                                      # 61 minutes after the tap
    assert client.get("/api/carbon", params={"sid": sid}).status_code == 404


def test_task18_a_second_tap_starts_the_hour_again_and_a_run_still_waiting_keeps_24_hours(web, client):
    sid = run_with_hold(client)
    waiting = [h for h in client.get("/api/holds").json() if h["status"] == "WAITING"]
    age_runs(web, 50 * 60)
    assert client.post("/api/decline", json={"session": sid, "hold_id": waiting[0]["id"]}).status_code == 200
    if len(waiting) > 1:                                       # another payment still waits: 24 hours from that tap
        age_runs(web, 23 * 3600)
        assert client.get("/api/carbon", params={"sid": sid}).status_code == 200
        age_runs(web, 2 * 3600)
        assert client.get("/api/carbon", params={"sid": sid}).status_code == 404


def test_f10_the_numbers_and_the_sentence_are_said_everywhere():
    assert KEEP in (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    assert (ROOT / "static" / "index.html").read_text(encoding="utf-8").count(KEEP) == 2
    assert "24 hours" in README and "one hour" in README and "loses everything when it restarts" in README


# ---- F11: /mcp is bounded -----------------------------------------------------------------------------------------

def test_f11_a_body_over_256_kb_gets_413_before_any_tool_runs(web, client):
    before = web.MCP_RECEIPTS.carbon.size_bytes()
    big = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                      "params": {"name": "update_vendor_payee", "arguments": {"vendor": "x", "new_paypal_email": "a@b.test", "reason": "A" * 300_000}}})
    h = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    r = client.post("/mcp/", content=big, headers=h)
    assert r.status_code == 413 and "too large" in r.json()["detail"]
    def chunks():                                              # no length declared: held to the same limit
        for _ in range(4):
            yield b"A" * 100_000
    assert client.post("/mcp/", content=chunks(), headers=h).status_code == 413
    assert web.MCP_RECEIPTS.carbon.size_bytes() == before
    assert client.post("/mcp/", content=b"{}", headers=h).status_code != 413


def test_f11_the_61st_call_in_a_minute_gets_429_and_another_address_does_not(web, client):
    h = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    codes = [client.post("/mcp/", content=b"{}", headers=h).status_code for _ in range(61)]
    assert 429 not in codes[:60] and codes[60] == 429
    assert "minute" in client.post("/mcp/", content=b"{}", headers=h).json()["detail"]
    web._MCP_CALLS[next(iter(web._MCP_CALLS))] = []            # a minute later
    assert client.post("/mcp/", content=b"{}", headers=h).status_code != 429


def test_f11_the_address_rule_is_the_one_of_the_visitor_limit(web, client, monkeypatch):
    monkeypatch.setattr(web, "BEHIND_PROXY", True)
    h = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    for i in range(60):
        client.post("/mcp/", content=b"{}", headers={**h, "X-Forwarded-For": "9.9.9.9"})
    assert client.post("/mcp/", content=b"{}", headers={**h, "X-Forwarded-For": "9.9.9.9"}).status_code == 429
    assert client.post("/mcp/", content=b"{}", headers={**h, "X-Forwarded-For": "8.8.8.8"}).status_code != 429


def mcp():
    srv, r = mcp_server.build(signer=Signer(Ed25519PrivateKey.generate()))
    sent = []
    for name in ("create_payout", "create_refund", "accept_dispute_claim"):
        orig = getattr(r.paypal, name)
        setattr(r.paypal, name, lambda *a, _o=orig, _n=name, **k: (sent.append(_n), _o(*a, **k))[1])
    return srv, r, sent


async def call(srv, name, **args):
    out = await srv.call_tool(name, args)
    return json.loads(out.content[0].text) if hasattr(out, "content") else json.loads(out[0][0].text)


def run(coro):
    import asyncio
    return asyncio.run(coro)


def test_f11_the_book_size_is_counted_as_it_grows():
    book = CarbonCopy(Signer(Ed25519PrivateKey.generate()))
    assert book.size_bytes() == 0
    book.append("note", {"type": "note", "x": "y" * 1000})
    one = book.size_bytes()
    assert one > 1000
    book.append("note", {"type": "note", "x": "y" * 1000})
    assert one * 2 - 100 < book.size_bytes() < one * 2 + 100
    assert abs(book.size_bytes() - len(json.dumps(book.receipts(), separators=(",", ":")))) < 10


def test_f11_past_the_cap_money_tools_refuse_nothing_is_forwarded_and_the_book_still_verifies():
    srv, r, sent = mcp()
    r.mcp_cap_bytes = 100_000
    pay = dict(vendor="Blue Ridge Finishes", receiver_email="orders@blueridgefinishes.com", amount=10.0, invoice_number="INV-X-1")
    first = run(call(srv, "create_payout", **pay))              # under the cap: it is judged and sealed as always
    assert mcp_server.BOOK_FULL not in json.dumps(first) and len(r.carbon.receipts()) > 1
    run(call(srv, "update_vendor_payee", vendor="Blue Ridge Finishes", new_paypal_email="a@example.test", reason="Z" * 120_000))
    assert r.carbon.size_bytes() >= r.mcp_cap_bytes
    n, ledger, sent_before = len(r.carbon.receipts()), len(r.ledger), len(sent)
    for tool, args in (("create_payout", pay), ("create_refund", {"capture_id": "C1", "amount": 1.0}),
                       ("accept_dispute_claim", {"dispute_id": "D1"}),
                       ("update_vendor_payee", {"vendor": "Blue Ridge Finishes", "new_paypal_email": "b@example.test"})):
        out = run(call(srv, tool, **args))
        assert out["blocked_by_receipts"] and out["why"] == [mcp_server.BOOK_FULL], tool
    assert len(r.carbon.receipts()) == n and len(r.ledger) == ledger and len(sent) == sent_before
    out = run(call(srv, "list_vendors"))                         # a read-only tool writes receipts too: it refuses as well
    assert out["blocked_by_receipts"] and out["why"] == [mcp_server.BOOK_FULL] and len(r.carbon.receipts()) == n
    book = run(call(srv, "carbon_book"))                         # only the book still answers, and writes nothing
    assert verify(book)["intact"] is True and book["head"]["count"] == n
    assert len(run(call(srv, "receipts_holds"))) >= 1


def test_f11_an_approval_of_an_mcp_hold_is_refused_while_the_book_is_full(web, client, monkeypatch):
    monkeypatch.setattr(web, "MCP_ON_PHONE", True)
    r = web.MCP_SESSION["r"]
    old_cap = getattr(r, "mcp_cap_bytes", None)
    r.holds.append({"id": "capfull1", "tool": "create_payout", "args": {"vendor": "v", "receiver_email": "a@b.test", "amount": 1.0,
                                                                        "invoice_number": "I"}, "why": ["x"], "status": "WAITING"})
    r.mcp_cap_bytes = 1
    try:
        n = r.carbon.size_bytes()
        res = client.post("/api/approve", json={"session": "mcp", "hold_id": "capfull1"})
        assert res.status_code == 409 and "book is full" in res.json()["detail"]
        assert r.carbon.size_bytes() == n and r.holds[-1]["status"] == "WAITING"
    finally:
        r.mcp_cap_bytes = old_cap
        r.holds[:] = [h for h in r.holds if h["id"] != "capfull1"]
