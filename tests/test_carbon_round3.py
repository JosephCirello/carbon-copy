"""Task 15: every money move gets its receipt, on every path (findings F1, F2, F3, F5, F6, F13, F14).

One test (or more) per finding. The stand-in PayPal, no network, no keys: signers are made in memory or from a throwaway phrase.
"""
from __future__ import annotations

import asyncio
import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from receipts import mcp_server, rules  # noqa: E402
from receipts.carbon import CarbonCopy, Signer, run_of, verify  # noqa: E402
from receipts.core import Receipts  # noqa: E402
from receipts.paypal import StandIn  # noqa: E402
from receipts.scenarios import by_id  # noqa: E402

README = (ROOT / "README.md").read_text(encoding="utf-8")
ASHWOOD = {"vendor": "Ashwood Timber Co.", "receiver_email": "billing@ashwoodtimberco.com", "amount": 3100.0,
           "invoice_number": "INV-AT-9001", "memo": "round 3"}
PAYEE_CHANGE = {"vendor": "Blue Ridge Finishes", "new_paypal_email": "new@blueridgefinishes.example", "reason": "round 3"}


def signer() -> Signer:
    return Signer(Ed25519PrivateKey.generate())


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


def kinds(book: CarbonCopy) -> list[str]:
    return [r["kind"] for r in book.receipts()]


def owner_actions(book: CarbonCopy) -> list[str]:
    return [r["event"]["action"] for r in book.receipts() if r["kind"] == "owner"]


# ---- F1: the MCP workspace has its own book ----------------------------------------------------------------------
def test_f1_the_mcp_workspace_writes_a_book_signed_by_the_given_signer_and_opened_by_a_run_receipt():
    s = signer()
    srv, r = mcp_server.build(signer=s)
    assert r.carbon is not None
    first = r.carbon.receipts()[0]
    run = run_of(r.carbon.receipts())
    assert first["kind"] == "run" and run["mode"] == "enforce" and run["source"] == "live" and run["model"] == "mcp client"
    assert run["scenario"] == "MCP_workspace"
    out = r.call("create_payout", dict(ASHWOOD))                  # allowed: a verdict and a PayPal receipt
    assert out.get("batch_status") == "SUCCESS"
    held = r.call("update_vendor_payee", dict(PAYEE_CHANGE))      # held: a verdict
    assert held.get("held_by_receipts")
    tap = r.approve(held["hold_id"])                              # the owner's tap
    assert "stamp" in tap
    ks = kinds(r.carbon)
    assert ks.count("verdict") == 2 and "paypal" in ks and ks.count("owner") >= 2
    book = r.carbon.book()
    assert book["public_key"] == s.public_key_hex and verify(book)["intact"]


def test_f1_the_carbon_book_tool_returns_the_book_and_the_command_line_checks_it(tmp_path):
    srv, r = mcp_server.build(signer=signer())
    r.call("create_payout", dict(ASHWOOD))
    content = asyncio.run(srv.call_tool("carbon_book", {}))
    text = content[0].text if isinstance(content, (list, tuple)) else content.content[0].text
    book = json.loads(text)
    assert set(book) == {"public_key", "head", "receipts"} and book["head"]["count"] == len(book["receipts"]) >= 3
    f = tmp_path / "mcp-book.json"
    f.write_text(text, encoding="utf-8")
    done = subprocess.run([sys.executable, "-m", "receipts.carbon", "verify", str(f)], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0 and done.stdout.startswith("intact")


def _stdio(env_extra: dict):
    env = {**os.environ, "PAYPAL_MODE": "standin", **env_extra}
    proc = subprocess.Popen([sys.executable, "-m", "receipts.mcp_server"], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", env=env)

    def ask(msg):
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()
        return json.loads(proc.stdout.readline())
    ask({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                                                          "clientInfo": {"name": "test", "version": "1"}}})
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    proc.stdin.flush()
    return proc, ask


def test_f1_the_stdio_server_has_the_same_book_and_the_same_tool(monkeypatch):
    phrase = "round three stdio phrase, not a real key"
    monkeypatch.setenv("CARBON_COPY_KEY", phrase)
    expected_key = Signer.from_env().public_key_hex
    proc, ask = _stdio({"CARBON_COPY_KEY": phrase})
    try:
        names = {t["name"] for t in ask({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]}
        assert "carbon_book" in names
        ask({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "create_payout", "arguments": ASHWOOD}})
        got = ask({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "carbon_book", "arguments": {}}})
        book = json.loads(got["result"]["content"][0]["text"])
    finally:
        proc.kill()
    assert book["public_key"] == expected_key and book["receipts"][0]["kind"] == "run"
    assert [x["kind"] for x in book["receipts"]].count("verdict") == 1 and verify(book)["intact"]


