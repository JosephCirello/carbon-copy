"""Carbon Copy: an append-only, signed receipt book for every money move and decision.

Every event that passes through Receipts (a verdict, a PayPal call, a desk call,
an owner's tap, a flagged word, the end-of-day report) gets one receipt here, at
the moment it happens. Each receipt carries the fingerprint of the receipt before
it and a signature over its own fingerprint. The book also carries a signed count
of its receipts, so removing receipts from the end — which the chain of links
alone cannot show — is caught. The book only ever appends; there is no update or
delete. Anyone holding the receipts and the public key can run ``verify`` and
learn whether the book is intact or which receipt was first changed, in plain
words.

The private signing key never leaves this module: it comes from the
``CARBON_COPY_KEY`` environment variable (64 hex characters are the Ed25519 seed;
any other text is hashed into one) or is generated in memory at start-up. Verifying the book needs only the receipts and
the public key — and, to catch a book cut back to an older signed count, the
owner's phone stamps. No secret is ever needed to check.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import math
import os
import re
import sys
import threading
import time
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

#: The link of the first receipt: 64 zeros stand for "no receipt before this one".
GENESIS = "0" * 64
_HEX64 = re.compile(r"[0-9a-fA-F]{64}")
#: A public key as the book writes it: exactly 64 lowercase hex characters, nothing else (no spaces, no capitals).
_KEY64 = re.compile(r"[0-9a-f]{64}")
#: The seven keys a receipt carries, and the only ones it may carry: they are the seal.
SEALED_KEYS = frozenset({"n", "at_ms", "kind", "event", "prev", "fp", "sig"})
#: The keys the fingerprint covers: all must be present (a missing key is not the same as a null).
_CONTENT_KEYS = frozenset({"n", "at_ms", "kind", "event", "prev", "fp"})
#: The three keys a book is read from; anything else beside them is not part of the book.
BOOK_KEYS = ("public_key", "head", "receipts")


#: The largest whole number every JSON tool (a browser's included) holds exactly.
MAX_SAFE_INT = 2 ** 53 - 1
_SURROGATE = re.compile("[\ud800-\udfff]")
_MAX_DEPTH = 100


def _clean_text(s: str) -> str:
    """The text with every lone surrogate replaced by U+FFFD (it could not be written as UTF-8)."""
    return _SURROGATE.sub("\ufffd", str.__str__(s))


def safe_json(x, _depth: int = 0):
    """The "safe JSON" form of any value: the only form that is stored, hashed and handed out.

    Strings and dict keys have lone surrogates replaced by U+FFFD. An integer is kept
    only when ``abs(n) <= 2**53 - 1``, otherwise it is written as its decimal text. A
    float that is whole and within that range becomes an int; every other float
    (NaN, Infinity, 298.5) becomes the text Python's ``repr`` gives. Tuples become
    lists. Any other type (Decimal, datetime, set, bytes, an object) becomes
    ``str(value)``. Keys are written sorted by Unicode code point (by ``canonical``). The result holds only
    strings, safe integers, booleans, null, lists and dicts, so ``json.dumps`` can
    never fail on it and a browser's ``JSON.stringify`` gives the same bytes. The
    input is not changed, and no value can make this raise.
    """
    if x is None or isinstance(x, bool):
        return x
    if isinstance(x, str):
        return _clean_text(x)
    if isinstance(x, int):
        n = int(x)
        if abs(n) <= MAX_SAFE_INT:
            return n
        try:
            return str(n)
        except ValueError:      # Python refuses to write a number of thousands of digits
            return "(a number too large to write)"
    if isinstance(x, float):
        f = float(x)
        if math.isfinite(f) and f.is_integer() and abs(f) <= MAX_SAFE_INT:
            return int(f)
        return repr(f)
    if _depth >= _MAX_DEPTH:
        return _clean_text(_text_of(x))
    if isinstance(x, dict):
        out: dict = {}
        for k, v in x.items():
            key = _clean_text(k) if isinstance(k, str) else _clean_text(_text_of(k))
            val = safe_json(v, _depth + 1)
            # two keys that clean to the same text: the larger cleaned value wins, whatever the dict order
            if key not in out or _sort_text(val) > _sort_text(out[key]):
                out[key] = val
        return out        # canonical() writes the keys sorted by code point
    if isinstance(x, (list, tuple)):
        return [safe_json(v, _depth + 1) for v in x]
    return _clean_text(_text_of(x))


def _sort_text(v) -> str:
    return json.dumps(v, sort_keys=True, ensure_ascii=False)


def _text_of(x) -> str:
    try:
        return str(x)
    except Exception:  # noqa: BLE001  an object whose own __str__ fails still gets a stable word
        return f"<{type(x).__name__}>"


def normalise(x):
    """The value with every whole-number float turned into an int, recursively.

    A browser writes 1836.0 as 1836, so the same number must hash the same either
    way. Tuples become lists; dicts and lists are rebuilt (the input is not
    changed); anything else is returned as it is. ``safe_json`` is the full cleaning
    step used when a receipt is written; this lighter step is what ``canonical``
    applies to a value that is already clean.
    """
    if isinstance(x, float):
        return int(x) if x.is_integer() else x
    if isinstance(x, dict):
        return {k: normalise(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [normalise(v) for v in x]
    return x


def canonical(x) -> bytes:
    """The stable byte form of a JSON-shaped value: keys sorted by code point, no
    spaces, text as UTF-8 (no ``\\u`` escapes), whole floats as ints.

    There is no ``default=``: a value ``safe_json`` has not cleaned (a Decimal, a
    date, a set) raises ``TypeError`` instead of being hashed one way and sent
    another, and NaN or Infinity raise ``ValueError``. Run anything an agent wrote
    through :func:`safe_json` first.
    """
    return json.dumps(
        normalise(x), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")

def fingerprint(x) -> str:
    """SHA-256 over the canonical form of ``x``, as 64 hex characters."""
    return hashlib.sha256(canonical(x)).hexdigest()


class Signer:
    """Holds one Ed25519 private key and signs receipt fingerprints.

    No method, attribute or repr returns the private key or its seed. The key
    comes from the ``CARBON_COPY_KEY`` environment variable (64 hex characters, an
    Ed25519 seed) or is generated in memory when that variable is not set; a key
    generated in memory is never written anywhere.
    """

    __slots__ = ("_private", "temporary")

    def __init__(self, private_key: Ed25519PrivateKey, temporary: bool = False):
        self._private = private_key
        self.temporary = temporary          # True for a key made in memory because none was set

    @classmethod
    def from_env(cls) -> "Signer":
        """Read ``CARBON_COPY_KEY`` or make a fresh key in memory.

        Any text is accepted: 64 hex characters are the Ed25519 seed itself; any
        other text gives the seed SHA-256 of its UTF-8 bytes, so a generated random
        value (a hosting service's) works as a fixed key.
        """
        text = os.environ.get("CARBON_COPY_KEY")
        if text:
            seed = bytes.fromhex(text) if _HEX64.fullmatch(text) else hashlib.sha256(text.encode("utf-8")).digest()
            return cls(Ed25519PrivateKey.from_private_bytes(seed))
        return cls(Ed25519PrivateKey.generate(), temporary=True)

    def sign(self, fp_hex: str) -> str:
        """Sign ``bytes.fromhex(fp_hex)`` and return the signature as base64."""
        return base64.b64encode(self._private.sign(bytes.fromhex(fp_hex))).decode("ascii")

    @property
    def short_key(self) -> str:
        """The first 16 hex characters of the public key, for a footer."""
        return self.public_key_hex[:16]

    @property
    def public_key_hex(self) -> str:
        """The public key, as 64 hex characters, safe to publish."""
        pub = self._private.public_key()
        return pub.public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        ).hex()

    def __repr__(self) -> str:
        return f"Signer(public_key_hex={self.public_key_hex!r})"


class CarbonCopy:
    """The receipt book. Append only; never edit, never delete.

    Each receipt is::

        {"n": int, "at_ms": int, "kind": str, "event": dict,
         "prev": str, "fp": str, "sig": str}

    where ``at_ms`` is the time in whole milliseconds since the epoch, ``prev`` is the previous receipt's fingerprint (64 zeros for the first),
    ``fp`` is this receipt's own fingerprint and ``sig`` is a signature over
    ``bytes.fromhex(fp)``. The stored ``event`` is the event exactly as passed to
    :meth:`append` minus its own ``"t"``, cleaned into safe JSON (see
    :func:`safe_json`): that cleaned form is what is stored, hashed and handed out.
    """

    def __init__(self, signer: Signer):
        self._signer = signer
        self._receipts: list[dict] = []
        self._lock = threading.Lock()      # one receipt is written at a time; a stamp is read between writes

    def append(self, kind: str, event: dict) -> dict:
        """Build, fingerprint, sign and store one receipt; return a copy of it.

        The receipt's time is the event's own ``"t"`` (seconds) as whole milliseconds
        in ``at_ms``, a safe integer like everything else that is sealed; if the event
        carries no usable ``"t"`` the current time is used. The stored event is the
        event minus ``"t"`` cleaned by :func:`safe_json`, which is a fresh copy, so
        changing the event afterwards cannot change the book. Whatever the event
        holds (a lone surrogate, NaN, a huge number, a Decimal) this does not raise,
        so an action is never left without its receipt. The one thing it refuses is a ``kind`` that is not a
        non-empty text (``ValueError``): the check reads such a receipt as changed.
        """
        if not isinstance(kind, str) or not kind:
            raise ValueError("a receipt's kind must be a non-empty text")
        ev = safe_json({k: v for k, v in event.items() if k != "t"})
        at_ms = _receipt_time_ms(event.get("t"))
        with self._lock:
            n = len(self._receipts) + 1
            prev = self._receipts[-1]["fp"] if self._receipts else GENESIS
            fp = fingerprint({"n": n, "at_ms": at_ms, "kind": safe_json(kind), "event": ev, "prev": prev})
            receipt = {
                "n": n,
                "at_ms": at_ms,
                "kind": safe_json(kind),
                "event": ev,
                "prev": prev,
                "fp": fp,
                "sig": self._signer.sign(fp),
            }
            self._receipts.append(receipt)
            return copy.deepcopy(receipt)
    def receipts(self) -> list[dict]:
        """Return deep copies of every receipt, so changing them cannot change the book."""
        return copy.deepcopy(self._receipts)

    def book(self) -> dict:
        """Return the public key, a signed head and the receipts, all as copies.

        The head is a signed count of the book::

            {"count": N, "last_fp": <fp of receipt N or 64 zeros>, "sig": <base64>}

        ``count`` is the number of receipts and ``last_fp`` is the fingerprint of
        the last receipt (64 zeros when the book is empty). ``sig`` is a signature
        over ``bytes.fromhex(fingerprint({"count": N, "last_fp": ...}))`` made with
        the same key as the receipts. A hash chain alone cannot show when the last
        receipt (or the last several) has been deleted: every receipt left still
        links up. The signed head does, so the check can tell the book is short.
        """
        receipts = self.receipts()
        return {"public_key": self._signer.public_key_hex, "head": self._head(), "receipts": receipts}

    def _head(self) -> dict:
        with self._lock:
            count = len(self._receipts)
            last_fp = self._receipts[-1]["fp"] if self._receipts else GENESIS
            return {"count": count, "last_fp": last_fp,
                    "sig": self._signer.sign(fingerprint({"count": count, "last_fp": last_fp}))}

    def stamp(self) -> dict:
        """The book's signed head together with the public key that signed it: what an owner's device keeps.

        ``{"count", "last_fp", "sig", "public_key"}``. Cheap (it does not copy the receipts), so it can be
        handed out with every event.
        """
        return {**self._head(), "public_key": self._signer.public_key_hex}


def _receipt_time_ms(t) -> int:
    """A receipt's time in whole milliseconds: the event's ``t`` (seconds), or now when it is missing, not a finite
    number, or outside 0 to 2**53 - 1 milliseconds (the range every JSON tool holds exactly)."""
    if not isinstance(t, bool) and isinstance(t, (int, float)) and math.isfinite(t):
        try:
            ms = round(t * 1000)
        except (OverflowError, ValueError):
            ms = -1
        if 0 <= ms <= MAX_SAFE_INT:
            return ms
    return round(time.time() * 1000)


def _time_ok(v) -> bool:
    """True for a receipt time a book may hold: a whole number of milliseconds from 0 to 2**53 - 1 (5.0 reads as 5, as a browser reads it)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    return math.isfinite(v) and float(v).is_integer() and 0 <= v <= MAX_SAFE_INT


def public_book(book: dict) -> dict:
    """A copy of ``book`` with only the three parts a book is read from (``public_key``, ``head``, ``receipts``), and in each
    receipt only its seven sealed keys. What the screen shows and what is exported goes through here, so nothing that sits
    outside the seal is ever shown beside it."""
    out = {k: copy.deepcopy(book[k]) for k in BOOK_KEYS if isinstance(book, dict) and k in book}
    if isinstance(out.get("receipts"), list):
        out["receipts"] = [{k: v for k, v in r.items() if k in SEALED_KEYS} if isinstance(r, dict) else r
                           for r in out["receipts"]]
    return out


def _signature_ok(public_key_hex: str, fp_hex: str, sig_b64: str) -> bool:
    """True only if ``sig_b64`` is a valid signature over ``bytes.fromhex(fp_hex)``
    for the given public key. Any tampered, malformed or mismatched input is False.

    The key must be exactly 64 lowercase hex characters and the signature must be canonical base64 (standard
    alphabet, padded, and equal to the re-encoding of what it decodes to): base64 has spare bits at the end, so
    several texts decode to one signature, and only the one the signer wrote is accepted.
    """
    try:
        if not isinstance(public_key_hex, str) or not _KEY64.fullmatch(public_key_hex):
            return False
        if not isinstance(sig_b64, str):
            return False
        raw = base64.b64decode(sig_b64, validate=True)
        if base64.b64encode(raw).decode("ascii") != sig_b64:
            return False
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        pub.verify(raw, bytes.fromhex(fp_hex))
        return True
    except (ValueError, TypeError, InvalidSignature):
        # bad public key / bad hex / bad base64 / wrong length -> not a match;
        # InvalidSignature -> a well-formed signature that does not verify.
        return False


WHY_KEY = "it was signed with a different key than the one your device trusts"
WHY_STAMP_BAD = "a stamp on your device is damaged or forged"
WHY_SHORT = "the book is shorter than a stamp your device already holds"
WHY_UNREADABLE = "this is not a carbon-copy book we can read"
WHY_BAD_KEY = "its public key is not written the way a key must be"

RESTART_NOTE = ("This server makes a new temporary signing key every time it starts. If you restarted it yourself, "
                "that is why the key changed: press 'Forget what this device trusts' and run the day again. "
                "The hosted demo uses a fixed key, so this never happens there.")


def restart_note(book_key, trusted_key, temporary) -> str | None:
    """Words for the owner, never a verdict: verify() is not asked and not changed. Only a temporary server key,
    a key the device already trusts and a book signed with another key give the note."""
    if temporary is not True or not isinstance(book_key, str) or not isinstance(trusted_key, str):
        return None
    return RESTART_NOTE if book_key.lower() != trusted_key.lower() else None


def _changed(count: int, why: str, first_bad: int | None = None) -> dict:
    out = {"intact": False, "count": count}
    if first_bad is not None:
        out["first_bad"] = first_bad
    out["why"] = why
    return out


def _whole(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _stamp_ok(stamp, key_hex: str) -> bool:
    """True only for a well-formed stamp whose signature verifies against ``key_hex``."""
    if not isinstance(stamp, dict):
        return False
    count, last_fp, sig = stamp.get("count"), stamp.get("last_fp"), stamp.get("sig")
    if not _whole(count) or count < 0 or not isinstance(last_fp, str) or not isinstance(sig, str):
        return False
    try:
        head_fp = fingerprint({"count": count, "last_fp": last_fp})
    except (TypeError, ValueError):
        return False
    return _signature_ok(key_hex, head_fp, sig)


def verify(book: dict, stamps=None, expected_key: str | None = None) -> dict:
    """Check a book using only the receipts, the public key and the owner's stamps.

    ``expected_key`` is the public key (hex) the owner's device trusts. When it is
    given and the book carries a different key the book is *changed* ("it was signed
    with a different key than the one your device trusts"): a book re-signed from
    start to end under a new key is otherwise internally perfect. Without it the
    book's own key is used for every signature, which proves the book is consistent
    but not who wrote it.

    A book that is not an object holding a list in ``receipts`` is *changed* ("this is not
    a carbon-copy book we can read"), and so is one whose ``public_key`` is not exactly 64
    lowercase hex characters. Only ``public_key``, ``head`` and ``receipts`` are read.

    Walks the receipts in order. For each it asks, in turn: does it carry only its seven
    sealed keys (``n, at_ms, kind, event, prev, fp, sig``); is ``n`` the next
    number; does ``prev`` equal the previous receipt's fingerprint; is ``at_ms`` a whole
    number of milliseconds and does the recomputed fingerprint equal the stored ``fp``;
    does the signature (canonical base64) verify. It stops at the first receipt that
    fails any of these.

    Returns ``{"intact": True, "count": N}`` when every receipt checks out, or
    ``{"intact": False, "count": N, "first_bad": n, "why": "<plain words>"}``
    naming the first receipt that fails and why. After the receipts it checks the
    signed head: a book with no head is *changed* ("the book has no signed count"); a
    head whose signature does not verify is *changed* ("the book's signed count was
    changed"); a head whose count or last fingerprint does not match the receipts is
    *changed* ("receipts are missing from the end of the book").

    Only when the book is intact on its own does it look at ``stamps``, the signed
    heads the owner's device kept. Every stamp is checked first: it must be an object
    with a whole-number ``count``, a text ``last_fp`` and a text ``sig``, and its
    signature must verify against the key the device trusts (the book's key when no
    ``expected_key``). A stamp that is malformed or forged makes the book *changed*
    ("a stamp on your device is damaged or forged"); so does ``stamps`` that is not
    a list. Then each stamp is compared with the book: a ``count`` beyond the end
    gives "the book is shorter than a stamp your device already holds"; a position
    that exists but holds another fingerprint gives "receipt #N no longer matches the
    stamp your device kept".
    """
    if not isinstance(book, dict) or not isinstance(book.get("receipts"), list):
        return _changed(0, WHY_UNREADABLE, 1)       # any shape but an object holding a list of receipts
    receipts = book["receipts"]
    public_key = book.get("public_key", "")
    if not isinstance(public_key, str) or not _KEY64.fullmatch(public_key):
        return _changed(len(receipts), WHY_BAD_KEY)
    if expected_key is not None and (
        not isinstance(public_key, str) or not isinstance(expected_key, str)
        or public_key.lower() != expected_key.lower()
    ):
        return _changed(len(receipts), WHY_KEY)
    prev_fp = GENESIS
    for i, r in enumerate(receipts):
        if not isinstance(r, dict):
            return _changed(len(receipts), "its content was changed", i + 1)
        if not SEALED_KEYS.issuperset(r):           # only the seven sealed keys; anything else sits outside the seal
            return _changed(len(receipts), f"receipt #{i + 1} carries something outside its seal", i + 1)
        n = r.get("n")
        if n != i + 1 or isinstance(n, bool):
            return _changed(len(receipts), "a receipt is missing", i + 1)
        if r.get("prev") != prev_fp:
            return _changed(len(receipts), "its link to the receipt before was broken", n)
        try:
            content_ok = _CONTENT_KEYS.issubset(r) and isinstance(r["kind"], str) and r["kind"] != "" \
                and _time_ok(r.get("at_ms")) and fingerprint(
                {"n": n, "at_ms": r.get("at_ms"), "kind": r.get("kind"),
                 "event": r.get("event"), "prev": r.get("prev")}) == r.get("fp")
        except (TypeError, ValueError):     # a value no honest book holds (NaN, a date): not the content that was signed
            content_ok = False
        if not content_ok:
            return _changed(len(receipts), "its content was changed", n)
        if not _signature_ok(public_key, r.get("fp", ""), r.get("sig", "")):
            return _changed(len(receipts), "its signature does not match", n)
        prev_fp = r.get("fp")
    # ---- the signed head: proves how many receipts the book should hold ----
    # Every receipt left still links up after receipts are cut from the end, so the
    # chain alone would say intact. The head is a count and the last fingerprint,
    # signed, so the check can see the missing ones.
    head = book.get("head")
    if not isinstance(head, dict):
        return _changed(len(receipts), "the book has no signed count")
    try:
        head_fp = fingerprint({"count": head.get("count"), "last_fp": head.get("last_fp")})
    except (TypeError, ValueError):
        return _changed(len(receipts), "the book's signed count was changed")
    if not _signature_ok(public_key, head_fp, head.get("sig", "")):
        return _changed(len(receipts), "the book's signed count was changed")
    if head.get("count") != len(receipts) or head.get("last_fp") != prev_fp:
        return _changed(len(receipts), "receipts are missing from the end of the book", len(receipts) + 1)
    # ---- the owner's device stamps: prove the book was not cut back or rewritten ----
    # The head inside the book closes its END, not its PAST: someone holding an older
    # signed head can cut the book back to that older length and put the older head
    # back. The device holds copies of the heads it saw, outside the book. Each must
    # be genuine (signed by the key the device trusts) before it is believed, then
    # the book must still hold what it stamped.
    if stamps is not None and stamps != []:
        if not isinstance(stamps, list):
            return _changed(len(receipts), WHY_STAMP_BAD)
        key = expected_key.lower() if isinstance(expected_key, str) else public_key
        if not all(_stamp_ok(s, key) for s in stamps):
            return _changed(len(receipts), WHY_STAMP_BAD)
        n = len(receipts)
        for stamp in stamps:
            sc, sl = stamp["count"], stamp["last_fp"]
            if sc > n:
                return _changed(n, WHY_SHORT, sc)
            if (sc >= 1 and receipts[sc - 1].get("fp") != sl) or (sc == 0 and sl != GENESIS):
                return _changed(n, f"receipt #{sc} no longer matches the stamp your device kept", max(sc, 1))
    return {"intact": True, "count": len(receipts)}

def _different_value(v):
    """A value of the same rough kind as ``v`` but never equal to it, for the tamper demo."""
    if isinstance(v, bool):
        return not v
    if isinstance(v, (int, float)):
        return v + 1
    if isinstance(v, str):
        number = _number_in(v)
        return repr(number + 1) if number is not None else v + "!"
    if isinstance(v, list):
        return [*v, "tampered"]
    if isinstance(v, dict):
        return {**v, "_tampered": True}
    return "tampered"


def _number_in(v):
    """The number a text such as "298.5" holds (an amount the book wrote as text), else None."""
    if isinstance(v, str):
        try:
            f = float(v)
        except ValueError:
            return None
        return f if math.isfinite(f) else None
    return None


def _usd(v) -> str:
    if isinstance(v, str) and _number_in(v) is not None:
        v = _number_in(v)
    return f"${v:,.2f}" if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)


def _show(field: str, v) -> str:
    if field == "amount":
        return _usd(v)
    return json.dumps(v, sort_keys=True, ensure_ascii=False, default=str) if isinstance(v, (dict, list)) else str(v)


def _answered_hold(receipts: list, idx: int) -> tuple:
    """The amount and payee of the held payment the owner action at ``idx`` answers (None when not found)."""
    hold_id = (receipts[idx].get("event") or {}).get("hold_id")
    for r in receipts[:idx]:
        ev = r.get("event") or {}
        if r.get("kind") == "verdict" and hold_id is not None and ev.get("id") == hold_id:
            args = ev.get("args") or {}
            return ev.get("amount"), args.get("vendor") or args.get("payee") or args.get("email")
    return None, None


def _owner_story(receipts: list, idx: int, before: str, after: str) -> str:
    amount, payee = _answered_hold(receipts, idx)
    what = "payment" if amount is None else f"{_usd(amount)} payment"
    if payee:
        what += f" to {payee}"
    verb = {"approved": "APPROVED", "declined": "DECLINED"}
    was = {"approved": "approved", "declined": "declined"}
    return (f"We changed receipt #{idx + 1} in a copy of the book so it says Maya {verb.get(after, after)} the {what}. "
            f"She {was.get(before, before)} it.")


def _change_one(book: dict, n: int | None = None) -> tuple[dict, dict]:
    """A deep copy of ``book`` with one value changed in one receipt, and what was changed.

    Which receipt and which value is explained in :func:`tamper_demo`. The book passed in is never modified.
    Returns ``(copy, {"n", "field", "before", "after", "say"})``; ``n`` is None when the book has no receipts.
    """
    work = public_book(book)
    receipts = work.get("receipts") or []
    if not receipts:
        return work, {"n": None, "field": None, "before": None, "after": None, "say": None}
    if n is not None:
        idx = n - 1
    else:
        owner = [i for i, r in enumerate(receipts)
                 if r.get("kind") == "owner" and (r.get("event") or {}).get("action") in ("declined", "approved")]
        declined = [i for i in owner if receipts[i]["event"]["action"] == "declined"]
        if owner:
            idx = (declined or owner)[-1]
        else:
            # the most recent money move, so the demo changes a real amount when one exists
            with_amount = [i for i, r in enumerate(receipts) if "amount" in (r.get("event") or {})]
            idx = with_amount[-1] if with_amount else len(receipts) - 1
    if idx < 0 or idx >= len(receipts):
        idx = len(receipts) - 1
    rec = receipts[idx]
    ev = rec.get("event")
    if isinstance(ev, dict) and rec.get("kind") == "owner" and ev.get("action") in ("declined", "approved"):
        field, before = "action", ev["action"]
        after = "approved" if before == "declined" else "declined"
        ev[field] = after
        say = _owner_story(receipts, idx, before, after)
    else:
        if isinstance(ev, dict) and ev:
            field = "amount" if "amount" in ev else next(iter(ev))
            before = ev.get(field)
            after = _different_value(before)
            ev[field] = after
        else:
            field = "kind"
            before = rec.get("kind")
            after = _different_value(before) if before is not None else "tampered"
            rec["kind"] = after
        say = (f"We changed receipt #{idx + 1} from {_show(field, before)} to {_show(field, after)} "
               f"in a copy of the book.")
    return work, {"n": idx + 1, "field": field, "before": before, "after": after, "say": say}


def forge_demo(book: dict, n: int | None = None) -> dict:
    """The real attack, built for the demo: a whole new book that says something else and reads perfect on its own.

    Makes the same change as :func:`tamper_demo` (Maya's "declined" flipped to "approved" when the book holds an
    owner action), then rebuilds EVERY receipt with fresh links and fingerprints and signs each one, and a new
    signed head, with a brand-new key made here and thrown away. Checked alone, with the key it carries, the forged
    book is intact; checked against the key the owner's device trusts it is not. The book passed in is never
    modified. Returns ``{"book", "n", "field", "before", "after", "say"}``; ``book`` is None for an empty book.
    """
    work, what = _change_one(book, n)
    if what["n"] is None:
        return {"book": None, **what}
    signer = Signer(Ed25519PrivateKey.generate())
    prev = GENESIS
    for r in work["receipts"]:
        r["prev"] = prev
        r["fp"] = fingerprint({"n": r.get("n"), "at_ms": r.get("at_ms"), "kind": r.get("kind"),
                               "event": r.get("event"), "prev": prev})
        r["sig"] = signer.sign(r["fp"])
        prev = r["fp"]
    head_fp = fingerprint({"count": len(work["receipts"]), "last_fp": prev})
    work["head"] = {"count": len(work["receipts"]), "last_fp": prev, "sig": signer.sign(head_fp)}
    work["public_key"] = signer.public_key_hex
    return {"book": work, **what}


def tamper_demo(book: dict, n: int | None = None) -> dict:
    """Show the check catching a change to one receipt, without touching the real book.

    Deep-copies the book and changes one value in one receipt's event, then runs
    :func:`verify` on the copy. When the book holds an owner action, THAT receipt is
    the one changed: a "declined" becomes "approved", the exact lie the book exists to
    catch (a record edited afterwards to say the owner approved a payment she
    declined). With no owner action it changes the amount of the latest money move,
    else another field (or the receipt's ``kind`` when the event is empty). Returns the
    receipt number, the field changed, the before and after values, the result and
    ``say``, the change in plain words, and ``book``, the changed copy itself (public_key, head, receipts, the
    same shape :func:`forge_demo` returns; None for an empty book) so the owner's device can check it too. The
    book passed in is never modified.
    """
    work, what = _change_one(book, n)
    return {**what, "result": verify(work), "book": None if what["n"] is None else work}


RUN_MODES = ("enforce", "observe")
RUN_SOURCES = ("live", "recorded")


def run_event(mode: str, source: str, scenario: str, model: str, title: str | None = None,
              started_ms: int | None = None) -> dict:
    """The event of the receipt (kind ``run``) that opens every run's book: what the run was, sealed.

    ``mode`` is ``enforce`` or ``observe``, ``source`` is ``live`` or ``recorded``. ``started`` is the start time as
    UTC text. Plain data in, plain data out; it only builds the event, ``append()`` writes it."""
    if mode not in RUN_MODES or source not in RUN_SOURCES:
        raise ValueError("a run is enforce or observe, live or recorded")
    ms = started_ms if isinstance(started_ms, int) and 0 <= started_ms <= MAX_SAFE_INT else round(time.time() * 1000)
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ms / 1000))
    return {"mode": mode, "source": source, "scenario": scenario, "title": title or scenario, "model": model,
            "started": started, "t": ms / 1000}


