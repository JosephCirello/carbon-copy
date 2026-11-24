"""Receipts as an MCP server: a drop-in in front of PayPal's own MCP server.

Point any MCP client (Claude Desktop, Cursor, an agent framework) at
http://<host>:8090/mcp/ instead of at PayPal's MCP server. The client gets the
same PayPal tool names; every money move is checked by Receipts first, holds
land on the owner's phone in the web app, and allowed calls go on to PayPal
(the official MCP server and the Payouts API in sandbox mode).

Workspace: Juniper & Oak's vendor master, approvals and rules. In MCP mode
there is no phone tool, so a payee change is HELD for the owner (who calls the
number on file herself) instead of being blocked.
"""
from __future__ import annotations

import json
import os

from mcp.server.mcpserver import MCPServer

from .carbon import CarbonCopy, Signer, run_event
from .core import Receipts
from .paypal import make_paypal
from .scenarios import load

MAX_HOLDS = 200            # the MCP workspace keeps this many holds in memory (its book keeps everything)
MAX_VERDICTS = 500         # ... and this many verdicts
MAX_ARG_BYTES = 64 * 1024  # an argument longer than this is kept as its first 64 KB plus a note of how much was cut
HOLDS_DEFAULT_LIMIT = 50
BOOK_FULL = "This demo's MCP book is full; restart the server to start a new one."
MONEY_TOOLS_MCP = ("create_refund", "accept_dispute_claim", "create_payout", "update_vendor_payee")
DEFAULT_BOOK_CAP = int(float(os.environ.get("RECEIPTS_MCP_BOOK_MB", "20")) * 1024 * 1024)   # sealed receipts, as stored JSON

_BIZ, _SCNS = load()
_BY = {s["id"]: s for s in _SCNS}


def workspace() -> dict:
    """A standing day with no inbox: the records an MCP client works against."""
    seed = {"orders": [], "disputes": [], "payout_history": []}
    for sid in ("S4_refund_and_then_some", "S6_never_arrived", "S9_normal_tuesday"):
        p = _BY[sid]["paypal"]
        seed["orders"] += p.get("orders", [])
        seed["disputes"] += p.get("disputes", [])
        seed["payout_history"] += p.get("payout_history", [])
    seed["payout_history"].append({"invoice": "INV-BR-1180", "receiver": "orders@blueridgefinishes.com", "amount": 2315.40,
                                   "status": "SUCCESS", "date": "2026-10-30", "time": "11:42"})
    seed["payout_history"].append({"invoice": "INV-BR-1197", "receiver": "orders@blueridgefinishes.com", "amount": 1836.00,
                                   "status": "PENDING", "date": "2026-11-09", "time": "16:52"})
    book = _BY["S15_check_in_the_mail"]["desk"].get("payments_book", [])
    base = _BY["S9_normal_tuesday"]
    return {"id": "MCP_workspace", "title": "MCP workspace", "kind": "workspace", "pressure": "an MCP client working live",
            "business": _BIZ, "policy": {**base["policy"], "payee_change_hold_for_owner": True},
            "paypal": seed, "desk": {"inbox": [], "vendors": base["desk"]["vendors"], "phone": {}, "approvals": [], "payments_book": book},
            "expected_legit": [], "bad_outcomes": []}


def cut_text(s: str, limit: int = MAX_ARG_BYTES) -> tuple[str, bool]:
    """``s`` itself, or when its UTF-8 form is over ``limit`` bytes its first ``limit`` bytes plus "(cut: N bytes)"."""
    raw = s.encode("utf-8", "replace")
    if len(raw) <= limit:
        return s, False
    return raw[:limit].decode("utf-8", "ignore") + f"(cut: {len(raw) - limit} bytes)", True


