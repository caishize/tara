"""Buffer management for ReactiveSessionActor.

Handles buffering and flushing of ADDITIVE, CONFIRM, and SIDEKICK signals
that arrive during active generation. Buffers are drained as a single
combined query when the session transitions to IDLE.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..intervention.types import InterventionSignal

if TYPE_CHECKING:
    from .reactive_session_actor import ReactiveSessionActor

logger = logging.getLogger(__name__)


def build_confirm_prompt(
    action_id: str,
    confirmation: str,
    *,
    is_ambiguous: bool = False,
    user_text: str = "",
) -> str:
    """Build a confirmation prompt for the SDK.

    Centralizes the confirm prompt construction that was previously
    duplicated across _do_confirm, _flush_buffered_confirms, and
    _flush_all_buffered.
    """
    if confirmation == "approve" and is_ambiguous:
        return (
            f"用户似乎在确认操作，但措辞不够明确。\n"
            f"操作ID: {action_id}\n"
            f"用户原文: {user_text}\n"
            f"如果该操作涉及支付、删除或发送等不可撤销的行为，"
            f"请先向用户确认再执行；否则可以直接继续。"
        )
    if confirmation == "approve":
        return (
            f"用户已确认执行操作\n"
            f"操作ID: {action_id}\n"
            f"请继续执行已确认的操作。"
        )
    return (
        f"用户已拒绝执行操作\n"
        f"操作ID: {action_id}\n"
        f"请根据用户的拒绝做出相应调整。"
    )


def _confirm_signal_to_prompt(signal: InterventionSignal) -> str:
    """Convert a buffered CONFIRM signal into a prompt string."""
    return build_confirm_prompt(
        action_id=signal.payload.get("pending_action_id", ""),
        confirmation=signal.payload.get("confirmation", "approve"),
    )


class ActorBuffersMixin:
    """Mixin providing signal buffer management and flushing."""

    def _extract_signal_text(
        self: "ReactiveSessionActor", signal: InterventionSignal
    ) -> str:
        """Extract user text from signal payload, trying type-specific keys first."""
        p = signal.payload
        return (
            p.get("corrected_input")
            or p.get("additional_input")
            or p.get("new_input")
            or p.get("text", "")
        )

    async def _flush_buffered_additives(
        self: "ReactiveSessionActor",
    ) -> None:
        """Combine buffered ADDITIVE signals and send as single query."""
        if not self._buffered_additives:
            return

        texts = [
            self._extract_signal_text(s)
            for s in self._buffered_additives
            if self._extract_signal_text(s)
        ]
        self._buffered_additives.clear()
        self._additive_this_turn += len(texts)

        if not texts:
            return

        combined = "\n---\n".join(texts)
        prompt = (
            "用户在你回复期间发送了新消息，请回复用户:\n"
            f"{combined}"
        )
        await self._query_sdk(
            prompt,
            source="flush_buffered_additives",
        )

    async def _flush_buffered_confirms(
        self: "ReactiveSessionActor",
    ) -> None:
        """Combine buffered CONFIRM signals and send with [USER_CONFIRMATION] tags."""
        if not self._buffered_confirms:
            return

        texts = [
            _confirm_signal_to_prompt(s) for s in self._buffered_confirms
        ]
        self._buffered_confirms.clear()

        if not texts:
            return

        combined = "\n---\n".join(texts)
        wrapped = (
            "[USER_CONFIRMATION]\n"
            f"{combined}\n"
            "[/USER_CONFIRMATION]"
        )
        await self._query_sdk(
            wrapped,
            source="flush_buffered_confirms",
        )

    async def _flush_buffered_sidekicks(
        self: "ReactiveSessionActor",
    ) -> None:
        """Combine buffered SIDEKICK signals and send with [SYSTEM_INSIGHT] tags."""
        if not self._buffered_sidekicks:
            return

        texts = [
            self._extract_signal_text(s)
            for s in self._buffered_sidekicks
            if self._extract_signal_text(s)
        ]
        self._buffered_sidekicks.clear()

        if not texts:
            return

        combined = "\n---\n".join(texts)
        wrapped = (
            "[SYSTEM_INSIGHT]\n"
            f"{combined}\n"
            "[/SYSTEM_INSIGHT]"
        )
        await self._query_sdk(
            wrapped,
            source="flush_buffered_sidekicks",
        )
        self._record_sidekick_injection(count=len(texts))

    async def _flush_all_buffered(self: "ReactiveSessionActor") -> None:
        """Combine all buffered signals into a single query.

        Prevents rapid multi-turn queries that would occur if each category
        were flushed independently via separate _query_sdk calls.
        """
        logger.info(
            "AQ flush_buffered_start: session=%s pending_len=%d pending_head_job=%s "
            "confirm_cnt=%d sidekick_cnt=%d additive_cnt=%d",
            self.session_id,
            len(self._pending),
            self._pending_head_job_id(),
            len(self._buffered_confirms),
            len(self._buffered_sidekicks),
            len(self._buffered_additives),
        )
        parts: List[str] = []
        sidekick_count = 0

        # Collect confirm texts
        if self._buffered_confirms:
            confirm_texts = [
                _confirm_signal_to_prompt(s) for s in self._buffered_confirms
            ]
            self._buffered_confirms.clear()
            if confirm_texts:
                confirm_combined = "\n---\n".join(confirm_texts)
                parts.append(
                    f"[USER_CONFIRMATION]\n{confirm_combined}\n[/USER_CONFIRMATION]"
                )

        # Collect sidekick texts
        if self._buffered_sidekicks:
            sidekick_texts = [
                self._extract_signal_text(s)
                for s in self._buffered_sidekicks
                if self._extract_signal_text(s)
            ]
            self._buffered_sidekicks.clear()
            if sidekick_texts:
                sidekick_count = len(sidekick_texts)
                sidekick_combined = "\n---\n".join(sidekick_texts)
                parts.append(
                    f"[SYSTEM_INSIGHT]\n{sidekick_combined}\n[/SYSTEM_INSIGHT]"
                )

        # Collect additive texts — sent as plain user messages so the model
        # responds to them directly instead of treating them as silent context.
        if self._buffered_additives:
            additive_texts = [
                self._extract_signal_text(s)
                for s in self._buffered_additives
                if self._extract_signal_text(s)
            ]
            self._additive_this_turn += len(additive_texts)
            self._buffered_additives.clear()
            if additive_texts:
                combined_additive = "\n---\n".join(additive_texts)
                parts.append(
                    "用户在你回复期间发送了新消息，请回复用户:\n"
                    f"{combined_additive}"
                )

        if not parts:
            logger.info(
                "AQ flush_buffered_skip: session=%s pending_len=%d pending_head_job=%s "
                "reason=no_buffered_parts",
                self.session_id,
                len(self._pending),
                self._pending_head_job_id(),
            )
            return

        combined_prompt = "\n\n".join(parts)
        logger.info(
            "AQ flush_buffered_submit: session=%s pending_len=%d pending_head_job=%s "
            "parts=%d prompt_len=%d",
            self.session_id,
            len(self._pending),
            self._pending_head_job_id(),
            len(parts),
            len(combined_prompt),
        )
        await self._query_sdk(combined_prompt, source="flush_all_buffered")
        if sidekick_count > 0:
            self._record_sidekick_injection(count=sidekick_count)
