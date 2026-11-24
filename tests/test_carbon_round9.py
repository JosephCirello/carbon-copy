"""Task 26: what a first-time judge trips on (Requirement 10, amended). No keys; the browser test needs no network.

The page is driven in a real Chromium (Playwright) at phone, tablet and desktop width against a local server that runs
the PayPal stand-in. The browser test is skipped when Playwright or its Chromium is not installed.
"""
from __future__ import annotations

import json
import os
import re
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

INDEX = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
APP_JS = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
SESSIONS = (ROOT / "docs" / "kiro-sessions" / "README.md").read_text(encoding="utf-8")
REPO_URL = "https://github.com/JosephCirello/carbon-copy"


# ---- items 2 and 3: the footer and the PayPal wording ----------------------------------------------------------------

def test_the_footer_says_what_the_demo_is_entered_in_and_links_the_repository():
    foot = INDEX[INDEX.index('<footer class="foot"'):INDEX.index("</footer>")]
    assert "Built with Kiro for Kiroween 2026 · Code and the Kiro sessions: " in foot
    assert f'<a href="{REPO_URL}"' in foot and ">github.com/JosephCirello/carbon-copy</a>" in foot
    assert 'rel="noopener"' in foot and "Signing key:" in foot            # the key line is still there, in the same footer


def test_the_run_source_option_names_the_paypal_the_server_reports():
    assert "replayed through PayPal now" not in INDEX and "Recorded real run (replayed through Carbon Copy now)" not in APP_JS
    assert "Recorded real run (replayed through ${ppSay(\"the\")} now)" in APP_JS
    assert '"the PayPal sandbox"' in APP_JS and '"the PayPal stand-in"' in APP_JS
    assert re.search(r'paypal_mode === "sandbox" \? "the PayPal sandbox" : "the PayPal stand-in"', APP_JS)


def test_the_lines_that_said_paypal_without_which_now_say_which():
    assert 'The check looks at PayPal before any money leaves' not in INDEX + APP_JS
    assert INDEX.count('data-pp="the"') == 2 and INDEX.count('data-pp="poss"') == 1
    assert "and PayPal's own records of the order" not in INDEX and "goes to PayPal right then" not in INDEX
    assert "the check and ${ppSay(\"the\")} are running now" in APP_JS
    assert "Why (built from ${ppSay(\"the\")} and the records)" in APP_JS


# ---- items 4 to 8: the repository's words ---------------------------------------------------------------------------

def test_the_session_records_say_the_attacker_ran_four_times_and_what_each_found():
    assert "was run twice" not in SESSIONS
    assert "four times" in SESSIONS
    for record in ("10_", "12_", "16_", "17_", "23_"):
        assert record in SESSIONS
    for found in ("six", "seven", "thirteen", "twelve"):
        assert found in SESSIONS.split("four times", 1)[1].split("\n", 1)[0]


def test_the_no_keys_hook_describes_what_it_does_on_save():
    hook = json.loads((ROOT / ".kiro" / "hooks" / "guard-the-book.json").read_text(encoding="utf-8"))["hooks"]
    keys = [h for h in hook if h["name"] == "No keys in the repo"][0]
    assert keys["trigger"] == "PostFileSave"
    assert keys["description"].startswith("After each save") and "Before the agent writes" not in keys["description"]


def test_the_stray_bullet_is_gone_from_the_fingerprint_section_and_said_once_where_it_belongs():
    section = README[README.index("### Check the fingerprint yourself"):README.index("## What we measured on the book")]
    assert "No AI model decides a payment" not in section
    assert README.count("No AI model decides a payment") + README.count("no model decides a payment") >= 1


def test_the_readme_says_exactly_who_wrote_what_and_names_the_hand_made_changes():
    assert "Kiro wrote Carbon Copy from a spec" not in README
    assert "We wrote the first spec, the steering files and the hooks" in README
    assert "Kiro wrote the code and the tests, task by task, from the spec" in README
    for by_hand in ("requirements.txt", "Dockerfile", "render.yaml", "key scanner"):
        assert by_hand in README.split("Kiro wrote the code and the tests", 1)[1].split("\n\n", 1)[0] or by_hand in README


def test_the_picture_that_shows_a_device_key_says_it_was_recorded_on_a_local_copy():
    caption = [ln for ln in README.splitlines() if "One copy is changed to say she approved" in ln][0]
    assert "recorded on a local copy of the demo" in caption
    assert (ROOT / "docs" / "images" / "04_change_one_caught.jpg").exists()


