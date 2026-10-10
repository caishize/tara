"""Conversation module SQLAlchemy models.

Canonical model definitions for the conversation module.

Tables:
    - assistant_chat_sessions: chat session records
    - assistant_chat_messages: individual messages within sessions
    - session_summaries: 1:1 compressed context per session
    - tool_execution_logs: three-layer tool call records
"""

import uuid
from typing import Any, Dict

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

from ...db.session import Base


class AssistantChatSession(Base):
    """Chat session for AI assistant dialogue."""

    __tablename__ = "assistant_chat_sessions"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False)
    family_id = Column(PGUUID(as_uuid=True), nullable=False)
    title = Column(String(200))
    started_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_active_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    context = Column(JSONB)
    status = Column(String(20), default="active")
    archived_at = Column(DateTime(timezone=True))
    message_count = Column(Integer, default=0, server_default="0")
    # Full-duplex: SDK session identity for cross-process recovery
    sdk_session_id = Column(String(200))
    # Full-duplex: cumulative generation count (incl. interrupt + resume)
    generation_count = Column(Integer, default=0, server_default="0")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    messages = relationship(
        "ConversationMessage",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    summary = relationship(
        "SessionSummary",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )
    tool_executions = relationship(
        "ToolExecutionLog",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_assistant_chat_sessions_user", "user_id", "status"),
        Index("ix_assistant_chat_sessions_family", "family_id"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "family_id": str(self.family_id),
            "title": self.title,
            "started_at": (
                self.started_at.isoformat() if self.started_at else None
            ),
            "last_active_at": (
                self.last_active_at.isoformat()
                if self.last_active_at
                else None
            ),
            "context": self.context,
            "status": self.status,
            "archived_at": (
                self.archived_at.isoformat() if self.archived_at else None
            ),
            "message_count": self.message_count or 0,
            "sdk_session_id": self.sdk_session_id,
            "generation_count": self.generation_count or 0,
        }


class ConversationMessage(Base):
    """Individual message within a chat session."""

    __tablename__ = "assistant_chat_messages"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("assistant_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    intent = Column(String(50))
    entities = Column(JSONB)
    message_metadata = Column(JSONB)
    sequence_number = Column(Integer)
    path_type = Column(String(20))  # fast | slow | hybrid | async | intervention
    tool_calls = Column(JSONB)
    is_superseded = Column(
        Boolean, nullable=False, default=False, server_default="false",
    )  # True when message was edited/regenerated and replaced by a newer one
    card_type = Column(String(50))  # UI card type: weather, schedule, trip, etc.
    # Full-duplex: tracks same generation across interrupt + resume
    generation_id = Column(PGUUID(as_uuid=True))
    # Full-duplex: True when message was interrupted before completion
    is_partial = Column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    # Full-duplex: intervention type that triggered this message
    signal_type = Column(String(30))
    # Full-duplex: generation_id this message continues from
    continues_from = Column(PGUUID(as_uuid=True))
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    session = relationship("AssistantChatSession", back_populates="messages")

    __table_args__ = (
        Index(
            "ix_assistant_chat_messages_session", "session_id", "created_at"
        ),
        Index("ix_chat_messages_generation", "generation_id"),
    )

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": str(self.id),
            "session_id": str(self.session_id),
            "role": self.role,
            "content": self.content,
            "intent": self.intent,
            "entities": self.entities,
            "metadata": self.message_metadata,
            "sequence_number": self.sequence_number,
            "path_type": self.path_type,
            "tool_calls": self.tool_calls,
            "is_superseded": self.is_superseded or False,
            "card_type": self.card_type,
            "generation_id": (
                str(self.generation_id) if self.generation_id else None
            ),
            "is_partial": self.is_partial or False,
            "signal_type": self.signal_type,
            "continues_from": (
                str(self.continues_from) if self.continues_from else None
            ),
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
        }
        meta = self.message_metadata or {}
        if meta.get("async_source"):
            result["async_source"] = meta["async_source"]
        return result


class SessionSummary(Base):
    """Rolling compressed context summary for a session (1:1)."""

    __tablename__ = "session_summaries"

    session_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("assistant_chat_sessions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id = Column(PGUUID(as_uuid=True), nullable=False)
    family_id = Column(PGUUID(as_uuid=True), nullable=False)
    content = Column(Text, nullable=False)
    compressed_up_to = Column(Integer, nullable=False, default=0)
    token_count = Column(Integer)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
    )

    session = relationship(
        "AssistantChatSession", back_populates="summary", uselist=False
    )

    __table_args__ = (Index("ix_session_summaries_user", "user_id"),)

    def to_dict(self) -> dict:
        return {
            "session_id": str(self.session_id),
            "user_id": str(self.user_id),
            "family_id": str(self.family_id),
            "content": self.content,
            "compressed_up_to": self.compressed_up_to,
            "token_count": self.token_count,
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
            "updated_at": (
                self.updated_at.isoformat() if self.updated_at else None
            ),
        }


class ToolExecutionLog(Base):
    """Tool execution log with three-layer result storage.

    Layer 1: summary (one-line text, embedded in message.tool_calls)
    Layer 2: key_results (structured JSONB for quick inspection)
    Layer 3: full_result (complete tool response, for view_tool_details)
    """

    __tablename__ = "tool_execution_logs"

    id = Column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("assistant_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(PGUUID(as_uuid=True), nullable=False)
    family_id = Column(PGUUID(as_uuid=True), nullable=False)
    message_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("assistant_chat_messages.id", ondelete="SET NULL"),
    )
    path_type = Column(String(20), nullable=False, default="slow")
    tool_name = Column(String(100), nullable=False)
    arguments = Column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    status = Column(String(20), nullable=False, default="running")
    error_message = Column(Text)
    summary = Column(Text)
    key_results = Column(JSONB)
    full_result = Column(JSONB)
    execution_time_ms = Column(Integer)
    iteration = Column(Integer, nullable=False, default=1)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=func.now()
    )

    session = relationship(
        "AssistantChatSession", back_populates="tool_executions"
    )
    message = relationship("ConversationMessage")

    __table_args__ = (
        Index("ix_tool_exec_session", "session_id", "created_at"),
        Index("ix_tool_exec_user", "user_id", "created_at"),
        Index(
            "ix_tool_exec_user_tool", "user_id", "tool_name", "created_at"
        ),
    )

    _VALID_STATUSES = frozenset({"running", "success", "error"})
    _VALID_PATH_TYPES = frozenset({"fast", "slow", "hybrid", "intervention"})

    @validates("status")
    def validate_status(self, _key: str, value: str) -> str:
        if value not in self._VALID_STATUSES:
            raise ValueError(
                f"Invalid status: {value}. "
                f"Must be one of {self._VALID_STATUSES}"
            )
        return value

    @validates("path_type")
    def validate_path_type(self, _key: str, value: str) -> str:
        if value not in self._VALID_PATH_TYPES:
            raise ValueError(
                f"Invalid path_type: {value}. "
                f"Must be one of {self._VALID_PATH_TYPES}"
            )
        return value

    @property
    def short_id(self) -> str:
        return str(self.id).split("-")[0]

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "short_id": self.short_id,
            "session_id": str(self.session_id),
            "user_id": str(self.user_id),
            "family_id": str(self.family_id),
            "message_id": (
                str(self.message_id) if self.message_id else None
            ),
            "path_type": self.path_type,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "status": self.status,
            "error_message": self.error_message,
            "summary": self.summary,
            "key_results": self.key_results,
            "full_result": self.full_result,
            "execution_time_ms": self.execution_time_ms,
            "iteration": self.iteration,
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
        }

    def to_layer1(self) -> dict:
        """Layer 1: for message tool_calls JSONB and LLM context."""
        return {
            "execution_id": str(self.id),
            "short_id": self.short_id,
            "tool_name": self.tool_name,
            "summary": self.summary,
            "status": self.status,
        }

    def to_context_line(self) -> str:
        """Format for agent context display."""
        status_icon = {
            "running": "⏳",
            "success": "✅",
            "error": "❌",
        }.get(self.status, "❓")
        summary_text = f' "{self.summary}"' if self.summary else ""
        return (
            f"[#{self.short_id}] {self.tool_name} "
            f"{status_icon}{summary_text}"
        )