def run_of(receipts) -> dict | None:
    """The sealed event of receipt 1 when it is of kind ``run``, else None. Everything the screen says about
    what the run was comes from here."""
    if not isinstance(receipts, list) or not receipts or not isinstance(receipts[0], dict):
        return None
    first = receipts[0]
    ev = first.get("event")
    if first.get("kind") != "run" or not isinstance(ev, dict):
        return None
    return ev


def read_check_file(parsed, key=None, stamps=None):
    """From a parsed file, ``(book, stamps, key)`` to check. The file is a bare book or the download the page
    writes (``{"book", "stamps", "trusted_key"}``). With the download, its stamps and trusted key are used
    unless ``stamps`` or ``key`` is given (the flags win). Raises ValueError when the file is neither."""
    if isinstance(parsed, dict) and "receipts" not in parsed and isinstance(parsed.get("book"), dict):
        book = parsed["book"]
        if stamps is None:
            stamps = parsed.get("stamps")
        if key is None:
            key = parsed.get("trusted_key")
            if key is not None and not (isinstance(key, str) and _HEX64.fullmatch(key)):
                raise ValueError("the trusted key in the file is not 64 hex characters")
        return book, stamps, key
    if not isinstance(parsed, dict):
        raise ValueError("it is not a carbon-copy book")
    return parsed, stamps, key


