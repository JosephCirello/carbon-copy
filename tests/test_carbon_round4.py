"""Task 16: a check that does not need to trust us, and honest limits (findings F4, F7, F8, F9, F10, F11, F12).

The stand-in PayPal, no network, no keys: signers are made in memory. The browser parts run under node.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

import build_verify  # noqa: E402
from receipts import mcp_server  # noqa: E402
from receipts.carbon import CarbonCopy, Signer, caveats, forge_demo, read_key_file, run_event, verify  # noqa: E402

README = (ROOT / "README.md").read_text(encoding="utf-8")
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not on PATH")
NO_KEY = "This file has no key from your device, so the check can only compare the book with itself."
NO_STAMP = "This file has no stamp, so it cannot tell whether the end of the book was rewritten."
KEEP = "This server keeps a run for one hour after its last activity (it starting, or your last approve or decline), and for 24 hours when a payment in it is waiting for you. Download the carbon copies to keep them."
HOSTED = "345c0cf441241146d896623a4dc08bc3a7c0f004c60975e2d072382552a9f6e1"
DAY, MODEL = "S14_crossed_in_the_mail", "glm-5.3"


def small_book(n: int = 4):
    signer = Signer(Ed25519PrivateKey.generate())
    carbon = CarbonCopy(signer)
    carbon.append("run", run_event("enforce", "recorded", "S9_normal_tuesday", "a model"))
    for i in range(n):
        carbon.append("say", {"type": "say", "text": f"line {i}"})
    return carbon


def download(carbon, with_stamp=True, with_key=True):
    book = carbon.book()
    return {"book": book, "stamps": [carbon.stamp()] if with_stamp else [], "trusted_key": book["public_key"] if with_key else None}


def cli(*args):
    done = subprocess.run([sys.executable, "-m", "receipts.carbon", "verify", *map(str, args)], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8")
    return done.returncode, done.stdout, done.stderr


# ---- F8a: the page's check cannot be swapped -----------------------------------------------------------------------
@needs_node
def test_f8_the_check_is_frozen_and_cannot_be_assigned_over(tmp_path):
    script = tmp_path / "t.js"
    script.write_text(
        'require(process.argv[2]);\n'
        'const first = globalThis.CarbonVerify;\n'
        'try { globalThis.CarbonVerify = { verify: async () => ({ intact: true }) }; } catch (e) {}\n'
        'try { first.verify = async () => ({ intact: true }); } catch (e) {}\n'
        'console.log(JSON.stringify({ same: globalThis.CarbonVerify === first, frozen: Object.isFrozen(first),\n'
        '  real: String(first.verify).includes("WHY_UNREADABLE") }));\n', encoding="utf-8")
    out = subprocess.run([NODE, str(script), str(ROOT / "static" / "carbon_verify.js")], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == {"same": True, "frozen": True, "real": True}


def test_f8_the_page_captures_the_check_once_and_never_looks_it_up_at_click_time():
    app_js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert app_js.count("window.CarbonVerify") == 1 and "const CHECK = window.CarbonVerify;" in app_js
    assert "await CHECK.verify(book, stamps, key)" in app_js
    assert "Object.freeze" in (ROOT / "static" / "carbon_verify.js").read_text(encoding="utf-8")


def test_f8_the_third_party_script_is_pinned_with_an_integrity_hash():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    tag = re.search(r"<script[^>]*ag-grid-community@[^>]*>", html).group(0)
    assert "ag-grid-community@32.3.3/dist/ag-grid-community.min.js" in tag      # an exact version
    assert re.search(r'integrity="sha384-[A-Za-z0-9+/]{64}"', tag) and 'crossorigin="anonymous"' in tag


# ---- F8b: verify.html -----------------------------------------------------------------------------------------------
def test_verify_html_is_what_the_build_script_builds_and_carries_the_check_byte_for_byte():
    data = (ROOT / "verify.html").read_bytes()
    assert data == build_verify.build().encode("utf-8"), "run: .venv\\Scripts\\python.exe tools\\build_verify.py"
    inlined = re.search(rb'<script id="carbon-verify">(.*?)</script>', data, re.S).group(1)
    assert inlined == (ROOT / "static" / "carbon_verify.js").read_bytes()


def test_verify_html_uses_nothing_from_anywhere():
    html = (ROOT / "verify.html").read_text(encoding="utf-8")
    assert not re.search(r"<(script|link|img|iframe|audio|video|source|embed|object)\b[^>]*\b(src|href)\s*=", html, re.I)
    assert "@import" not in html and "url(" not in html and not re.search(r"https?://", html)
    assert "fetch(" not in html and "XMLHttpRequest" not in html and "WebSocket" not in html
    assert "default-src 'none'" in html                                    # the browser itself refuses any connection


def test_the_readme_publishes_the_hash_of_verify_html():
    sha = hashlib.sha256((ROOT / "verify.html").read_bytes()).hexdigest()
    assert sha in README, "README's SHA-256 of verify.html is not the file's"
    assert len(set(re.findall(r"`([0-9a-f]{64})`", README)) - {HOSTED}) == 1


HARNESS = r"""
const fs = require("fs"), vm = require("vm");
const html = fs.readFileSync(process.argv[2], "utf8");
const cases = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
function el(id) {
  const e = { id, children: [], hidden: false, className: "", _t: "", attrs: {},
    appendChild(c) { this.children.push(c); return c; }, setAttribute(k, v) { this.attrs[k] = v; },
    addEventListener() {}, classList: { add() {}, remove() {} } };
  Object.defineProperty(e, "textContent", { get() { return this._t; }, set(v) { this._t = String(v); this.children = []; } });
  return e;
}
const els = {};
globalThis.window = globalThis;
globalThis.addEventListener = () => {};
globalThis.document = { getElementById: (id) => (els[id] = els[id] || el(id)), createElement: () => el("") };
const dump = (e) => [e.className + "|" + e._t].concat(...e.children.map(dump));
const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
for (const s of scripts) vm.runInThisContext(s);
(async () => {
  const out = [];
  for (const text of cases) {
    for (const k of ["result", "keys"]) { document.getElementById(k); els[k].children = []; els[k]._t = ""; els[k].hidden = false; }
    document.getElementById("keys").hidden = true;
    await globalThis.__checkText(text);
    out.push({ result: dump(document.getElementById("result")).filter((x) => x !== "|"), keys: document.getElementById("keys").hidden ? null : dump(document.getElementById("keys")).filter((x) => x !== "|") });
  }
  console.log(JSON.stringify(out));
})();
"""


def run_page(tmp_path, texts, use_file_key=False):
    """Each text as a dropped file. With ``use_file_key`` the switch "Use the key in this file instead" is ticked first."""
    (tmp_path / "h.js").write_text(HARNESS.replace("document.getElementById(\"keys\").hidden = true;",
                                                   "document.getElementById(\"keys\").hidden = true; document.getElementById(\"useFileKey\").checked = %s;"
                                                   % ("true" if use_file_key else "false")), encoding="utf-8")
    (tmp_path / "c.json").write_text(json.dumps(texts), encoding="utf-8")
    done = subprocess.run([NODE, str(tmp_path / "h.js"), str(ROOT / "verify.html"), str(tmp_path / "c.json")], capture_output=True,
                          text=True, encoding="utf-8", timeout=120)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


@needs_node
def test_verify_html_says_intact_or_changed_with_the_reason_and_the_notes(tmp_path):
    carbon = small_book()
    honest = download(carbon)
    changed = json.loads(json.dumps(honest))
    changed["book"]["receipts"][2]["event"]["text"] = "line X"
    forged = forge_demo(carbon.book())["book"]
    texts = [json.dumps(honest), json.dumps(changed), json.dumps(honest["book"]), json.dumps({**honest, "stamps": []}),
             json.dumps({**honest, "book": forged}), "not json", json.dumps([1, 2])]
    got = run_page(tmp_path, texts, use_file_key=True)         # these books are from "our own server": the switch is ticked
    flat = ["\n".join(g["result"]) for g in got]
    assert "stamp ok|INTACT" in flat[0] and "All 5 receipts are as they were written." in flat[0] and NO_KEY not in flat[0] and NO_STAMP not in flat[0]
    assert "stamp bad|CHANGED AT #3" in flat[1] and "its content was changed" in flat[1]
    assert "INTACT" in flat[2] and NO_KEY in flat[2] and NO_STAMP in flat[2]            # a bare book: nothing to hold it against
    assert "INTACT" in flat[3] and NO_STAMP in flat[3] and NO_KEY not in flat[3]
    assert "CHANGED" in flat[4] and "different key" in flat[4]                           # re-signed under another key
    assert "Could not read the file" in flat[5] and "Could not read the file" in flat[6]
    # the download's key beside the published one, and whether they match
    keys0 = "\n".join(got[0]["keys"])
    assert HOSTED in keys0 and honest["trusted_key"] in keys0 and "do NOT match" in keys0
    assert "names no trusted key" in "\n".join(got[2]["keys"])


@needs_node
def test_verify_html_says_when_the_download_trusts_the_published_key(tmp_path):
    carbon = small_book()
    d = download(carbon)
    d["trusted_key"] = HOSTED
    d["book"]["public_key"] = HOSTED                # the page only compares the words: the check itself says CHANGED here
    got = run_page(tmp_path, [json.dumps(d)], use_file_key=True)
    assert "They match" in "\n".join(got[0]["keys"])


# ---- F9: the published key ------------------------------------------------------------------------------------------
def test_f9_the_hosted_key_is_published_outside_the_server():
    assert read_key_file(ROOT / "HOSTED_KEY.txt") == HOSTED
    assert HOSTED in README and HOSTED in (ROOT / "HOSTED_KEY.txt").read_text(encoding="utf-8")
    assert HOSTED in (ROOT / "verify.html").read_text(encoding="utf-8")


def test_f9_the_command_line_takes_a_key_file(tmp_path):
    carbon = small_book()
    d = download(carbon, with_key=False)
    f = tmp_path / "book.json"
    f.write_text(json.dumps(d), encoding="utf-8")
    own = tmp_path / "own_key.txt"
    own.write_text("this book's key: " + d["book"]["public_key"].upper() + "\nand some words\n", encoding="utf-8")
    code, out, _ = cli(f, "--key-file", own)
    assert code == 0 and out.startswith("intact (5 receipts)")
    code, out, _ = cli(f, "--key-file", ROOT / "HOSTED_KEY.txt")                 # the published key is not this book's key
    assert code == 1 and "different key" in out
    code, _, err = cli(f, "--key-file", tmp_path / "missing.txt")
    assert code == 2 and err.startswith("could not read the key file") and "Traceback" not in err
    (tmp_path / "empty.txt").write_text("no key here", encoding="utf-8")
    assert cli(f, "--key-file", tmp_path / "empty.txt")[0] == 2
    code, _, err = cli(f, "--key-file", own, "--key", d["book"]["public_key"])
    assert code == 2 and "not both" in err


# ---- F7: no bare "intact" -------------------------------------------------------------------------------------------
def test_f7_caveats_in_plain_code():
    assert caveats(None, []) == [NO_KEY, NO_STAMP] and caveats("k" * 64, [{"count": 1}]) == []
    assert caveats("k" * 64, None) == [NO_STAMP] and caveats(None, [{"count": 1}]) == [NO_KEY]


def test_f7_the_command_line_says_what_it_had_nothing_to_hold_the_book_against(tmp_path):
    carbon = small_book()
    forged = forge_demo(carbon.book())["book"]          # re-signed under a new key: reads intact with nothing to hold it against
    f = tmp_path / "forged.json"
    f.write_text(json.dumps(forged), encoding="utf-8")
    code, out, _ = cli(f)
    lines = out.splitlines()
    assert code == 0 and lines[0].startswith("intact") and lines[1:] == [NO_KEY, NO_STAMP]
    g = tmp_path / "full.json"
    g.write_text(json.dumps(download(carbon)), encoding="utf-8")
    code, out, _ = cli(g)
    assert code == 0 and out.splitlines() == ["intact (5 receipts)"]                # a key and a stamp: nothing to add
    g.write_text(json.dumps(download(carbon, with_stamp=False)), encoding="utf-8")
    assert cli(g)[1].splitlines() == ["intact (5 receipts)", NO_STAMP]
    g.write_text(json.dumps(download(carbon, with_key=False)), encoding="utf-8")
    assert cli(g)[1].splitlines() == ["intact (5 receipts)", NO_KEY]
    assert cli(g, "--key", carbon.book()["public_key"])[1].splitlines() == ["intact (5 receipts)"]       # the flag is a key
    assert cli(tmp_path / "missing.json")[0] == 2
    bad = json.loads(g.read_text(encoding="utf-8"))
    bad["book"]["receipts"][1]["event"]["text"] = "x"
    g.write_text(json.dumps(bad), encoding="utf-8")
    assert cli(g)[0] == 1


# ---- F10: the hour is said ------------------------------------------------------------------------------------------
def test_f10_the_phone_and_the_carbon_tab_say_the_server_keeps_a_run_for_an_hour():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert html.count(KEEP) == 2 and 'id="phKeep"' in html and 'id="ccKeep"' in html
    assert '$("#phKeep").hidden' in js and '$("#ccKeep").hidden = !hasBook' in js
    assert "It lapsed and was never sent to PayPal." in js and "This one has expired" in js


def test_f10_readme_limits_state_the_hour_the_forty_runs_and_the_visitor_limit():
    limits = README.split("## Limits we know about")[1].split("License")[0]
    assert "one hour after its last activity" in limits and "for 24 hours" in limits and "at most 40 runs per visitor and 300 visitors" in limits
    assert "30 new visitors in 10 minutes" in limits


def test_f8_readme_limits_say_the_in_page_check_comes_from_the_server():
    limits = README.split("## Limits we know about")[1].split("License")[0]
    assert "runs code our server sends" in limits and "dishonest operator could send a check that lies" in limits
    assert "command line from a fresh clone" in limits and "`verify.html` saved from GitHub" in limits
    assert "10,000 receipts takes about 6 seconds" in limits and "50,000 about 30" in limits and "7 to 153 receipts" in limits


# ---- F4: one client cannot push the others out ----------------------------------------------------------------------
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
    yield TestClient
    web.VISITORS.clear()
    web._NEW_BY_ADDRESS.clear()


def policy_body(web):
    return {"policy": web.DEFAULT_RULES["policy"], "english": "", "sources": {}, "compiled_by": "owner"}


def chosen_cookie(web) -> dict:
    return {"Cookie": f"{web.VISITOR_COOKIE}={secrets.token_urlsafe(32)}"}


def observe_run(web, client, headers=None):
    """A visitor made the only way one can be made now: a run starts (the cheapest is the recorded run with nothing checking it,
    which holds nothing). The replay is not slowed down."""
    rows = client.get("/api/recorded", params={"scenario": DAY, "model": MODEL}).json()
    pick = sorted((r for r in rows if r["mode"] == "observe"), key=lambda r: -(r["attempts"] or 0))[0]
    return client.get("/api/replay", params={"line": pick["line"], "speed": 1000}, headers=headers or {})


@pytest.fixture(autouse=True)
def _no_pauses_in_replays(web, monkeypatch):
    monkeypatch.setattr(web.time, "sleep", lambda _s: None)


def hold_waiting(web, client):
    rows = client.get("/api/recorded", params={"scenario": DAY, "model": MODEL}).json()
    pick = sorted((r for r in rows if r["mode"] == "enforce"), key=lambda r: -(r["attempts"] or 0))[0]
    res = client.get("/api/replay", params={"line": pick["line"], "speed": 100})
    assert res.status_code == 200 and '"type": "done"' in res.text
    assert [h for h in client.get("/api/holds").json() if h["status"] == "WAITING"]


def test_f4_a_policy_request_with_no_cookie_keeps_nothing(web, fresh):
    c = fresh(web.app)
    res = c.post("/api/policy", json=policy_body(web))
    assert res.status_code == 400 and "load the page first" in res.json()["detail"].lower()
    assert not web.VISITORS and not web._NEW_BY_ADDRESS
    assert c.post("/api/policy", json=policy_body(web)).status_code == 200      # task 22: its cookie came back SIGNED, so the save may make the visitor, with no run
    assert len(web.VISITORS) == 1 and len(web._NEW_BY_ADDRESS) == 1
    assert observe_run(web, c).status_code == 200                               # a run starts: the same visitor
    assert len(web.VISITORS) == 1 and c.post("/api/policy", json=policy_body(web)).status_code == 200


def test_f4_301_cookieless_requests_do_not_push_anyone_out(web, fresh, monkeypatch):
    monkeypatch.setattr(web, "MAX_VISITORS", 300)
    victim = fresh(web.app)
    hold_waiting(web, victim)
    assert len(web.VISITORS) == 1
    for _ in range(301):
        r = fresh(web.app).post("/api/policy", json=policy_body(web))          # every one carries no cookie
        assert r.status_code == 400
    assert len(web.VISITORS) == 1
    assert [h for h in victim.get("/api/holds").json() if h["status"] == "WAITING"], "the victim's waiting payment was pushed out"


def test_f4_when_the_table_is_full_a_visitor_with_a_waiting_hold_is_dropped_last(web, fresh, monkeypatch):
    monkeypatch.setattr(web, "MAX_VISITORS", 3)
    victim = fresh(web.app)
    hold_waiting(web, victim)                                  # the oldest visitor, with a payment waiting
    for i in range(6):                                         # six more, one at a time, each past the limit of three
        c = fresh(web.app)
        assert observe_run(web, c).status_code == 200
        assert len(web.VISITORS) <= 3
    assert [h for h in victim.get("/api/holds").json() if h["status"] == "WAITING"], "the waiting payment was dropped for idle visitors"


def test_f4_only_when_everyone_has_something_does_the_oldest_go(web, fresh, monkeypatch):
    monkeypatch.setattr(web, "MAX_VISITORS", 2)
    a, b, c = fresh(web.app), fresh(web.app), fresh(web.app)
    for p in (a, b, c):
        hold_waiting(web, p)
    assert len(web.VISITORS) == 2
    assert not a.get("/api/holds").json() and b.get("/api/holds").json() and c.get("/api/holds").json()


def test_f4_a_young_run_protects_its_visitor_and_an_old_one_does_not(web, fresh, monkeypatch):
    monkeypatch.setattr(web, "MAX_VISITORS", 2)
    a = fresh(web.app)
    assert observe_run(web, a).status_code == 200              # a visitor whose only run has nothing waiting
    b = fresh(web.app)
    hold_waiting(web, b)
    for v in web.VISITORS.values():
        for s in v.sessions.values():
            s["t"] -= web.SESSION_MAX_AGE_S + 5                # every run is now over an hour old: a's is over, b's waits (24 hours)
    d = fresh(web.app)
    assert observe_run(web, d).status_code == 200
    assert len(web.VISITORS) == 2
    assert [h for h in b.get("/api/holds").json() if h["status"] == "WAITING"] and not a.get("/api/holds").json()


def test_f4_thirty_new_visitors_in_ten_minutes_per_address_then_429(web, fresh):
    codes = []
    for _ in range(32):
        codes.append(observe_run(web, fresh(web.app)))
    assert [r.status_code for r in codes] == [200] * 30 + [429] * 2
    assert "wait" in codes[-1].json()["detail"].lower() and "visitor" in codes[-1].json()["detail"].lower()


def test_f4_the_address_is_the_one_the_proxy_added_and_only_behind_the_proxy(web, fresh, monkeypatch):
    monkeypatch.setattr(web, "NEW_VISITORS_PER_ADDRESS", 2)
    monkeypatch.setattr(web, "BEHIND_PROXY", False)            # a header anyone can send is ignored: rotating it buys nothing
    got = [observe_run(web, fresh(web.app), {"X-Forwarded-For": f"10.0.0.{i}"}).status_code for i in range(4)]
    assert got == [200, 200, 429, 429]
    web._NEW_BY_ADDRESS.clear()
    monkeypatch.setattr(web, "BEHIND_PROXY", True)
    def start(addr):
        return observe_run(web, fresh(web.app), {"X-Forwarded-For": addr}).status_code
    # the LAST entry is the one the proxy added; whatever the client wrote in front of it is not counted
    assert [start("10.1.1.1, 203.0.113.5"), start("10.2.2.2, 203.0.113.5"), start("10.9.9.9, 203.0.113.5")] == [200, 200, 429]
    assert start("203.0.113.6") == 200                          # another client address is counted on its own


def test_f4_render_sets_the_proxy_flag():
    assert "RECEIPTS_BEHIND_PROXY" in (ROOT / "render.yaml").read_text(encoding="utf-8")


# ---- F12: policy text has a size ------------------------------------------------------------------------------------
def test_f12_policy_text_over_the_limits_is_refused_with_413(web, fresh):
    c = fresh(web.app)
    assert observe_run(web, c).status_code == 200              # a run has started, so there is a visitor to keep rules for
    body = policy_body(web)
    assert c.post("/api/policy", json={**body, "english": "x" * 20_000}).status_code == 200
    r = c.post("/api/policy", json={**body, "english": "x" * 20_001})
    assert r.status_code == 413 and "too long" in r.json()["detail"]
    assert c.post("/api/policy", json={**body, "sources": {f"k{i}": "q" for i in range(200)}}).status_code == 200
    assert c.post("/api/policy", json={**body, "sources": {f"k{i}": "q" for i in range(201)}}).status_code == 413
    assert c.post("/api/policy", json={**body, "sources": {"k": "q" * 2_000}}).status_code == 200
    r = c.post("/api/policy", json={**body, "sources": {"k": "q" * 2_001}})
    assert r.status_code == 413 and "too long" in r.json()["detail"]
    assert len(web.VISITORS[next(iter(web.VISITORS))].rules["english"]) <= 20_000        # the refused text was never kept


# ---- F11: /mcp does not keep everything -----------------------------------------------------------------------------
PAYEE = {"vendor": "Blue Ridge Finishes", "new_paypal_email": "n@blueridgefinishes.example", "reason": "r"}


def mcp():
    return mcp_server.build(signer=Signer(Ed25519PrivateKey.generate()))


def call_tool(srv, name, args):
    content = asyncio.run(srv.call_tool(name, args))
    return json.loads((content[0].text if isinstance(content, (list, tuple)) else content.content[0].text))


def test_f11_an_argument_over_64_kb_is_kept_as_its_first_64_kb_plus_the_cut(tmp_path):
    text, hit = mcp_server.cut_text("é" * 40_000)
    assert hit and text.endswith("(cut: 14464 bytes)") and len(text.encode("utf-8")) <= 64 * 1024 + 30
    assert mcp_server.cut_text("short") == ("short", False)
    srv, r = mcp()
    held = r.call("update_vendor_payee", {**PAYEE, "reason": "A" * 300_000})
    assert held["held_by_receipts"]
    full = [x for x in r.carbon.receipts() if x["kind"] == "verdict"][-1]["event"]["args"]["reason"]
    call_tool(srv, "receipts_holds", {})                       # any tool call trims the history
    kept = r.holds[-1]["args"]["reason"]
    assert kept == "A" * 65536 + f"(cut: {300_000 - 65536} bytes)" and r.holds[-1]["cut"] is True
    assert r.verdicts[-1]["args"]["reason"] == kept
    assert full == "A" * 300_000, "the book keeps everything"
    assert verify(r.carbon.book())["intact"]


def test_f11_a_hold_with_a_cut_argument_cannot_be_approved():
    srv, r = mcp()
    held = r.call("update_vendor_payee", {**PAYEE, "reason": "A" * 100_000})
    call_tool(srv, "receipts_holds", {})
    before = len(r.carbon.receipts())
    out = r.approve(held["hold_id"])
    assert "too long to keep" in out["error"] and len(r.carbon.receipts()) == before
    assert r.holds[-1]["status"] == "WAITING" and r.decline(held["hold_id"])["declined"] == held["hold_id"]


def test_f11_the_workspace_keeps_the_last_200_holds_and_500_verdicts_and_the_book_keeps_all():
    srv, r = mcp()
    for i in range(300):
        r.call("create_payout", {"vendor": "Ashwood Timber Co.", "receiver_email": "billing@ashwoodtimberco.com", "amount": 1.0,
                                 "invoice_number": f"INV-X-{i}", "memo": ""})
    for i in range(210):
        r.call("update_vendor_payee", {**PAYEE, "new_paypal_email": f"n{i}@x.example"})
    total_verdicts = sum(1 for x in r.carbon.receipts() if x["kind"] == "verdict")
    assert total_verdicts == 510
    call_tool(srv, "receipts_holds", {})
    assert len(r.holds) == 200 and len(r.verdicts) == 500
    assert r.holds[-1]["args"]["new_paypal_email"] == "n209@x.example"                      # the newest are the ones kept
    assert sum(1 for x in r.carbon.receipts() if x["kind"] == "verdict") == 510, "nothing is removed from the book"


def test_f11_receipts_holds_takes_a_limit_newest_first_default_50():
    srv, r = mcp()
    for i in range(70):
        r.call("update_vendor_payee", {**PAYEE, "new_paypal_email": f"n{i}@x.example"})
    default = call_tool(srv, "receipts_holds", {})
    assert len(default) == 50 and default[0]["args"]["new_paypal_email"] == "n69@x.example"
    three = call_tool(srv, "receipts_holds", {"limit": 3})
    assert [h["args"]["new_paypal_email"] for h in three] == ["n69@x.example", "n68@x.example", "n67@x.example"]
    assert call_tool(srv, "receipts_holds", {"limit": 0}) == []
    assert len(call_tool(srv, "receipts_holds", {"limit": 100000})) == 70               # a huge limit is capped at what is kept (<= 200)
