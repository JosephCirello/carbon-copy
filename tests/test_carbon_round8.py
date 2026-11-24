"""Task 25: the hosted /mcp answers a client (Requirement 20), and the README's first screen is true.

The MCP library's DNS-rebinding protection stays ON; only the allowed Host and Origin values are set. No network, no keys.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from receipts import mcp_server  # noqa: E402
from receipts.carbon import Signer  # noqa: E402
from tests.readme_counts import repo_counts  # noqa: E402

README = (ROOT / "README.md").read_text(encoding="utf-8")
HOSTED = "carbon-copy-ywv3.onrender.com"
INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def mcp_app(env: dict):
    srv, _ = mcp_server.build(signer=Signer(Ed25519PrivateKey.generate()))
    return srv.streamable_http_app(streamable_http_path="/", transport_security=mcp_server.transport_security(env))


def initialize(env: dict, host: str, origin: str | None = None):
    headers = {**HEADERS, "Host": host, **({"Origin": origin} if origin else {})}
    with TestClient(mcp_app(env), base_url="http://testserver") as c:
        return c.post("/", content=json.dumps(INIT), headers=headers)


# ---- item 1 and 2: the allowed hosts ------------------------------------------------------------------------------

@pytest.mark.parametrize("env", [{"RECEIPTS_ALLOWED_HOSTS": HOSTED}, {"RENDER_EXTERNAL_HOSTNAME": HOSTED},
                                 {"RECEIPTS_ALLOWED_HOSTS": f"other.example, {HOSTED.upper()} ,"}])
def test_the_hosted_name_is_accepted_when_configured_either_way(env):
    r = initialize(env, HOSTED)
    assert r.status_code == 200, r.text
    assert "serverInfo" in r.text


def test_the_hosted_name_with_a_port_and_an_https_origin_are_accepted_when_configured():
    env = {"RENDER_EXTERNAL_HOSTNAME": HOSTED}
    assert initialize(env, HOSTED + ":443", origin="https://" + HOSTED).status_code == 200


def test_an_unknown_host_is_still_refused_with_or_without_the_hosted_name_configured():
    for env in ({}, {"RECEIPTS_ALLOWED_HOSTS": HOSTED}, {"RENDER_EXTERNAL_HOSTNAME": HOSTED}):
        for host in ("evil.example.com", "evil.example.com:443", HOSTED + ".evil.example.com", "x" + HOSTED):
            r = initialize(env, host)
            assert r.status_code == 421, (env, host, r.status_code)
            assert "Invalid Host header" in r.text


def test_with_nothing_configured_the_hosted_name_is_refused_as_before_and_localhost_works():
    assert initialize({}, HOSTED).status_code == 421
    assert initialize({}, "localhost:8091").status_code == 200
    assert initialize({}, "127.0.0.1:8091").status_code == 200
    assert initialize({}, "[::1]:8091").status_code == 200


def test_a_foreign_origin_is_refused_even_on_an_allowed_host():
    r = initialize({"RECEIPTS_ALLOWED_HOSTS": HOSTED}, HOSTED, origin="https://evil.example.com")
    assert r.status_code == 403 and "Invalid Origin header" in r.text


def test_the_protection_stays_on_and_only_plain_names_are_taken():
    ts = mcp_server.transport_security({"RECEIPTS_ALLOWED_HOSTS": f"*, *.onrender.com, a b, https://{HOSTED}/mcp/, ,.x, :9, user@h"})
    assert ts.enable_dns_rebinding_protection is True
    assert mcp_server.allowed_host_names({"RECEIPTS_ALLOWED_HOSTS": "*, *.onrender.com, a b, .x, :9, user@h"}) == []
    assert mcp_server.allowed_host_names({"RECEIPTS_ALLOWED_HOSTS": f"https://{HOSTED}/mcp/"}) == [HOSTED]
    assert "*" not in ts.allowed_hosts and not any(h.startswith("*") for h in ts.allowed_hosts)
    assert HOSTED in ts.allowed_hosts and f"https://{HOSTED}" in ts.allowed_origins
    assert {"127.0.0.1:*", "localhost:*", "[::1]:*"} <= set(ts.allowed_hosts)


def test_both_variables_add_up_and_duplicates_collapse():
    names = mcp_server.allowed_host_names({"RECEIPTS_ALLOWED_HOSTS": "a.example,b.example", "RENDER_EXTERNAL_HOSTNAME": "a.example"})
    assert names == ["a.example", "b.example"]
    assert mcp_server.allowed_host_names({}) == []


def test_the_real_app_uses_the_settings_in_a_fresh_process():
    """app.py, started with the variable set, answers the hosted Host through its own middleware, and refuses a stranger."""
    code = (
        "import json, sys\n"
        "from fastapi.testclient import TestClient\n"
        "import app\n"
        f"body = {json.dumps(json.dumps(INIT))}\n"
        f"h = {HEADERS!r}\n"
        "out = {}\n"
        "with TestClient(app.app) as c:\n"
        f"    out['hosted'] = c.post('/mcp/', content=body, headers={{**h, 'Host': {HOSTED!r}}}).status_code\n"
        "    out['stranger'] = c.post('/mcp/', content=body, headers={**h, 'Host': 'evil.example.com'}).status_code\n"
        "print('RESULT' + json.dumps(out))\n")
    for var in ("RECEIPTS_ALLOWED_HOSTS", "RENDER_EXTERNAL_HOSTNAME"):
        env = {k: v for k, v in os.environ.items() if k not in ("RECEIPTS_ALLOWED_HOSTS", "RENDER_EXTERNAL_HOSTNAME", "CARBON_COPY_KEY")}
        env.update({"PAYPAL_MODE": "standin", var: HOSTED})
        done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
        line = next((ln for ln in done.stdout.splitlines() if ln.startswith("RESULT")), "")
        assert line, done.stderr[-800:]
        assert json.loads(line[6:]) == {"hosted": 200, "stranger": 421}, var


def test_render_yaml_names_the_hosted_host_and_stdio_has_no_host_check():
    yaml = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert re.search(r"RECEIPTS_ALLOWED_HOSTS\s*\n\s*value:\s*\"?" + re.escape(HOSTED), yaml)
    # the stdio entry point never builds an HTTP app, so the settings do not touch it
    assert "transport_security" not in (ROOT / "receipts" / "mcp_server.py").read_text(encoding="utf-8").split('if __name__')[1]


# ---- items 3 to 5: the README, with its numbers read from the repository ------------------------------------------

def test_the_first_screen_has_the_judge_block_with_numbers_read_from_the_repository():
    head = README[:README.index("## Try it")]
    assert head.index("# Carbon Copy") < head.index("**Kiroween 2026 · Resurrection.**") < head.index("## Kiroween 2026: Resurrection") \
        < head.index("### For judges, in 30 seconds") < head.index("### At a glance")
    judges = head[head.index("### For judges, in 30 seconds"):head.index("### At a glance")]
    assert len([ln for ln in judges.splitlines() if ln.startswith("- ")]) in (4, 5)
    for click in ("Run Maya's day", "Decline the double payment on her phone", "Try to forge the record"):
        assert click in judges
    assert "Video: (link added at submission)" in judges and "https://carbon-copy-ywv3.onrender.com" in judges
    # the attacker numbers: the findings counted in the four reports
    sessions = ROOT / "docs" / "kiro-sessions"
    per_report = []
    for prefix, pat in (("10_", r"^\*\*\d+\. "), ("12_", r"^\d+\. \*\*"), ("17_", r"^\*\*F\d+\. "), ("23_", r"^\*\*\d+\. ")):
        text = next(sessions.glob(prefix + "*.md")).read_text(encoding="utf-8")
        body = text.split("## Proven findings")[1] if "## Proven findings" in text else text.split("\n## Findings")[1]
        body = re.split(r"\n## (?:Caught|Tried and caught|Not proven)", body)[0]
        per_report.append(len(re.findall(pat, body, re.M)))
    assert per_report == [6, 7, 13, 12]
    assert f"4 rounds of attacks" in judges and f"{sum(per_report)} weak spots" in judges
    assert f"({' + '.join(map(str, per_report))})" in judges
    # the receipts number: the one "What we measured on the book" prints, stated again
    measured = README[README.index("## What we measured on the book"):README.index("## How Kiro built it")]
    total = re.search(r"([\d,]+) receipts in all", measured).group(1)
    assert f"{total} receipts from recorded AI runs" in judges
    assert f"Every receipt of every book changed, one at a time: {total} of {total} caught" in measured


def test_the_four_pictures_exist_each_with_a_caption_and_03_and_07_sit_where_the_readme_talks_about_the_check_and_the_attacker():
    images = ROOT / "docs" / "images"
    glance = README[README.index("### At a glance"):README.index("Maya runs a nine-person")]
    for name in ("01_two_sides.jpg", "02_maya_declines.jpg", "04_change_one_caught.jpg", "05_forgery_caught.jpg"):
        assert (images / name).is_file() and f"docs/images/{name}" in glance
    rows = [ln for ln in glance.splitlines() if ln.startswith("|")]
    assert len(rows) == 4 and all(len([c for c in r.strip("|").split("|") if c.strip()]) == 4 for r in rows[2:])      # a caption under each
    how_it_works = README[README.index("## How it works"):README.index("## What we measured on the book")]
    assert "docs/images/03_check_intact.jpg" in how_it_works and (images / "03_check_intact.jpg").is_file()
    attacker = README[README.index("- **Custom agent.**"):README.index("- **Powers.**")]
    assert "docs/images/07_kiro_attacker.jpg" in attacker and (images / "07_kiro_attacker.jpg").is_file()


def test_the_kiro_table_counts_are_read_from_the_repository():
    section = README[README.index("## How Kiro built it"):README.index("## Limits we know about")]
    table = section.split("**Spec first, never vibe.**")[0]
    assert section.index("| Kiro feature | How we used it | Why it mattered |") < section.index("- **Which Kiro surface")
    rows = {r.split("|")[1].strip(): r for r in table.splitlines() if r.startswith("| ") and not r.startswith("| Kiro feature")}
    assert list(rows) == ["Spec", "Steering", "Hooks", "MCP", "Custom agent", "Property-based tests", "Kiro CLI headless"]
    held = repo_counts()
    assert f"{held['requirements']} requirements, {held['tasks']} tasks" in rows["Spec"]
    changes = len(re.findall(r"^\d+\. \*\*", README.split("The spec changed when gaps were found,")[-1].split("## Limits")[0], re.M))
    assert f"changed {changes} times" in rows["Spec"]
    steering = list((ROOT / ".kiro" / "steering").glob("*.md"))
    assert f"{len(steering)} files" in rows["Steering"] and all(p.name in rows["Steering"] for p in steering)
    hooks = sum(len(json.loads(p.read_text(encoding="utf-8"))["hooks"]) for p in (ROOT / ".kiro" / "hooks").glob("*.json"))
    assert rows["Hooks"].split("|")[2].strip().startswith(f"{hooks}, in `.kiro/hooks/*.json`")
    assert "carbon-copy" in json.loads((ROOT / ".kiro" / "settings" / "mcp.json").read_text(encoding="utf-8"))["mcpServers"]
    assert f"{held['runs']} recorded sessions" in rows["Kiro CLI headless"]
    assert "4 runs, 38 proven findings" in rows["Custom agent"]
    assert "hypothesis" in rows["Property-based tests"]
    assert "**Spec first, never vibe.**" in section and "A change nobody wrote down" in section


def test_point_your_own_ai_at_it_says_how_what_and_the_limits():
    sec = README[README.index("## Point your own AI at it"):README.index("## What came from Receipts")]
    assert "https://carbon-copy-ywv3.onrender.com/mcp/" in sec
    block = json.loads(re.search(r"```json\n(.*?)\n```", sec, re.S).group(1))
    server = next(iter(block["mcpServers"].values()))
    assert server["url"] == "https://carbon-copy-ywv3.onrender.com/mcp/" and "command" not in server      # Kiro's remote form: url (+ headers)
    assert "python examples/mcp_client_demo.py https://carbon-copy-ywv3.onrender.com/mcp/" in sec
    assert (ROOT / "examples" / "mcp_client_demo.py").is_file()
    for word in ("blocked_by_receipts", "held_by_receipts", "Blocked", "Held", "Cleared", "carbon_book",
                 "python -m receipts.carbon verify mcp-book.json --key-file HOSTED_KEY.txt",
                 "shared by every visitor", "PayPal stand-in", "60 requests a minute", "256 KB", "20 MB"):
        assert word in sec, word
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "MCP_MAX_BODY = 256 * 1024" in app_text and "MCP_CALLS_PER_MINUTE = 60" in app_text


def test_the_spec_has_requirement_20_design_and_task_25():
    spec = ROOT / ".kiro" / "specs" / "carbon-copy"
    assert "### Requirement 20:" in (spec / "requirements.md").read_text(encoding="utf-8")
    assert "## Task 25:" in (spec / "design.md").read_text(encoding="utf-8")
    assert re.search(r"^- \[x\] 25\. ", (spec / "tasks.md").read_text(encoding="utf-8"), re.M)