class InterventionAuditLog(Base):
    """Audit trail for intervention signals processed during active generation.

    Records every classification + action taken for debugging and improvement.
    """

    __tablename__ = "intervention_audit_log"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("assistant_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    signal_id = Column(PGUUID(as_uuid=True), nullable=False)
    signal_type = Column(String(30), nullable=False)
    job_id = Column(String(100), nullable=False)
    user_id = Column(PGUUID(as_uuid=True), nullable=False)
    generation_state = Column(String(20), nullable=False)
    action_taken = Column(String(30), nullable=False)
    payload = Column(JSONB)
    classification_confidence = Column(Float)
    latency_ms = Column(Integer)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_intervention_audit_session", "session_id", "created_at"
        ),
        Index("ix_intervention_audit_type", "signal_type"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "session_id": str(self.session_id),
            "signal_id": str(self.signal_id),
            "signal_type": self.signal_type,
            "job_id": self.job_id,
            "user_id": str(self.user_id),
            "generation_state": self.generation_state,
            "action_taken": self.action_taken,
            "payload": self.payload,
            "classification_confidence": self.classification_confidence,
            "latency_ms": self.latency_ms,
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
        }


__all__ = [
    "AssistantChatSession",
    "ConversationMessage",
    "InterventionAuditLog",
    "SessionSummary",
    "ToolExecutionLog",
]
