# entry_guard.py
import threading
from typing import Dict

_ENTRY_LOCK = threading.RLock()
_ENTRY_STATE: Dict[str, str] = {}   # symbol -> "idle"|"pending"|"open"

def is_blocked(symbol: str) -> bool:
    with _ENTRY_LOCK:
        return _ENTRY_STATE.get(symbol) in ("pending", "open")

def set_pending(symbol: str):
    with _ENTRY_LOCK:
        _ENTRY_STATE[symbol] = "pending"

def set_open(symbol: str):
    with _ENTRY_LOCK:
        _ENTRY_STATE[symbol] = "open"

def clear(symbol: str):
    with _ENTRY_LOCK:
        _ENTRY_STATE[symbol] = "idle"

def state(symbol: str) -> str:
    with _ENTRY_LOCK:
        return _ENTRY_STATE.get(symbol, "idle")

def seed_open_many(symbols):
    with _ENTRY_LOCK:
        for s in symbols:
            _ENTRY_STATE[s] = "open"