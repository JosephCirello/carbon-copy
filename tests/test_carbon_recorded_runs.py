"""The book on every recorded run (Requirement 16.10). Marked ``recorded``: the default run skips it (pytest.ini),
CI runs it as its own step:  .venv\\Scripts\\python.exe -m pytest -m recorded -q

Every recorded run (the open models' in results/, the frontier models' in results/frontier/, the same picks the
app's replay offers) is replayed in BOTH arms (the check on, nothing checking) the way /api/replay does it: the recorded
words and tool calls, with the rule book and the PayPal stand-in running now, a sealed ``run`` receipt first, a stamp
for the device after every event, and every hold declined by the owner. Then, for every book:

  1. Python's check, with the device's stamps and pinned key, says intact; after a JSON round trip, intact.
  2. Every receipt changed, one at a time: caught at that receipt (every receipt of every book).
  3. tamper_demo's change is caught at the receipt it changed; forge_demo (rewritten and re-signed under a new key)
     is caught; two receipts swapped is caught; the last receipt cut off and the head re-signed by the REAL key is
     caught with the device's last stamp (and, with no stamp at all, reads intact: the limit the README states).
  4. The browser's check (static/carbon_verify.js under node, in batches) gives the same answer as Python on the
     honest, changed, forged, swapped and cut-off books and on every 15th one-receipt change.

The test prints the numbers it measured (run it with ``-q``; they are printed even without ``-s``).
It needs no network and no key: the stand-in PayPal, a signer made in memory.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

import pytest

pytestmark = pytest.mark.recorded

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from receipts import measure  # noqa: E402
from receipts.carbon import CarbonCopy, Signer, fingerprint, forge_demo, run_event, tamper_demo, verify  # noqa: E402
from receipts.core import Receipts  # noqa: E402
from receipts.paypal import make_paypal  # noqa: E402
from receipts.scenarios import load  # noqa: E402

NODE = shutil.which("node")
BATCH = 300                 # cases handed to one node process
SAMPLE_EVERY = 15           # every 15th one-receipt change also goes through the browser's check

RUNNER = r"""
const { verify } = require(process.argv[2]);
const cases = JSON.parse(require("fs").readFileSync(process.argv[3], "utf8"));
(async () => {
  const out = [];
  for (const c of cases) out.push(await verify(c.book, c.stamps, c.key));
  console.log(JSON.stringify(out));
})();
"""


def recorded_runs():
    """(group, run) for every recorded run the replay offers, errored runs left out as the replay leaves them out."""
    for group, folder in (("open", ROOT / "results"), ("frontier", ROOT / "results" / "frontier")):
        for rec in measure._pick(folder):
            if rec["outcome"].get("class") in ("ERROR", "NO_TOOL_CALLS"):
                continue
            yield group, rec


def replay(rec, mode, scenarios, policy, signer):
    """One recorded run, replayed exactly as /api/replay does (app.py): its own book, a sealed run receipt first,
    the recorded words and calls through Receipts now, a stamp after each event. Every hold is then declined."""
    scn = scenarios[rec["scenario"]]
    pp = make_paypal(scn.get("paypal", {}), scn["id"])
    carbon = CarbonCopy(signer)
    stamps = []
    r = Receipts(scn, pp, mode=mode, policy=dict(policy), carbon=carbon)
    carbon.append("run", run_event(r.mode, "recorded", r.scenario["id"], rec["model"], title=r.scenario.get("title")))
    last_text = ""
    for e in rec["events"]:
        if e["type"] == "say" and e.get("where") == "reply":
            last_text = e["text"]
            r.note_words(e["text"], "reply")
        elif e["type"] == "call":
            r.call(e["tool"], e["args"], step_text=last_text)
        stamps.append(carbon.stamp())
    for h in list(r.holds):
        if h.get("status") == "WAITING":
            stamps.append(r.decline(h["id"])["stamp"])
    r.outcome()
    stamps.append(carbon.stamp())
    pp.close()
    return carbon, stamps


def cut_last(book, signer):
    """The real key holder deletes the last receipt and signs a new head for the shorter book."""
    b = copy.deepcopy(book)
    b["receipts"] = b["receipts"][:-1]
    count, last_fp = len(b["receipts"]), b["receipts"][-1]["fp"]
    b["head"] = {"count": count, "last_fp": last_fp, "sig": signer.sign(fingerprint({"count": count, "last_fp": last_fp}))}
    return b


def swap_two(book):
    b = copy.deepcopy(book)
    rs = b["receipts"]
    rs[1], rs[2] = rs[2], rs[1]
    return b


def change(receipt):
    """One change to one receipt: a field of its event, or its kind when the event is empty."""
    ev = receipt["event"]
    if isinstance(ev, dict) and ev:
        k = sorted(ev)[0]
        v = ev[k]
        ev[k] = (v + "x") if isinstance(v, str) else "changed"
        if ev[k] == v:
            ev[k] = "changed"
    else:
        receipt["kind"] = receipt["kind"] + "x"


def same_answer(a, b) -> bool:
    return bool(a.get("intact")) == bool(b.get("intact")) and a.get("first_bad") == b.get("first_bad") and a.get("why") == b.get("why")


class Browser:
    """The browser's check under node, fed in batches; every answer is compared with Python's."""

    def __init__(self):
        self.cases, self.expect, self.same, self.different, self.seconds, self.examples = [], [], 0, 0, 0.0, []
        self.dir = Path(tempfile.mkdtemp(prefix="carbon_recorded_"))
        (self.dir / "runner.js").write_text(RUNNER, encoding="utf-8")

    def add(self, tag, book, stamps, key, python_answer):
        self.cases.append({"book": book, "stamps": stamps, "key": key})
        self.expect.append((tag, python_answer))
        if len(self.cases) >= BATCH:
            self.flush()

    def flush(self):
        if not self.cases:
            return
        (self.dir / "cases.json").write_text(json.dumps(self.cases, allow_nan=False), encoding="utf-8")
        t = time.time()
        done = subprocess.run([NODE, str(self.dir / "runner.js"), str(ROOT / "static" / "carbon_verify.js"), str(self.dir / "cases.json")],
                              capture_output=True, text=True, encoding="utf-8", timeout=900)
        self.seconds += time.time() - t
        assert done.returncode == 0, done.stderr[:500]
        for (tag, py), js in zip(self.expect, json.loads(done.stdout)):
            if same_answer(js, py):
                self.same += 1
            else:
                self.different += 1
                self.examples.append({"case": tag, "python": py, "browser": js})
        self.cases, self.expect = [], []

    def close(self):
        self.flush()
        shutil.rmtree(self.dir, ignore_errors=True)


@pytest.fixture(scope="module")
def measured():
    saved = os.environ.get("PAYPAL_MODE")
    os.environ["PAYPAL_MODE"] = "standin"            # the stand-in, never a real PayPal account
    try:
        _, scns = load()
        scenarios = {s["id"]: s for s in scns}
        policy = json.loads((ROOT / "scenarios" / "scenarios.json").read_text(encoding="utf-8"))["policy"]
        from receipts.rules import DEFAULT_POLICY
        policy = {**DEFAULT_POLICY, **policy}        # the rules every visitor starts from (app.DEFAULT_RULES["policy"])
        signer = Signer(Ed25519PrivateKey.generate())
        browser = Browser() if NODE else None
        t0 = time.time()
        tally, problems = Counter(), []
        sizes, runs = [], 0
        changes = caught_at = caught_elsewhere = missed = 0
        for group, rec in recorded_runs():
            runs += 1
            for mode in ("enforce", "observe"):
                tag = f"{group}:{rec['model']}:{rec['scenario']}:{mode}:rep{rec.get('rep')}"
                carbon, stamps = replay(rec, mode, scenarios, policy, signer)
                book = carbon.book()
                key = book["public_key"]
                sizes.append(len(book["receipts"]))
                rt = json.loads(json.dumps(book, allow_nan=False))        # what a browser sends back
                t = tamper_demo(book)
                f = forge_demo(book)
                sw, cut = swap_two(rt), cut_last(rt, signer)
                answers = {"intact": (rt, verify(book, stamps, key), True), "round_trip": (rt, verify(rt, stamps, key), True),
                           "tamper": (t["book"], t["result"], False), "forge": (f["book"], verify(f["book"], stamps, key), False),
                           "swap": (sw, verify(sw, stamps, key), False), "cut": (cut, verify(cut, stamps, key), False),
                           "cut_no_stamps": (cut, verify(cut, [], key), True)}
                for name, (b, got, want) in answers.items():
                    ok = bool(got.get("intact")) == want and (name != "tamper" or got.get("first_bad") == t["n"])
                    tally[f"{name}_{'ok' if ok else 'FAIL'}"] += 1
                    if not ok:
                        problems.append({"run": tag, "what": name, "got": got})
                    if browser and name in ("intact", "tamper", "forge", "swap", "cut"):
                        browser.add(f"{tag}:{name}", b, stamps, key, got)
                for i in range(len(rt["receipts"])):               # every receipt, changed one at a time
                    b = copy.deepcopy(rt)
                    change(b["receipts"][i])
                    got = verify(b, stamps, key)
                    changes += 1
                    if got.get("intact"):
                        missed += 1
                        problems.append({"run": tag, "what": "change missed", "receipt": i + 1})
                    elif got.get("first_bad") != i + 1:
                        caught_elsewhere += 1
                        problems.append({"run": tag, "what": "change named another receipt", "receipt": i + 1, "named": got.get("first_bad")})
                    else:
                        caught_at += 1
                    if browser and changes % SAMPLE_EVERY == 0:
                        browser.add(f"{tag}:change#{i + 1}", b, stamps, key, got)
        if browser:
            browser.close()
        return {"runs": runs, "books": len(sizes), "receipts": sum(sizes), "min": min(sizes), "max": max(sizes),
                "tally": dict(sorted(tally.items())), "changes": changes, "caught_at_that_receipt": caught_at,
                "caught_elsewhere": caught_elsewhere, "missed": missed, "problems": problems[:20],
                "browser": None if browser is None else {"answers": browser.same + browser.different, "same": browser.same,
                                                        "different": browser.different, "examples": browser.examples[:5],
                                                        "node_seconds": round(browser.seconds, 1)},
                "seconds": round(time.time() - t0, 1)}
    finally:
        if saved is None:
            os.environ.pop("PAYPAL_MODE", None)
        else:
            os.environ["PAYPAL_MODE"] = saved


def test_every_recorded_run_is_replayed_in_both_arms(measured):
    assert measured["runs"] > 0 and measured["books"] == 2 * measured["runs"]
    assert measured["min"] >= 1


def test_every_honest_book_is_intact(measured):
    n = measured["books"]
    assert measured["tally"].get("intact_ok") == n and measured["tally"].get("round_trip_ok") == n, measured["problems"]
    assert "intact_FAIL" not in measured["tally"] and "round_trip_FAIL" not in measured["tally"]


def test_every_one_receipt_change_is_caught_at_that_receipt(measured):
    assert measured["changes"] == measured["receipts"]
    assert measured["caught_at_that_receipt"] == measured["changes"], measured["problems"]
    assert measured["caught_elsewhere"] == 0 and measured["missed"] == 0


def test_every_forgery_swap_and_cut_off_is_caught_with_the_devices_stamp(measured):
    n = measured["books"]
    for name in ("tamper", "forge", "swap", "cut"):
        assert measured["tally"].get(f"{name}_ok") == n, (name, measured["problems"])
    # with no stamp at all a cut-off book signed by the real key reads intact: the limit the README states
    assert measured["tally"].get("cut_no_stamps_ok") == n


@pytest.mark.skipif(NODE is None, reason="node is not on PATH, so the browser check cannot be run here")
def test_the_browser_agrees_with_python_on_every_case(measured, capsys):
    b = measured["browser"]
    assert b["answers"] > 0 and b["different"] == 0, b["examples"]
    with capsys.disabled():
        print("\n--- What we measured on the book ---")
        print(f"recorded runs: {measured['runs']}; books (both arms): {measured['books']}; receipts: {measured['receipts']:,} "
              f"({measured['min']} to {measured['max']} per book)")
        print(f"honest books intact: {measured['tally']['intact_ok']} of {measured['books']} "
              f"(and {measured['tally']['round_trip_ok']} after a JSON round trip)")
        print(f"one-receipt changes caught at that receipt: {measured['caught_at_that_receipt']:,} of {measured['changes']:,}; "
              f"named another receipt: {measured['caught_elsewhere']}; missed: {measured['missed']}")
        print(f"changed by tamper_demo / forged and re-signed / two swapped / cut off with the real key, caught: "
              f"{measured['tally']['tamper_ok']} / {measured['tally']['forge_ok']} / {measured['tally']['swap_ok']} / {measured['tally']['cut_ok']} of {measured['books']}")
        print(f"browser (node) and Python gave the same answer on {b['same']:,} of {b['answers']:,} checks; different: {b['different']}")
        print(f"time: {measured['seconds']} s in all, {b['node_seconds']} s of it in the browser's check")
