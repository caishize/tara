"""
Pub/Sub message types and structures.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional
from datetime import datetime
import uuid
from ..utils.timezone import utc_now


class MessageType(str, Enum):
    """Types of messages that can be published."""
    CONTENT = "content"           # Streaming response content
    PROGRESS = "progress"         # Processing progress updates
    CONFIRM_CARD = "confirm_card" # Action confirmation request
    ASK_USER_QUESTION = "ask_user_question"  # Agent asking user a question
    ERROR = "error"               # Error notification
    COMPLETE = "complete"         # Task completion
    BACKGROUND_JOB = "background_job"  # Background job started
    TOOL_EXECUTION = "tool_execution"  # Tool execution status (start/success/error)
    THINKING = "thinking"              # Agent thinking/reasoning progress
    # Full-duplex intervention events
    GENERATION_STATE = "generation_state"     # Generation state change notification
    PARTIAL_CONTENT = "partial_content"       # Interrupted generation partial content
    BRIDGING = "bridging"                     # Transition marker between generations
    SIDEKICK_INSIGHT = "sidekick_insight"     # Proactive insight push to client
    MEMORY_EXTRACTED = "memory_extracted"     # Memory extraction notification to client


@dataclass(frozen=True)
class PubSubMessage:
    """
    Immutable message structure for Pub/Sub communication.

    Attributes:
        user_id: Target user for the message
        message_type: Type of message (see MessageType)
        payload: Message content
        trace_id: Distributed tracing ID
        timestamp: Message creation time (auto-generated)
        message_id: Unique message ID (auto-generated)
        job_id: Optional job ID for correlating messages to a specific chat job
        seq: Optional sequence number within a job for ordering/resume
    """
    user_id: str
    message_type: MessageType
    payload: Dict[str, Any]
    trace_id: str
    timestamp: str = field(default_factory=lambda: utc_now().isoformat())
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_id: Optional[str] = None
    seq: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for serialization."""
        d: Dict[str, Any] = {
            "user_id": self.user_id,
            "message_type": self.message_type.value if isinstance(self.message_type, MessageType) else self.message_type,
            "payload": self.payload,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "message_id": self.message_id,
        }
        if self.job_id is not None:
            d["job_id"] = self.job_id
        if self.seq is not None:
            d["seq"] = self.seq
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PubSubMessage":
        """Create message from dictionary."""
        message_type = data.get("message_type", "content")
        if isinstance(message_type, str):
            try:
                message_type = MessageType(message_type)
            except ValueError:
                message_type = MessageType.CONTENT

        return cls(
            user_id=data["user_id"],
            message_type=message_type,
            payload=data.get("payload", {}),
            trace_id=data.get("trace_id", ""),
            timestamp=data.get("timestamp", utc_now().isoformat()),
            message_id=data.get("message_id", str(uuid.uuid4())),
            job_id=data.get("job_id"),
            seq=data.get("seq"),
        )
