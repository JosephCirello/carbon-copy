"""Task 12: what our own attacker found in its second round (C1 to C8).

The command line runs through ``subprocess`` exactly as the README says; the page's own functions (``static/app.js``,
``static/carbon_verify.js``) run under node. No network, no keys on disk.
"""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from receipts.carbon import (  # noqa: E402
    GENESIS, CarbonCopy, Signer, fingerprint, read_check_file, run_event, run_of, verify,
)

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not on PATH")
APPJS = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
VERIFYJS = ROOT / "static" / "carbon_verify.js"
DAY, MODEL = "S14_crossed_in_the_mail", "glm-5.3"


def make_book(n_extra=2):
    signer = Signer(Ed25519PrivateKey.generate())
    c = CarbonCopy(signer)
    c.append("run", run_event("enforce", "recorded", "S14", "glm-5.3"))
    c.append("verdict", {"id": "h1", "amount": 1836.0, "decision": "HOLD"})
    for i in range(n_extra):
        c.append("note", {"i": i})
    return signer, c


def cli(*args):
    p = subprocess.run([sys.executable, "-m", "receipts.carbon", "verify", *args], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", timeout=120)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def node(prog, payload):
    out = subprocess.run([NODE, "-e", prog, json.dumps(payload)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def between(start, end):
    i = APPJS.index(start)
    return APPJS[i:APPJS.index(end, i)]


def download_like_the_page(book, stamps, key):
    """The file "Download the carbon copies" writes: the page's own bookParts(), under node, with its own JSON.stringify."""
    prog = ("const p=JSON.parse(process.argv[1]); const CC=p.book; CC.session='s'; const deviceStamps=()=>p.stamps; const devicePinned=()=>p.key;\n"
            + between("function bookParts", "const short =") + "\nconsole.log(JSON.stringify(bookParts(), null, 2));")
    return node(prog, {"book": book, "stamps": stamps, "key": key})


# ---------------------------------------------------------------- C1
@needs_node
def test_c1_the_command_line_reads_the_file_the_page_downloads(tmp_path):
    signer, c = make_book()
    text = download_like_the_page(c.book(), [c.stamp()], signer.public_key_hex)
    assert set(json.loads(text)) == {"book", "stamps", "trusted_key"}
    f = tmp_path / "carbon_copies.json"
    f.write_text(text, encoding="utf-8")
    code, out, err = cli(str(f))
    assert (code, out) == (0, f"intact ({len(c.receipts())} receipts)"), err
    # the download's own key and stamps are used: another key in the flag wins, and then the book is changed
    other = Signer(Ed25519PrivateKey.generate()).public_key_hex
    code, out, _ = cli(str(f), "--key", other)
    assert code == 1 and "different key" in out


@needs_node
def test_c1_the_download_uses_its_own_stamps_and_flags_win(tmp_path):
    signer, c = make_book()
    old_book, old_stamp = c.book(), c.stamp()
    c.append("note", {"i": 9})
    # the download holds a stamp newer than its book: the book is short, so it reads changed
    f = tmp_path / "d.json"
    f.write_text(download_like_the_page(old_book, [c.stamp()], signer.public_key_hex), encoding="utf-8")
    code, out, _ = cli(str(f))
    assert code == 1 and "shorter" in out
    # --stamps wins over the file's stamps
    s = tmp_path / "s.json"
    s.write_text(json.dumps([old_stamp]), encoding="utf-8")
    assert cli(str(f), "--stamps", s.as_posix())[0] == 0


def test_c1_a_bare_book_still_reads_and_a_bad_trusted_key_is_exit_2(tmp_path):
    signer, c = make_book()
    f = tmp_path / "bare.json"
    f.write_text(json.dumps(c.book()), encoding="utf-8")
    assert cli(str(f))[0] == 0
    g = tmp_path / "bad.json"
    g.write_text(json.dumps({"book": c.book(), "stamps": [], "trusted_key": "nope"}), encoding="utf-8")
    code, _, err = cli(str(g))
    assert code == 2 and "Traceback" not in err
    assert read_check_file({"book": c.book(), "trusted_key": None})[2] is None


# ---------------------------------------------------------------- C2
@pytest.mark.parametrize("which", ["book", "stamps"])
def test_c2_a_file_nested_200000_deep_is_exit_2_with_one_plain_line(tmp_path, which):
    deep = tmp_path / "deep.json"
    deep.write_text("[" * 200000 + "]" * 200000, encoding="utf-8")
    signer, c = make_book()
    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps(c.book()), encoding="utf-8")
    code, out, err = cli(str(deep)) if which == "book" else cli(str(ok), "--stamps", str(deep))
    assert code == 2 and "Traceback" not in err and len(err.splitlines()) == 1 and out == ""


def test_c2_a_missing_file_and_a_file_that_is_not_utf8_are_exit_2(tmp_path):
    bad = tmp_path / "bin.json"
    bad.write_bytes(b"\xff\xfe\x00\x80 not json")
    for path in (str(tmp_path / "missing.json"), str(bad)):
        code, _, err = cli(path)
        assert code == 2 and "Traceback" not in err and len(err.splitlines()) == 1


# ---------------------------------------------------------------- C3
def sentence(receipt):
    start, end = APPJS.index("function ccSentence"), APPJS.index("const esc0")
    prog = ("const ccWhat=()=>'a move',plain=(x)=>x,markerWords=(x)=>x,PP_NAME=(b)=>'PayPal '+b,TOOL_PLAIN={create_refund:'a refund'},esc0=(s)=>String(s??'');\n"
            + APPJS[start:end] + "\nconsole.log(ccSentence(JSON.parse(process.argv[1])));")
    return node(prog, receipt)


REFUSED = {"error": "UNPROCESSABLE_ENTITY", "details": [{"issue": "REFUND_AMOUNT_EXCEEDED"}]}


@needs_node
def test_c3_when_paypal_refused_the_screen_says_so_and_never_says_it_went_to_paypal():
    owner = sentence({"kind": "owner", "event": {"action": "approved", "hold_id": "h", "result": REFUSED}})
    assert owner == "Maya approved a held payment. PayPal refused it: the refund is more than what is left on that payment."
    pp = sentence({"kind": "paypal", "event": {"tool": "create_refund", "backend": "standin", "result": REFUSED}})
    assert pp.startswith("PayPal refused it: the refund is more than what is left on that payment.")
    assert "went to PayPal" not in owner + pp and not pp.startswith("Sent to")


@needs_node
def test_c3_other_errors_and_the_honest_case():
    ok_owner = sentence({"kind": "owner", "event": {"action": "approved", "result": {"status": "COMPLETED"}}})
    assert ok_owner == "Maya approved a held payment. It went to PayPal."
    assert sentence({"kind": "paypal", "event": {"tool": "create_refund", "backend": "sandbox", "result": {"status": "COMPLETED"}}}) \
        == "Sent to PayPal sandbox: a refund."
    odd = sentence({"kind": "owner", "event": {"action": "approved", "result": {"error": "RESOURCE_NOT_FOUND"}}})
    assert odd == "Maya approved a held payment. PayPal refused it: resource not found."
    late = sentence({"kind": "owner", "event": {"action": "approved", "result": {"error": "timeout calling create_payout"}}})
    assert "did not answer in time" in late and "went to PayPal" not in late


@needs_node
def test_c3_the_sealed_refusal_comes_from_a_real_stand_in_run():
    """Two held full refunds of one capture, both approved: the second is refused, and the sealed receipts say so."""
    os.environ.setdefault("PAYPAL_MODE", "standin")
    import app
    from receipts.core import Receipts
    scn = app.BY_ID["S6_never_arrived"]
    pp = app.make_paypal(scn.get("paypal", {}), scn["id"])
    assert pp.backend == "standin"
    book = CarbonCopy(Signer(Ed25519PrivateKey.generate()))
    r = Receipts(scn, pp, mode="enforce", policy=dict(app.DEFAULT_RULES["policy"]), carbon=book)
    cap = pp.ids["D.capture_id"]
    h1, h2 = (r.call("create_refund", {"capture_id": cap, "amount": 265}) for _ in range(2))
    r.approve(h1["hold_id"])
    r.approve(h2["hold_id"])
    owner = [x for x in book.receipts() if x["kind"] == "owner"][-1]
    assert "PayPal refused it" in sentence(owner) and "went to PayPal" not in sentence(owner)


# ---------------------------------------------------------------- C4
def node_verify(cases):
    prog = ("const {verify,parseStamps}=require(%s);const cases=JSON.parse(process.argv[1]);(async()=>{const out=[];"
            "for(const c of cases){out.push(await verify(c.book, c.stamps_text!==undefined?c.stamps_text:c.stamps, c.key));}console.log(JSON.stringify(out));})();"
            % json.dumps(str(VERIFYJS)))
    return json.loads(node(prog, cases))


@needs_node
def test_b1_a_trusted_key_in_capitals_is_the_same_key_with_stamps_in_both_checks():
    signer, c = make_book()
    book, stamps, key = json.loads(json.dumps(c.book())), [c.stamp()], signer.public_key_hex.upper()
    assert verify(book, stamps, key)["intact"] is True
    assert node_verify([{"book": book, "stamps": stamps, "key": key}])[0] == {"intact": True, "count": len(book["receipts"])}


@needs_node
@pytest.mark.parametrize("written", ["6.0", "6e0", "6.00", "0.6e1"])
def test_b2_a_stamp_count_written_as_a_fraction_is_damaged_in_both_checks(written):
    signer = Signer(Ed25519PrivateKey.generate())
    c = CarbonCopy(signer)
    for i in range(6):
        c.append("note", {"i": i})
    st = c.stamp()
    text = '[{"count":%s,"last_fp":"%s","sig":"%s","public_key":"%s"}]' % (written, st["last_fp"], st["sig"], st["public_key"])
    book = json.loads(json.dumps(c.book()))
    py = verify(book, json.loads(text), signer.public_key_hex)
    js = node_verify([{"book": book, "stamps_text": text, "key": signer.public_key_hex}])[0]
    assert py == js and py["intact"] is False and "damaged or forged" in py["why"]
    # the same stamp written 6 is genuine in both
    good = text.replace(written, "6", 1)
    assert verify(book, json.loads(good), signer.public_key_hex)["intact"] is True
    assert node_verify([{"book": book, "stamps_text": good, "key": signer.public_key_hex}])[0]["intact"] is True


def _forged_with_kind(signer, kind, drop_key):
    """A key holder's receipt whose kind is ``kind`` (a book append() would not write), optionally with the key removed."""
    ev = {"a": 1}
    fp = fingerprint({"n": 1, "at_ms": 5, "kind": kind, "event": ev, "prev": GENESIS})
    r = {"n": 1, "at_ms": 5, "kind": kind, "event": ev, "prev": GENESIS, "fp": fp, "sig": signer.sign(fp)}
    if drop_key:
        del r["kind"]
    head = {"count": 1, "last_fp": fp}
    head["sig"] = signer.sign(fingerprint(head))
    return {"public_key": signer.public_key_hex, "head": head, "receipts": [r]}


@needs_node
@pytest.mark.parametrize("kind", [None, "", 5, ["x"]])
@pytest.mark.parametrize("drop", [False, True])
def test_b3_a_kind_that_is_not_text_or_is_missing_is_changed_in_both_checks(kind, drop):
    signer = Signer(Ed25519PrivateKey.generate())
    book = json.loads(json.dumps(_forged_with_kind(signer, kind, drop)))
    py = verify(book, None, signer.public_key_hex)
    js = node_verify([{"book": book, "stamps": None, "key": signer.public_key_hex}])[0]
    assert py == js and py["intact"] is False and py["first_bad"] == 1


@pytest.mark.parametrize("kind", [None, "", 5, ["x"], b"x"])
def test_b3_append_refuses_a_kind_that_is_not_a_non_empty_text(kind):
    c = CarbonCopy(Signer(Ed25519PrivateKey.generate()))
    with pytest.raises(ValueError):
        c.append(kind, {"a": 1})
    assert c.receipts() == []


@needs_node
@pytest.mark.parametrize("key", ["n", "at_ms", "event", "prev", "fp", "sig"])
def test_b3_every_missing_sealed_key_is_changed_in_both_checks(key):
    signer, c = make_book()
    book = json.loads(json.dumps(c.book()))
    del book["receipts"][1][key]
    py = verify(book, None, signer.public_key_hex)
    js = node_verify([{"book": book, "stamps": None, "key": signer.public_key_hex}])[0]
    assert py == js and py["intact"] is False and py["first_bad"] == 2


# ---------------------------------------------------------------- C5
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


def replay(client, mode=None):
    rows = client.get("/api/recorded", params={"scenario": DAY, "model": MODEL}).json()
    pick = sorted((r for r in rows if r["mode"] == "enforce"), key=lambda r: -(r["attempts"] or 0))[0]
    params = {"line": pick["line"], "speed": 100, **({"mode": mode} if mode else {})}
    assert client.get("/api/replay", params=params).status_code == 200
    return client.get("/api/carbon", params={"mode": mode} if mode else {}).json()


@pytest.mark.parametrize("mode", ["enforce", "observe"])
def test_c5_every_run_book_starts_with_a_sealed_run_receipt(client, mode):
    got = replay(client, mode)
    first = got["receipts"][0]
    assert first["kind"] == "run" and first["n"] == 1
    assert first["event"]["mode"] == mode and first["event"]["source"] == "recorded"
    assert first["event"]["scenario"] == DAY and first["event"]["model"] == MODEL and first["event"]["started"]
    assert [r["kind"] for r in got["receipts"]].count("run") == 1
    key = client.get("/api/carbon/key").json()["public_key"]
    assert verify({k: got[k] for k in ("public_key", "head", "receipts")}, None, key)["intact"] is True
    assert run_of(got["receipts"]) == first["event"]


def test_c5_changing_what_the_run_was_is_caught(client):
    got = replay(client, "observe")
    key = client.get("/api/carbon/key").json()["public_key"]
    lie = {k: copy.deepcopy(got[k]) for k in ("public_key", "head", "receipts")}
    lie["receipts"][0]["event"]["mode"] = "enforce"
    out = verify(lie, None, key)
    assert out["intact"] is False and out["first_bad"] == 1


def test_c5_run_event_only_takes_known_modes_and_sources():
    for bad in (("auto", "live"), ("enforce", "replayed")):
        with pytest.raises(ValueError):
            run_event(bad[0], bad[1], "S", "m")
    assert run_of([]) is None and run_of([{"kind": "verdict", "event": {}}]) is None


def test_c5_the_ledger_takes_model_scenario_and_time_from_the_run_receipt(web):
    signer = Signer(Ed25519PrivateKey.generate())
    book = CarbonCopy(signer)
    book.append("run", run_event("enforce", "live", "S6_never_arrived", "sealed-model", started_ms=1_700_000_000_000))
    rec = {"scenario": "WRONG", "model": "WRONG", "mode": "observe", "ts": "1999-01-01T00:00:00Z",
           "verdicts": [{"id": "v1", "tool": "create_refund", "args": {"capture_id": "C"}, "amount": 5.0, "decision": "HOLD",
                         "findings": []}], "outcome": {"ledger": []}, "paypal_backend": "standin"}
    row = web._ledger_from(rec, live=True, book=book)[0]
    assert (row["model"], row["scenario"], row["when"]) == ("sealed-model", "S6_never_arrived", "2023-11-14T22:13:20Z")
    assert row["arm"] == "Carbon Copy ON"
    # rows with no book (the recorded results files) read as they always did
    assert web._ledger_from(rec)[0]["model"] == "WRONG"
    # a book that has no run receipt gives the row nothing it cannot back
    bare = web._ledger_from(rec, live=True, book=CarbonCopy(signer))[0]
    assert (bare["model"], bare["scenario"], bare["when"]) == ("", "", "")


@needs_node
def test_c5_the_header_reads_the_sealed_run_not_the_api_fields():
    book = {"mode": "enforce", "source": "live run", "receipts": [
        {"kind": "run", "event": {"mode": "observe", "source": "recorded", "scenario": "s", "model": "m"}}]}
    prog = ("let CC=JSON.parse(process.argv[1]);\n" + between("function ccRun", "function drawCarbon")
            + "\nconsole.log(JSON.stringify([ccRun(), ccRunMode()]));")
    got = json.loads(node(prog, book))
    assert got[1] == "observe" and got[0]["source"] == "recorded"
    book["receipts"][0]["kind"] = "note"
    assert json.loads(node(prog, book)) == [None, None]


def test_c5_the_screen_never_displays_the_unsealed_mode_or_source():
    assert "CC.source" not in APPJS
    assert "CC.mode" not in between("function drawCarbon", "async function loadCarbon")
    assert "CC.mode" not in between('$("#ccSwitch").addEventListener', '$("#ccCheck")')


# ---------------------------------------------------------------- C6
def test_c6_the_device_keeps_100_runs_and_the_readme_says_what_eviction_means():
    assert re.search(r"DEV_MAX_RUNS = 100\b", APPJS)
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    limits = readme[readme.index("## Limits we know about"):]
    assert "100 runs" in limits and "kept no stamp for this run" in limits and "reads intact" in limits


def test_c6_the_no_stamp_line_sits_directly_under_the_verdict():
    check = between('$("#ccCheck").addEventListener', '$("#ccTamper")')
    assert check.index("ccStamp(out) + ccNotes()") < check.index("All ${out.count} receipts")
    assert "kept no stamp for this run" in APPJS


@needs_node
def test_c6_a_device_holding_100_runs_still_has_the_first_one():
    store = between("const DEVICE =", "const ARMS")
    prog = ("const mem={};global.localStorage={getItem:k=>(k in mem?mem[k]:null),setItem:(k,v)=>{mem[k]=String(v)},removeItem:k=>{delete mem[k]}};\n"
            + store + "\nconst st=(i)=>({count:1,last_fp:'a'.repeat(64),sig:'s'+i,public_key:'b'.repeat(64)});\n"
            "for(let i=0;i<101;i++) deviceKeep('run'+i, st(i));\n"
            "console.log(JSON.stringify([deviceStamps('run0').length, deviceStamps('run1').length, deviceStamps('run100').length]));")
    assert json.loads(node(prog, None)) == [0, 1, 1]       # 101 runs: only the very oldest is let go


# ---------------------------------------------------------------- C7
@needs_node
def test_c7_each_button_fetches_the_current_book_before_it_acts():
    for start, end, first_use in (
        ('$("#ccCheck").addEventListener', '$("#ccTamper")', "checkOnDevice"),
        ('$("#ccTamper").addEventListener', '$("#ccForge")', 'fetch("/api/carbon/tamper'),
        ('$("#ccForge").addEventListener', '$("#ccDownload")', 'fetch("/api/carbon/forge'),
        ('$("#ccDownload").addEventListener', "/* the footer", "bookParts()"),
    ):
        body = between(start, end)
        assert "await refreshBook()" in body, start
        assert body.index("await refreshBook()") < body.index(first_use), start


@needs_node
def test_c7_refresh_replaces_a_stale_copy_with_the_servers_current_book():
    prog = ("let CC={session:'abc',receipts:[1]}, CC_PICK=null; let drawn=0, asked=null; const drawCarbon=()=>{drawn++};\n"
            "global.fetch=async(u)=>{asked=u; return {ok:true,json:async()=>({session:'abc',receipts:[1,2,3]})}};\n"
            + between("async function refreshBook", "const NO_FRESH")
            + "\n(async()=>{const ok=await refreshBook(); console.log(JSON.stringify([ok,CC.receipts.length,asked,drawn]));})();")
    assert json.loads(node(prog, None)) == [True, 3, "/api/carbon?sid=abc", 1]


# ---------------------------------------------------------------- C8
def test_c8_the_attacker_stays_on_the_stand_in_and_knows_what_is_fixed():
    agent = json.loads((ROOT / ".kiro" / "agents" / "carbon-attacker.json").read_text(encoding="utf-8"))
    prompt = agent["prompt"]
    assert "PAYPAL_MODE=standin" in prompt and "never start the sandbox" in prompt
    for label in ("C1", "C2", "C3", "C4", "C5", "C6", "C7"):
        assert f"({label})" in prompt
    for label in ("A1", "A6"):
        assert label in prompt


def test_c8_the_spec_carries_requirement_12_and_task_12():
    spec = ROOT / ".kiro" / "specs" / "carbon-copy"
    assert "### Requirement 12" in (spec / "requirements.md").read_text(encoding="utf-8")
    assert "## Task 12" in (spec / "design.md").read_text(encoding="utf-8")
    tasks = (spec / "tasks.md").read_text(encoding="utf-8")
    assert re.search(r"- \[x\] 12\. ", tasks) and "12.10" in tasks
