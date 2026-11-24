#!/usr/bin/env python3
"""Receipts, the web app.

  uvicorn app:app --host 0.0.0.0 --port 8090

  /                 the product: live console, owner's phone, rules, ledger, results
  /api/run          live: a model works a day's inbox through Receipts (server-sent events)
  /api/replay       a recorded real run, re-driven through Receipts and PayPal now
  /api/approve      the owner approves a held money move (it then goes to PayPal)
  /api/compile      plain-English rules -> exact policy (AI drafts, code validates)

Every visitor has their own state. The first request sets an opaque random id in a cookie; the held
payments, the runs, the rules and the reset are kept under that id, so one visitor never sees or changes
another's. The recorded runs and the book built from them are read-only and shared.
"""
from __future__ import annotations

import copy
import json
import os
import queue
import re
import secrets
import threading
import time
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Any

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from receipts.agent import run_episode
from receipts.carbon import CarbonCopy, Signer, forge_demo, run_event, run_of, safe_json, tamper_demo, verify as carbon_verify
from receipts.compiler import FIELDS, ai_compile
from receipts.core import Receipts
from receipts.paypal import make_paypal
from receipts.rules import DEFAULT_POLICY
from receipts.scenarios import load
from run_batch import FRONTIER, MODELS

ROOT = Path(__file__).resolve().parent
RESULTS = Path(os.environ.get("RECEIPTS_RESULTS", str(ROOT / "results")))
BIZ, SCENARIOS = load()
BY_ID = {s["id"]: s for s in SCENARIOS}
LIVE_ALLOWED = os.environ.get("RECEIPTS_LIVE", "1") == "1"      # hosted demo can turn live model runs off

#: The one signing key of this process: every book it writes is signed with it, so the page can print it and a
#: device can pin it. From CARBON_COPY_KEY when set (any text), else made in memory and flagged temporary.
SIGNER = Signer.from_env()

# Receipts as an MCP server, mounted at /mcp: a drop-in in front of PayPal's own tools. Its workspace is one
# standing workspace shared by every MCP client, with its own carbon-copy book signed by SIGNER (the carbon_book
# MCP tool returns it). Its holds reach the web phone only where that is asked for: RECEIPTS_MCP_ON_PHONE=1, for a
# single-person demo on your own machine. Off by default, because with it on anyone who can open the page can
# approve or decline the MCP holds. The receipts_holds MCP tool lists them either way.
MCP_ON_PHONE = os.environ.get("RECEIPTS_MCP_ON_PHONE", "0") == "1"
MCP_SESSION: dict = {}              # {"r": Receipts} once the MCP server is built
from receipts.mcp_server import build as build_mcp  # noqa: E402
MCP_SERVER, MCP_RECEIPTS = build_mcp(register=lambda r: MCP_SESSION.__setitem__("r", r), signer=SIGNER)


def _warm():
    """Parse the recorded runs once at start-up, so the first visitor to Results or the Ledger does not wait
    (on a small hosted machine the first parse takes several seconds)."""
    try:
        from receipts import measure
        measure.results(RESULTS, "all")
        _episodes()
    except Exception:  # noqa: BLE001
        pass


@asynccontextmanager
async def lifespan(_app):
    threading.Thread(target=_warm, daemon=True).start()
    async with MCP_SERVER.session_manager.run():
        yield


