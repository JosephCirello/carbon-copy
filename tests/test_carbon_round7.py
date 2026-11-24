"""Task 22: saving rules before a run (signed visitor cookie) and the instant between the tap's look and its send (one lock per run).

Amends Requirement 19, items 11 and 13. The stand-in PayPal, no network, no keys: signers are made in memory.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from receipts import mcp_server  # noqa: E402
from receipts.carbon import Signer  # noqa: E402
from tests.readme_counts import assert_readme_counts_match, assert_spec_changes_match  # noqa: E402

README = (ROOT / "README.md").read_text(encoding="utf-8")
PAY = dict(vendor="Ashwood Timber Co.", receiver_email="billing@ashwoodtimberco.com", memo="task 22")


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
def fresh(web):
    from fastapi.testclient import TestClient
    web.VISITORS.clear()
    web._NEW_BY_ADDRESS.clear()
    yield lambda: TestClient(web.app, raise_server_exceptions=False)
    web.VISITORS.clear()
    web._NEW_BY_ADDRESS.clear()


def body(web, english="Pay nothing over $4,000 without asking me."):
    return {"policy": web.DEFAULT_RULES["policy"], "english": english, "sources": {}, "compiled_by": "owner"}


# ---- 1. saving rules before a run ------------------------------------------------------------------------------------------
def test_a_fresh_page_load_creates_nothing_and_hands_out_a_signed_cookie(web, fresh):
    c = fresh()
    page = c.get("/")
    assert page.status_code == 200
    cookie = c.cookies[web.VISITOR_COOKIE]
    assert web.valid_visitor_cookie(cookie) and "." in cookie
    assert "HttpOnly" in page.headers["set-cookie"] and not web.VISITORS and not web._NEW_BY_ADDRESS


def test_a_fresh_page_load_then_a_rules_save_works_with_no_run(web, fresh):
    c = fresh()
    c.get("/")
    assert not web.VISITORS
    res = c.post("/api/policy", json=body(web, "my own rules"))
    assert res.status_code == 200 and res.json()["english"] == "my own rules"
    assert len(web.VISITORS) == 1 and c.cookies[web.VISITOR_COOKIE] in web.VISITORS
    assert c.get("/api/policy").json()["english"] == "my own rules"           # kept: the next request sees them
    assert c.post("/api/policy", json=body(web, "changed")).json()["english"] == "changed" and len(web.VISITORS) == 1
    other = fresh()
    other.get("/")
    assert other.get("/api/policy").json()["english"] == web.DEFAULT_RULES["english"]       # nobody else's change


def test_a_run_after_a_rules_save_uses_the_same_visitor_and_its_rules(web, fresh):
    c = fresh()
    c.get("/")
    c.post("/api/policy", json=body(web, "saved before the run"))
    (vid,) = list(web.VISITORS)
    rows = c.get("/api/recorded", params={"scenario": "S14_crossed_in_the_mail", "model": "glm-5.3"}).json()
    pick = sorted((r for r in rows if r["mode"] == "observe"), key=lambda r: -(r["attempts"] or 0))[0]
    assert c.get("/api/replay", params={"line": pick["line"], "speed": 1000}).status_code == 200
    assert list(web.VISITORS) == [vid] and web.VISITORS[vid].rules["english"] == "saved before the run"


@pytest.mark.parametrize("kind", ["none", "unsigned", "wrong_tag", "other_key", "no_tag", "id_only_tag", "non_ascii", "short_id", "tag_of_another_id"])
def test_a_hand_written_cookie_is_refused_and_creates_nothing(web, fresh, kind):
    import base64, hashlib, hmac
    c = fresh()
    vid = "A" * 43
    other = hmac.new(b"someone else's key", vid.encode(), hashlib.sha256).digest()
    cookies = {
        "none": None,
        "unsigned": vid,
        "wrong_tag": vid + "." + "B" * 43,
        "other_key": vid + "." + base64.urlsafe_b64encode(other).decode().rstrip("="),
        "no_tag": vid + ".",
        "id_only_tag": "." + web.sign_visitor_id(vid).split(".")[1],
        "non_ascii": vid + ".é" * 3,
        "short_id": web.sign_visitor_id("short"),
        "tag_of_another_id": "C" * 43 + "." + web.sign_visitor_id(vid).split(".")[1],
    }
    headers = {} if cookies[kind] is None else {"Cookie": f"{web.VISITOR_COOKIE}={cookies[kind]}".encode("utf-8")}
    res = c.post("/api/policy", json=body(web), headers=headers)
    assert res.status_code == 400 and "load the page first" in res.json()["detail"].lower()
    assert not web.VISITORS and not web._NEW_BY_ADDRESS
    if cookies[kind] is not None:
        assert res.headers["set-cookie"].startswith(web.VISITOR_COOKIE + "=")              # replaced with a signed one
        assert web.valid_visitor_cookie(res.headers["set-cookie"].split(";")[0].split("=", 1)[1])


def test_a_made_up_cookie_is_no_cookie_for_a_run_too_and_the_visitor_is_the_one_the_server_issued(web, fresh):
    c = fresh()
    made_up = "A" * 43
    rows = c.get("/api/recorded", params={"scenario": "S14_crossed_in_the_mail", "model": "glm-5.3"}).json()
    pick = sorted((r for r in rows if r["mode"] == "observe"), key=lambda r: -(r["attempts"] or 0))[0]
    assert c.get("/api/replay", params={"line": pick["line"], "speed": 1000}, headers={"Cookie": f"{web.VISITOR_COOKIE}={made_up}"}).status_code == 200
    assert made_up not in web.VISITORS and len(web.VISITORS) == 1 and all(web.valid_visitor_cookie(k) for k in web.VISITORS)


def test_rules_saves_count_against_the_per_address_limit_on_new_visitors(web, fresh):
    for _ in range(web.NEW_VISITORS_PER_ADDRESS):
        c = fresh()
        c.get("/")
        assert c.post("/api/policy", json=body(web)).status_code == 200
    c = fresh()
    c.get("/")
    res = c.post("/api/policy", json=body(web))
    assert res.status_code == 429 and "too many new visitors" in res.json()["detail"].lower()
    assert len(web.VISITORS) == web.NEW_VISITORS_PER_ADDRESS


def test_a_flood_of_page_loads_and_made_up_cookies_makes_no_visitor_and_pushes_no_one_out(web, fresh):
    maya = fresh()
    maya.get("/")
    maya.post("/api/policy", json=body(web, "maya's rules"))
    for i in range(web.MAX_VISITORS + 50):
        c = fresh()
        c.get("/")
        assert c.post("/api/policy", json=body(web), headers={"Cookie": f"{web.VISITOR_COOKIE}={i:024d}"}).status_code == 400
    assert len(web.VISITORS) == 1 and maya.get("/api/policy").json()["english"] == "maya's rules"


def test_a_request_that_does_not_save_or_run_creates_no_visitor_even_with_a_valid_cookie(web, fresh):
    c = fresh()
    c.get("/")
    for get in ("/api/policy", "/api/holds", "/api/carbon", "/api/ledger", "/api/meta"):
        assert c.get(get).status_code == 200, get
    assert c.post("/api/reset").status_code == 200
    assert c.post("/api/approve", json={"session": "x", "hold_id": "y"}).status_code == 404
    assert not web.VISITORS and not web._NEW_BY_ADDRESS


def test_the_cookie_key_is_derived_from_the_key_text_with_a_label_and_is_not_the_signing_key(web, monkeypatch):
    monkeypatch.setenv("CARBON_COPY_KEY", "a throwaway phrase for this test")
    first, second = web._cookie_key(), web._cookie_key()
    assert first == second and len(first) == 32                       # a restart with the same key text accepts the same cookies
    import hashlib
    assert first != hashlib.sha256(b"a throwaway phrase for this test").digest()      # not the plain hash of the key text
    monkeypatch.setenv("CARBON_COPY_KEY", "another phrase")
    assert web._cookie_key() != first
    monkeypatch.delenv("CARBON_COPY_KEY")
    assert web._cookie_key() != web._cookie_key()                     # no key text: made in memory, different every start


def test_the_cookie_key_never_reaches_a_file_a_log_or_an_error():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    uses = [ln for ln in src.splitlines() if "COOKIE_KEY" in ln]
    assert all(not re.search(r"(print|log|write|open|raise|detail)", ln) for ln in uses), uses


# ---- 2. the instant between the tap's look and its send ----------------------------------------------------------------
def workspace():
    return mcp_server.build(signer=Signer(Ed25519PrivateKey.generate()))


def held(r, invoice: str, amount: float = 9000.0) -> str:
    h = r.call("create_payout", {**PAY, "invoice_number": invoice, "amount": amount})
    assert h.get("held_by_receipts"), h
    return h["hold_id"]


def paid(r, invoice: str) -> list[dict]:
    return [h for h in r.paypal.history if h["invoice"] == invoice]


def slow_forward(r, seconds: float = 0.05):
    """Make the send take a moment, so a second move that is let in during the first one's send is certain to show."""
    real = r.paypal.create_payout

    def slow(*a, **k):
        time.sleep(seconds)
        return real(*a, **k)

    r.paypal.create_payout = slow


