import threading
from typing import Callable, Optional, Any
from dataclasses import dataclass, field
import time


OrderId = str

# Signature expectations (use your existing functions here):
# - cancel: Callable[[OrderId], Any]                 # must attempt to cancel the order
# - is_done: Callable[[OrderId], bool]               # True if order is already filled/canceled/closed
# Optional callbacks:
# - on_cancelled: Callable[[OrderId, str], None]     # reason ∈ {"timeout", "manual"}
# - on_skipped: Callable[[OrderId, str], None]       # e.g., "already_done"
# - logger: object with .info/.warning/.error (optional)


@dataclass
class SelfCancelTimer:
    order_id: OrderId
    timeout_s: float
    cancel: Callable[[OrderId], Any]
    is_done: Callable[[OrderId], bool]
    on_cancelled: Optional[Callable[[OrderId, str], None]] = None
    on_skipped: Optional[Callable[[OrderId, str], None]] = None
    logger: Optional[Any] = None
    name: Optional[str] = None

    _timer: Optional[threading.Timer] = field(default=None, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _active: bool = field(default=False, init=False)
    _started_at: float = field(default=0.0, init=False)

    def start(self) -> None:
        """Start the self-cancel timer. Safe to call once."""
        with self._lock:
            if self._active:
                return
            self._active = True
            self._started_at = time.time()
            self._timer = threading.Timer(self.timeout_s, self._timeout_handler)
            self._timer.daemon = True  # don't block interpreter exit
            self._timer.setName(self.name or f"SelfCancelTimer[{self.order_id}]")
            self._timer.start()
            if self.logger:
                self.logger.info(
                    f"[{self._timer.getName()}] started: order_id={self.order_id}, "
                    f"timeout={self.timeout_s:.3f}s"
                )

    def cancel_timer(self, reason: str = "manual") -> None:
        """Manually stop the timer (no order action)."""
        with self._lock:
            if not self._active:
                return
            if self._timer is not None:
                self._timer.cancel()
            self._active = False
        if self.logger:
            self.logger.info(f"[SelfCancelTimer] timer stopped for order_id={self.order_id} (reason={reason})")

    def mark_filled_or_closed(self) -> None:
        """
        Notify the timer that the order completed early (e.g., on fill webhook or polling).
        This prevents a late timeout from attempting a cancel.
        """
        self.cancel_timer(reason="already_done")
        if self.on_skipped:
            self.on_skipped(self.order_id, "already_done")

    def is_running(self) -> bool:
        with self._lock:
            return self._active

    def _timeout_handler(self) -> None:
        """
        Runs in the timer thread. Checks status; if still open, cancels the order.
        """
        try:
            # Double-check status at timeout to avoid cancelling a filled order
            already_done = False
            try:
                already_done = bool(self.is_done(self.order_id))
            except Exception as e:
                if self.logger:
                    self.logger.error(f"[SelfCancelTimer] is_done failed for order_id={self.order_id}: {e}")

            if already_done:
                if self.logger:
                    self.logger.info(f"[SelfCancelTimer] skip cancel: order already done (order_id={self.order_id})")
                if self.on_skipped:
                    self.on_skipped(self.order_id, "already_done")
                return

            # Attempt cancel
            if self.logger:
                self.logger.info(f"[SelfCancelTimer] timeout reached; cancelling order_id={self.order_id}")
            try:
                self.cancel(self.order_id)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"[SelfCancelTimer] cancel failed for order_id={self.order_id}: {e}")
                # Even if cancel throws, we consider the timer finished
            finally:
                if self.on_cancelled:
                    self.on_cancelled(self.order_id, "timeout")
        finally:
            with self._lock:
                self._active = False
                self._timer = None


def schedule_self_cancel(
    order_id: OrderId,
    *,
    timeout_s: float,
    cancel: Callable[[OrderId], Any],
    is_done: Callable[[OrderId], bool],
    on_cancelled: Optional[Callable[[OrderId, str], None]] = None,
    on_skipped: Optional[Callable[[OrderId, str], None]] = None,
    logger: Optional[Any] = None,
    name: Optional[str] = None,
) -> SelfCancelTimer:
    """
    Functional helper; returns the running timer object so callers can .mark_filled_or_closed()
    as soon as fills come in (websocket/webhook) or .cancel_timer() if they must stop it.
    """
    t = SelfCancelTimer(
        order_id=order_id,
        timeout_s=timeout_s,
        cancel=cancel,
        is_done=is_done,
        on_cancelled=on_cancelled,
        on_skipped=on_skipped,
        logger=logger,
        name=name,
    )
    t.start()
    return t


# ======================================================================================================================
# **********************************************************************************************************************
# ======================================================================================================================
# **********************************************************************************************************************
# ======================================================================================================================
# How it's used
# # --- example_integration.py ---
#
# # Suppose you already have:
# # def cancel_order(order_id: str) -> dict: ...
# # def is_order_done(order_id: str) -> bool: ...
# # def place_order(symbol: str, side: str, qty: float, ... ) -> str: returns order_id
#
# from self_cancel_timer import schedule_self_cancel
#
# def on_cancelled(order_id: str, reason: str) -> None:
#     print(f"[callback] order {order_id} cancelled (reason={reason})")
#
# def on_skipped(order_id: str, reason: str) -> None:
#     print(f"[callback] cancel skipped for {order_id} (reason={reason})")
#
#
# def place_with_self_cancel(symbol: str, side: str, qty: float, timeout_s: float) -> str:
#     order_id = place_order(symbol, side, qty)     # your existing function
#
#     # Fire-and-forget timer; keep the returned handle if you want to stop it later
#     timer = schedule_self_cancel(
#         order_id,
#         timeout_s=timeout_s,
#         cancel=cancel_order,          # your existing cancellation function
#         is_done=is_order_done,        # your existing status check
#         on_cancelled=on_cancelled,
#         on_skipped=on_skipped,
#         logger=logger,                # optional
#         name=f"SC-{symbol}-{order_id}",
#     )
#
#     # If you have a websocket/webhook that detects fills, call:
#     # timer.mark_filled_or_closed()
#
#     return order_id