# v2_on_candle_close_tp_sl.py  — actor-based delayed-brackets
from __future__ import annotations
import time, threading, queue
from dataclasses import dataclass, replace
from typing import Optional, Dict, Tuple

# ----------------- Data -----------------
@dataclass
class Bracket:
    active: bool
    entry_price: float
    tp: Optional[float]
    sl: Optional[float]
    created_at_ms: int

def _compute_tp_sl(entry_price: float, tp_pct: float, sl_pct: float) -> Tuple[float, float]:
    return entry_price * (1.0 + float(tp_pct)), entry_price * (1.0 - float(sl_pct))

# ----------------- Actor -----------------
class BracketActor:
    def __init__(self):
        self._q: "queue.Queue[Tuple[str, dict]]" = queue.Queue()
        self._t = threading.Thread(target=self._run, name="BracketActor", daemon=True)
        self._stop = False
        self._registry: Dict[str, Bracket] = {}

    def start(self):
        if not self._t.is_alive():
            self._stop = False
            self._t.start()

    def shutdown(self):
        self._q.put(("SHUTDOWN", {}))
        # no join here (daemon); add a join if you need orderly stop

    # ---- API (enqueue) ----
    def register(self, symbol: str, entry_price: float, tp_pct: float, sl_pct: float):
        self._q.put(("REGISTER", {"symbol": symbol, "entry": entry_price, "tp_pct": tp_pct, "sl_pct": sl_pct}))

    def deactivate(self, symbol: str):
        self._q.put(("DEACTIVATE", {"symbol": symbol}))

    def clear(self, symbol: str):
        self._q.put(("CLEAR", {"symbol": symbol}))

    def snapshot(self, symbol: str) -> Optional[Bracket]:
        reply: "queue.Queue[Optional[Bracket]]" = queue.Queue(maxsize=1)
        self._q.put(("SNAPSHOT", {"symbol": symbol, "reply": reply}))
        return reply.get()

    def has_active(self, symbol: str) -> bool:
        br = self.snapshot(symbol)
        return bool(br and br.active)

    def eval_close(self, symbol: str, close_price: float) -> Optional[dict]:
        # returns {"symbol": s, "exit": "TP"|"SL", "price": float} or None
        reply: "queue.Queue[Optional[dict]]" = queue.Queue(maxsize=1)
        self._q.put(("EVAL", {"symbol": symbol, "close": close_price, "reply": reply}))
        return reply.get()

    # ---- Worker ----
    def _run(self):
        while not self._stop:
            cmd, payload = self._q.get()
            if cmd == "SHUTDOWN":
                self._stop = True
                continue

            if cmd == "REGISTER":
                s = payload["symbol"]; entry = float(payload["entry"])
                tp_pct = float(payload["tp_pct"]); sl_pct = float(payload["sl_pct"])
                tp, sl = _compute_tp_sl(entry, tp_pct, sl_pct)
                now = int(time.time() * 1000)
                # policy: newer wins; change if you prefer to ignore when active exists
                self._registry[s] = Bracket(True, entry, tp, sl, now)

            elif cmd == "DEACTIVATE":
                s = payload["symbol"]
                b = self._registry.get(s)
                if b:
                    self._registry[s] = replace(b, active=False)

            elif cmd == "CLEAR":
                s = payload["symbol"]
                self._registry.pop(s, None)

            elif cmd == "SNAPSHOT":
                s = payload["symbol"]; reply = payload["reply"]
                b = self._registry.get(s)
                reply.put(None if b is None else replace(b))

            elif cmd == "EVAL":
                s = payload["symbol"]; c = float(payload["close"]); reply = payload["reply"]
                b = self._registry.get(s)
                if not b or not b.active:
                    reply.put(None); continue
                hit = None
                # TP first, then SL; switch order if you prefer SL dominance
                if (b.tp is not None) and (c >= b.tp):
                    self._registry[s] = replace(b, active=False)
                    hit = {"symbol": s, "exit": "TP", "price": b.tp}
                elif (b.sl is not None) and (c <= b.sl):
                    self._registry[s] = replace(b, active=False)
                    hit = {"symbol": s, "exit": "SL", "price": b.sl}
                reply.put(hit)

# ----------------- Singleton facade (keeps your old names) -----------------
_ACTOR: Optional[BracketActor] = None

def _ensure_actor():
    global _ACTOR
    if _ACTOR is None:
        _ACTOR = BracketActor()
        _ACTOR.start()
    return _ACTOR

# old name kept, but now just enqueues to the actor
def register_delayed_bracket(symbol: str, *, entry_price: float, tp_pct: float, sl_pct: float):
    _ensure_actor().register(symbol, entry_price, tp_pct, sl_pct)

def on_candle_close(symbol: str, close_price: float) -> Optional[dict]:
    # synchronous request/reply to actor (still serialized)
    return _ensure_actor().eval_close(symbol, close_price)

# helper accessors (use these instead of touching any dict directly)
def get_bracket_snapshot(symbol: str) -> Optional[Bracket]:
    return _ensure_actor().snapshot(symbol)

def has_active_bracket(symbol: str) -> bool:
    return _ensure_actor().has_active(symbol)

def deactivate_bracket(symbol: str):
    _ensure_actor().deactivate(symbol)

def clear_bracket(symbol: str):
    _ensure_actor().clear(symbol)
