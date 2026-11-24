"""The browser's check and the Python check must say the same thing about the same book (task 9, D5, F9).

``static/carbon_verify.js`` is run under node (which has ``crypto.subtle`` with Ed25519). The book is written
through Receipts with tricky content: unicode, keys that sort differently by code point than by UTF-16 unit, 298.5,
2**60, 9007199254740993, NaN, a lone surrogate, nested lists and types JSON does not have. Skipped when node is not
on the path. No network, no keys on disk.
"""
from __future__ import annotations

import copy
import datetime
import decimal
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from receipts.carbon import CarbonCopy, Signer, forge_demo, verify  # noqa: E402
from receipts.core import Receipts  # noqa: E402
from receipts.paypal import StandIn  # noqa: E402
from receipts.scenarios import by_id  # noqa: E402

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not on PATH, so the browser check cannot be run here")

RUNNER = """
const { verify } = require(process.argv[2]);
const cases = JSON.parse(require("fs").readFileSync(process.argv[3], "utf8"));
(async () => {
  const out = [];
  for (const c of cases) out.push(await verify(c.book, c.stamps, c.key));
  console.log(JSON.stringify(out));
})();
"""


def tricky_book():
    scn = by_id()["S5_i_am_the_owner"]
    pp = StandIn(scn["paypal"], scn["id"])
    carbon = CarbonCopy(Signer(Ed25519PrivateKey.generate()))
    r = Receipts(scn, pp, mode="enforce", carbon=carbon)
    r.emit(type="say", where="reply", text="café ☕ 😀 \ud83d lone", marker=None)
    r.emit(type="note", **{"\U00010000": "astral", "\uffff": "bmp", "é": "e", "Z": 1, "a\u0000b": "ctl"},
           numbers=[298.5, 2 ** 60, 9007199254740993, float(2 ** 60), float("nan"), float("inf"), -0.0, 1836.0, 7,
                    True, None, 2 ** 53 - 1, 2 ** 53],
           nested=[[1, [2, ["\ud800", {"k\udfff": (1, 2)}]]], []],
           odd=[decimal.Decimal("1.10"), datetime.date(2026, 1, 2), b"bytes", {"a-set"}])
    res = r.call("create_refund", {"capture_id": pp.ids["C.capture_id"], "amount": 420})
    out = r.approve(res["hold_id"])
    return carbon, out["stamp"]