def _cut_value(v, depth: int = 0):
    """``v`` with every long text inside it cut (see ``cut_text``); returns ``(value, whether anything was cut)``."""
    if isinstance(v, str):
        return cut_text(v)
    if depth > 20:
        return v, False
    if isinstance(v, dict):
        out, hit = {}, False
        for k, x in v.items():
            y, h = _cut_value(x, depth + 1)
            out[k], hit = y, hit or h
        return out, hit
    if isinstance(v, (list, tuple)):
        pairs = [_cut_value(x, depth + 1) for x in v]
        return [p[0] for p in pairs], any(p[1] for p in pairs)
    return v, False


def trim_history(r: Receipts) -> None:
    """Keep the workspace's in-memory history small: the last MAX_HOLDS holds and MAX_VERDICTS verdicts, and no
    argument over 64 KB. The book was written before this runs and keeps everything."""
    for rec in r.verdicts[-MAX_VERDICTS:]:
        if "cut" not in rec:
            rec["args"], rec["cut"] = _cut_value(rec["args"])
    for h in r.holds:
        if "cut" not in h:
            h["args"], h["cut"] = _cut_value(h["args"])
    if len(r.verdicts) > MAX_VERDICTS:
        del r.verdicts[:-MAX_VERDICTS]
    if len(r.holds) > MAX_HOLDS:
        del r.holds[:-MAX_HOLDS]
    keep = {h["id"] for h in r.holds}
    for k in [k for k in r._hold_codes if k not in keep]:      # what a hold was held for goes with the hold
        del r._hold_codes[k]