def _plain(result: dict) -> str:
    """One line in plain words: intact with the count, or the first changed receipt."""
    if result.get("intact"):
        return f"intact ({result.get('count', 0)} receipts)"
    first_bad = result.get("first_bad")
    why = result.get("why", "")
    return f"receipt {first_bad}: {why}" if first_bad is not None else why


def _main(argv=None) -> int:
    """``python -m receipts.carbon verify <book.json> [--stamps <stamps.json>] [--key <hex>]``.

    Prints *intact* with the count, or the first changed receipt in plain words.
    Exits 0 when intact, 1 when changed, 2 when a file could not be read (one plain
    line on standard error, never a traceback). ``--key`` is the public key to trust.
    """
    import argparse

    parser = argparse.ArgumentParser(prog="python -m receipts.carbon", description="Check a carbon-copy receipt book.")
    sub = parser.add_subparsers(dest="command", required=True)
    verify_p = sub.add_parser("verify", help="check a book and print intact or the first changed receipt")
    verify_p.add_argument("book", help="path to a book JSON file")
    verify_p.add_argument("--stamps", help="path to a JSON list of the owner's device stamps")
    verify_p.add_argument("--key", help="the public key to trust, 64 hex characters (a book signed with another key is changed)")
    args = parser.parse_args(argv)

    if args.command == "verify":
        if args.key is not None and not _HEX64.fullmatch(args.key):
            print("could not use the key: it must be 64 hex characters", file=sys.stderr)
            return 2
        try:
            parsed = json.loads(Path(args.book).read_text(encoding="utf-8-sig"))
            flag_stamps = json.loads(Path(args.stamps).read_text(encoding="utf-8-sig")) if args.stamps else None
            book, stamps, key = read_check_file(parsed, key=args.key, stamps=flag_stamps)
        except Exception as exc:      # noqa: BLE001  missing, not UTF-8, not JSON, nested too deep, wrong shape: never a traceback
            why = str(exc).splitlines()[0][:200] if isinstance(exc, (OSError, ValueError)) and str(exc) else "it is not a file we can read"
            print(f"could not read the file: {why}", file=sys.stderr)
            return 2
        try:
            out = verify(book, stamps, expected_key=key)
        except Exception:  # noqa: BLE001  a book that breaks the check is not intact
            out = {"intact": False, "count": 0, "why": "this is not a carbon-copy book we can read"}
        print(_plain(out))
        return 0 if out.get("intact") else 1
    return 2

if __name__ == "__main__":
    sys.exit(_main())
