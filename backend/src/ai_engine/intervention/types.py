"""
Core data types for the intervention system.

Defines the state machine, signal protocol, stitching context,
and budget constraints for full-duplex conversation handling.
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from ...core.utils.timezone import utc_now


class GenerationState(str, Enum):
    """State machine for SDK generation lifecycle."""
    IDLE = "IDLE"
    GENERATING = "GENERATING"
    TOOL_EXECUTING = "TOOL_EXECUTING"
    WAITING_USER = "WAITING_USER"


class InterventionType(str, Enum):
    """Types of user intervention during active generation."""
    CORRECTION = "correction"
    ADDITIVE = "additive"
    CANCEL = "cancel"
    CONFIRM = "confirm"
    DIGRESSION = "digression"
    SIDEKICK_INSIGHT = "sidekick_insight"


# Priority mapping: lower = higher priority
INTERVENTION_PRIORITIES: Dict[str, int] = {
    InterventionType.CANCEL.value: 1,
    InterventionType.CORRECTION.value: 1,
    InterventionType.ADDITIVE.value: 2,
    InterventionType.CONFIRM.value: 2,
    InterventionType.DIGRESSION.value: 3,
    InterventionType.SIDEKICK_INSIGHT.value: 3,
}

# Tools that perform non-reversible external operations.
# During execution of these tools, CORRECTION/CANCEL signals
# must be deferred until the tool completes.
NON_INTERRUPTIBLE_TOOLS: frozenset = frozenset({
    "create_trip",
    "book_ticket",
    "send_message",
    "checkout",
    "create_task",
    "confirm_action",
})

# -- Stitching context token limits --
_STITCH_PARTIAL_TEXT_MAX_CHARS = 200
_STITCH_PARTIAL_THINKING_MAX_CHARS = 100


@dataclass(frozen=True)
class InterventionSignal:
    """Immutable signal published via Redis PubSub for intervention dispatch.

    Attributes:
        signal_id: Unique identifier (UUID v4).
        type: Intervention type (see InterventionType).
        session_id: Target chat session.
        job_id: Current generation job (for stale-signal rejection).
        user_id: Originating user.
        timestamp: ISO 8601 UTC timestamp.
        payload: Type-specific data (see optimization doc section 4.2).
        priority: 1=immediate, 2=next gap, 3=best effort.
    """
    signal_id: str
    type: str
    session_id: str
    job_id: str
    user_id: str
    timestamp: str
    payload: Dict[str, Any]
    priority: int = 2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "type": self.type,
            "session_id": self.session_id,
            "job_id": self.job_id,
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "priority": self.priority,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InterventionSignal":
        return cls(
            signal_id=data.get("signal_id", str(uuid.uuid4())),
            type=data["type"],
            session_id=data["session_id"],
            job_id=data["job_id"],
            user_id=data["user_id"],
            timestamp=data.get("timestamp", utc_now().isoformat()),
            payload=data.get("payload", {}),
            priority=data.get("priority", INTERVENTION_PRIORITIES.get(data["type"], 2)),
        )

    @classmethod
    def from_json(cls, raw: str) -> "InterventionSignal":
        return cls.from_dict(json.loads(raw))

    @classmethod
    def create(
        cls,
        signal_type: str,
        session_id: str,
        job_id: str,
        user_id: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> "InterventionSignal":
        """Factory with auto-generated signal_id and timestamp."""
        return cls(
            signal_id=str(uuid.uuid4()),
            type=signal_type,
            session_id=session_id,
            job_id=job_id,
            user_id=user_id,
            timestamp=utc_now().isoformat(),
            payload=payload or {},
            priority=INTERVENTION_PRIORITIES.get(signal_type, 2),
        )


@dataclass(frozen=True)
class StitchingContext:
    """Breakpoint snapshot saved when generation is interrupted.

    Stored in Redis at ``session:stitch:{session_id}`` with TTL 300s.
    Consumed by the next turn to build a seamless correction prompt.

    Token budget: hard-capped at ~500 tokens.
      - partial_text: last 200 chars
      - partial_thinking: last 100 chars
    """
    partial_text: str
    partial_thinking: str
    interrupted_at: datetime
    reason: str  # correction | digression | cancel
    original_input: str
    completed_tools: List[str] = field(default_factory=list)
    partial_tool: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        # Truncate at construction time for bounded memory
        if self.partial_text and len(self.partial_text) > _STITCH_PARTIAL_TEXT_MAX_CHARS:
            object.__setattr__(
                self, "partial_text",
                self.partial_text[-_STITCH_PARTIAL_TEXT_MAX_CHARS:],
            )
        if self.partial_thinking and len(self.partial_thinking) > _STITCH_PARTIAL_THINKING_MAX_CHARS:
            object.__setattr__(
                self, "partial_thinking",
                self.partial_thinking[-_STITCH_PARTIAL_THINKING_MAX_CHARS:],
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "partial_text": self.partial_text[-_STITCH_PARTIAL_TEXT_MAX_CHARS:],
            "partial_thinking": self.partial_thinking[-_STITCH_PARTIAL_THINKING_MAX_CHARS:],
            "interrupted_at": self.interrupted_at.isoformat(),
            "reason": self.reason,
            "original_input": self.original_input,
            "completed_tools": list(self.completed_tools),
            "partial_tool": self.partial_tool,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StitchingContext":
        interrupted_at_raw = data["interrupted_at"]
        if isinstance(interrupted_at_raw, str):
            interrupted_at_raw = datetime.fromisoformat(
                interrupted_at_raw.replace("Z", "+00:00")
            )
        return cls(
            partial_text=data.get("partial_text", ""),
            partial_thinking=data.get("partial_thinking", ""),
            interrupted_at=interrupted_at_raw,
            reason=data.get("reason", ""),
            original_input=data.get("original_input", ""),
            completed_tools=data.get("completed_tools", []),
            partial_tool=data.get("partial_tool"),
        )

    @classmethod
    def from_json(cls, raw: str) -> "StitchingContext":
        return cls.from_dict(json.loads(raw))


@dataclass(frozen=True)
class InterventionBudget:
    """Per-session limits on intervention operations.

    When any limit is exceeded the actor triggers a session reset:
    compress history → close SDK client → new session with summary context.
    """
    max_interventions_per_session: int = 5
    max_additive_per_turn: int = 2
    max_correction_per_session: int = 3
    context_compression_threshold: int = 3


@dataclass(frozen=True)
class SessionStatus:
    """Cross-process visibility of a session's generation state.

    Stored in Redis at ``session:status:{session_id}`` with TTL 600s,
    refreshed by the actor's heartbeat loop every 10 seconds.
    """
    state: str
    job_id: str
    worker_id: str
    sdk_session_id: str
    last_heartbeat: str
    task_summary: str
    active_tool: Optional[str] = None
    user_id: str = ""
    # C3: Partial text for F1 intervention classifier context
    partial_text: str = ""
    # C4: Structured fields for F2 entity matching in SidekickWorker
    mentioned_person_ids: tuple = ()
    mentioned_locations: tuple = ()
    action_category: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "job_id": self.job_id,
            "worker_id": self.worker_id,
            "sdk_session_id": self.sdk_session_id,
            "last_heartbeat": self.last_heartbeat,
            "task_summary": self.task_summary,
            "active_tool": self.active_tool,
            "user_id": self.user_id,
            "partial_text": self.partial_text,
            "mentioned_person_ids": list(self.mentioned_person_ids),
            "mentioned_locations": list(self.mentioned_locations),
            "action_category": self.action_category,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionStatus":
        return cls(
            state=data["state"],
            job_id=data["job_id"],
            worker_id=data.get("worker_id", ""),
            sdk_session_id=data.get("sdk_session_id", ""),
            last_heartbeat=data.get("last_heartbeat", ""),
            task_summary=data.get("task_summary", ""),
            active_tool=data.get("active_tool"),
            user_id=data.get("user_id", ""),
            partial_text=data.get("partial_text", ""),
            mentioned_person_ids=tuple(data.get("mentioned_person_ids") or ()),
            mentioned_locations=tuple(data.get("mentioned_locations") or ()),
            action_category=data.get("action_category", ""),
        )

    @classmethod
    def from_json(cls, raw: str) -> Optional["SessionStatus"]:
        if not raw:
            return None
        return cls.from_dict(json.loads(raw))

    def is_active(self) -> bool:
        """True when the session has an active (non-IDLE) generation."""
        return self.state in (
            GenerationState.GENERATING.value,
            GenerationState.TOOL_EXECUTING.value,
            GenerationState.WAITING_USER.value,
        )


@dataclass(frozen=True)
class ClassificationResult:
    """Output of InterventionClassifier.classify()."""
    type: str
    confidence: float
    latency_ms: int = 0

    @property
    def effective_type(self) -> str:
        """Apply confidence degradation with type-aware fallback.

        Low-confidence classifications use safe defaults per type:
        - DIGRESSION stays DIGRESSION: queueing as a new request is always
          safe and preserves the user's original intent.
        - CORRECTION at low confidence → DIGRESSION: avoid losing the user's
          message as supplementary info; queue it as a new request instead.
        - CANCEL at low confidence → ADDITIVE: false-positive cancel is
          dangerous, so degrade to the non-disruptive default.
        - ADDITIVE / CONFIRM stay as-is: already non-disruptive.
        """
        if self.confidence >= 0.60:
            return self.type
        if self.type == InterventionType.DIGRESSION.value:
            return InterventionType.DIGRESSION.value
        if self.type == InterventionType.CORRECTION.value:
            return InterventionType.DIGRESSION.value
        return InterventionType.ADDITIVE.value

    @property
    def requires_audit(self) -> bool:
        """True when confidence is in the audit band (0.60 – 0.85)."""
        return 0.60 <= self.confidence < 0.85


# -- Redis key helpers --

def session_status_key(session_id: str) -> str:
    return f"session:status:{session_id}"


def session_signal_channel(session_id: str) -> str:
    return f"session:signal:{session_id}"


def session_stitch_key(session_id: str) -> str:
    return f"session:stitch:{session_id}"


STITCH_TTL_SECONDS: int = 300