def run_node(tmp_path, cases):
    (tmp_path / "runner.js").write_text(RUNNER, encoding="utf-8")
    (tmp_path / "cases.json").write_text(json.dumps(cases, allow_nan=False), encoding="utf-8")
    done = subprocess.run([NODE, str(tmp_path / "runner.js"), str(ROOT / "static" / "carbon_verify.js"),
                           str(tmp_path / "cases.json")], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_the_browser_check_agrees_with_python_on_a_book_of_tricky_content(tmp_path):
    carbon, tap_stamp = tricky_book()
    book = carbon.book()
    key = book["public_key"]
    stamps = [carbon.stamp(), {**tap_stamp}]
    through_a_browser = json.loads(json.dumps(book, allow_nan=False))      # what the page receives and sends back

    changed = copy.deepcopy(through_a_browser)
    changed["receipts"][1]["event"]["numbers"][0] = "299.5"            # receipt #2, the one with the tricky numbers
    forged = forge_demo(book)["book"]
    bad_stamp = {**stamps[0], "sig": "AAAA"}
    cut = copy.deepcopy(through_a_browser)                       # cut back to 2 receipts under the head of the whole book
    cut["receipts"] = cut["receipts"][:2]

    cases = [
        {"book": through_a_browser, "stamps": stamps, "key": key},
        {"book": through_a_browser, "stamps": [], "key": None},
        {"book": changed, "stamps": stamps, "key": key},
        {"book": forged, "stamps": stamps, "key": key},
        {"book": through_a_browser, "stamps": [bad_stamp], "key": key},
        {"book": through_a_browser, "stamps": ["not an object"], "key": key},
        {"book": cut, "stamps": stamps, "key": key},
        {"book": through_a_browser, "stamps": stamps[0], "key": key},      # stamps that are not a list
    ]
    got = run_node(tmp_path, cases)

    n = len(book["receipts"])
    assert got[0] == {"intact": True, "count": n}                 # untouched: intact in the browser
    assert got[1] == {"intact": True, "count": n}
    assert got[2]["intact"] is False and got[2]["first_bad"] == 2  # the first changed receipt is named (#2)
    assert got[3]["why"] == "it was signed with a different key than the one your device trusts"
    assert got[4]["why"] == "a stamp on your device is damaged or forged"
    assert got[5]["why"] == "a stamp on your device is damaged or forged"
    assert got[6]["why"] == "receipts are missing from the end of the book"
    assert got[7]["why"] == "a stamp on your device is damaged or forged"
    # the two checks give the same answer, word for word, on every case
    for case, out in zip(cases, got):
        assert verify(case["book"], case["stamps"], expected_key=case["key"]) == out


def test_node_names_the_right_receipt_when_the_changed_one_is_inside_the_stamped_part(tmp_path):
    carbon, tap_stamp = tricky_book()
    book = json.loads(json.dumps(carbon.book(), allow_nan=False))
    book["receipts"][-1]["event"]["status"] = "FAKE"            # the last receipt, which the stamp covers
    n = len(book["receipts"])
    got = run_node(tmp_path, [{"book": book, "stamps": [carbon.stamp()], "key": book["public_key"]}])[0]
    assert got["intact"] is False and got["first_bad"] == n and got["why"] == "its content was changed"


# ---- task 11: the attacker's findings, answered the same way by both checks ----------------------------------------

_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def _attack_cases():
    """(name, book, stamps, key, honest): each attack from the attacker's report built against a fresh honest book."""
    signer = Signer(Ed25519PrivateKey.generate())
    carbon = CarbonCopy(signer)
    carbon.append("verdict", {"t": 1795462000.001, "id": "h1", "amount": 1836.0, "verdict": "HOLD"})
    carbon.append("owner", {"t": 1795462000.002, "action": "declined", "hold_id": "h1"})
    carbon.append("note", {"t": 1e21, "x": 1})                          # A1: an event time no tool can hold
    carbon.append("note", {"x": 2})
    key, stamp = signer.public_key_hex, carbon.stamp()
    honest = json.loads(json.dumps(carbon.book(), allow_nan=False))
    cases = [("honest", honest, [stamp], key, True), ("honest with no key pinned", honest, None, None, True)]

    def variant(name, edit, pinned=(key, None)):
        for k in pinned:
            b = copy.deepcopy(honest)
            edit(b)
            cases.append((name, b, [stamp], k, False))

    for junk in ({}, 0, "", False, None, "x"):                          # A2
        variant(f"receipts is {junk!r}", lambda b, j=junk: b.__setitem__("receipts", j))
    variant("no receipts field", lambda b: b.pop("receipts"))
    for bad in ([], None, "book", 7):
        cases.append((f"book is {bad!r}", bad, None, key, False))
    variant("extra field on a receipt", lambda b: b["receipts"][1].update({"approved_by": "maya", "note": "by phone"}))   # A3
    variant("extra field on the first receipt", lambda b: b["receipts"][0].update({"x": 1}))
    variant("extra field beside the book", lambda b: b.update({"verdict": "approved"}))                    # allowed: not read
    variant("a sealed key removed", lambda b: b["receipts"][2].pop("kind"))
    sig = honest["receipts"][0]["sig"]
    last = sig[-3]
    base = _ALPHABET.index(last) & ~0xF
    for k in range(16):                                                 # A4: every spelling of the first signature
        other = sig[:-3] + _ALPHABET[base + k] + "=="
        if other == sig:
            continue
        variant("receipt signature spelled " + other[-4:], lambda b, o=other: b["receipts"][0].__setitem__("sig", o))
    head_sig = honest["head"]["sig"]
    base = _ALPHABET.index(head_sig[-3]) & ~0xF
    for k in range(16):
        other = head_sig[:-3] + _ALPHABET[base + k] + "=="
        if other == head_sig:
            continue
        variant("head signature spelled " + other[-4:], lambda b, o=other: b["head"].__setitem__("sig", o))
    st_base = _ALPHABET.index(stamp["sig"][-3]) & ~0xF
    for k in range(16):
        other = stamp["sig"][:-3] + _ALPHABET[st_base + k] + "=="
        cases.append(("stamp signature spelled " + other[-4:], copy.deepcopy(honest), [{**stamp, "sig": other}], key, other == stamp["sig"]))
    variant("signature without padding", lambda b: b["receipts"][3].__setitem__("sig", b["receipts"][3]["sig"].rstrip("=")))
    variant("signature with a newline", lambda b: b["receipts"][3].__setitem__("sig", b["receipts"][3]["sig"] + "\n"))
    spaced = " ".join(key[i:i + 2] for i in range(0, 64, 2))
    for bad in (spaced, key.upper(), key + "\n", key[:-2], "", None, 5):                       # A5
        variant(f"public key {bad!r}", lambda b, v=bad: b.__setitem__("public_key", v))
    old = copy.deepcopy(honest)                                                                 # old format
    for r in old["receipts"]:
        r["at"] = r.pop("at_ms") / 1000
    cases.append(("a book from before task 11", old, None, key, False))
    return cases


def test_both_checks_answer_every_attack_the_same_way_and_catch_it(tmp_path):
    cases = _attack_cases()
    js = run_node(tmp_path, [{"book": b, "stamps": s, "key": k} for _, b, s, k, _ in cases])
    same_spelling = 0
    for (name, book, stamps, key, honest), got_js in zip(cases, js):
        got_py = verify(copy.deepcopy(book), copy.deepcopy(stamps), key)
        assert got_py == got_js, (name, got_py, got_js)
        if name.startswith("stamp signature spelled") and honest:
            same_spelling += 1
        if name == "extra field beside the book":
            assert got_py["intact"] is True, name           # outside the three parts: not read, so not an alarm
        elif honest:
            assert got_py["intact"] is True, (name, got_py)
        else:
            assert got_py["intact"] is False, (name, got_py)
    assert same_spelling == 1                              # exactly one of the 16 stamp spellings is the real one


def test_the_reasons_the_attacks_get_are_the_plain_ones(tmp_path):
    cases = {c[0]: c for c in _attack_cases()}

    def both(name):
        _, book, stamps, key, _ = cases[name]
        py = verify(copy.deepcopy(book), copy.deepcopy(stamps), key)
        assert run_node(tmp_path, [{"book": book, "stamps": stamps, "key": key}])[0] == py
        return py

    assert both("receipts is {}")["why"] == "this is not a carbon-copy book we can read"
    assert both("extra field on a receipt")["why"] == "receipt #2 carries something outside its seal"
    assert both("signature without padding")["why"] == "its signature does not match"
    assert both("public key ''")["why"] == "its public key is not written the way a key must be"


def test_an_honest_book_with_a_huge_event_time_reads_intact_in_the_browser_too(tmp_path):
    """A1: the attacker's false alarm, with the time now sealed as whole milliseconds."""
    signer = Signer(Ed25519PrivateKey.generate())
    carbon = CarbonCopy(signer)
    for t in (1e21, 1e300, -5.0, 9007199254740.992, 1795462000.5):
        carbon.append("note", {"t": t, "x": 1})
    book = json.loads(json.dumps(carbon.book(), allow_nan=False))
    out = run_node(tmp_path, [{"book": book, "stamps": [carbon.stamp()], "key": signer.public_key_hex}])[0]
    assert out == {"intact": True, "count": 5} == verify(book, [carbon.stamp()], signer.public_key_hex)


# ---- task 14: "Try to change one" is checked in the browser, so both checks must agree on the changed copy -------------

def test_the_browser_and_python_agree_on_the_changed_copy_of_marias_book(tmp_path):
    from receipts.carbon import tamper_demo
    signer = Signer(Ed25519PrivateKey.generate())
    carbon = CarbonCopy(signer)
    carbon.append("run", {"mode": "enforce", "source": "recorded", "scenario": "S14", "model": "m", "title": "t",
                          "started": "2026-01-01T00:00:00Z", "t": 1795462000.0})
    carbon.append("verdict", {"t": 1795462000.001, "id": "h1", "amount": 1836.0, "verdict": "HOLD"})
    carbon.append("owner", {"t": 1795462000.002, "action": "declined", "hold_id": "h1"})
    carbon.append("note", {"t": 1795462000.003, "x": 1})
    real = carbon.book()
    key, stamps = signer.public_key_hex, [carbon.stamp()]
    demo = tamper_demo(real)
    page_copy = json.loads(json.dumps(demo["book"], allow_nan=False))        # what the page receives
    assert demo["n"] == 3 and demo["field"] == "action" and demo["after"] == "approved"
    got = run_node(tmp_path, [{"book": page_copy, "stamps": stamps, "key": key},
                              {"book": page_copy, "stamps": [], "key": None},
                              {"book": json.loads(json.dumps(real)), "stamps": stamps, "key": key}])
    want = verify(page_copy, stamps, expected_key=key)
    assert got[0] == want and want["intact"] is False and want["first_bad"] == 3
    assert got[0]["why"] == demo["result"]["why"] == "its content was changed"       # the server's own reason, word for word
    assert got[1] == demo["result"]                                                  # no stamps, no key: same as the server's run
    assert got[2] == {"intact": True, "count": len(real["receipts"])}               # the real book is still intact
