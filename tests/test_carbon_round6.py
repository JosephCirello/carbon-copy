"""Task 21: the fourth attacker round's twelve findings (Requirement 19). One or more tests for each.

The stand-in PayPal, no network, no keys: signers are made in memory. The browser parts run under node.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from receipts import mcp_server, rules  # noqa: E402
from receipts.carbon import WHY_BIG_NUMBER, CarbonCopy, Signer, load_json_text, verify  # noqa: E402
from tests.test_carbon_round4 import HOSTED, NODE, cli, download, needs_node, run_page, small_book  # noqa: E402
from tests.readme_counts import assert_readme_counts_match, assert_spec_changes_match  # noqa: E402
from tests.test_carbon_round5 import call, run  # noqa: E402

README = (ROOT / "README.md").read_text(encoding="utf-8")
DAY, MODEL = "S14_crossed_in_the_mail", "glm-5.3"
PAY = dict(vendor="Ashwood Timber Co.", receiver_email="billing@ashwoodtimberco.com", memo="task 21")
CHANGED_STAMP = "a stamp on your device is damaged or forged"


def workspace():
    srv, r = mcp_server.build(signer=Signer(Ed25519PrivateKey.generate()))
    return srv, r


def held(r, invoice: str, amount: float = 9000.0) -> str:
    h = r.call("create_payout", {**PAY, "invoice_number": invoice, "amount": amount})
    assert h.get("held_by_receipts"), h
    return h["hold_id"]


def owner_actions(r) -> list[str]:
    return [x["event"]["action"] for x in r.carbon.receipts() if x["kind"] == "owner"]


def paid(r, invoice: str) -> list[dict]:
    return [h for h in r.paypal.history if h["invoice"] == invoice]


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
def client(web, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(web.time, "sleep", lambda _s: None)          # a replay is not slowed down
    web.VISITORS.clear()
    web._NEW_BY_ADDRESS.clear()
    web._MCP_CALLS.clear()
    yield TestClient(web.app, raise_server_exceptions=False)
    web.VISITORS.clear()
    web._NEW_BY_ADDRESS.clear()
    web._MCP_CALLS.clear()


def start_run(client, mode: str = "enforce", headers=None):
    """A recorded run (the one with the most trap attempts in that arm); returns (response, session id)."""
    rows = client.get("/api/recorded", params={"scenario": DAY, "model": MODEL}).json()
    line = sorted((r for r in rows if r["mode"] == mode), key=lambda r: -(r["attempts"] or 0))[0]["line"]
    res = client.get("/api/replay", params={"line": line, "speed": 1000}, headers=headers or {})
    sid = None
    if res.status_code == 200:
        sid = next(json.loads(ln[5:])["session"] for ln in res.text.splitlines() if ln.startswith("data:") and '"type": "session"' in ln)
    return res, sid


def waiting(client) -> list[dict]:
    return [h for h in client.get("/api/holds").json() if h["status"] == "WAITING"]


def visitor_of(web, client):
    return web.VISITORS[client.cookies[web.VISITOR_COOKIE]]


def age(visitor, seconds: float) -> None:
    visitor.seen -= seconds
    for s in visitor.sessions.values():
        s["t"] -= seconds


# ---- 1. the owner's tap looks again --------------------------------------------------------------------------------
def test_two_holds_for_one_bill_approved_one_after_the_other_pay_it_once_and_the_second_tap_is_refused():
    srv, r = workspace()
    h1, h2 = held(r, "INV-T21-1"), held(r, "INV-T21-1")
    first = r.approve(h1)
    assert first["batch_status"] == "SUCCESS" and len(paid(r, "INV-T21-1")) == 1
    second = r.approve(h2)
    assert second["refused_at_tap"] is True and second["error"] == "INV-T21-1 was paid while this was waiting"
    assert "payout_batch_id" not in second and len(paid(r, "INV-T21-1")) == 1               # PayPal paid it once
    assert owner_actions(r) == ["approved", "sent", "approved", "refused_at_tap"]
    last = r.carbon.receipts()[-1]["event"]
    assert last["reason"] == "INV-T21-1 was paid while this was waiting"
    hold = next(h for h in r.holds if h["id"] == h2)
    assert hold["status"] == "APPROVED" and hold["result"] == {"error": "INV-T21-1 was paid while this was waiting", "refused_at_tap": True}
    assert r.approve(h2) == {"error": "no such waiting hold"}                               # decided once
    assert verify(r.carbon.book(), [second["stamp"]])["intact"] and second["stamp"]["count"] == len(r.carbon.receipts())


def test_a_hold_approved_after_the_same_bill_was_paid_another_way_is_refused():
    srv, r = workspace()
    hid = held(r, "INV-T21-2")
    ok = r.call("create_payout", {**PAY, "invoice_number": "INV-T21-2", "amount": 900.0})     # smaller, so allowed: the bill is paid
    assert ok["batch_status"] == "SUCCESS"
    out = r.approve(hid)
    assert out["refused_at_tap"] and out["error"] == "INV-T21-2 was paid while this was waiting"
    assert len(paid(r, "INV-T21-2")) == 1 and owner_actions(r) == ["approved", "refused_at_tap"]


def test_an_ordinary_hold_is_still_sent_at_the_tap_and_what_it_was_held_for_does_not_refuse_it():
    srv, r = workspace()
    hid = held(r, "INV-T21-3")                          # held only for being over the owner's limit
    out = r.approve(hid)
    assert out["batch_status"] == "SUCCESS" and "refused_at_tap" not in out and owner_actions(r) == ["approved", "sent"]


def test_a_payment_that_would_now_be_blocked_is_not_sent_and_says_why():
    srv, r = workspace()
    hid = held(r, "INV-T21-4")
    r.desk.vendor("Ashwood Timber Co.")["paypal_email"] = "changed@elsewhere.example"           # the payee on record moved while it waited
    out = r.approve(hid)
    assert out["refused_at_tap"] and "PayPal on record" in out["error"] and not paid(r, "INV-T21-4")


def test_the_card_says_before_the_tap_that_another_hold_waits_and_that_the_bill_was_paid_since():
    srv, r = workspace()
    h1, h2 = held(r, "INV-T21-5"), held(r, "INV-T21-5")
    note = r.hold_notes(next(h for h in r.holds if h["id"] == h1))
    assert len(note) == 1 and "Another payment for INV-T21-5 is also waiting" in note[0]
    r.approve(h1)
    after = r.hold_notes(next(h for h in r.holds if h["id"] == h2))
    assert after == ["If you approve this now it will be refused: INV-T21-5 was paid while this was waiting."]
    other = held(r, "INV-T21-6")
    assert r.hold_notes(next(h for h in r.holds if h["id"] == other)) == []                  # nothing to warn about


def test_the_phone_gets_the_notes_and_the_refusal_reason(web, monkeypatch):
    from fastapi.testclient import TestClient
    web.VISITORS.clear()
    r = web.MCP_RECEIPTS
    before = list(r.holds)
    monkeypatch.setattr(web, "MCP_ON_PHONE", True)
    try:
        h1, h2 = held(r, "INV-T21-7"), held(r, "INV-T21-7")
        c = TestClient(web.app, raise_server_exceptions=False)
        rows = {h["id"]: h for h in c.get("/api/holds").json()}
        assert rows[h1]["notes"] and rows[h2]["notes"]
        assert c.post("/api/approve", json={"session": "mcp", "hold_id": h1}).json()["batch_status"] == "SUCCESS"
        res = c.post("/api/approve", json={"session": "mcp", "hold_id": h2})
        assert res.status_code == 200 and res.json()["error"] == "INV-T21-7 was paid while this was waiting" and res.json()["stamp"]["public_key"]
        row = next(h for h in c.get("/api/holds").json() if h["id"] == h2)
        assert row["status"] == "APPROVED" and row["result"]["refused_at_tap"] and row["result"]["error"].startswith("INV-T21-7 was paid")
    finally:
        r.holds[:] = before
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert "refused at the tap" in js and "hold-note" in js and "h.notes" in js


def test_when_the_records_cannot_be_read_at_the_tap_nothing_is_sealed_or_sent():
    srv, r = workspace()
    hid = held(r, "INV-T21-8")
    real, n = r.paypal.payout_records, len(r.carbon.receipts())
    r.paypal.payout_records = lambda *_a, **_k: (_ for _ in ()).throw(OSError("no route to PayPal"))
    out = r.approve(hid)
    assert "could not be read" in out["error"] and "Nothing was sent" in out["error"]
    assert len(r.carbon.receipts()) == n and next(h for h in r.holds if h["id"] == hid)["status"] == "WAITING"
    r.paypal.payout_records = real
    assert r.approve(hid)["batch_status"] == "SUCCESS"                                          # she can tap again


# ---- 2. "not_sent" only for a send that never left ---------------------------------------------------------------
def test_a_timeout_after_paypal_took_the_money_is_sealed_no_answer_then_sent_with_paypals_id():
    srv, r = workspace()
    hid = held(r, "INV-T21-9")
    real = r.paypal.create_payout

    def moves_money_then_times_out(*a, **k):
        real(*a, **k)
        raise TimeoutError("read timed out")
    r.paypal.create_payout = moves_money_then_times_out
    out = r.approve(hid)
    assert owner_actions(r) == ["approved", "no_answer", "sent"] and "not_sent" not in owner_actions(r)
    in_paypal = paid(r, "INV-T21-9")
    assert len(in_paypal) == 1 and out["payout_batch_id"] == in_paypal[0]["id"] and "error" not in out
    sent = r.carbon.receipts()[-1]["event"]
    assert sent["action"] == "sent" and in_paypal[0]["id"] in json.dumps(sent["result"])
    noans = [x["event"] for x in r.carbon.receipts() if x["event"].get("action") == "no_answer"][0]
    assert noans["error"] == "PayPal did not answer; it may have been sent"
    assert next(h for h in r.holds if h["id"] == hid)["result"]["payout_batch_id"] == in_paypal[0]["id"]
    assert [l for l in r.ledger if l["kind"] == "payout" and l["ref"] == "INV-T21-9"]            # the money is in the run's ledger
    assert verify(r.carbon.book(), [out["stamp"]])["intact"]


def test_a_timeout_before_paypal_took_anything_is_sealed_no_answer_then_not_found():
    srv, r = workspace()
    hid = held(r, "INV-T21-10")
    r.paypal.create_payout = lambda *a, **k: (_ for _ in ()).throw(ConnectionError("connection dropped"))
    out = r.approve(hid)
    assert owner_actions(r) == ["approved", "no_answer", "not_found"] and not paid(r, "INV-T21-10")
    assert out["no_answer"] is True and "not found" in out["error"] and "PayPal did not answer" in out["error"]
    assert not [l for l in r.ledger if l["ref"] == "INV-T21-10"]


def test_when_the_lookup_fails_too_it_says_so_and_does_not_guess():
    srv, r = workspace()
    hid = held(r, "INV-T21-11")
    real_create, real_records = r.paypal.create_payout, r.paypal.payout_records

    def times_out_and_goes_dark(*a, **k):
        real_create(*a, **k)
        r.paypal.payout_records = lambda *_a, **_k: (_ for _ in ()).throw(OSError("down"))
        raise TimeoutError("read timed out")
    r.paypal.create_payout = times_out_and_goes_dark
    out = r.approve(hid)
    assert owner_actions(r) == ["approved", "no_answer", "lookup_failed"] and "Check PayPal before approving again" in out["error"]
    r.paypal.payout_records = real_records


def test_an_error_before_anything_left_is_still_not_sent():
    srv, r = workspace()
    hid = held(r, "INV-T21-12")
    r.paypal.create_payout = lambda *a, **k: (_ for _ in ()).throw(ValueError("PayPal could not read the amount"))
    out = r.approve(hid)
    assert owner_actions(r) == ["approved", "not_sent"] and out["error"] == "PayPal could not read the amount"


def test_a_refund_that_timed_out_after_it_was_taken_is_found_in_the_records():
    srv, r = workspace()
    cap = next(iter(r.paypal.orders.values()))["capture_id"]
    out = r.call("create_refund", {"capture_id": cap, "amount": 160.0})
    assert out.get("held_by_receipts"), out
    real = r.paypal.create_refund

    def takes_it_then_times_out(*a, **k):
        real(*a, **k)
        raise TimeoutError("read timed out")
    r.paypal.create_refund = takes_it_then_times_out
    res = r.approve(out["hold_id"])
    assert owner_actions(r) == ["approved", "no_answer", "sent"] and res["found_in_paypal_records"] is True


def test_the_phone_has_words_for_each_of_these():
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    for word in ("no_answer", "not_found", "lookup_failed", "refused_at_tap"):
        assert word in js, word
    assert "Approved, but " in js and "may have been sent" in js


# ---- 3. the address is the one the proxy added -----------------------------------------------------------------------
def request_with(xff, host="198.51.100.1"):
    from starlette.requests import Request
    headers = [(b"x-forwarded-for", xff.encode())] if xff is not None else []
    return Request({"type": "http", "headers": headers, "client": (host, 1234)})


def test_behind_the_proxy_the_address_is_the_last_entry_never_the_first(web, monkeypatch):
    monkeypatch.setattr(web, "BEHIND_PROXY", True)
    monkeypatch.setattr(web, "PROXY_HOPS", 1)
    assert web._client_address(request_with("spoofed, 203.0.113.9")) == "203.0.113.9"
    assert web._client_address(request_with("a, b, c, 203.0.113.9")) == "203.0.113.9"
    assert web._client_address(request_with("203.0.113.9")) == "203.0.113.9"
    assert web._client_address(request_with(None)) == "198.51.100.1"                           # no header: the socket's
    monkeypatch.setattr(web, "PROXY_HOPS", 2)                                                  # two proxies: the second from the right
    assert web._client_address(request_with("spoofed, 203.0.113.9, 10.0.0.2")) == "203.0.113.9"
    assert web._client_address(request_with("10.0.0.2")) == "198.51.100.1"                     # fewer entries than proxies: not trusted
    monkeypatch.setattr(web, "BEHIND_PROXY", False)
    assert web._client_address(request_with("spoofed, 203.0.113.9")) == "198.51.100.1"         # no proxy: the header is ignored


def test_the_proxy_hops_setting_is_read_from_the_environment():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'os.environ.get("RECEIPTS_PROXY_HOPS", "1")' in src and "PROXY_HOPS = max(1," in src


def test_a_spoofed_first_entry_does_not_get_round_the_60_a_minute_limit(web, client, monkeypatch):
    monkeypatch.setattr(web, "BEHIND_PROXY", True)
    h = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    codes = [client.post("/mcp/", content=b"{}", headers={**h, "X-Forwarded-For": f"203.0.{i // 250}.{i % 250}, 198.51.100.8"}).status_code
             for i in range(70)]
    assert 429 not in codes[:60] and codes[60:].count(429) == 10                                # one real address, stopped after 60
    other = client.post("/mcp/", content=b"{}", headers={**h, "X-Forwarded-For": "1.1.1.1, 198.51.100.9"}).status_code
    assert other != 429                                                                         # another real address is counted on its own


def test_a_spoofed_first_entry_does_not_get_round_the_30_new_visitors_limit(web, client, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(web, "BEHIND_PROXY", True)
    codes = []
    for i in range(34):
        c = TestClient(web.app)                                                                 # a new browser each time: a new visitor
        res, _ = start_run(c, "observe", {"X-Forwarded-For": f"203.0.113.{i}, 198.51.100.8"})
        codes.append(res.status_code)
    assert codes == [200] * 30 + [429] * 4 and len(web.VISITORS) == 30


# ---- 4. past the cap every MCP tool but carbon_book refuses ---------------------------------------------------------
TOOL_ARGS = {
    "list_vendors": {}, "list_recent_orders": {}, "list_transactions": {}, "payments_book": {}, "get_order": {"id": "x"},
    "create_refund": {"capture_id": "C1", "amount": 1.0}, "get_dispute": {"dispute_id": "D1"},
    "accept_dispute_claim": {"dispute_id": "D1"}, "get_shipment_tracking": {"order_id": "O1"},
    "create_payout": {**PAY, "amount": 10.0, "invoice_number": "INV-T21-CAP"},
    "update_vendor_payee": {"vendor": "Ashwood Timber Co.", "new_paypal_email": "x@example.test"}, "receipts_holds": {},
}


def test_past_the_cap_every_mcp_tool_refuses_except_carbon_book_and_the_book_stops_growing():
    srv, r = workspace()
    import asyncio
    names = {t.name for t in asyncio.run(srv.list_tools())}
    assert names == set(TOOL_ARGS) | {"carbon_book"}, names ^ (set(TOOL_ARGS) | {"carbon_book"})
    run(call(srv, "get_order", id="warm up"))
    r.mcp_cap_bytes = 1                                                                         # the book is over its cap now
    n = len(r.carbon.receipts())
    for tool, args in TOOL_ARGS.items():
        out = run(call(srv, tool, **args))
        assert out["blocked_by_receipts"] and out["why"] == [mcp_server.BOOK_FULL], tool
    assert len(r.carbon.receipts()) == n and not paid(r, "INV-T21-CAP")
    book = run(call(srv, "carbon_book"))                                                        # the one tool that still answers
    assert book["head"]["count"] == n and verify(book)["intact"]


def test_the_readme_sentence_about_the_cap_is_the_behaviour():
    limits = README.split("## Limits we know about")[1]
    assert "every tool except `carbon_book` refuses" in limits and "read-only tools and `carbon_book` still answer" not in limits


# ---- 5, 6, 7, 8. the clock and the table ---------------------------------------------------------------------------
def test_a_visitor_with_a_waiting_hold_is_not_forgotten_for_idleness_before_its_24_hours(web, client):
    start_run(client)
    assert waiting(client)
    age(visitor_of(web, client), 4 * 3600)                                                       # silent for 4 hours (the idle drop is 3)
    assert waiting(client), "a waiting payment was forgotten after 4 idle hours"
    age(visitor_of(web, client), 18 * 3600)                                                      # 22 hours in all
    assert waiting(client)
    age(visitor_of(web, client), 3 * 3600)                                                       # 25 hours: its 24 hours are up
    assert not waiting(client) and not web.VISITORS


def test_a_visitor_with_nothing_waiting_is_still_forgotten_when_idle(web, client):
    start_run(client, "observe")
    assert web.VISITORS
    age(visitor_of(web, client), 4 * 3600)
    assert client.get("/api/holds").json() == [] and not web.VISITORS


def test_newcomers_push_out_idle_visitors_first_then_runs_and_a_waiting_payment_last(web, client, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(web, "MAX_VISITORS", 3)
    maya = client
    start_run(maya)                                                                              # the oldest, a payment waiting
    assert waiting(maya)
    runner = TestClient(web.app)
    start_run(runner, "observe")                                                                 # a young run, nothing waiting
    nothing = TestClient(web.app)
    start_run(nothing, "observe")
    age(visitor_of(web, nothing), web.SESSION_MAX_AGE_S + 60)                                    # its run is over: nothing kept at all
    first_new = TestClient(web.app)
    start_run(first_new, "observe")                                                              # the fourth visitor: someone goes
    assert len(web.VISITORS) == 3
    assert waiting(maya) and runner.cookies[web.VISITOR_COOKIE] in web.VISITORS and nothing.cookies[web.VISITOR_COOKIE] not in web.VISITORS
    second_new = TestClient(web.app)
    start_run(second_new, "observe")                                                             # now only runs and Maya: the least recently seen run goes
    assert len(web.VISITORS) == 3 and waiting(maya)
    assert runner.cookies[web.VISITOR_COOKIE] not in web.VISITORS
    for _ in range(6):                                                                           # a crowd of newcomers with only runs
        start_run(TestClient(web.app), "observe")
    assert waiting(maya), "a visitor with a waiting payment was pushed out by visitors with only runs"


def test_a_waiting_hold_outranks_a_young_run_so_a_visitor_with_only_a_run_goes_first(web, client, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(web, "MAX_VISITORS", 2)
    young = TestClient(web.app)
    start_run(young, "observe")                                                                  # older than Maya, with a young run
    start_run(client)                                                                            # Maya: a payment waiting
    newcomer = TestClient(web.app)
    start_run(newcomer, "observe")
    assert waiting(client) and young.cookies[web.VISITOR_COOKIE] not in web.VISITORS


def test_a_tap_on_a_hold_that_does_not_exist_does_not_keep_a_run_alive(web, client):
    _, sid = start_run(client)
    for h in waiting(client):
        assert client.post("/api/decline", json={"session": sid, "hold_id": h["id"]}).status_code == 200
    run_ = visitor_of(web, client).sessions[sid]
    age(visitor_of(web, client), 50 * 60)
    t = run_["t"]
    for verb in ("decline", "approve"):
        res = client.post(f"/api/{verb}", json={"session": sid, "hold_id": "does-not-exist"})
        assert res.status_code == 200 and res.json()["error"] == "no such waiting hold"
    assert run_["t"] == t, "a tap on nothing restarted the run's clock"
    age(visitor_of(web, client), 15 * 60)                                                        # 65 minutes since its real last tap
    assert client.get("/api/carbon", params={"sid": sid}).status_code == 404


def test_a_tap_on_a_hold_that_was_already_decided_does_not_keep_a_run_alive(web, client):
    _, sid = start_run(client)
    hold = waiting(client)[0]
    others = [h for h in waiting(client) if h["id"] != hold["id"]]
    for h in others:
        client.post("/api/decline", json={"session": sid, "hold_id": h["id"]})
    assert client.post("/api/decline", json={"session": sid, "hold_id": hold["id"]}).status_code == 200
    age(visitor_of(web, client), 50 * 60)
    t = visitor_of(web, client).sessions[sid]["t"]
    client.post("/api/decline", json={"session": sid, "hold_id": hold["id"]})                    # it is decided: not a real tap any more
    assert visitor_of(web, client).sessions[sid]["t"] == t


def test_a_real_tap_still_restarts_the_clock_before_it_decides(web, client, monkeypatch):
    _, sid = start_run(client)
    r = visitor_of(web, client).sessions[sid]["r"]
    age(visitor_of(web, client), 2 * 3600)
    seen = {}
    real = r.decline

    def spy(hold_id):
        seen["t_when_deciding"] = visitor_of(web, client).sessions[sid]["t"]
        return real(hold_id)
    r.decline = spy
    hold = waiting(client)[0]
    before = visitor_of(web, client).sessions[sid]["t"]
    assert client.post("/api/decline", json={"session": sid, "hold_id": hold["id"]}).status_code == 200
    assert seen["t_when_deciding"] > before + 3600                                               # restarted before the decision was made


def test_the_run_cap_drops_the_oldest_run_with_nothing_waiting_and_spares_one_with_a_waiting_payment(web, client, monkeypatch):
    monkeypatch.setattr(web, "MAX_SESSIONS_PER_VISITOR", 3)
    _, first = start_run(client)                                                                 # a payment waiting
    assert waiting(client)
    _, b = start_run(client, "observe")
    _, c = start_run(client, "observe")
    _, d = start_run(client, "observe")                                                          # the fourth run: one must go
    sessions = visitor_of(web, client).sessions
    assert set(sessions) == {first, c, d}, "the run with a waiting payment, not the oldest idle run, was dropped"
    assert waiting(client)
    start_run(client, "observe")
    assert first in visitor_of(web, client).sessions and len(visitor_of(web, client).sessions) == 3


def test_the_run_cap_drops_a_run_with_a_waiting_payment_only_when_every_run_has_one(web, client, monkeypatch):
    monkeypatch.setattr(web, "MAX_SESSIONS_PER_VISITOR", 3)
    sids = [start_run(client)[1] for _ in range(3)]
    assert all(any(h["session"] == s for h in waiting(client)) for s in sids)
    _, fourth = start_run(client)
    assert set(visitor_of(web, client).sessions) == {sids[1], sids[2], fourth}                  # every run waited: the oldest goes


# ---- 9. verify.html checks against the published key -----------------------------------------------------------------
@needs_node
def test_verify_html_checks_against_the_published_key_by_default(tmp_path):
    c = small_book()
    d = download(c)                                                                              # signed with a key of its own, and says so
    forged = json.dumps(d)
    got = run_page(tmp_path, [forged])[0]
    flat = "\n".join(got["result"])
    assert "stamp bad|CHANGED" in flat and "signed with a different key than the published one" in flat and "INTACT" not in flat
    w, out = cli_text(tmp_path, forged, "--key-file", ROOT / "HOSTED_KEY.txt")
    assert w == 1 and "different key" in out                                                     # the command line says the same
    assert HOSTED in "\n".join(got["keys"]) and "The key this check trusts (the published one)" in "\n".join(got["keys"])


@needs_node
def test_verify_html_switch_checks_against_the_files_key_and_says_what_that_is_worth(tmp_path):
    d = download(small_book())
    got = run_page(tmp_path, [json.dumps(d)], use_file_key=True)[0]
    flat = "\n".join(got["result"])
    assert "stamp ok|INTACT" in flat
    assert "this check trusts because you chose to" in "\n".join(got["keys"])
    html = (ROOT / "verify.html").read_text(encoding="utf-8")
    assert "Use the key in this file instead (for a book from your own server)" in html
    assert "only as good as where the file came from" in html
    assert "the key published for the hosted demo" in html.lower() and "built into this page" in html


def cli_text(tmp_path, text, *flags):
    f = tmp_path / "dl.json"
    f.write_text(text, encoding="utf-8")
    done = subprocess.run([sys.executable, "-m", "receipts.carbon", "verify", str(f), *map(str, flags)], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", timeout=120)
    return done.returncode, done.stdout.strip()


# ---- 10. verify.html and the command line agree -------------------------------------------------------------------------
@needs_node
@pytest.mark.parametrize("stamps_text", ["[]", "null", "[1]"])
def test_stamps_written_as_text_read_changed_in_the_page_and_on_the_command_line_with_the_same_reason(tmp_path, stamps_text):
    c = small_book()
    d = download(c)
    for stamps in (stamps_text, json.dumps([c.stamp()])):                                        # also a real stamp list written as text
        text = json.dumps({**d, "stamps": stamps})
        page = "\n".join(run_page(tmp_path, [text], use_file_key=True)[0]["result"])
        code, out = cli_text(tmp_path, text)
        assert "stamp bad|CHANGED" in page and CHANGED_STAMP in page
        assert code == 1 and out.splitlines()[0] == CHANGED_STAMP


@needs_node
def test_stamps_that_are_a_real_list_or_nothing_still_read_as_before(tmp_path):
    c = small_book()
    d = download(c)
    for stamps, want in ((d["stamps"], "INTACT"), ([], "INTACT"), (None, "INTACT")):
        text = json.dumps({**d, "stamps": stamps})
        page = "\n".join(run_page(tmp_path, [text], use_file_key=True)[0]["result"])
        code, _ = cli_text(tmp_path, text)
        assert want in page and code == 0


def _text_with_number(d: dict, number: str) -> str:
    text = json.dumps(d)
    return text.replace('"trusted_key"', '"extra": ' + number + ', "trusted_key"', 1)


@needs_node
@pytest.mark.parametrize("number,flagged", [("9007199254740993", True), ("9007199254740992", True), ("-9007199254740992", True),
                                            ("123456789012345678901234567890", True), ("9007199254740991", False),
                                            ("-9007199254740991", False), ("1700000000000", False)])
def test_a_whole_number_past_2_53_reads_changed_in_both_with_the_same_reason(tmp_path, number, flagged):
    text = _text_with_number(download(small_book()), number)
    page = "\n".join(run_page(tmp_path, [text], use_file_key=True)[0]["result"])
    code, out = cli_text(tmp_path, text)
    if flagged:
        assert "stamp bad|CHANGED" in page and WHY_BIG_NUMBER in page
        assert code == 1 and out == WHY_BIG_NUMBER
    else:                                                                                        # the extra field only makes the file carry an unknown key: still intact
        assert WHY_BIG_NUMBER not in page and WHY_BIG_NUMBER not in out


@needs_node
def test_a_number_inside_text_is_not_a_number_and_the_page_reads_the_file_as_written(tmp_path):
    d = download(small_book())
    in_text = _text_with_number(d, '"9007199254740993"')
    page = "\n".join(run_page(tmp_path, [in_text], use_file_key=True)[0]["result"])
    code, out = cli_text(tmp_path, in_text)
    assert WHY_BIG_NUMBER not in page and WHY_BIG_NUMBER not in out and "INTACT" in page and code == 0
    # the attack's own shape: the signed number ...992, the file's text ...993 (JavaScript rounds both to the same double)
    c = CarbonCopy(Signer(Ed25519PrivateKey.generate()))
    c.append("note", {"type": "note", "text": "x", "t": 1_700_000_000})
    book = c.book()
    text = json.dumps({"book": book, "stamps": [], "trusted_key": book["public_key"]}).replace('"n": 1,', '"n": 1, "big": 9007199254740993,', 1)
    assert "9007199254740993" in text
    page = "\n".join(run_page(tmp_path, [text], use_file_key=True)[0]["result"])
    code, out = cli_text(tmp_path, text)
    assert "CHANGED" in page and WHY_BIG_NUMBER in page and code == 1 and out == WHY_BIG_NUMBER


BIG_CASES = ['9007199254740991', '9007199254740992', '-9007199254740992', '[1,2,{"a":12345678901234567890}]', '"9007199254740993"',
             '{"k":"\\"9007199254740993"}', '{"9007199254740993":1}', '1.5e300', '12345678901234567.5', '[0.1234567890123456789]',
             '[9007199254740992.0]', '{"a":"x","b":[9007199254740993]}', '[1e999]', '123', '{"a":' + "9" * 5000 + "}", '"' + "7" * 20 + '"']


@needs_node
def test_the_page_and_python_find_the_same_big_numbers_in_the_same_texts(tmp_path):
    script = tmp_path / "t.js"
    script.write_text('const api = require(process.argv[2]);\nconst cases = JSON.parse(require("fs").readFileSync(process.argv[3], "utf8"));\n'
                      'console.log(JSON.stringify(cases.map((t) => api.hasUnsafeInteger(t))));\n', encoding="utf-8")
    (tmp_path / "c.json").write_text(json.dumps(BIG_CASES), encoding="utf-8")
    done = subprocess.run([NODE, str(script), str(ROOT / "static" / "carbon_verify.js"), str(tmp_path / "c.json")], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    js = json.loads(done.stdout)
    py = [load_json_text(t)[1] for t in BIG_CASES]
    assert js == py, [(t[:40], j, p) for t, j, p in zip(BIG_CASES, js, py) if j != p]
    assert py[:3] == [False, True, True] and py[4] is False and py[5] is False and py[-2] is True


def test_a_huge_number_is_never_turned_into_a_python_number():
    parsed, big = load_json_text('{"a": ' + "9" * 6000 + "}")                                  # past Python's own limit on long numbers
    assert big is True and parsed == {"a": 0}


def test_the_command_line_reads_the_stamps_file_the_same_way(tmp_path):
    c = small_book()
    d = download(c, with_stamp=False)
    f = tmp_path / "b.json"
    f.write_text(json.dumps(d), encoding="utf-8")
    s = tmp_path / "s.json"
    s.write_text("[" + "9" * 20 + "]", encoding="utf-8")
    code, out, _ = cli(f, "--stamps", s)
    assert code == 1 and out.strip() == WHY_BIG_NUMBER


# ---- 11. a cookie the server never issued makes no visitor ------------------------------------------------------------------
def test_a_made_up_cookie_makes_no_visitor_and_a_policy_request_is_refused(web, client):
    body = {"policy": web.DEFAULT_RULES["policy"], "english": "x", "sources": {}, "compiled_by": "owner"}
    made_up = {"Cookie": f"{web.VISITOR_COOKIE}=" + "A" * 30}
    for headers in ({}, made_up):
        res = client.post("/api/policy", json=body, headers=headers)
        assert res.status_code == 400 and "load the page first" in res.json()["detail"].lower()
    assert not web.VISITORS and not web._NEW_BY_ADDRESS


def test_a_cookie_the_server_issued_makes_no_visitor_until_the_visitor_acts(web, client):
    client.get("/api/meta")
    assert web.VISITOR_COOKIE in client.cookies and not web.VISITORS         # loading the page creates nothing
    body = {"policy": web.DEFAULT_RULES["policy"], "english": "", "sources": {}, "compiled_by": "owner"}
    assert client.post("/api/policy", json=body).status_code == 200 and len(web.VISITORS) == 1      # task 22: a signed cookie may save rules before any run
    assert start_run(client, "observe")[0].status_code == 200 and len(web.VISITORS) == 1


def test_no_request_that_does_not_start_a_run_makes_a_visitor(web, client):
    made_up = {"Cookie": f"{web.VISITOR_COOKIE}=" + "B" * 30}
    for get in ("/api/policy", "/api/holds", "/api/carbon", "/api/ledger", "/api/meta", "/api/carbon/key"):
        assert client.get(get, headers=made_up).status_code == 200, get
    for post, body in (("/api/approve", {"session": "x", "hold_id": "y"}), ("/api/decline", {"session": "x", "hold_id": "y"})):
        assert client.post(post, json=body, headers=made_up).status_code == 404
    assert client.post("/api/reset", headers=made_up).status_code == 200
    assert not web.VISITORS and not web._NEW_BY_ADDRESS


def test_the_page_does_not_say_the_rules_are_in_force_when_the_server_did_not_keep_them():
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    i = js.index('$("#usePolicy").addEventListener')
    block = js[i:i + 1800]
    assert block.index("!res.ok") < block.index("In force for every run from now on.") and "j.detail" in block


# ---- 12. a payout or refund of zero is blocked ----------------------------------------------------------------------------
@pytest.mark.parametrize("amount", [0, 0.0, -0.0, "0", "0.00", "-0", "$0.00", 0.004, -1, -0.004])
def test_a_payout_of_zero_or_below_is_blocked_and_nothing_moves(amount):
    srv, r = workspace()
    moved = len(r.paypal.history)
    out = r.call("create_payout", {**PAY, "invoice_number": "INV-T21-Z", "amount": amount})
    assert out.get("blocked_by_receipts") and "the amount is not a positive number of dollars" in out["why"][0]
    assert r.verdicts[-1]["decision"] == "BLOCK" and r.verdicts[-1]["findings"][0]["code"] == "AMOUNT_NOT_A_NUMBER"
    assert len(r.paypal.history) == moved and r.ledger == []


def test_a_refund_of_zero_is_blocked_a_refund_with_no_amount_is_not_and_a_real_amount_is_not():
    srv, r = workspace()
    cap = next(iter(r.paypal.orders.values()))["capture_id"]
    for bad in (0, 0.0, -0.0, "0", -5):
        out = r.call("create_refund", {"capture_id": cap, "amount": bad})
        assert out.get("blocked_by_receipts") and "not a positive number of dollars" in out["why"][0], bad
    assert not r.call("create_refund", {"capture_id": cap}).get("blocked_by_receipts")             # a full refund: no amount
    assert not r.call("create_refund", {"capture_id": cap, "amount": 0.01}).get("blocked_by_receipts")


def test_the_amount_rule_itself():
    assert rules.amount_problem(0) and rules.amount_problem(-0.0) and rules.amount_problem("0.00") and rules.amount_problem(None)
    assert rules.amount_problem(0.01) is None and rules.amount_problem("$1,836.00") is None and rules.amount_problem(1e9) is None
    assert rules.amount_problem(float("nan")) and rules.amount_problem(float("inf"))


def test_zero_was_allowed_before_and_every_recorded_verdict_is_the_same_under_the_old_and_new_rules():
    """The proof is test_carbon_round3.py::test_f6_re_scoring_every_recorded_run_with_the_old_and_new_rules_gives_the_same_verdicts
    (results/episodes.jsonl and results/frontier, the rules before task 15, as task 15 left them, and now, in memory). It must exist."""
    src = (ROOT / "tests" / "test_carbon_round3.py").read_text(encoding="utf-8")
    assert "_task15_amount_problem" in src and "new == old == old15" in src


# ---- the spec and the README ----------------------------------------------------------------------------------------------
def test_the_spec_has_requirement_19_task_21_and_the_readme_counts_are_true():
    spec = ROOT / ".kiro" / "specs" / "carbon-copy"
    reqs = (spec / "requirements.md").read_text(encoding="utf-8")
    assert "### Requirement 19: the fourth attacker round's twelve findings" in reqs
    assert "## Task 21: the fourth attacker round's twelve findings" in (spec / "design.md").read_text(encoding="utf-8")
    tasks = (spec / "tasks.md").read_text(encoding="utf-8")
    assert "- [x] 21. The fourth attacker round's twelve findings" in tasks
    assert_readme_counts_match(README)       # the README's runs, tasks and requirements equal what the repository holds
    assert_spec_changes_match(README)
    assert re.search(r"^17\. \*\*The fourth attacker run's twelve findings\.\*\*", README, re.M)
    assert "fourth run twelve" in README and "not in the session records yet" not in README
    assert "(the fourth run's record is `23_` in the session records)" in README
    sessions = ROOT / "docs" / "kiro-sessions"
    assert (sessions / "23_agent_carbon_attacker_fourth_run.md").exists()