def test_f1_the_app_mcp_book_is_signed_by_the_apps_one_signer(web):
    assert web.MCP_RECEIPTS.carbon is not None
    assert web.MCP_RECEIPTS.carbon.book()["public_key"] == web.SIGNER.public_key_hex


# ---- F2: the MCP holds on the phone ----------------------------------------------------------------------------
def test_f2_the_phone_switch_is_off_unless_asked_for():
    env = {k: v for k, v in os.environ.items() if k != "RECEIPTS_MCP_ON_PHONE"}
    env["PAYPAL_MODE"] = "standin"
    code = "import app; print(app.MCP_ON_PHONE)"
    off = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
    on = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env={**env, "RECEIPTS_MCP_ON_PHONE": "1"}, capture_output=True,
                        text=True, encoding="utf-8")
    assert off.stdout.strip().endswith("False") and on.stdout.strip().endswith("True")


def test_f2_a_tap_on_an_mcp_hold_is_sealed_in_the_mcp_book_and_returns_its_stamp(web, monkeypatch):
    from fastapi.testclient import TestClient
    web.VISITORS.clear()
    r = web.MCP_RECEIPTS
    before = list(r.holds)
    monkeypatch.setattr(web, "MCP_ON_PHONE", True)
    try:
        held = r.call("update_vendor_payee", dict(PAYEE_CHANGE))
        n_before = len(r.carbon.receipts())
        res = TestClient(web.app).post("/api/approve", json={"session": "mcp", "hold_id": held["hold_id"]})
        assert res.status_code == 200
        stamp = res.json()["stamp"]
        book = r.carbon.book()
        assert stamp["public_key"] == web.SIGNER.public_key_hex and stamp["count"] == len(book["receipts"]) > n_before
        assert "approved" in owner_actions(r.carbon) and verify(book)["intact"]
        assert verify(book, [stamp])["intact"]
    finally:
        r.holds[:] = before


def test_f2_the_readme_says_how_to_check_the_mcp_book_and_that_the_phone_switch_is_for_your_own_machine():
    assert "carbon_book" in README
    assert "RECEIPTS_MCP_ON_PHONE=1" in README and "anyone who can open the page can decide the MCP holds" in README
    assert "for your own machine only" in README


# ---- F3: an honest book is never read as changed ---------------------------------------------------------------
def test_f3_readers_never_see_a_head_that_counts_receipts_they_were_not_given():
    book = CarbonCopy(signer())
    for i in range(30):
        book.append("verdict", {"type": "verdict", "i": i})
    stop = threading.Event()

    def writer():
        i = 0
        while not stop.is_set() and i < 1500:          # paced and capped, so reads overlap writes without the book growing huge
            book.append("verdict", {"type": "verdict", "i": i, "t": time.time()})
            i += 1
            time.sleep(0.0005)
    bad, reads, lock = [], [0], threading.Lock()

    def reader():
        for k in range(1000):
            got = book.book()
            ok = got["head"]["count"] == len(got["receipts"])
            why = "" if ok else "the head counts receipts that were not handed out"
            if ok and k % 25 == 0:                       # the full check, on a sample of the reads
                out = verify(got)
                ok, why = out["intact"], out.get("why", "")
            with lock:
                reads[0] += 1
                if not ok:
                    bad.append(why)
    w = threading.Thread(target=writer)
    w.start()
    readers = [threading.Thread(target=reader) for _ in range(4)]
    for t in readers:
        t.start()
    for t in readers:
        t.join()
    stop.set()
    w.join()
    assert reads[0] == 4000 and bad == []


# ---- F5: the owner's tap is always sealed ----------------------------------------------------------------------
def _held_workspace():
    srv, r = mcp_server.build(signer=signer())
    held = r.call("update_vendor_payee", dict(PAYEE_CHANGE))
    assert held.get("held_by_receipts")
    return r, held["hold_id"]


def test_f5_a_forward_that_raises_still_seals_the_tap_and_says_why():
    r, hid = _held_workspace()

    def boom(**_):
        raise ValueError("PayPal could not read the amount")
    r.desk.update_vendor_payee = boom
    out = r.approve(hid)                                              # no exception
    assert out["error"] == "PayPal could not read the amount" and out["stamp"]["count"] == len(r.carbon.receipts())
    assert owner_actions(r.carbon) == ["approved", "not_sent"]
    hold = r.holds[0]
    assert hold["status"] == "APPROVED" and hold["result"]["error"] == "PayPal could not read the amount"
    assert r.approve(hid) == {"error": "no such waiting hold"}        # decided once
    assert r.decline(hid) == {"error": "no such waiting hold"}
    assert verify(r.carbon.book(), [out["stamp"]])["intact"]