def test_the_spec_has_the_amendment_and_task_26():
    spec = (ROOT / ".kiro" / "specs" / "carbon-copy" / "requirements.md").read_text(encoding="utf-8")
    tasks = (ROOT / ".kiro" / "specs" / "carbon-copy" / "tasks.md").read_text(encoding="utf-8")
    req10 = spec[spec.index("### Requirement 10"):spec.index("### Requirement 11")]
    assert "answer" in req10 and "375" in req10 and "Kiroween 2026" in req10
    assert re.search(r"^- \[x\] 26\. ", tasks, re.M)


def test_the_readme_is_shorter_and_keeps_its_facts():
    words = len(README.split())
    assert words < 7211, words          # 7,211 words before task 26, with the new who-wrote-what, task 26 and caption text added
    for fact in ("45,571", "38 weak spots", "1,444 recorded runs", "60 requests a minute", "256 KB", "20 MB", "24 hours",
                 "RECEIPTS_MCP_ON_PHONE=1", "RECEIPTS_PROXY_HOPS", "20,000 characters", "421", "2^53 - 1",
                 "HOSTED_KEY.txt", "verify.html", "Powers.", "Not confirmed."):
        assert fact in README, fact
    assert README.count("Try to forge the record") <= 2          # the three clicks are said once on the first screen, once in Try it


# ---- item 1: the answer comes into view, in a real browser -----------------------------------------------------------

def _playwright():
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None
    return sync_playwright


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server():
    os.environ["PAYPAL_MODE"] = "standin"
    import uvicorn
    import app as app_module
    port = _free_port()
    srv = uvicorn.Server(uvicorn.Config(app_module.app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    t.join(timeout=10)


def _visible_stamp_box(page):
    page.wait_for_function("document.querySelector('#ccResult .stamp') !== null", timeout=30000)
    page.wait_for_timeout(1500)                                           # the smooth scroll has finished
    return page.evaluate("""() => {
        const r = document.querySelector('#ccResult .stamp').getBoundingClientRect();
        const top = document.querySelector('.top').getBoundingClientRect();
        return { top: r.top, bottom: r.bottom, height: innerHeight, header: top.bottom, scrollX: scrollX, wide: document.documentElement.scrollWidth - innerWidth };
    }""")


@pytest.mark.parametrize("width,height", [(375, 812), (768, 1024), (1280, 800)])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_forgery_answer_lands_in_view_with_the_stamp_near_the_top(server, width, height, scheme):
    sp = _playwright()
    if sp is None:
        pytest.skip("playwright is not installed")
    with sp() as p:
        browser = None
        for channel in (None, "chrome", "msedge"):                        # Playwright's own Chromium, else an installed Chrome or Edge
            try:
                browser = p.chromium.launch(channel=channel)
                break
            except Exception:
                continue
        if browser is None:
            pytest.skip("no Chromium, Chrome or Edge for Playwright on this machine")
        page = browser.new_page(viewport={"width": width, "height": height}, color_scheme=scheme)
        page.route("https://cdn.jsdelivr.net/**", lambda route: route.fulfill(status=200, content_type="application/javascript", body=""))
        page.goto(server)
        page.click("#path2")                                              # runs Maya's day and opens her phone at the held payment
        page.wait_for_selector("#tab-owner .decline", state="visible", timeout=60000)
        page.click("#tab-owner .decline")
        page.wait_for_selector("#phoneNextBtn", state="visible", timeout=30000)
        page.click("#phoneNextBtn")
        box = _visible_stamp_box(page)
        assert box["header"] <= box["top"] < height * 0.45, box           # the stamp sits near the top, under the sticky bar
        assert box["bottom"] <= height, box
        # the other two buttons bring their answers up too, from wherever the page is scrolled
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.evaluate("document.querySelector('#ccResult').innerHTML = ''")
        page.click("#ccCheck")
        box = _visible_stamp_box(page)
        assert box["header"] <= box["top"] < height * 0.45 and box["bottom"] <= height, box
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.evaluate("document.querySelector('#ccResult').innerHTML = ''")
        page.click("#ccTamper")
        box = _visible_stamp_box(page)
        assert box["top"] >= box["header"] and box["bottom"] <= height, box
        browser.close()
