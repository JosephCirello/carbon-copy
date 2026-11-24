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
