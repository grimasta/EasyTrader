# --- example_integration.py ---

# Suppose you already have:
# def cancel_order(order_id: str) -> dict: ...
# def is_order_done(order_id: str) -> bool: ...
# def place_order(symbol: str, side: str, qty: float, ... ) -> str: returns order_id

from grok_produce.structured.api_client.self_cancel_timer import schedule_self_cancel

def on_cancelled(order_id: str, reason: str) -> None:
    print(f"[callback] order {order_id} cancelled (reason={reason})")

def on_skipped(order_id: str, reason: str) -> None:
    print(f"[callback] cancel skipped for {order_id} (reason={reason})")


def place_with_self_cancel(symbol: str, side: str, qty: float, timeout_s: float) -> str:
    order_id = place_order(symbol, side, qty)     # your existing function

    # Fire-and-forget timer; keep the returned handle if you want to stop it later
    timer = schedule_self_cancel(
        order_id,
        timeout_s=timeout_s,
        cancel=cancel_order,          # your existing cancellation function
        is_done=is_order_done,        # your existing status check
        on_cancelled=on_cancelled,
        on_skipped=on_skipped,
        logger=logger,                # optional
        name=f"SC-{symbol}-{order_id}",
    )

    # If you have a websocket/webhook that detects fills, call:
    # timer.mark_filled_or_closed()

    return order_id
