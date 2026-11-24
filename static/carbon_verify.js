/* Carbon Copy: the check, in the browser (and under node, for the parity test).
 *
 * verify(book, stamps, pinnedKey) answers the same question as receipts/carbon.py verify(), in the same plain
 * words, using only the book, the stamps this device kept and the key this device trusts. It never asks the
 * server. SHA-256 and Ed25519 come from crypto.subtle.
 *
 * The fingerprint recipe: SHA-256 over the UTF-8 bytes of the receipt's {n, at, kind, event, prev} written as JSON
 * with keys sorted by Unicode code point, no spaces, and text kept as UTF-8. A book holds only strings, safe
 * integers, booleans, null, lists and objects (the server cleans everything else before it writes a receipt), so
 * JSON.stringify of each piece gives the bytes Python gives.
 */
(function (root) {
  "use strict";
  const GENESIS = "0".repeat(64);
  const WHY_KEY = "it was signed with a different key than the one your device trusts";
  const WHY_STAMP_BAD = "a stamp on your device is damaged or forged";
  const WHY_SHORT = "the book is shorter than a stamp your device already holds";
  const subtle = () => (root.crypto && root.crypto.subtle) || null;
  const enc = new TextEncoder();

  function codePointCompare(a, b) {                 // order keys by Unicode code point, not by UTF-16 unit
    let i = 0, j = 0;
    while (i < a.length && j < b.length) {
      const x = a.codePointAt(i), y = b.codePointAt(j);
      if (x !== y) return x < y ? -1 : 1;
      i += x > 0xffff ? 2 : 1; j += y > 0xffff ? 2 : 1;
    }
    return i < a.length ? 1 : j < b.length ? -1 : 0;   // one is the start of the other: the shorter comes first
  }

  function canonical(x) {                           // the text whose UTF-8 bytes are fingerprinted
    if (x === null) return "null";
    switch (typeof x) {
      case "string": return JSON.stringify(x);
      case "boolean": return x ? "true" : "false";
      case "number":
        if (!Number.isFinite(x)) throw new Error("a number that is not a number");
        return JSON.stringify(x);
      case "object":
        if (Array.isArray(x)) return "[" + x.map(canonical).join(",") + "]";
        return "{" + Object.keys(x).sort(codePointCompare).map((k) => JSON.stringify(k) + ":" + canonical(x[k])).join(",") + "}";
      default: throw new Error("a value JSON cannot hold");
    }
  }

  const toHex = (buf) => Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, "0")).join("");
  const fromHex = (h) => {
    if (typeof h !== "string" || !/^([0-9a-fA-F]{2})*$/.test(h)) throw new Error("not hex");
    return Uint8Array.from(h.match(/../g) || [], (p) => parseInt(p, 16));
  };
  const fromBase64 = (s) => {
    if (typeof s !== "string" || !/^[A-Za-z0-9+/]*={0,2}$/.test(s) || s.length % 4) throw new Error("not base64");
    const bin = atob(s);
    return Uint8Array.from(bin, (c) => c.charCodeAt(0));
  };

  async function fingerprint(x) {
    return toHex(await subtle().digest("SHA-256", enc.encode(canonical(x))));
  }

  async function signatureOk(keyHex, fpHex, sigB64) {
    try {
      const key = await subtle().importKey("raw", fromHex(keyHex), { name: "Ed25519" }, false, ["verify"]);
      return await subtle().verify({ name: "Ed25519" }, key, fromBase64(sigB64), fromHex(fpHex));
    } catch (e) { return false; }
  }

  /* Can this browser verify Ed25519? (Older browsers cannot; the page then asks the server and says so.) */
  async function supportsEd25519() {
    try {
      const probe = fromHex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a");
      await subtle().importKey("raw", probe, { name: "Ed25519" }, false, ["verify"]);
      return true;
    } catch (e) { return false; }
  }

  const changed = (count, why, firstBad) => {
    const out = { intact: false, count };
    if (firstBad !== undefined && firstBad !== null) out.first_bad = firstBad;
    out.why = why;
    return out;
  };
  const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
  const isWhole = (v) => typeof v === "number" && Number.isInteger(v);

  async function stampOk(stamp, keyHex) {
    if (!isObj(stamp)) return false;
    const { count, last_fp: lastFp, sig } = stamp;
    if (!isWhole(count) || count < 0 || typeof lastFp !== "string" || typeof sig !== "string") return false;
    return signatureOk(keyHex, await fingerprint({ count, last_fp: lastFp }), sig);
  }

  async function verify(book, stamps, pinnedKey) {
    if (!isObj(book) || !(book.receipts == null || Array.isArray(book.receipts))) return changed(0, "this is not a carbon-copy book we can read", 1);
    const receipts = book.receipts || [];
    const publicKey = typeof book.public_key === "string" ? book.public_key : "";
    const count = receipts.length;
    if (pinnedKey != null && (typeof pinnedKey !== "string" || publicKey.toLowerCase() !== pinnedKey.toLowerCase())) return changed(count, WHY_KEY);
    let prev = GENESIS;
    for (let i = 0; i < count; i++) {
      const r = receipts[i];
      if (!isObj(r)) return changed(count, "its content was changed", i + 1);
      const n = r.n;
      if (n !== i + 1) return changed(count, "a receipt is missing", i + 1);
      if (r.prev !== prev) return changed(count, "its link to the receipt before was broken", n);
      let contentOk = false;
      try { contentOk = (await fingerprint({ n, at: r.at, kind: r.kind, event: r.event, prev: r.prev })) === r.fp; } catch (e) { contentOk = false; }
      if (!contentOk) return changed(count, "its content was changed", n);
      if (!(await signatureOk(publicKey, r.fp, r.sig))) return changed(count, "its signature does not match", n);
      prev = r.fp;
    }
    const head = book.head;
    if (!isObj(head)) return changed(count, "the book has no signed count");
    let headFp;
    try { headFp = await fingerprint({ count: head.count, last_fp: head.last_fp }); } catch (e) { return changed(count, "the book's signed count was changed"); }
    if (!(await signatureOk(publicKey, headFp, head.sig))) return changed(count, "the book's signed count was changed");
    if (head.count !== count || head.last_fp !== prev) return changed(count, "receipts are missing from the end of the book", count + 1);
    if (stamps != null && !(Array.isArray(stamps) && stamps.length === 0)) {
      if (!Array.isArray(stamps)) return changed(count, WHY_STAMP_BAD);
      const key = pinnedKey != null ? pinnedKey : publicKey;
      for (const s of stamps) if (!(await stampOk(s, key))) return changed(count, WHY_STAMP_BAD);
      for (const s of stamps) {
        if (s.count > count) return changed(count, WHY_SHORT, s.count);
        if ((s.count >= 1 && receipts[s.count - 1].fp !== s.last_fp) || (s.count === 0 && s.last_fp !== GENESIS))
          return changed(count, `receipt #${s.count} no longer matches the stamp your device kept`, Math.max(s.count, 1));
      }
    }
    return { intact: true, count };
  }

  const api = { verify, canonical, fingerprint, supportsEd25519, codePointCompare };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.CarbonVerify = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
