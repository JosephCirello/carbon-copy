r"""Build verify.html: the check for a downloaded book, as one file that needs nothing from anywhere.

  .venv\Scripts\python.exe tools\build_verify.py            write verify.html
  .venv\Scripts\python.exe tools\build_verify.py --check    exit 1 when verify.html is not what this script builds

static/carbon_verify.js is placed inside verify.html byte for byte (between ``<script id="carbon-verify">`` and the next
``</script>``), so the file the owner saves from GitHub runs the same check the page does and the command line agrees
with. The published key of the hosted demo is read from HOSTED_KEY.txt. Plain code, no model, no network, no secret.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from receipts.carbon import read_key_file  # noqa: E402

OUT = ROOT / "verify.html"
CHECK_JS = ROOT / "static" / "carbon_verify.js"
HOSTED_KEY = ROOT / "HOSTED_KEY.txt"

OPEN, CLOSE = '<script id="carbon-verify">', "</script>"

TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<title>Check a Carbon Copy book</title>
<style>
  body { font-family: system-ui, "Segoe UI", sans-serif; max-width: 44rem; margin: 2rem auto; padding: 0 1rem; color: #1d2433; background: #fffdf8; line-height: 1.5; }
  h1 { margin-bottom: .2rem; }
  .drop { border: 3px dashed #8a93a8; border-radius: 14px; padding: 2.2rem 1rem; text-align: center; background: #fff; cursor: pointer; }
  .drop.over { border-color: #1d2433; background: #f0f3fa; }
  .stamp { display: inline-block; font-family: "Courier New", monospace; font-weight: 700; font-size: 2rem; padding: .2rem 1rem; border: 4px solid; border-radius: 8px; transform: rotate(-3deg); margin: 1rem 0 .4rem; }
  .stamp.ok { color: #1b7a3a; }
  .stamp.bad { color: #b3261e; }
  .note { color: #7a5200; }
  .mono { font-family: "Courier New", monospace; overflow-wrap: anywhere; }
  .keys { border: 1px solid #cfd4e0; border-radius: 10px; padding: .6rem 1rem; background: #fff; }
  .fine { color: #55607a; font-size: .92rem; }
</style>
</head>
<body>
<h1>Check a Carbon Copy book</h1>
<p>This page checks a book of carbon copies that you downloaded from the Carbon copy tab. It works on your own computer and does not need the internet. Nothing you drop here leaves this page.</p>
<div class="drop" id="drop" tabindex="0" role="button" aria-label="Choose the downloaded file, or drop it here">
  <p><b>Drop the downloaded file here</b>, or choose it.</p>
  <input type="file" id="pick" accept=".json,application/json">
</div>
<p class="fine">The check uses the key published for the hosted demo (it is built into this page). A book signed with any other key reads CHANGED.</p>
<label class="fine"><input type="checkbox" id="useFileKey"> Use the key in this file instead (for a book from your own server)</label>
<p class="fine note">Checked, the check is only as good as where the file came from: a file written by someone else can name any key it likes, and then it will read INTACT.</p>
<div id="result" aria-live="polite"></div>
<div class="keys" id="keys" hidden></div>
<p class="fine">The key published for the hosted demo is <span class="mono" id="pubKey"></span>. It is also in HOSTED_KEY.txt in the repository. Save this page from GitHub, not from the demo, so the check does not come from the server it checks.</p>
<script id="carbon-verify">__CHECK__</script>
<script>
(function () {
  "use strict";
  const CHECK = window.CarbonVerify;
  const PUBLISHED = "__PUBLISHED_KEY__";
  const NO_KEY = "This file has no key from your device, so the check can only compare the book with itself.";
  const NO_STAMP = "This file has no stamp, so it cannot tell whether the end of the book was rewritten.";
  const HEX64 = /^[0-9a-fA-F]{64}$/;
  const $ = (id) => document.getElementById(id);
  const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
  $("pubKey").textContent = PUBLISHED;

  function line(parent, text, cls) {
    const p = document.createElement("p");
    if (cls) p.className = cls;
    p.textContent = text;
    parent.appendChild(p);
    return p;
  }
  function say(lines) {                           // lines: [text, class] pairs; text only, never markup
    const box = $("result");
    box.textContent = "";
    lines.forEach(([t, c]) => line(box, t, c));
  }
  function stampWord(out) {
    const el = document.createElement("div");
    el.className = "stamp " + (out.intact ? "ok" : "bad");
    el.setAttribute("role", "img");
    el.textContent = out.intact ? "INTACT" : (out.first_bad == null ? "CHANGED" : "CHANGED AT #" + out.first_bad);
    el.setAttribute("aria-label", out.intact ? "The book is intact" : "The book was changed");
    return el;
  }
  function showKeys(trusted, bookKey, fromFile) {
    const box = $("keys");
    box.hidden = false;
    box.textContent = "";
    const same = (a, b) => typeof a === "string" && typeof b === "string" && a.toLowerCase() === b.toLowerCase();
    line(box, (fromFile ? "The key in this file, which this check trusts because you chose to: " : "The key this check trusts (the published one): ") + (typeof trusted === "string" && trusted ? trusted : "none"), "mono");
    line(box, "The key published for the hosted demo: " + PUBLISHED, "mono");
    if (fromFile)
      line(box, !trusted ? "This download names no trusted key, so there is nothing to compare with the published one."
        : same(trusted, PUBLISHED) ? "They match: the key this download trusts is the published one."
        : "They do NOT match. This download trusts a different key than the hosted demo's published key. If this book came from the hosted demo, do not rely on it.",
        same(trusted, PUBLISHED) || !trusted ? "" : "note");
    if (typeof bookKey === "string")
      line(box, same(bookKey, PUBLISHED) ? "The book is signed with the published key." : "The book is signed with a different key than the published one: " + bookKey, same(bookKey, PUBLISHED) ? "" : "mono note");
  }
  function changed(why) {                           // a verdict of CHANGED with no receipt number, in words only
    const box = $("result");
    box.textContent = "";
    box.appendChild(stampWord({ intact: false }));
    line(box, why);
  }

  let LAST_TEXT = null;                           // the last file read, so the switch can check it again
  async function checkText(text) {
    LAST_TEXT = text;
    const fromFile = $("useFileKey").checked === true;     // by default the PUBLISHED key is trusted, as the command line does with --key-file HOSTED_KEY.txt
    $("keys").hidden = true;
    text = text.replace(/^\ufeff/, "");
    let parsed;
    try { parsed = CHECK.parseStamps(text); }
    catch (e) { return say([["Could not read the file: it is not a file we can read.", "note"]]); }
    if (CHECK.hasUnsafeInteger(text)) return changed(CHECK.WHY_BIG_NUMBER);     // the number as written in the file, not as JavaScript rounds it
    let book = null, stamps = null, trusted = fromFile ? null : PUBLISHED;
    if (isObj(parsed) && !("receipts" in parsed) && isObj(parsed.book)) {
      book = parsed.book;
      stamps = parsed.stamps === undefined ? null : parsed.stamps;
      if (typeof stamps === "string") stamps = { written_as_text: stamps };     // stamps written as text are damaged, not a list to read
      if (fromFile) {
        trusted = parsed.trusted_key === undefined ? null : parsed.trusted_key;
        if (trusted !== null && !(typeof trusted === "string" && HEX64.test(trusted)))
          return say([["Could not read the file: the trusted key in the file is not 64 hex characters.", "note"]]);
      }
    } else if (isObj(parsed)) {
      book = parsed;
    } else {
      return say([["Could not read the file: it is not a carbon-copy book.", "note"]]);
    }
    if (!(await CHECK.supportsEd25519()))
      return say([["This browser cannot check the seals itself (it has no Ed25519). Use a current browser, or the command line: python -m receipts.carbon verify <file>.", "note"]]);
    let out;
    try { out = await CHECK.verify(book, stamps, trusted); }
    catch (e) { out = { intact: false, count: 0, why: "this is not a carbon-copy book we can read" }; }
    const box = $("result");
    box.textContent = "";
    box.appendChild(stampWord(out));
    const why = !fromFile && out.why === CHECK.WHY_KEY ? "it was signed with a different key than the published one" : String(out.why || "");
    line(box, out.intact ? "All " + out.count + " receipts are as they were written." : why);
    if (!(typeof trusted === "string" && trusted)) line(box, NO_KEY, "note");
    if (!(Array.isArray(stamps) && stamps.length)) line(box, NO_STAMP, "note");
    showKeys(trusted, isObj(book) ? book.public_key : null, fromFile);
  }

  function readFile(file) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => checkText(String(reader.result));
    reader.onerror = () => say([["Could not read the file.", "note"]]);
    reader.readAsText(file, "utf-8");
  }
  const drop = $("drop");
  $("pick").addEventListener("change", (e) => readFile(e.target.files[0]));
  $("useFileKey").addEventListener("change", () => { if (LAST_TEXT !== null) checkText(LAST_TEXT); });
  ["dragenter", "dragover"].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", (e) => readFile(e.dataTransfer.files[0]));
  window.addEventListener("dragover", (e) => e.preventDefault());       // a file dropped beside the box must not open in the tab
  window.addEventListener("drop", (e) => e.preventDefault());
  window.__checkText = checkText;            // for the tests, which run this page's own code under a stand-in page
})();
</script>
</body>
</html>
'''


def build() -> str:
    code = CHECK_JS.read_bytes().decode("utf-8")
    if CLOSE in code or "__PUBLISHED_KEY__" in code:
        raise SystemExit("static/carbon_verify.js holds text that cannot be placed inside a page script")
    key = read_key_file(HOSTED_KEY)
    return TEMPLATE.replace("__PUBLISHED_KEY__", key).replace("__CHECK__", code)


def main(argv=None) -> int:
    html = build()
    data = html.encode("utf-8")
    if "--check" in (argv if argv is not None else sys.argv[1:]):
        same = OUT.exists() and OUT.read_bytes() == data
        print("verify.html is up to date" if same else "verify.html is not what tools/build_verify.py builds")
        return 0 if same else 1
    OUT.write_bytes(data)
    print(f"wrote {OUT.name}: sha256 {hashlib.sha256(data).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
