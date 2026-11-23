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
``CARBON_COPY_KEY`` environment variable (a 32-byte Ed25519 seed in hex) or is
generated in memory at start-up. Verifying the book needs only the receipts and
the public key — and, to catch a book cut back to an older signed count, the
owner's phone stamps. No secret is ever needed to check.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import sys
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


def canonical(x) -> bytes:
    """The stable byte form of any JSON-shaped value.

    Keys are sorted, there are no spaces, text stays as UTF-8 (no ``\\u`` escapes)
    and anything JSON cannot represent is read through ``str``. Two values that
    mean the same thing always produce the same bytes on any machine, so the
    fingerprint can never depend on dict order, float formatting or platform.
    """
    return json.dumps(
        x, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
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

    __slots__ = ("_private",)

    def __init__(self, private_key: Ed25519PrivateKey):
        self._private = private_key

    @classmethod
    def from_env(cls) -> "Signer":
        """Read ``CARBON_COPY_KEY`` (an Ed25519 seed in hex) or make a fresh key."""
        seed_hex = os.environ.get("CARBON_COPY_KEY")
        if seed_hex:
            private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex))
        else:
            private_key = Ed25519PrivateKey.generate()
        return cls(private_key)

    def sign(self, fp_hex: str) -> str:
        """Sign ``bytes.fromhex(fp_hex)`` and return the signature as base64."""
        return base64.b64encode(self._private.sign(bytes.fromhex(fp_hex))).decode("ascii")

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

        {"n": int, "at": float, "kind": str, "event": dict,
         "prev": str, "fp": str, "sig": str}

    where ``prev`` is the previous receipt's fingerprint (64 zeros for the first),
    ``fp`` is this receipt's own fingerprint and ``sig`` is a signature over
    ``bytes.fromhex(fp)``. The stored ``event`` is the event exactly as passed to
    :meth:`append` minus its own ``"t"``.
    """

    def __init__(self, signer: Signer):
        self._signer = signer
        self._receipts: list[dict] = []

    def append(self, kind: str, event: dict) -> dict:
        """Build, fingerprint, sign and store one receipt; return a copy of it.

        The receipt's time is the event's own ``"t"`` (rounded to milliseconds so
        the stored value and the hashed value are the same number); if the event
        carries no ``"t"`` the current time is used. The stored event is a deep copy
        of the event minus ``"t"``, so changing the event afterwards cannot change
        the book.
        """
        n = len(self._receipts) + 1
        at = round(event.get("t", time.time()), 3)
        ev = copy.deepcopy({k: v for k, v in event.items() if k != "t"})
        prev = self._receipts[-1]["fp"] if self._receipts else GENESIS
        fp = fingerprint({"n": n, "at": at, "kind": kind, "event": ev, "prev": prev})
        receipt = {
            "n": n,
            "at": at,
            "kind": kind,
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
        count = len(receipts)
        last_fp = receipts[-1]["fp"] if receipts else GENESIS
        head_fp = fingerprint({"count": count, "last_fp": last_fp})
        head = {"count": count, "last_fp": last_fp, "sig": self._signer.sign(head_fp)}
        return {"public_key": self._signer.public_key_hex, "head": head, "receipts": receipts}


def _signature_ok(public_key_hex: str, fp_hex: str, sig_b64: str) -> bool:
    """True only if ``sig_b64`` is a valid signature over ``bytes.fromhex(fp_hex)``
    for the given public key. Any tampered, malformed or mismatched input is False."""
    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        pub.verify(base64.b64decode(sig_b64), bytes.fromhex(fp_hex))
        return True
    except (ValueError, InvalidSignature):
        # bad public key / bad hex / bad base64 / wrong length -> not a match;
        # InvalidSignature -> a well-formed signature that does not verify.
        return False


def verify(book: dict, stamps=None) -> dict:
    """Check a book using only the receipts and the public key (and the stamps).

    Walks the receipts in order. For each it asks, in turn: is ``n`` the next
    number; does ``prev`` equal the previous receipt's fingerprint; does the
    recomputed fingerprint equal the stored ``fp``; does the signature verify. It
    stops at the first receipt that fails any of these.

    Returns ``{"intact": True, "count": N}`` when every receipt checks out, or
    ``{"intact": False, "count": N, "first_bad": n, "why": "<plain words>"}``
    naming the first receipt that fails and why, in one of four plain reasons.
    After the receipts it checks the signed head: a book with no head is *changed*
    ("the book has no signed count"); a head whose signature does not verify is
    *changed* ("the book's signed count was changed"); a head whose count or last
    fingerprint does not match the receipts is *changed* ("receipts are missing
    from the end of the book"). The head is what catches receipts removed from the
    end, which the chain of links alone cannot show.

    Only when the book is intact on its own does it look at ``stamps`` — a list of
    the owner's phone stamps, each a signed head handed to the phone when the
    owner tapped. A signed count inside the book can be cut back to an older signed
    count that still matches the receipts left; the phone holds a copy of the count
    the book reached, outside the book. If any stamp's ``count`` is greater than the
    number of receipts, or its ``last_fp`` is not the fingerprint of the receipt at
    that position, the book is *changed* ("the book is shorter than a stamp the
    owner's phone already holds"). The stamps are read only for their ``count`` and
    ``last_fp``; a false stamp fails closed — it says *changed*.
    """
    receipts = book.get("receipts") or []
    public_key = book.get("public_key", "")
    prev_fp = GENESIS
    for i, r in enumerate(receipts):
        n = r.get("n")
        if n != i + 1:
            return {"intact": False, "count": len(receipts), "first_bad": i + 1,
                    "why": "a receipt is missing"}
        if r.get("prev") != prev_fp:
            return {"intact": False, "count": len(receipts), "first_bad": n,
                    "why": "its link to the receipt before was broken"}
        if fingerprint({"n": n, "at": r.get("at"), "kind": r.get("kind"),
                        "event": r.get("event"), "prev": r.get("prev")}) != r.get("fp"):
            return {"intact": False, "count": len(receipts), "first_bad": n,
                    "why": "its content was changed"}
        if not _signature_ok(public_key, r.get("fp", ""), r.get("sig", "")):
            return {"intact": False, "count": len(receipts), "first_bad": n,
                    "why": "its signature does not match"}
        prev_fp = r.get("fp")
    # ---- the signed head: proves how many receipts the book should hold ----
    # Every receipt left still links up after receipts are cut from the end, so the
    # chain alone would say intact. The head is a count and the last fingerprint,
    # signed, so the check can see the missing ones.
    head = book.get("head")
    if not isinstance(head, dict):
        return {"intact": False, "count": len(receipts),
                "why": "the book has no signed count"}
    head_fp = fingerprint({"count": head.get("count"), "last_fp": head.get("last_fp")})
    if not _signature_ok(public_key, head_fp, head.get("sig", "")):
        return {"intact": False, "count": len(receipts),
                "why": "the book's signed count was changed"}
    if head.get("count") != len(receipts) or head.get("last_fp") != prev_fp:
        return {"intact": False, "count": len(receipts), "first_bad": len(receipts) + 1,
                "why": "receipts are missing from the end of the book"}
    # ---- the owner's phone stamps: prove the book was not cut back to an older count ----
    # The head inside the book closes its END, not its PAST: someone holding an older
    # signed head can cut the book back to that older length and put the older head
    # back, and the receipts left still link up and still match. The phone holds a
    # copy of the head outside the book; if any stamp reaches further than the
    # receipts the book now holds, or its last_fp is not the receipt at that
    # position, the book was cut back to an older state.
    if stamps:
        n = len(receipts)
        for stamp in stamps:
            if not isinstance(stamp, dict):
                continue
            sc = stamp.get("count")
            sl = stamp.get("last_fp")
            if not isinstance(sc, int) or not isinstance(sl, str):
                continue
            if sc > n or (1 <= sc <= n and receipts[sc - 1].get("fp") != sl):
                return {"intact": False, "count": n, "first_bad": sc,
                        "why": "the book is shorter than a stamp the owner's phone already holds"}
    return {"intact": True, "count": len(receipts)}


def _different_value(v):
    """A value of the same rough kind as ``v`` but never equal to it, for the tamper demo."""
    if isinstance(v, bool):
        return not v
    if isinstance(v, (int, float)):
        return v + 1
    if isinstance(v, str):
        return v + "!"
    if isinstance(v, list):
        return [*v, "tampered"]
    if isinstance(v, dict):
        return {**v, "_tampered": True}
    return "tampered"


def tamper_demo(book: dict, n: int | None = None) -> dict:
    """Show the check catching a change to one receipt, without touching the real book.

    Deep-copies the book, changes one value in one receipt's event — the amount if
    there is one, else another field of the event (or the receipt's ``kind`` when
    the event is empty) — runs :func:`verify` on the copy and returns the receipt
    number, the field changed, the before and after values, and the result. The book
    passed in is never modified: only the deep copy is.
    """
    work = copy.deepcopy(book)
    receipts = work.get("receipts") or []
    if not receipts:
        return {"n": None, "field": None, "before": None, "after": None, "result": verify(work)}
    if n is not None:
        idx = n - 1
    else:
        # the most recent money move, so the demo changes a real amount when one exists
        with_amount = [i for i, r in enumerate(receipts) if "amount" in (r.get("event") or {})]
        idx = with_amount[-1] if with_amount else len(receipts) - 1
    if idx < 0 or idx >= len(receipts):
        idx = len(receipts) - 1
    rec = receipts[idx]
    ev = rec.get("event")
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
    return {"n": idx + 1, "field": field, "before": before, "after": after, "result": verify(work)}


def _plain(result: dict) -> str:
    """One line in plain words: intact with the count, or the first changed receipt."""
    if result.get("intact"):
        return f"intact ({result.get('count', 0)} receipts)"
    first_bad = result.get("first_bad")
    why = result.get("why", "")
    return f"receipt {first_bad}: {why}" if first_bad is not None else why


def _main(argv=None) -> int:
    """``python -m receipts.carbon verify <book.json> [--stamps <stamps.json>]``.

    Prints *intact* with the count, or the first changed receipt in plain words, and
    exits 0 when intact, 1 when changed.
    """
    import argparse

    parser = argparse.ArgumentParser(prog="python -m receipts.carbon", description="Check a carbon-copy receipt book.")
    sub = parser.add_subparsers(dest="command", required=True)
    verify_p = sub.add_parser("verify", help="check a book and print intact or the first changed receipt")
    verify_p.add_argument("book", help="path to a book JSON file")
    verify_p.add_argument("--stamps", help="path to a JSON list of the owner's phone stamps")
    args = parser.parse_args(argv)

    if args.command == "verify":
        try:
            book = json.loads(Path(args.book).read_text(encoding="utf-8"))
            stamps = json.loads(Path(args.stamps).read_text(encoding="utf-8")) if args.stamps else None
        except (OSError, json.JSONDecodeError) as exc:
            print(f"could not read the book: {exc}", file=sys.stderr)
            return 1
        out = verify(book, stamps)
        print(_plain(out))
        return 0 if out.get("intact") else 1
    return 1


if __name__ == "__main__":
    sys.exit(_main())
