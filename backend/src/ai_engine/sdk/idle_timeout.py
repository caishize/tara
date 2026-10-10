"""
Idle timeout utilities for SDK async streams.

Provides an async generator wrapper that raises ``IdleTimeoutError``
when no item is yielded within a configurable number of seconds.
This is *not* a total execution time limit — actively-working agents
that keep producing messages will never be interrupted.
"""

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Log a warning when the gap between consecutive messages exceeds this threshold.
_GAP_WARNING_SECONDS = 30


class IdleTimeoutError(Exception):
    """Raised when no SDK message is received within the idle timeout."""


async def iter_with_idle_timeout(
    aiter,
    idle_seconds: int,
    keepalive: Optional[asyncio.Event] = None,
):
    """Wrap an async iterator with per-item idle timeout.

    Yields items from *aiter* as long as each next item arrives within
    *idle_seconds*.  If the gap between two consecutive items exceeds
    the limit, raises ``IdleTimeoutError``.

    If *keepalive* is provided, setting it resets the idle timer without
    requiring a new item from the stream.  This is useful when long-running
    tool calls (e.g. sub-agent execution) are in progress — the tool can
    periodically signal the keepalive to prevent premature timeouts.

    Args:
        aiter: Any async iterable (e.g. ``client.receive_response()``).
        idle_seconds: Maximum seconds to wait for the next item.
        keepalive: Optional event — setting it resets the idle timer.

    Yields:
        Items from the underlying async iterator.

    Raises:
        IdleTimeoutError: If the stream goes silent for too long.
    """
    if idle_seconds <= 0:
        # Timeout disabled: pass through the stream unchanged.
        async for item in aiter:
            yield item
        return

    ait = aiter.__aiter__()
    item_count = 0
    last_item_at = time.monotonic()
    last_item_type = "start"

    while True:
        try:
            if keepalive is None:
                item = await asyncio.wait_for(
                    ait.__anext__(), timeout=idle_seconds,
                )
            else:
                item = await _wait_with_keepalive(ait, idle_seconds, keepalive)
        except StopAsyncIteration:
            total_elapsed = time.monotonic() - last_item_at
            logger.debug(
                "idle_timeout: stream ended normally after %d items "
                "(final_gap=%.1fs, last_type=%s)",
                item_count, total_elapsed, last_item_type,
            )
            return
        except asyncio.TimeoutError:
            total_elapsed = time.monotonic() - last_item_at
            raise IdleTimeoutError(
                f"No SDK message received for {idle_seconds}s "
                f"(total_items_before_timeout={item_count}, "
                f"last_message_type={last_item_type}, "
                f"actual_gap={total_elapsed:.1f}s)"
            )

        now = time.monotonic()
        gap = now - last_item_at
        item_count += 1
        item_type = type(item).__name__

        if gap > _GAP_WARNING_SECONDS:
            logger.warning(
                "idle_timeout: long gap between messages: %.1fs "
                "(item_count=%d, prev_type=%s, curr_type=%s, "
                "idle_limit=%ds)",
                gap, item_count, last_item_type, item_type, idle_seconds,
            )
        elif item_count == 1:
            logger.info(
                "idle_timeout: first message received after %.1fs (type=%s)",
                gap, item_type,
            )

        last_item_at = now
        last_item_type = item_type
        yield item


async def _wait_with_keepalive(
    ait,
    idle_seconds: int,
    keepalive: asyncio.Event,
):
    """Wait for the next item, resetting the deadline on each keepalive signal.

    Returns the next item from *ait*.  Raises ``asyncio.TimeoutError`` if
    neither the next item nor a keepalive arrives within *idle_seconds*.
    Raises ``StopAsyncIteration`` when the underlying iterator is exhausted.
    """
    loop = asyncio.get_event_loop()
    deadline = loop.time() + idle_seconds

    # Wrap __anext__ in a task so we can race it against keepalive
    next_fut = asyncio.ensure_future(ait.__anext__())
    try:
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise asyncio.TimeoutError()

            # Consume already-set keepalive without waiting to avoid
            # losing signals that arrived just before this loop iteration.
            if keepalive.is_set():
                keepalive.clear()
                deadline = loop.time() + idle_seconds
                continue

            ka_fut = asyncio.ensure_future(keepalive.wait())

            done, _ = await asyncio.wait(
                {next_fut, ka_fut},
                timeout=remaining,
                return_when=asyncio.FIRST_COMPLETED,
            )

            if next_fut in done:
                ka_fut.cancel()
                return next_fut.result()

            if ka_fut in done:
                # Keepalive received — reset the deadline
                keepalive.clear()
                deadline = loop.time() + idle_seconds
                continue

            # Neither completed → timed out
            ka_fut.cancel()
            raise asyncio.TimeoutError()
    except BaseException:
        if not next_fut.done():
            next_fut.cancel()
        raise