def test_f5_the_approved_receipt_is_written_before_the_forward():
    r, hid = _held_workspace()
    seen = {}
    real = r._forward

    def spy(tool, args):
        seen["owner_before"] = owner_actions(r.carbon)
        return real(tool, args)
    r._forward = spy
    r.approve(hid)
    assert seen["owner_before"] == ["approved"] and owner_actions(r.carbon) == ["approved", "sent"]


def test_f5_the_api_answers_200_with_the_error_and_the_stamp_and_the_phone_can_show_it(web, monkeypatch):
    from fastapi.testclient import TestClient
    web.VISITORS.clear()
    r = web.MCP_RECEIPTS
    before = list(r.holds)
    monkeypatch.setattr(web, "MCP_ON_PHONE", True)
    real = r.desk.update_vendor_payee
    try:
        held = r.call("update_vendor_payee", dict(PAYEE_CHANGE))

        def boom(**_):
            raise ValueError("the stand-in cannot parse 1836 USD")
        r.desk.update_vendor_payee = boom
        c = TestClient(web.app, raise_server_exceptions=False)
        res = c.post("/api/approve", json={"session": "mcp", "hold_id": held["hold_id"]})
        assert res.status_code == 200
        j = res.json()
        assert j["error"] == "the stand-in cannot parse 1836 USD" and j["stamp"]["public_key"] == web.SIGNER.public_key_hex
        row = next(h for h in c.get("/api/holds").json() if h["id"] == held["hold_id"])
        assert row["status"] == "APPROVED" and row["result"]["error"] == "the stand-in cannot parse 1836 USD"
    finally:
        r.desk.update_vendor_payee = real
        r.holds[:] = before
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert "Approved, but PayPal did not take it: " in js and "not_sent" in js


def test_f5_two_taps_at_once_on_one_hold_act_once():
    for _ in range(25):
        r, hid = _held_workspace()
        go = threading.Barrier(2)
        results = []

        def tap(fn):
            go.wait()
            results.append(fn(hid))
        ts = [threading.Thread(target=tap, args=(r.approve,)), threading.Thread(target=tap, args=(r.decline,))]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        acted = [x for x in results if x.get("error") != "no such waiting hold"]
        assert len(acted) == 1
        decided = [a for a in owner_actions(r.carbon) if a in ("approved", "declined")]
        assert len(decided) == 1 and r.holds[0]["status"] in ("APPROVED", "DECLINED")


# ---- F6: a bad amount is blocked -------------------------------------------------------------------------------
@pytest.mark.parametrize("amount", ["NaN", float("nan"), "inf", float("inf"), "-inf", -5, "-0.01", "twelve", "1836 USD", "1e999"])
def test_f6_a_payout_with_an_amount_that_is_not_dollars_is_blocked_and_nothing_moves(amount):
    srv, r = mcp_server.build(signer=signer())
    moved = len(r.paypal.history)
    out = r.call("create_payout", {**ASHWOOD, "amount": amount})
    assert out.get("blocked_by_receipts") and "the amount is not a positive number of dollars" in out["why"][0]
    assert r.verdicts[-1]["decision"] == "BLOCK" and r.verdicts[-1]["findings"][0]["code"] == "AMOUNT_NOT_A_NUMBER"
    assert len(r.paypal.history) == moved and r.ledger == []


def test_f6_a_refund_with_a_bad_amount_is_blocked_and_a_whole_refund_and_real_amounts_are_not():
    srv, r = mcp_server.build(signer=signer())
    cap = next(iter(r.paypal.orders.values()))["capture_id"]
    for bad in ("NaN", "inf", -1, "lots"):
        out = r.call("create_refund", {"capture_id": cap, "amount": bad})
        assert out.get("blocked_by_receipts") and "not a positive number of dollars" in out["why"][0]
    assert rules.amount_problem(None) is not None and rules.amount_problem("$1,836.00") is None and rules.amount_problem(0) is not None
    assert not r.call("create_refund", {"capture_id": cap, "amount": 1}).get("blocked_by_receipts")


def _task15_amount_problem(x):
    """The rule as task 15 wrote it: finite and not below zero (zero and -0.0 passed)."""
    import math
    a = rules.money(x)
    return "the amount is not a number of dollars" if a is None or not math.isfinite(a) or a < 0 else None