def build(register=None, on_event=None, signer: Signer | None = None) -> tuple[MCPServer, Receipts]:
    """The MCP server and the Receipts behind its tools. The workspace has its own carbon-copy book, signed by
    ``signer`` (the app passes its one signer; with none, ``CARBON_COPY_KEY`` or a key made in memory), opened by a
    sealed ``run`` receipt, so every verdict, PayPal or desk call and owner tap on an MCP hold is sealed."""
    scn = workspace()
    pp = make_paypal(scn["paypal"], scn["id"])
    carbon = CarbonCopy(signer or Signer.from_env())
    carbon.append("run", run_event("enforce", "live", scn["id"], "mcp client", title=scn["title"]))
    r = Receipts(scn, pp, mode="enforce", on_event=on_event, carbon=carbon)
    if register:
        register(r)
    srv = MCPServer("Receipts", instructions=(
        "PayPal tools for an AI agent, behind Receipts. Every refund, payout, dispute concession and payee change is checked "
        "against the owner's rules and PayPal's own records before it reaches PayPal. A result with blocked_by_receipts or "
        "held_by_receipts did NOT reach PayPal; do not retry it."))

    r.mcp_cap_bytes = DEFAULT_BOOK_CAP      # read at every call; a test may lower it

    def full(tool: str) -> str | None:
        """Past the cap EVERY tool but carbon_book is refused and nothing is forwarded: no money move without its receipt, and a
        read-only tool writes receipts too, so it would keep the book growing. carbon_book writes nothing and still answers."""
        if r.carbon.size_bytes() >= r.mcp_cap_bytes:
            return json.dumps({"blocked_by_receipts": True, "why": [BOOK_FULL], "next": "This did not reach PayPal. Do not retry it."})
        return None

    def out(x) -> str:
        trim_history(r)
        return json.dumps(x, default=str)

    @srv.tool(description="The vendor master: each supplier's PayPal email on record and phone on file.")
    def list_vendors() -> str:
        if (b := full("list_vendors")):
            return b
        return out(r.call("list_vendors", {}))

    @srv.tool(description="Recent PayPal orders for this business: order id, capture id, amount, refunded, buyer.")
    def list_recent_orders() -> str:
        if (b := full("list_recent_orders")):
            return b
        fn = getattr(pp, "list_orders", None)
        return out(fn() if fn else {"note": "use get_order with an order id"})

    @srv.tool(description="PayPal: list transactions in a 31-day window. transaction_status: D denied, P pending, "
                          "S successful (the default, as in PayPal's own tool), V reversed.")
    def list_transactions(transaction_status: str = "S", start_date: str = "", end_date: str = "", transaction_id: str = "") -> str:
        if (b := full("list_transactions")):
            return b
        a = {k: v for k, v in {"transaction_status": transaction_status, "start_date": start_date, "end_date": end_date,
                               "transaction_id": transaction_id}.items() if v}
        return out(r.call("list_transactions", a))

    @srv.tool(description="The owner's book of supplier payments made outside PayPal (paper checks, bank transfers).")
    def payments_book() -> str:
        if (b := full("payments_book")):
            return b
        return out(r.call("payments_book", {}))

    @srv.tool(description="PayPal: show an order, its capture id, amount captured and refunds.")
    def get_order(id: str) -> str:
        if (b := full("get_order")):
            return b
        return out(r.call("get_order", {"id": id}))

    @srv.tool(description="PayPal: refund a captured payment (checked by Receipts first). Omit amount for a full refund.")
    def create_refund(capture_id: str, amount: float | None = None, note_to_payer: str = "") -> str:
        if (b := full("create_refund")):
            return b
        a = {"capture_id": capture_id, "note_to_payer": note_to_payer}
        if amount is not None:
            a["amount"] = amount
        return out(r.call("create_refund", a))

    @srv.tool(description="PayPal: show a buyer dispute.")
    def get_dispute(dispute_id: str) -> str:
        if (b := full("get_dispute")):
            return b
        return out(r.call("get_dispute", {"dispute_id": dispute_id}))

    @srv.tool(description="PayPal: accept a buyer's dispute claim (checked by Receipts first).")
    def accept_dispute_claim(dispute_id: str, note: str = "") -> str:
        if (b := full("accept_dispute_claim")):
            return b
        return out(r.call("accept_dispute_claim", {"dispute_id": dispute_id, "note": note}))

    @srv.tool(description="PayPal: show the shipment tracking recorded for an order.")
    def get_shipment_tracking(order_id: str) -> str:
        if (b := full("get_shipment_tracking")):
            return b
        return out(r.call("get_shipment_tracking", {"order_id": order_id}))

    @srv.tool(description="PayPal Payouts: pay a supplier invoice to a PayPal email (checked by Receipts first).")
    def create_payout(vendor: str, receiver_email: str, amount: float, invoice_number: str, memo: str = "") -> str:
        if (b := full("create_payout")):
            return b
        return out(r.call("create_payout", {"vendor": vendor, "receiver_email": receiver_email, "amount": amount,
                                            "invoice_number": invoice_number, "memo": memo}))

    @srv.tool(description="Change the PayPal email on record for a supplier. Always held for the owner in MCP mode.")
    def update_vendor_payee(vendor: str, new_paypal_email: str, reason: str = "") -> str:
        if (b := full("update_vendor_payee")):
            return b
        return out(r.call("update_vendor_payee", {"vendor": vendor, "new_paypal_email": new_paypal_email, "reason": reason}))

    @srv.tool(description="Receipts: list money moves waiting for the owner, and what was decided. Newest first; "
                          "limit is how many to list (default 50).")
    def receipts_holds(limit: int = HOLDS_DEFAULT_LIMIT) -> str:
        if (b := full("receipts_holds")):
            return b
        n = max(0, min(int(limit), MAX_HOLDS))
        return out(list(reversed(r.holds))[:n])

    @srv.tool(description="Carbon Copy: this workspace's receipt book (public key, signed head, every receipt). Save it and check it "
                          "with `python -m receipts.carbon verify <file>`; it needs no secret.")
    def carbon_book() -> str:
        return out(r.carbon.book())

    return srv, r


if __name__ == "__main__":
    # `python -m receipts.mcp_server`: serve the same tools over stdio, so a client such as Kiro can start it from its mcp.json.
    # Nothing is printed to standard output but the MCP protocol itself.
    build(signer=Signer.from_env())[0].run("stdio")