def race(r, invoice: str, hold_id: str, amount: float = 900.0):
    """The owner's approve and the agent's own payout for the same invoice, started together."""
    gate = threading.Barrier(2)
    out: dict = {}

    def tap():
        gate.wait()
        out["tap"] = r.approve(hold_id)

    def agent():
        gate.wait()
        out["agent"] = r.call("create_payout", {**PAY, "invoice_number": invoice, "amount": amount})

    ts = [threading.Thread(target=tap), threading.Thread(target=agent)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    return out


class NoLock:
    """What the run's lock would be if there were none (the control that shows the race test can fail)."""
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_control_without_the_shared_lock_the_same_invoice_is_paid_twice():
    srv, r = workspace()
    slow_forward(r)
    r.run_lock = NoLock()
    twice = 0
    for i in range(6):
        inv = f"INV-T22-C{i}"
        race(r, inv, held(r, inv))
        twice += len(paid(r, inv)) == 2
    assert twice >= 1, "the race never showed: the test could not tell a missing lock from a present one"


def test_with_the_shared_lock_an_approve_and_an_agent_payout_for_one_invoice_pay_it_once_even_when_the_send_is_slow():
    srv, r = workspace()
    slow_forward(r)
    for i in range(12):
        inv = f"INV-T22-S{i}"
        out = race(r, inv, held(r, inv))
        assert len(paid(r, inv)) == 1, (inv, out)
        sent = [x for x in (out["tap"], out["agent"]) if x.get("batch_status") == "SUCCESS"]
        assert len(sent) == 1
        loser = out["agent"] if sent[0] is out["tap"] else out["tap"]
        assert loser.get("refused_at_tap") or loser.get("blocked_by_receipts") or loser.get("held_by_receipts"), loser


def test_thousands_of_races_an_approve_and_an_agent_payout_for_one_invoice_exactly_one_pays_every_time():
    srv, r = workspace()
    unlucky = 0
    for i in range(2500):
        if i and i % 40 == 0:
            srv, r = workspace()          # a fresh book now and then, so a cumulative rule never decides the race
        inv = f"INV-T22-{i}"
        race(r, inv, held(r, inv))
        n = len(paid(r, inv))
        unlucky += n != 1
        assert n == 1, (inv, n)
    assert unlucky == 0


def test_the_mcp_tools_and_the_phones_taps_on_mcp_holds_take_the_same_lock():
    srv, r = workspace()
    taken: list[str] = []

    class Counting:
        def __init__(self, inner):
            self.inner = inner

        def __enter__(self):
            taken.append("in")
            return self.inner.__enter__()

        def __exit__(self, *a):
            taken.append("out")
            return self.inner.__exit__(*a)

    r.run_lock = Counting(r.run_lock)
    args = {**PAY, "invoice_number": "INV-T22-M1", "amount": 9000.0}
    text = asyncio.run(srv.call_tool("create_payout", args))
    held_out = json.loads(text.content[0].text)
    assert held_out["held_by_receipts"] and taken == ["in", "out"]           # an MCP tool call takes the run's lock
    taken.clear()
    r.approve(held_out["hold_id"])                                           # what /api/approve calls for an MCP hold
    assert taken[0] == "in" and taken[-1] == "out" and len(paid(r, "INV-T22-M1")) == 1
    taken.clear()
    asyncio.run(srv.call_tool("list_vendors", {}))
    assert taken == []                                                       # a read does not wait on a payment


def test_an_mcp_payout_and_a_phone_tap_for_one_invoice_pay_once_through_the_tool_layer():
    srv, r = workspace()
    slow_forward(r)
    for i in range(8):
        inv = f"INV-T22-P{i}"
        hid = held(r, inv)
        gate = threading.Barrier(2)

        def tap():
            gate.wait()
            r.approve(hid)

        def tool():
            gate.wait()
            asyncio.run(srv.call_tool("create_payout", {**PAY, "invoice_number": inv, "amount": 900.0}))

        ts = [threading.Thread(target=tap), threading.Thread(target=tool)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        assert len(paid(r, inv)) == 1, inv


def test_a_tap_made_while_the_same_thread_holds_the_runs_lock_does_not_deadlock():
    srv, r = workspace()
    hid = held(r, "INV-T22-R")

    def inside():
        with r.run_lock:                         # as an event handler running inside ``call`` would
            r.approve(hid)

    t = threading.Thread(target=inside, daemon=True)
    t.start()
    t.join(10)
    assert not t.is_alive() and len(paid(r, "INV-T22-R")) == 1


# ---- the spec and the README ----------------------------------------------------------------------------------------------
def test_the_readme_no_longer_names_the_gap_and_the_counts_are_true():
    spec = ROOT / ".kiro" / "specs" / "carbon-copy"
    reqs = (spec / "requirements.md").read_text(encoding="utf-8")
    assert "### Requirement 19" in reqs                                            # amended, not a new requirement
    assert "amended by task 22" in reqs and "THE INSTANT BETWEEN THE TAP'S LOOK AND ITS SEND IS CLOSED" in reqs
    assert "## Task 22:" in (spec / "design.md").read_text(encoding="utf-8")
    tasks = (spec / "tasks.md").read_text(encoding="utf-8")
    assert "- [x] 22. " in tasks
    assert "in the instant between that look and the send is not seen" not in README
    assert "not atomically" not in README
    assert_spec_changes_match(README)
    assert_readme_counts_match(README)
