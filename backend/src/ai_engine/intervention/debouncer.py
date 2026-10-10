"""
Intervention debouncer for full-duplex signal processing.

Implements a last-write-wins debounce window: within DEBOUNCE_WINDOW_SECONDS,
only the latest signal is dispatched. CANCEL signals bypass debouncing
entirely and are dispatched immediately.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Optional

from .types import InterventionSignal, InterventionType

logger = logging.getLogger(__name__)

# Debounce window in seconds.  Signals arriving within this window
# replace earlier pending signals (last-write-wins).
DEBOUNCE_WINDOW_SECONDS: float = 1.5


class InterventionDebouncer:
    """Debounce intervention signals with last-write-wins semantics.

    CANCEL signals bypass the debounce window and dispatch immediately.
    All other signal types replace any pending signal within the window.

    Usage::

        debouncer = InterventionDebouncer(on_dispatch=handle_signal)
        debouncer.submit(signal)  # non-blocking, calls on_dispatch when ready
    """

    def __init__(
        self,
        on_dispatch: Optional[Callable[[InterventionSignal], Awaitable[None]]] = None,
        window: float = DEBOUNCE_WINDOW_SECONDS,
    ) -> None:
        self._window = max(0.0, window)
        self._pending: Optional[InterventionSignal] = None
        self._timer_task: Optional[asyncio.Task] = None
        self._on_dispatch = on_dispatch

    async def submit(self, signal: InterventionSignal) -> Optional[InterventionSignal]:
        """Submit a signal for debounced dispatch.

        Returns the signal immediately if it's CANCEL (bypass).
        Returns None for all other types (dispatched asynchronously via callback).
        """
        if signal.type == InterventionType.CANCEL.value:
            self._cancel_pending_timer()
            logger.debug(
                "CANCEL signal bypasses debounce: signal_id=%s session=%s",
                signal.signal_id,
                signal.session_id,
            )
            return signal

        # Replace any pending signal (last-write-wins)
        self._pending = signal

        # Start or restart the timer
        if self._timer_task is not None and not self._timer_task.done():
            self._timer_task.cancel()
        self._timer_task = asyncio.create_task(
            self._debounce_wait(), name="debounce-timer"
        )

        return None  # non-blocking: callback will fire later

    async def _debounce_wait(self) -> None:
        """Sleep for the debounce window then dispatch whatever is pending."""
        try:
            await asyncio.sleep(self._window)
        except asyncio.CancelledError:
            return

        dispatched = self._pending
        self._pending = None

        if dispatched is not None:
            logger.debug(
                "Debounced signal dispatched: type=%s signal_id=%s session=%s",
                dispatched.type,
                dispatched.signal_id,
                dispatched.session_id,
            )
            if self._on_dispatch is not None:
                try:
                    await self._on_dispatch(dispatched)
                except Exception:
                    logger.warning(
                        "Debounce dispatch callback failed: signal_id=%s",
                        dispatched.signal_id,
                        exc_info=True,
                    )

    def _cancel_pending_timer(self) -> None:
        """Cancel any in-flight debounce timer."""
        if self._timer_task is not None and not self._timer_task.done():
            self._timer_task.cancel()
            self._timer_task = None
        old_pending = self._pending
        self._pending = None
        if old_pending is not None:
            logger.info(
                "Pending signal cancelled by CANCEL: signal_id=%s",
                old_pending.signal_id,
            )

    def reset(self) -> None:
        """Cancel any pending timer and clear state."""
        self._cancel_pending_timer()
        self._pending = None
