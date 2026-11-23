"""Carbon Copy: an append-only, signed receipt book for every money move and decision.

Every event that passes through Receipts (a verdict, a PayPal call, a desk call,
an owner's tap, a flagged word, the end-of-day report) gets one receipt here, at
the moment it happens. Each receipt carries the fingerprint of the receipt before
it and a signature over its own fingerprint. The book only ever appends; there is
no update or delete. Anyone holding the receipts and the public key can run
``verify`` and learn whether the book is intact or which receipt was first changed,
in plain words.

The private signing key never leaves this module: it comes from the
``CARBON_COPY_KEY`` environment variable (a 32-byte Ed25519 seed in hex) or is
generated in memory at start-up. Verifying the book needs only the receipts and
the public key.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import time

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
        """Return ``{"public_key": <hex>, "receipts": [...]}``, all as copies."""
        return {"public_key": self._signer.public_key_hex, "receipts": self.receipts()}


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


def verify(book: dict) -> dict:
    """Check a book using only the receipts and the public key.

    Walks the receipts in order. For each it asks, in turn: is ``n`` the next
    number; does ``prev`` equal the previous receipt's fingerprint; does the
    recomputed fingerprint equal the stored ``fp``; does the signature verify. It
    stops at the first receipt that fails any of these.

    Returns ``{"intact": True, "count": N}`` when every receipt checks out, or
    ``{"intact": False, "count": N, "first_bad": n, "why": "<plain words>"}``
    naming the first receipt that fails and why, in one of four plain reasons.
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
    return {"intact": True, "count": len(receipts)}