app = FastAPI(title="Carbon Copy", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")
# The rules every visitor starts from. Never changed after start-up: a visitor's own rules are a copy.
DEFAULT_RULES = {"policy": dict(BIZ and {**DEFAULT_POLICY, **json.loads((ROOT / "scenarios" / "scenarios.json").read_text(encoding="utf-8"))["policy"]}),
                 "english": BIZ["owner_rules_english"], "sources": {}, "compiled_by": "defaults"}

# ---- one state per visitor ------------------------------------------------------------------------------
VISITOR_COOKIE = "receipts_visitor"
VISITOR_SCOPE_KEY = "receipts.visitor"
ISSUED_SCOPE_KEY = "receipts.visitor_issued"      # True when this request carried no cookie and was handed a new id
MAX_VISITORS = int(os.environ.get("RECEIPTS_MAX_VISITORS", "300"))            # least recently used is dropped past this
VISITOR_IDLE_S = float(os.environ.get("RECEIPTS_VISITOR_IDLE_HOURS", "3")) * 3600
SESSION_MAX_AGE_S = 3600            # a run with nothing waiting is kept for an hour
HOLD_MAX_AGE_S = 24 * 3600          # a run that still has a WAITING hold is kept for 24 hours
MCP_MAX_BODY = 256 * 1024           # an /mcp request body over this is refused with 413 before any tool runs
MCP_CALLS_PER_MINUTE = 60           # /mcp requests one client address may make in a minute
MAX_SESSIONS_PER_VISITOR = 40       # oldest run dropped past this
NEW_VISITORS_PER_ADDRESS = 30       # new visitors one client address may start ...
NEW_VISITOR_WINDOW_S = 600          # ... in this many seconds
BEHIND_PROXY = os.environ.get("RECEIPTS_BEHIND_PROXY", "0") == "1"      # on Render: the client address is the first X-Forwarded-For
MAX_ENGLISH_CHARS = 20_000          # the owner's rules in words
MAX_SOURCES = 200                   # quotes kept beside the rules
MAX_SOURCE_CHARS = 2_000            # one quote
_VISITOR_ID_OK = re.compile(r"^[A-Za-z0-9_-]{24,64}$")


class Visitor:
    """What one visitor has done: their runs (and the holds inside them), their rules, their live-run ledger rows."""
    __slots__ = ("sessions", "rules", "live_ledger", "seen")

    def __init__(self):
        self.sessions: dict[str, dict] = {}      # session id -> {"r": Receipts, "t": last activity}
        self.rules: dict = copy.deepcopy(DEFAULT_RULES)
        self.live_ledger: list[dict] = []
        self.seen = time.time()


VISITORS: "OrderedDict[str, Visitor]" = OrderedDict()      # least recently seen first
_VISITORS_LOCK = threading.RLock()


class VisitorCookie:
    """Plain ASGI middleware (it never buffers, so the event streams pass straight through): reads the visitor
    id from the cookie, or makes a new random one and sets it on the response. HttpOnly, SameSite=Lax, and
    Secure when the page was served over https (directly, or behind a proxy that says so)."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path", "").startswith("/mcp"):
            return await self.inner(scope, receive, send)
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        vid = None
        for part in headers.get("cookie", "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == VISITOR_COOKIE and _VISITOR_ID_OK.match(value):
                vid = value
        issued = vid is None
        if issued:
            vid = secrets.token_urlsafe(32)
        scope[VISITOR_SCOPE_KEY] = vid
        scope[ISSUED_SCOPE_KEY] = issued
        if not issued:
            return await self.inner(scope, receive, send)
        https = scope.get("scheme") == "https" or headers.get("x-forwarded-proto", "").split(",")[0].strip().lower() == "https"
        cookie = f"{VISITOR_COOKIE}={vid}; Path=/; Max-Age=604800; HttpOnly; SameSite=Lax" + ("; Secure" if https else "")

        async def send_with_cookie(message):
            if message["type"] == "http.response.start":
                message = {**message, "headers": list(message.get("headers", [])) + [(b"set-cookie", cookie.encode("latin-1"))]}
            await send(message)

        await self.inner(scope, receive, send_with_cookie)


app.add_middleware(VisitorCookie)

_MCP_CALLS: dict[str, list[float]] = {}      # client address -> when it made its recent /mcp requests
_MCP_LOCK = threading.Lock()


class McpGuard:
    """Plain ASGI middleware for /mcp, which has no login: 60 requests per client address per minute (429), and a
    body over 256 KB is refused (413) before any tool runs. The body is read here, at most 256 KB + 1 byte, then
    handed on unchanged, so a request with no length is held to the same limit."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope["type"] != "http" or not (path == "/mcp" or path.startswith("/mcp/")):
            return await self.inner(scope, receive, send)
        now = time.time()
        addr = _client_address(Request(scope))
        with _MCP_LOCK:
            recent = [t for t in _MCP_CALLS.get(addr, []) if now - t < 60]
            too_many = len(recent) >= MCP_CALLS_PER_MINUTE
            if not too_many:
                recent.append(now)
            _MCP_CALLS[addr] = recent
            if len(_MCP_CALLS) > 5000:
                for k in [k for k, v in _MCP_CALLS.items() if not v or now - v[-1] >= 60]:
                    _MCP_CALLS.pop(k, None)
        if too_many:
            return await JSONResponse({"detail": "Too many requests from your address in the last minute. Please wait a minute and try again."},
                                      status_code=429, headers={"Retry-After": "60"})(scope, receive, send)
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        too_big = {"detail": "That request is too large for this demo (the limit is 256 KB). Nothing was done."}
        try:
            declared = int(headers.get("content-length", "0") or 0)
        except ValueError:
            declared = 0
        if declared > MCP_MAX_BODY:
            return await JSONResponse(too_big, status_code=413)(scope, receive, send)
        chunks, size, more = [], 0, True
        while more:
            msg = await receive()
            if msg["type"] == "http.disconnect":
                return
            body = msg.get("body", b"")
            size += len(body)
            if size > MCP_MAX_BODY:
                return await JSONResponse(too_big, status_code=413)(scope, receive, send)
            chunks.append(body)
            more = msg.get("more_body", False)
        whole, sent = b"".join(chunks), False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": whole, "more_body": False}
            return await receive()

        await self.inner(scope, replay, send)


app.add_middleware(McpGuard)


_NEW_BY_ADDRESS: dict[str, list[float]] = {}      # client address -> when it started its recent new visitors


def _client_address(request: Request) -> str:
    """Who is asking: the first X-Forwarded-For address when the server sits behind a proxy that sets it
    (RECEIPTS_BEHIND_PROXY=1, as on Render), else the socket's own address."""
    if BEHIND_PROXY:
        first = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if first:
            return first[:64]
    return request.client.host if request.client else "unknown"


def _admit_new_visitor(request: Request, now: float) -> None:
    """Count one new visitor against this address; past the limit, 429 in plain words. Caller holds _VISITORS_LOCK."""
    addr = _client_address(request)
    recent = [t for t in _NEW_BY_ADDRESS.get(addr, []) if now - t < NEW_VISITOR_WINDOW_S]
    if len(recent) >= NEW_VISITORS_PER_ADDRESS:
        _NEW_BY_ADDRESS[addr] = recent
        raise HTTPException(429, "Too many new visitors have started from your address in the last few minutes. Please wait ten minutes and try again.")
    recent.append(now)
    _NEW_BY_ADDRESS[addr] = recent
    if len(_NEW_BY_ADDRESS) > 5000:                      # forget addresses that have been quiet for a whole window
        for k in [k for k, v in _NEW_BY_ADDRESS.items() if not v or now - v[-1] >= NEW_VISITOR_WINDOW_S]:
            _NEW_BY_ADDRESS.pop(k, None)


def _run_expired(s: dict, now: float) -> bool:
    """A run is over when its last activity (it starting, or the owner's last approve or decline on it) is more than
    an hour ago, or more than 24 hours ago when a payment in it is still waiting. ``s["t"]`` is that last activity."""
    age = now - s["t"]
    if age <= SESSION_MAX_AGE_S:
        return False
    return age > HOLD_MAX_AGE_S or not any(h.get("status") == "WAITING" for h in list(s["r"].holds))


def _holds_something(v: "Visitor", now: float) -> bool:
    """A visitor worth keeping when the table is full: a payment waiting for them, or a run younger than an hour."""
    return any(not _run_expired(s, now) for s in list(v.sessions.values()))


def _make_room(now: float, keep: str | None = None) -> None:
    """Past MAX_VISITORS, drop the least recently seen visitor who has no waiting hold and no run younger than an
    hour; only when there is none, drop the least recently seen of all. ``keep`` (the visitor just made) is never the one\n    dropped. Caller holds _VISITORS_LOCK."""
    while len(VISITORS) > max(1, MAX_VISITORS):
        others = [(k, v) for k, v in VISITORS.items() if k != keep]
        if not others:
            return
        victim = next((k for k, v in others if not _holds_something(v, now)), others[0][0])
        VISITORS.pop(victim, None)


def _visitor(request: Request, create: bool = False, may_start: bool = True) -> Visitor | None:
    """This visitor's state. Reading never creates one (a visitor who has done nothing costs no memory);
    acting does. ``may_start`` is False for a request that does not start a run: with no cookie of its own it
    creates nothing. Idle visitors expire, and past MAX_VISITORS room is made (see ``_make_room``)."""
    vid = request.scope.get(VISITOR_SCOPE_KEY)
    now = time.time()
    with _VISITORS_LOCK:
        for k in [k for k, v in VISITORS.items() if now - v.seen > VISITOR_IDLE_S]:
            VISITORS.pop(k, None)
        v = VISITORS.get(vid) if vid else None
        if v is None:
            if not create or (not may_start and request.scope.get(ISSUED_SCOPE_KEY, True)):
                return None
            _admit_new_visitor(request, now)
            v = Visitor()
            if vid:
                VISITORS[vid] = v
                _make_room(now, keep=vid)
        else:
            VISITORS.move_to_end(vid)
        v.seen = now
        for k in [k for k, s in v.sessions.items() if _run_expired(s, now)]:
            v.sessions.pop(k, None)
        return v


def _rules(request: Request) -> dict:
    v = _visitor(request)
    return v.rules if v else DEFAULT_RULES


@app.get("/", response_class=HTMLResponse)
def index():
    return (ROOT / "static" / "index.html").read_text(encoding="utf-8")


def _resolved_paypal() -> str:
    from receipts.paypal import creds
    m = os.environ.get("PAYPAL_MODE", "auto").lower()
    return ("sandbox" if all(creds()) else "standin") if m == "auto" else m


@app.get("/api/meta")
def meta():
    # "models" stays the twelve open models; the seven frontier models are listed beside them when their recorded runs
    # are on disk. A file check only: this is the hosted demo's health check and must never wait on parsing the runs.
    frontier = FRONTIER if any((RESULTS / "frontier" / n).exists() for n in ("episodes_scored.jsonl", "episodes.jsonl")) else []
    return {"business": BIZ, "models": MODELS, "frontier_models": frontier, "live_allowed": LIVE_ALLOWED,
            "paypal_mode": _resolved_paypal(),
            "scenarios": [{"id": s["id"], "title": s["title"], "kind": s["kind"], "pressure": s["pressure"]} for s in SCENARIOS]}


@app.get("/api/inbox")
def inbox(scenario: str):
    if scenario not in BY_ID:
        raise HTTPException(404, "no such day")
    from receipts.desk import Desk
    from receipts.paypal import StandIn
    scn = BY_ID[scenario]
    return {"title": scn["title"], "kind": scn["kind"], "pressure": scn["pressure"],
            "messages": Desk(scn, StandIn(scn.get("paypal", {}), scn["id"]).ids).inbox}


@app.get("/api/policy")
def get_policy(request: Request):
    return {**_rules(request), "fields": {k: {"kind": v[0], "label": v[1]} for k, v in FIELDS.items()}}


class CompileIn(BaseModel):
    english: str


@app.post("/api/compile")
def compile_rules(body: CompileIn):
    out = ai_compile(body.english)
    return {**out, "english": body.english, "fields": {k: {"kind": v[0], "label": v[1]} for k, v in FIELDS.items()}}


class PolicyIn(BaseModel):
    policy: dict
    english: str = ""
    sources: dict = {}
    compiled_by: str = "owner"


@app.post("/api/policy")
def set_policy(body: PolicyIn, request: Request):
    """This visitor's rules, for this visitor's runs from now on. Nobody else's change."""
    from receipts.compiler import _validate
    if len(body.english) > MAX_ENGLISH_CHARS:
        raise HTTPException(413, f"Those rules are too long to keep: the most is {MAX_ENGLISH_CHARS:,} characters.")
    if len(body.sources) > MAX_SOURCES or any(len(str(k)) > MAX_SOURCE_CHARS or len(v if isinstance(v, str) else json.dumps(v, default=str)) > MAX_SOURCE_CHARS for k, v in body.sources.items()):
        raise HTTPException(413, f"Those quotes are too long to keep: at most {MAX_SOURCES} of them, each up to {MAX_SOURCE_CHARS:,} characters.")
    visitor = _visitor(request, create=True, may_start=False)
    if visitor is None:
        raise HTTPException(400, "Please load the page first, then save your rules.")
    rules = visitor.rules
    rules.update({"policy": _validate(body.policy), "english": body.english or rules["english"],
                  "sources": body.sources, "compiled_by": body.compiled_by})
    return rules


def _data(ev) -> str:
    """One event as JSON a browser can read. NaN and Infinity are not JSON, so an event holding one is written
    again in its safe form (see ``safe_json``) instead of breaking the stream."""
    try:
        return json.dumps(ev, default=str, allow_nan=False)
    except Exception:  # noqa: BLE001  NaN, a very deep argument (RecursionError), anything else: never end the stream
        pass
    try:
        return json.dumps(safe_json(ev))
    except Exception:  # noqa: BLE001
        head = ev.get("head") if isinstance(ev, dict) else None
        try:
            return json.dumps({"type": "unshown", "msg": "One event was too large or too deep to show here. It is in the book.",
                               "head": safe_json(head)})
        except Exception:  # noqa: BLE001
            return '{"type": "unshown", "msg": "One event could not be shown here. It is in the book."}'


def _sse(q: queue.Queue, carbon_of=None):
    """The events of one run as a server-sent stream. With ``carbon_of`` (a function giving the run's book, or
    None) every event also carries ``head``: a stamp of the book at that moment, signed, for the owner's device
    to keep."""
    while True:
        ev = q.get()
        if ev is None:
            break
        book = carbon_of() if carbon_of else None
        if book is not None and isinstance(ev, dict):
            ev = {**ev, "head": book.stamp()}
        yield f"data: {_data(ev)}\n\n"


def _carbon_of(visitor: Visitor, sid: str):
    def get():
        s = visitor.sessions.get(sid)
        return s["carbon"] if s else None
    return get


def _register(r: Receipts, q: queue.Queue, sid: str, visitor: Visitor, source: str = "live run", model: str = ""):
    """Keep the run with its own carbon-copy book (a live run gets it here, before its first event; a replay
    built its Receipts with one already) and the stamps the owner's phone is handed."""
    if r.carbon is None:
        r.carbon = CarbonCopy(SIGNER)
    if not r.carbon.receipts():
        # the first receipt of every book says what the run was; the screen and the ledger read it from here
        r.carbon.append("run", run_event(r.mode, "live" if source.startswith("live") else "recorded", r.scenario["id"], model,
                                         title=r.scenario.get("title")))
    with _VISITORS_LOCK:
        visitor.sessions[sid] = {"sid": sid, "r": r, "t": time.time(), "carbon": r.carbon, "stamps": [], "source": source}
        while len(visitor.sessions) > MAX_SESSIONS_PER_VISITOR:
            visitor.sessions.pop(next(iter(visitor.sessions)))
    q.put({"type": "session", "session": sid, "mode": r.mode, "backend": r.paypal.backend, "note": getattr(r.paypal, "note", None)})


@app.get("/api/run")
def run(request: Request, scenario: str, model: str, mode: str = "enforce"):
    if not LIVE_ALLOWED:
        raise HTTPException(403, "Live model runs are off on this demo; use a recorded run.")
    if scenario not in BY_ID or mode not in ("enforce", "observe"):
        raise HTTPException(400, "bad scenario or mode")
    visitor = _visitor(request, create=True)
    policy = dict(visitor.rules["policy"])          # the rules as they stand when the run starts
    q: queue.Queue = queue.Queue()
    sid = uuid.uuid4().hex[:10]

    def work():
        # no key for this model's provider: say so plainly, instead of a run that "finishes" having done nothing
        # (found 2026-11-10 by running a fresh public clone with no keys, as a judge would)
        from receipts import providers
        prov = providers.provider_for(model)
        if not providers.key_for(prov):
            q.put({"type": "error", "msg": f"A live run needs an AI model key for {prov} ({' or '.join(providers.PROVIDERS[prov]['keys'])}), "
                                          "and this copy has none. Choose \"Recorded real run\" above: it replays real runs "
                                          "through Carbon Copy and PayPal now, with no keys."})
            q.put({"type": "done", "outcome": {"class": "ERROR"}, "error": "no model key"})
            q.put(None)
            return
        try:
            rec = run_episode(BY_ID[scenario], model, mode=mode, on_event=q.put, policy=policy,
                              on_start=lambda r: _register(r, q, sid, visitor, model=model))
            entry = visitor.sessions.get(sid)
            visitor.live_ledger.extend(_ledger_from(rec, live=True, book=entry["carbon"] if entry else None))
            q.put({"type": "done", "outcome": rec["outcome"], "seconds": rec["seconds"], "error": rec["error"]})
        except Exception as e:  # noqa: BLE001
            q.put({"type": "error", "msg": f"{type(e).__name__}: {e}"[:300]})
            q.put({"type": "done", "outcome": {"class": "ERROR"}})
        q.put(None)

    threading.Thread(target=work, daemon=True).start()
    return StreamingResponse(_sse(q, _carbon_of(visitor, sid)), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _episodes() -> list[dict]:
    """Every recorded run with its line number (the replay index), parsed once and reused until the file changes."""
    from receipts import measure
    p = RESULTS / "episodes_scored.jsonl"
    if not p.exists():
        p = RESULTS / "episodes.jsonl"
    if not p.exists():
        return []
    return measure.cached(("episodes", str(p)), measure._stamp(p), lambda: _parse_episodes(p))


def _parse_episodes(p: Path) -> list[dict]:
    out = []
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
        try:
            r = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        r["_line"] = i
        out.append(r)
    return out


# The seven frontier models' runs live in their own folder (results/frontier). They are replayed from the rows the
# Results tab and the book already hold in memory (measure.load_scored: the latest finished run per model, day, arm
# and run number), so no second copy is parsed. Their replay numbers start here, clear of the open models' line numbers.
FRONTIER_LINE0 = 1_000_000


def _frontier_episodes() -> list[dict]:
    from receipts import measure
    return measure._pick(RESULTS / "frontier")


def _recorded_run(line: int) -> dict | None:
    if line >= FRONTIER_LINE0:
        rows = _frontier_episodes()
        return rows[line - FRONTIER_LINE0] if line - FRONTIER_LINE0 < len(rows) else None
    return next((r for r in _episodes() if r["_line"] == line), None)


@app.get("/api/recorded")
def recorded(scenario: str | None = None, model: str | None = None):
    rows = []
    numbered = [(r["_line"], r) for r in _episodes()] + [(FRONTIER_LINE0 + i, r) for i, r in enumerate(_frontier_episodes())]
    for line, r in numbered:
        if r["outcome"].get("class") in ("ERROR", "NO_TOOL_CALLS"):
            continue
        if scenario and r["scenario"] != scenario:
            continue
        if model and r["model"] != model:
            continue
        rows.append({"line": line, "scenario": r["scenario"], "model": r["model"], "mode": r["mode"], "rep": r["rep"],
                     "ts": r.get("ts"), "class": r["outcome"]["class"], "attempts": r["outcome"].get("trap_attempts"),
                     "money_at_risk": r["outcome"].get("money_at_risk"), "report": r["outcome"].get("report"),
                     "said_no_did_it": r["outcome"].get("said_no_did_it")})
    return rows


@app.get("/api/replay")
def replay(request: Request, line: int, speed: float = 1.0, mode: str | None = None):
    """Re-drive a recorded run: the model's words and tool calls are the recorded ones;
    Receipts and PayPal run NOW. Labelled as a replay everywhere it is shown."""
    rec = _recorded_run(line)
    if rec is None or rec["outcome"].get("class") in ("ERROR", "NO_TOOL_CALLS"):
        raise HTTPException(404, "no such recorded run")
    scn = BY_ID[rec["scenario"]]
    visitor = _visitor(request, create=True)
    policy = dict(visitor.rules["policy"])          # this visitor's rules as they stand when the run starts
    q: queue.Queue = queue.Queue()
    sid = uuid.uuid4().hex[:10]
    use_mode = mode or rec["mode"]

    def work():
        try:
            pp = make_paypal(scn.get("paypal", {}), scn["id"])
            r = Receipts(scn, pp, mode=use_mode, policy=policy, on_event=q.put, carbon=CarbonCopy(SIGNER))
            _register(r, q, sid, visitor, source="recorded run, replayed", model=rec["model"])
            q.put({"type": "replay", "model": rec["model"], "recorded_at": rec.get("ts"), "recorded_mode": rec["mode"], "mode": use_mode})
            # Recorded against the stand-in; in the sandbox the same orders carry real PayPal ids.
            # Both are keyed by the same names ("A.capture_id"), so recorded ids translate one to one.
            from receipts.paypal import StandIn
            tr = {}
            if pp.backend == "sandbox":
                fake = StandIn(scn.get("paypal", {}), scn["id"]).ids
                tr = {v: pp.ids[k] for k, v in fake.items() if k in pp.ids}

            def T(x):
                if not tr:
                    return x
                if isinstance(x, str):
                    for a, b in tr.items():
                        x = x.replace(a, b)
                    return x
                if isinstance(x, dict):
                    return {k: T(v) for k, v in x.items()}
                if isinstance(x, list):
                    return [T(v) for v in x]
                return x

            last_text = ""
            for e in T(rec["events"]):
                time.sleep(max(0.05, 0.9 / max(speed, 0.1)))
                if e["type"] == "say" and e.get("where") == "reply":
                    last_text = e["text"]
                    m = r.note_words(e["text"], "reply")
                    q.put({"type": "say", "where": "reply", "text": e["text"], "marker": m})
                elif e["type"] == "call":
                    q.put({"type": "call", "tool": e["tool"], "args": e["args"]})
                    r.call(e["tool"], e["args"], step_text=last_text)
            out = r.outcome()
            q.put({"type": "done", "outcome": out, "replay": True})
            pp.close()
        except Exception as e:  # noqa: BLE001
            q.put({"type": "error", "msg": f"{type(e).__name__}: {e}"[:300]})
            q.put({"type": "done", "outcome": {"class": "ERROR"}})
        q.put(None)

    threading.Thread(target=work, daemon=True).start()
    return StreamingResponse(_sse(q, _carbon_of(visitor, sid)), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class HoldIn(BaseModel):
    session: str
    hold_id: str


def _sessions(request: Request) -> dict[str, Receipts]:
    """The runs whose holds this visitor may see and decide: their own, and the MCP workspace's where that is on."""
    v = _visitor(request)
    with _VISITORS_LOCK:
        out = {sid: s["r"] for sid, s in (v.sessions.items() if v else [])}
    if MCP_ON_PHONE and MCP_SESSION.get("r") is not None:
        out["mcp"] = MCP_SESSION["r"]
    return out


@app.get("/api/holds")
def holds(request: Request):
    out = []
    for sid, r in _sessions(request).items():
        for h in list(r.holds):
            out.append({"session": sid, **h, "scenario": r.scenario["title"], "amount": _amt(h)})
    return sorted(out, key=lambda h: h["status"] != "WAITING")


def _amt(h):
    a = h["args"]
    return a.get("amount")


@app.post("/api/reset")
def reset(request: Request):
    """Clear this visitor's runs and holds, nobody else's (their rules and the MCP workspace stay)."""
    v = _visitor(request)
    if v:
        with _VISITORS_LOCK:
            v.sessions.clear()
            v.live_ledger.clear()
    return {"reset": True}


def _with_key(r: Receipts, out):
    """The stamp the tap returns, plus the public key that signed it, so the owner's device can pin the key."""
    if isinstance(out, dict) and isinstance(out.get("stamp"), dict) and r.carbon is not None:
        out["stamp"] = {**out["stamp"], "public_key": r.carbon.stamp()["public_key"]}
    return out


def _keep_stamp(request: Request, sid: str, out) -> None:
    """The phone keeps the stamp handed over with the tap, in this run's session."""
    v = _visitor(request)
    stamp = out.get("stamp") if isinstance(out, dict) else None
    if v and stamp:
        with _VISITORS_LOCK:
            s = v.sessions.get(sid)
            if s is not None:
                s["stamps"].append(stamp)


def _touch(request: Request, sid: str) -> None:
    """The owner is acting on this run: its hour starts again. Done BEFORE the tap, because the tap can leave the run
    with nothing waiting, and a run already over an hour old with nothing waiting is dropped on the next request."""
    v = _visitor(request)
    if v:
        with _VISITORS_LOCK:
            s = v.sessions.get(sid)
            if s is not None:
                s["t"] = time.time()


@app.post("/api/approve")
def approve(body: HoldIn, request: Request):
    r = _sessions(request).get(body.session)
    if not r:
        raise HTTPException(404, "session expired")
    if body.session == "mcp" and r.carbon is not None and r.carbon.size_bytes() >= getattr(r, "mcp_cap_bytes", float("inf")):
        raise HTTPException(409, "This demo's MCP book is full; restart the server to start a new one.")     # an approval sends money: no room for its receipt
    _touch(request, body.session)
    out = _with_key(r, r.approve(body.hold_id))
    _keep_stamp(request, body.session, out)
    return out


@app.post("/api/decline")
def decline(body: HoldIn, request: Request):
    r = _sessions(request).get(body.session)
    if not r:
        raise HTTPException(404, "session expired")
    _touch(request, body.session)
    out = _with_key(r, r.decline(body.hold_id))
    _keep_stamp(request, body.session, out)
    return out


# ---- the carbon-copy book -------------------------------------------------------------------------------
def _carbon_session(request: Request, sid: str | None, mode: str | None = None) -> dict | None:
    """The run whose book to show. Only this visitor's runs, never another's.

    With an id: that run. Otherwise the latest run of the asked mode; with no mode, the latest ENFORCE run, and
    only when there is none the latest of any mode. The choice looks at the runs' modes, never at which replay
    finished last, so the two side-by-side replays cannot race.
    """
    v = _visitor(request)
    with _VISITORS_LOCK:
        mine = dict(v.sessions) if v else {}
    if sid is not None:
        return mine.get(sid)
    newest_first = list(reversed(mine.values()))
    if mode is not None:
        return next((s for s in newest_first if s["r"].mode == mode), None)
    return next((s for s in newest_first if s["r"].mode == "enforce"), None) or next(iter(newest_first), None)


def _check_mode(mode: str | None) -> None:
    if mode not in (None, "enforce", "observe"):
        raise HTTPException(400, "mode must be enforce or observe")


@app.get("/api/carbon")
def carbon_book(request: Request, sid: str | None = None, mode: str | None = None):
    _check_mode(mode)
    s = _carbon_session(request, sid, mode)
    if s is None:
        if sid is not None:
            raise HTTPException(404, "session expired")
        return {"public_key": None, "head": None, "receipts": [], "stamps": [], "source": None, "session": None,
                "mode": None, "has_twin": False}
    v = _visitor(request)
    mine = list(v.sessions.values()) if v else []
    with _VISITORS_LOCK:
        stamps = copy.deepcopy(s["stamps"])
        other = "observe" if s["r"].mode == "enforce" else "enforce"
        twin = any(o["r"].mode == other and o["r"].scenario["id"] == s["r"].scenario["id"] for o in mine)
    return {**s["carbon"].book(), "stamps": stamps, "source": s["source"], "session": s["sid"],
            "mode": s["r"].mode, "has_twin": twin}

@app.get("/api/carbon/key")
def carbon_key():
    """The public key every book of this server is signed with, for the page footer and for anyone checking."""
    return {"public_key": SIGNER.public_key_hex, "short": SIGNER.short_key, "temporary": SIGNER.temporary}


class VerifyIn(BaseModel):
    book: dict
    stamps: Any = None           # whatever the device holds; the check fails closed on anything that is not a list of stamps
    expected_key: str | None = None


@app.post("/api/carbon/verify")
def carbon_verify_book(body: VerifyIn):
    """The fallback check, for a browser with no Ed25519. The device sends its own stamps and the key it trusts;
    nothing here is read from the server's own session."""
    try:
        return carbon_verify(body.book, body.stamps, expected_key=body.expected_key)
    except Exception:  # noqa: BLE001  a file that is not a book fails closed
        return {"intact": False, "count": 0, "first_bad": 1, "why": "this is not a carbon-copy book we can read"}


@app.post("/api/carbon/tamper")
def carbon_tamper(request: Request, sid: str | None = None, mode: str | None = None):
    """Change one value in a COPY of the book. Returns the changed copy (``book``) for the browser to check, and the
    server's own verdict on it (``result``) for the command line and tests. The real book is never touched."""
    _check_mode(mode)
    s = _carbon_session(request, sid, mode)
    if s is None:
        raise HTTPException(404, "no run to copy yet")
    return tamper_demo(s["carbon"].book())


@app.post("/api/carbon/forge")
def carbon_forge(request: Request, sid: str | None = None, mode: str | None = None):
    """The real attack, for the demo: a copy of the book with the owner's decline flipped to approved and every
    receipt re-signed with a brand-new key. The browser checks it against the key it trusts. The real book is never touched."""
    _check_mode(mode)
    s = _carbon_session(request, sid, mode)
    if s is None:
        raise HTTPException(404, "no run to copy yet")
    out = forge_demo(s["carbon"].book())
    if out["book"] is None:
        raise HTTPException(404, "no receipts to copy yet")
    return {"book": out["book"], "n": out["n"], "field": out["field"], "say": out["say"]}


def _ledger_from(rec: dict, live: bool = False, book: CarbonCopy | None = None):
    """Ledger rows for one run. With its book, each row also carries the number and fingerprint of the receipt
    for its verdict; rows read from the recorded results files have no book and leave both blank."""
    by_id = {}
    sealed = None                      # with a book, model, scenario and time come only from its sealed run receipt
    if book is not None:
        sealed = run_of(book.receipts()) or {}
        by_id = {r["event"].get("id"): r for r in book.receipts() if r["kind"] == "verdict"}
    rows = []
    for v in rec.get("verdicts", []):
        a = v["args"]
        rows.append({"when": rec.get("ts") if sealed is None else sealed.get("started", ""),
                     "scenario": rec["scenario"] if sealed is None else sealed.get("scenario", ""),
                     "model": rec["model"] if sealed is None else sealed.get("model", ""),
                     "arm": "Carbon Copy ON" if (rec["mode"] if sealed is None else sealed.get("mode")) == "enforce" else "Carbon Copy OFF",
                     "tool": v["tool"], "amount": v.get("amount"),
                     "to": a.get("receiver_email") or a.get("new_paypal_email") or a.get("capture_id") or a.get("dispute_id"),
                     "ref": a.get("invoice_number") or a.get("capture_id") or a.get("dispute_id") or a.get("vendor"),
                     "decision": v["decision"], "codes": ", ".join(f["code"] for f in v["findings"]),
                     "why": " ".join(f["why"] for f in v["findings"]),
                     "said_first": v.get("words_class") == "SAID_NO_DID_IT",
                     "paypal_id": next((l.get("paypal_id") for l in rec["outcome"].get("ledger", [])
                                        if str(l.get("ref", "")).upper() == str(a.get("invoice_number", "")).upper()), None),
                     "backend": rec.get("paypal_backend"), "live": live,
                     "receipt_n": (by_id.get(v.get("id")) or {}).get("n"), "fp": (by_id.get(v.get("id")) or {}).get("fp")})
    return rows


@app.get("/api/ledger")
def ledger(request: Request, limit: int = 6000):
    """Every money move: this visitor's live runs first, then the measured runs of all 19 models, read through the
    same loader as the results (receipts/measure.py), so an errored run never appears and the frontier runs do."""
    from receipts import measure
    v = _visitor(request)
    rows = list(v.live_ledger) if v else []
    for r in measure.load_groups(RESULTS)["all"]:
        rows.extend(_ledger_from(r))
    return rows[:limit]


@app.get("/api/results")
def results(group: str = "all"):
    """The measurement, computed from the scored runs (receipts/measure.py), the same numbers the README states.
    group: all | open | frontier."""
    from receipts import measure
    return measure.results(RESULTS, group)


app.mount("/mcp", MCP_SERVER.streamable_http_app(streamable_http_path="/"))