def _episode_files():
    out = []
    for p in (ROOT / "results" / "episodes.jsonl", ROOT / "results" / "frontier" / "episodes.jsonl"):
        if p.exists():
            out.append(p)
    return out


def _verdicts_of(rec: dict, scn: dict) -> list[dict]:
    pp = StandIn(scn["paypal"], scn["id"])
    r = Receipts(scn, pp, mode=rec["mode"], policy=scn.get("policy"))
    last = ""
    for e in rec.get("events", []):
        if e["type"] == "say" and e.get("where") == "reply":
            last = e["text"]
            r.note_words(e["text"], "reply")
        elif e["type"] == "call":
            r.call(e["tool"], e["args"], step_text=last)
    return [{k: v for k, v in x.items() if k != "id"} for x in r.verdicts]


def test_f6_re_scoring_every_recorded_run_with_the_old_and_new_rules_gives_the_same_verdicts(monkeypatch):
    """The old rules are the new ones with the amount check switched off (the only change in receipts/rules.py)."""
    files = _episode_files()
    if not files:
        pytest.skip("no recorded runs on this machine")
    scenarios = by_id()
    runs = checked = 0
    for p in files:
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                scn = scenarios.get(rec.get("scenario"))
                if not scn or (rec.get("outcome") or {}).get("class") in ("ERROR", "NO_TOOL_CALLS") or rec.get("paypal_backend") != "standin":
                    continue
                new = _verdicts_of(rec, scn)
                with monkeypatch.context() as m:
                    m.setattr(rules, "amount_problem", lambda _x: None)
                    old = _verdicts_of(rec, scn)
                    m.setattr(rules, "amount_problem", _task15_amount_problem)      # task 21: and against the rules as task 15 left them
                    old15 = _verdicts_of(rec, scn)
                assert new == old == old15, f"a recorded run's verdicts changed ({rec.get('scenario')}, {rec.get('model')})"
                runs += 1
                checked += len(new)
    assert runs > 1000 and checked > 1000


# ---- F13: one event never ends the stream ----------------------------------------------------------------------
def _deep(n: int):
    x: object = "bottom"
    for _ in range(n):
        x = {"a": x}
    return x


def test_f13_a_very_deep_event_is_sent_in_its_cleaned_form(web):
    ev = {"type": "call", "tool": "create_payout", "args": _deep(3000)}
    text = web._data(ev)
    assert json.loads(text)["type"] == "call"
    assert json.loads(web._data({"type": "verdict", "amount": float("nan")}))["amount"] == "nan"
    assert json.loads(web._data({"type": "verdict", "amount": 298.5}))["amount"] == 298.5       # the usual form keeps numbers


def test_f13_when_even_the_cleaned_form_fails_a_placeholder_is_sent(web, monkeypatch):
    def broken(_x):
        raise RecursionError
    monkeypatch.setattr(web, "safe_json", broken)
    # NaN is refused by the first json.dumps (allow_nan=False) on every platform; no recursion limit is involved.
    out = json.loads(web._data({"type": "call", "amount": float("nan"), "head": {"count": 3}}))
    assert out["type"] == "unshown" and "msg" in out


def test_f13_the_stream_goes_on_after_a_deep_event(web):
    q: queue.Queue = queue.Queue()
    for ev in ({"type": "call", "args": _deep(3000)}, {"type": "say", "text": "after"}, None):
        q.put(ev)
    lines = [l for l in web._sse(q) if l.startswith("data: ")]
    assert len(lines) == 2 and json.loads(lines[1][6:])["text"] == "after"


# ---- F14: a tap does not copy the book --------------------------------------------------------------------------
def test_f14_a_tap_takes_the_head_and_never_copies_the_book(monkeypatch):
    r, hid = _held_workspace()

    def no_copy(*_a, **_k):
        raise AssertionError("the whole book was copied")
    monkeypatch.setattr(r.carbon, "book", no_copy)
    monkeypatch.setattr(r.carbon, "receipts", no_copy)
    out = r.approve(hid)
    assert out["stamp"]["count"] == len(r.carbon._receipts)
    held = r.call("update_vendor_payee", {**PAYEE_CHANGE, "new_paypal_email": "other@blueridgefinishes.example"})
    assert r.decline(held["hold_id"])["stamp"]["count"] == len(r.carbon._receipts)
    head = r.carbon.head()
    assert set(head) == {"count", "last_fp", "sig"} and head["count"] == len(r.carbon._receipts)
