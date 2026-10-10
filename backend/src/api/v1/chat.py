"""Chat API routes - /api/v1/chat/*

WebSocket-first chat API.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, Literal, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, field_validator
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.settings import settings
from ...core.auth import require_auth
from ...db.session import get_db
from ...modules.conversation.models import AssistantChatSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])

MAX_MESSAGE_LENGTH = 10000
MAX_SESSION_ID_LENGTH = 100

# Allowed characters for session_id (alphanumeric, underscore, hyphen).
_SESSION_ID_ALLOWED_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "_-"
)


def _is_valid_session_id_chars(value: str) -> bool:
    """Check if value contains only allowed session_id characters."""
    return bool(value) and all(c in _SESSION_ID_ALLOWED_CHARS for c in value)


# ==================== Request/Response Models ====================


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)
    session_id: Optional[str] = Field(None, max_length=MAX_SESSION_ID_LENGTH)
    force_slow_path: bool = False
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    location_name: Optional[str] = Field(None, max_length=100)

    @field_validator('message')
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        return ' '.join(v.split())

    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not _is_valid_session_id_chars(v):
                raise ValueError('session_id must contain only alphanumeric characters, underscores, and hyphens')
            try:
                UUID(v)
            except (ValueError, AttributeError):
                raise ValueError('session_id must be a valid UUID')
        return v


class RegenerateRequest(BaseModel):
    message_id: str

    @field_validator('message_id')
    @classmethod
    def validate_message_id(cls, v: str) -> str:
        try:
            UUID(v)
        except (ValueError, AttributeError):
            raise ValueError('message_id must be a valid UUID')
        return v


class EditMessageRequest(BaseModel):
    message_id: str
    new_content: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)
    session_id: Optional[str] = Field(None, max_length=MAX_SESSION_ID_LENGTH)
    force_slow_path: bool = False
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    location_name: Optional[str] = Field(None, max_length=100)

    @field_validator("message_id")
    @classmethod
    def validate_message_id(cls, v: str) -> str:
        try:
            UUID(v)
        except (ValueError, AttributeError):
            raise ValueError("message_id must be a valid UUID")
        return v

    @field_validator("new_content")
    @classmethod
    def sanitize_new_content(cls, v: str) -> str:
        cleaned = " ".join(v.split())
        if not cleaned:
            raise ValueError("new_content must not be empty after trimming whitespace")
        return cleaned

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not _is_valid_session_id_chars(v):
                raise ValueError(
                    "session_id must contain only alphanumeric characters, underscores, and hyphens"
                )
            try:
                UUID(v)
            except (ValueError, AttributeError):
                raise ValueError("session_id must be a valid UUID")
        return v


class FeedbackRequest(BaseModel):
    message_id: str
    feedback: Literal["positive", "negative"]
    reason: Optional[str] = Field(None, max_length=500)

    @field_validator('message_id')
    @classmethod
    def validate_message_id(cls, v: str) -> str:
        try:
            UUID(v)
        except (ValueError, AttributeError):
            raise ValueError('message_id must be a valid UUID')
        return v


class CancelRequest(BaseModel):
    session_id: str = Field(..., max_length=MAX_SESSION_ID_LENGTH)

    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        if not _is_valid_session_id_chars(v):
            raise ValueError('session_id must contain only alphanumeric characters, underscores, and hyphens')
        try:
            UUID(v)
        except (ValueError, AttributeError):
            raise ValueError('session_id must be a valid UUID')
        return v


# ==================== Helpers ====================


def _check_agent_enabled() -> None:
    if not settings.claude_agent_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Claude Agent is not enabled. Set CLAUDE_AGENT_ENABLED=true",
        )
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Anthropic API key not configured",
        )


def _validate_uuid(value: str, field_name: str) -> UUID:
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} format: must be a valid UUID",
        )


async def _classify_intent(request: ChatRequest, user_id, db):
    """Classify intent using the existing dual-brain router."""
    from ...ai_engine.router import get_intent_router, RouteType
    from ...ai_engine.router.types import (
        IntentClassification, IntentCategory, Difficulty, ActionType,
    )

    t0 = time.monotonic()

    if request.force_slow_path:
        return IntentClassification(
            route_type=RouteType.SLOW,
            intent_category=IntentCategory.UNKNOWN,
            confidence=1.0,
            difficulty=Difficulty.THINKING,
            action=ActionType.CHAT,
            reasoning="Forced slow path",
        )

    # Warm-client precedence:
    # If a pooled SDK client already exists for this session, skip intent
    # classification and route directly to slow path for context continuity.
    if request.session_id:
        from ...ai_engine.sdk.sdk_client_pool import has_active_client
        warm = await has_active_client(request.session_id)
        t_warm = time.monotonic()
        logger.info(
            "_classify_intent: warm_check=%s (%.0fms) session=%s",
            warm, (t_warm - t0) * 1000, request.session_id[:8] if request.session_id else "none",
        )
        if warm:
            return IntentClassification(
                route_type=RouteType.SLOW,
                intent_category=IntentCategory.UNKNOWN,
                confidence=1.0,
                difficulty=Difficulty.THINKING,
                action=ActionType.CHAT,
                reasoning="Warm SDK client detected, routed directly to slow path",
            )

    t_before_classify = time.monotonic()
    intent_router = get_intent_router()
    intent = await intent_router.classify(
        user_input=request.message,
        user_id=str(user_id),
        session_id=request.session_id,
        db=db,
    )
    t_after = time.monotonic()
    logger.info(
        "_classify_intent DONE: total=%.0fms, classify=%.0fms, route=%s, msg=%.30s",
        (t_after - t0) * 1000,
        (t_after - t_before_classify) * 1000,
        intent.route_type,
        request.message,
    )

    return intent


async def _ensure_session(
    db: AsyncSession,
    user_id: UUID,
    family_id: UUID,
    session_id: Optional[str],
) -> UUID:
    """Get or create a session, returning its UUID."""
    from ...modules.conversation import SessionService

    svc = SessionService(db)
    sid = UUID(session_id) if session_id else None
    session, _ = await svc.get_or_create_session(
        user_id=user_id,
        family_id=family_id,
        session_id=sid,
    )
    return session.id


def _validate_optional_session_id(session_id: Optional[str]) -> Optional[str]:
    if session_id is None:
        return None

    sid = session_id.strip()
    if not sid:
        return None

    if not _is_valid_session_id_chars(sid):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id must contain only alphanumeric characters, underscores, and hyphens",
        )

    try:
        UUID(sid)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id must be a valid UUID",
        )
    return sid


async def _on_background_task_error(
    task: "asyncio.Task[Any]",
    job_id: str,
    user_id: str,
    session_id: str,
) -> None:
    """Write a Redis error marker when a Fast/Hybrid background task fails.

    Best-effort: any failure here is silently logged, never propagated.
    The poll endpoint can then surface the error to the client.
    """
    exc = task.exception()
    if exc is None:
        return
    logger.error("Background task %s failed: %s", job_id, exc, exc_info=exc)
    try:
        from ...core.cache import redis_client

        await redis_client.set(
            f"job_status:{job_id}",
            json.dumps({
                "status": "error",
                "message": "处理失败，请重试",
                "session_id": session_id,
            }),
            ttl=300,
        )
    except Exception:
        logger.debug("Failed to write error marker for job %s", job_id, exc_info=True)


def _make_done_callback(
    job_id: str, user_id: str, session_id: str,
) -> "Callable[[asyncio.Task[Any]], None]":
    """Return a synchronous done-callback that schedules the async error handler."""
    def _cb(task: "asyncio.Task[Any]") -> None:
        if task.cancelled() or task.exception() is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(
            _on_background_task_error(task, job_id, user_id, session_id)
        )
    return _cb


async def _get_session_status(session_id: Optional[str]):
    """Check if a session has an active generation via Redis."""
    if not session_id:
        return None
    from ...ai_engine.intervention.types import SessionStatus, session_status_key
    from ...core.cache import redis_client

    try:
        raw = await redis_client.get(session_status_key(session_id))
        if not raw:
            return None
        status = SessionStatus.from_json(raw)
        if status and status.last_heartbeat:
            try:
                hb_time = datetime.fromisoformat(status.last_heartbeat)
                from ...core.utils.timezone import utc_now
                age = (utc_now() - hb_time).total_seconds()
                # Heartbeat staleness: 30s = 3x heartbeat interval (10s).
                # Independent of the session:status key TTL (600s) which prevents
                # Redis memory leaks. The staleness check detects crashed workers
                # that stopped sending heartbeats.
                if age > 30:
                    return None
            except (ValueError, TypeError):
                pass
        return status
    except Exception as e:
        logger.debug("Failed to read session status for %s: %s", session_id, e)
        return None


async def _get_intervention_count(db: AsyncSession, session_id: UUID) -> int:
    """Count intervention signals for a session from audit log."""
    try:
        from ...modules.conversation.models import InterventionAuditLog
        result = await db.execute(
            select(sa.func.count(InterventionAuditLog.id)).where(
                InterventionAuditLog.session_id == session_id
            )
        )
        return result.scalar() or 0
    except Exception:
        return 0


async def _get_last_user_message(db: AsyncSession, session_id: UUID) -> str:
    """Get the most recent user message content from a session."""
    from ...modules.conversation.models import ConversationMessage

    result = await db.execute(
        select(ConversationMessage.content)
        .where(
            ConversationMessage.session_id == session_id,
            ConversationMessage.role == "user",
            ConversationMessage.is_superseded.is_(False),
        )
        .order_by(ConversationMessage.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row or ""


async def _build_signal_payload(
    signal_type: str,
    message: str,
    last_msg: str,
    db: Optional[AsyncSession] = None,
    user_id: Optional[UUID] = None,
) -> Dict[str, Any]:
    """Build type-specific payload for an intervention signal."""
    from ...ai_engine.intervention.types import InterventionType

    if signal_type == InterventionType.CORRECTION.value:
        return {
            "text": message,
            "corrected_input": message,
            "original_input": last_msg,
            "intent_class": InterventionType.CORRECTION.value,
        }
    if signal_type == InterventionType.ADDITIVE.value:
        return {
            "text": message,
            "additional_input": message,
            "intent_class": InterventionType.ADDITIVE.value,
        }
    if signal_type == InterventionType.CANCEL.value:
        return {"reason": "user_initiated"}
    if signal_type == InterventionType.CONFIRM.value:
        # Infer approval/rejection from message keywords.
        #
        # Keyword matching order matters for Chinese: compound words checked before
        # single characters to avoid false matches (e.g. "不错" = positive, not "不").
        # Approve overrides are checked first to handle negation-of-negation patterns.
        _APPROVE_OVERRIDES = ("不错", "好的", "是的", "行的", "可以的")
        _REJECT_PHRASES = ("不要", "不行", "不用", "取消", "拒绝", "算了", "cancel", "no", "reject")
        _APPROVE_PHRASES = ("好", "是", "确认", "ok", "yes", "approve", "确定", "同意", "可以", "行")
        msg_lower = message.lower().strip()
        if any(w in msg_lower for w in _APPROVE_OVERRIDES):
            confirmation = "approve"
        elif any(w in msg_lower for w in _REJECT_PHRASES):
            confirmation = "reject"
        elif any(w in msg_lower for w in _APPROVE_PHRASES):
            confirmation = "approve"
        else:
            # W4 fix: Default to approve but flag as ambiguous so downstream
            # handlers can request explicit re-confirmation for destructive ops.
            confirmation = "approve"
            logger.info(
                "CONFIRM keyword match ambiguous, defaulting to approve: message=%.60s",
                message,
            )
        is_ambiguous = confirmation == "approve" and not any(
            w in msg_lower for w in (*_APPROVE_OVERRIDES, *_APPROVE_PHRASES)
        )
        # Resolve the most recent pending action for this user
        pending_action_id = ""
        if db is not None and user_id is not None:
            try:
                from ...modules.conversation.pending_action import (
                    ActionStatus,
                    PendingAction,
                )

                pa_result = await db.execute(
                    select(PendingAction.id)
                    .where(
                        PendingAction.user_id == user_id,
                        PendingAction.status == ActionStatus.PENDING.value,
                    )
                    .order_by(PendingAction.created_at.desc())
                    .limit(1)
                )
                pa_id = pa_result.scalar_one_or_none()
                if pa_id is not None:
                    pending_action_id = str(pa_id)
            except Exception:
                logger.debug(
                    "Failed to resolve pending_action_id for CONFIRM signal",
                    exc_info=True,
                )

        payload = {
            "text": message,
            "pending_action_id": pending_action_id,
            "confirmation": confirmation,
            "intent_class": InterventionType.CONFIRM.value,
        }
        if is_ambiguous:
            payload["is_ambiguous"] = True
        return payload
    if signal_type == InterventionType.DIGRESSION.value:
        return {
            "text": message,
            "new_input": message,
            "intent_class": InterventionType.DIGRESSION.value,
        }
    return {"text": message, "input": message}


async def _try_intervention_routing(
    request: ChatRequest,
    db: AsyncSession,
    user_id: UUID,
    session_id: UUID,
) -> Optional[SignalAcceptedResponse]:
    """Attempt to route as an intervention signal if there's an active generation.

    Returns SignalAcceptedResponse if routed as intervention, None otherwise.
    Falls back to normal routing on any error.
    """
    session_status = await _get_session_status(str(session_id))
    if session_status is None or not session_status.is_active():
        return None

    t0 = time.monotonic()

    try:
        from ...ai_engine.intervention.classifier import get_intervention_classifier
        from ...ai_engine.intervention.types import (
            ClassificationResult,
            InterventionSignal,
            InterventionType,
            INTERVENTION_PRIORITIES,
            session_signal_channel,
        )
        from ...core.cache import redis_client
        from ...modules.conversation import MessageService

        classifier = get_intervention_classifier()
        last_msg = await _get_last_user_message(db, session_id)

        # PLAN-003: CANCEL keyword fast-path — exact-match bypasses LLM classifier
        _cancel_keywords = {"取消", "停", "算了", "别说了", "stop", "cancel"}
        stripped = request.message.strip().lower()
        if stripped in _cancel_keywords:
            result = ClassificationResult(
                type=InterventionType.CANCEL.value,
                confidence=1.0,
            )
            logger.info(
                "cancel_keyword_fast_path: session=%s keyword=%r",
                session_id, stripped,
            )
        else:
            result = await classifier.classify(
                current_task_summary=session_status.task_summary,
                last_user_message=last_msg,
                new_user_message=request.message,
                active_tool=session_status.active_tool,
                generation_state=session_status.state,
                partial_text_summary=session_status.partial_text,
            )
        effective_type = result.effective_type

        signal = InterventionSignal.create(
            signal_type=effective_type,
            session_id=str(session_id),
            job_id=session_status.job_id,
            user_id=str(user_id),
            payload=await _build_signal_payload(
                effective_type, request.message, last_msg,
                db=db, user_id=user_id,
            ),
        )

        # Save user message FIRST and commit to release the FOR UPDATE row
        # lock before publishing the Redis signal.  The actor may resume the
        # worker almost instantly after receiving the signal, and the worker's
        # _save_conversation_unified also acquires FOR UPDATE on the same
        # assistant_chat_sessions row — publishing before commit causes a
        # ~1–2 s lock wait.
        msg_svc = MessageService(db)
        await msg_svc.save_user_message(
            session_id=session_id,
            content=request.message,
            path_type="intervention",
            intent=effective_type,
            metadata={
                "signal_id": signal.signal_id,
                "signal_type": effective_type,
                "classification_confidence": result.confidence,
                "job_id": session_status.job_id,
            },
        )
        await db.commit()

        # Publish signal to the session's signal channel (after commit)
        channel = session_signal_channel(str(session_id))
        if redis_client.client:
            await redis_client.client.publish(channel, signal.to_json())
            logger.info(
                "AQ intervention_published: session=%s signal_id=%s type=%s "
                "target_job_id=%s user_id=%s channel=%s",
                str(session_id),
                signal.signal_id,
                effective_type,
                session_status.job_id,
                str(user_id),
                channel,
            )
        else:
            logger.warning(
                "AQ intervention_publish_skipped: session=%s signal_id=%s type=%s "
                "target_job_id=%s user_id=%s reason=redis_client_none",
                str(session_id),
                signal.signal_id,
                effective_type,
                session_status.job_id,
                str(user_id),
            )

        t_done = time.monotonic()

        # Write intervention audit log for observability
        try:
            from ...modules.conversation.models import InterventionAuditLog
            import uuid as _uuid

            audit_entry = InterventionAuditLog(
                session_id=session_id,
                signal_id=_uuid.UUID(signal.signal_id),
                signal_type=effective_type,
                job_id=session_status.job_id,
                user_id=user_id,
                generation_state=session_status.state,
                action_taken="published",
                payload=signal.payload,
                classification_confidence=result.confidence,
                latency_ms=int((t_done - t0) * 1000),
            )
            db.add(audit_entry)
            await db.commit()
        except Exception as audit_err:
            logger.debug("Failed to write intervention audit log: %s", audit_err)

        logger.info(
            "Intervention routed: type=%s, confidence=%.2f, effective=%s, "
            "latency_ms=%.0f, session=%s",
            result.type,
            result.confidence,
            effective_type,
            (t_done - t0) * 1000,
            str(session_id)[:8],
        )

        return SignalAcceptedResponse(
            signal_id=signal.signal_id,
            signal_type=effective_type,
            classification_confidence=result.confidence,
        )

    except Exception as e:
        logger.warning(
            "Intervention routing failed, falling back to normal routing: %s",
            e,
            exc_info=True,
        )
        await db.rollback()
        return None


async def _dispatch_ws_chat_job(
    request: ChatRequest,
    db: AsyncSession,
    user_id: UUID,
    family_id: UUID,
) -> "ChatJobResponse":
    """Classify route and dispatch a chat job for WebSocket delivery."""
    from ...ai_engine.queue.task_queue import TaskPayload, get_task_queue
    from ...ai_engine.router import RouteType
    from ...modules.conversation import MessageService
    from .ws_publishers import publish_fast_path, publish_hybrid_path

    t_dispatch_start = time.monotonic()

    intent = await _classify_intent(request, user_id, db)
    t_classified = time.monotonic()
    logger.info(
        "Chat dispatch stage: stage=classified route=%s classify_ms=%.0f session=%s",
        intent.route_type,
        (t_classified - t_dispatch_start) * 1000,
        request.session_id[:8] if request.session_id else "new",
    )

    session_id = await _ensure_session(
        db=db,
        user_id=user_id,
        family_id=family_id,
        session_id=request.session_id,
    )
    t_session = time.monotonic()
    str_session_id = str(session_id)
    job_id = str(uuid4())
    logger.info(
        "Chat dispatch stage: stage=session_ready job_id=%s session=%s session_ms=%.0f",
        job_id,
        str_session_id,
        (t_session - t_classified) * 1000,
    )

    context: Optional[Dict[str, Any]] = None
    if getattr(request, "latitude", None) is not None:
        context = {
            "latitude": request.latitude,
            "longitude": request.longitude,
            "location_name": getattr(request, "location_name", None),
        }

    done_cb = _make_done_callback(job_id, str(user_id), str_session_id)

    if intent.route_type == RouteType.FAST:
        bg = asyncio.create_task(
            publish_fast_path(
                intent=intent,
                message=request.message,
                user_id=str(user_id),
                family_id=str(family_id),
                job_id=job_id,
                session_id=str_session_id,
                context=context,
            )
        )
        bg.add_done_callback(done_cb)
        route = "fast"
    elif intent.route_type == RouteType.SLOW:
        msg_svc = MessageService(db)
        logger.info(
            "Chat dispatch stage: stage=save_user_message_start job_id=%s session=%s",
            job_id,
            str_session_id,
        )
        await msg_svc.save_user_message(
            session_id=session_id,
            content=request.message,
            path_type="slow",
            intent=(
                intent.intent_category.value
                if intent.intent_category
                else None
            ),
            metadata={"job_id": job_id, "route_type": "slow"},
        )
        logger.info(
            "Chat dispatch stage: stage=save_user_message_done job_id=%s session=%s",
            job_id,
            str_session_id,
        )
        logger.info(
            "Chat dispatch stage: stage=db_commit_start job_id=%s session=%s",
            job_id,
            str_session_id,
        )
        await db.commit()
        logger.info(
            "Chat dispatch stage: stage=db_commit_done job_id=%s session=%s",
            job_id,
            str_session_id,
        )

        context_snapshot: Dict[str, Any] = {}
        if context:
            context_snapshot.update(context)
        if intent.skill_hint:
            # Keep both keys for backward compatibility across workers.
            context_snapshot["skill_hint"] = intent.skill_hint
            context_snapshot["skill"] = intent.skill_hint
        context_snapshot["user_message_saved"] = True

        task = TaskPayload(
            job_id=job_id,
            user_id=str(user_id),
            family_id=str(family_id),
            user_input=request.message,
            route_type="slow",
            session_id=str_session_id,
            context_snapshot=context_snapshot,
            metadata={"user_message_saved": True},
        )

        queue = get_task_queue()
        logger.info(
            "Chat dispatch stage: stage=enqueue_start job_id=%s session=%s",
            job_id,
            str_session_id,
        )
        try:
            await queue.enqueue(task)
        except Exception as e:
            logger.error("Failed to enqueue slow task: %s", e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="任务排队失败，请稍后重试",
            )
        t_enqueued = time.monotonic()
        logger.info(
            "Chat dispatch timing: classify_ms=%.0f, session_ms=%.0f, "
            "enqueue_total_ms=%.0f, total_ms=%.0f, "
            "route=%s, job_id=%s, session_id=%s, "
            "warm_client_skip=%s",
            (t_classified - t_dispatch_start) * 1000,
            (t_session - t_classified) * 1000,
            (t_enqueued - t_session) * 1000,
            (t_enqueued - t_dispatch_start) * 1000,
            "slow",
            job_id,
            str_session_id,
            intent.reasoning or "",
        )
        route = "slow"
    else:
        bg = asyncio.create_task(
            publish_hybrid_path(
                intent=intent,
                message=request.message,
                user_id=str(user_id),
                family_id=str(family_id),
                job_id=job_id,
                session_id=str_session_id,
                context=context,
            )
        )
        bg.add_done_callback(done_cb)
        route = "hybrid"

    return ChatJobResponse(
        job_id=job_id,
        session_id=str_session_id,
        route_type=route,
    )


# Cached ASR client keyed by (provider, base_url, api_key) to avoid
# creating a new HTTP connection for every voice transcription.
_asr_client: Optional[AsyncOpenAI] = None
_asr_client_key: Optional[tuple] = None


def _get_asr_client(api_key: str, base_url: Optional[str]) -> AsyncOpenAI:
    """Return a cached AsyncOpenAI client for voice transcription."""
    global _asr_client, _asr_client_key
    cache_key = (api_key, base_url)
    if _asr_client is not None and _asr_client_key == cache_key:
        return _asr_client

    client_args: Dict[str, Any] = {"api_key": api_key, "timeout": 120.0}
    if base_url:
        client_args["base_url"] = base_url
    _asr_client = AsyncOpenAI(**client_args)
    _asr_client_key = cache_key
    return _asr_client


async def _transcribe_voice_upload(audio: UploadFile) -> Dict[str, Any]:
    """Transcribe uploaded audio via OpenAI-compatible ASR providers."""
    max_bytes = max(1, settings.asr_max_audio_size_mb) * 1024 * 1024
    audio_bytes = await audio.read()
    await audio.close()

    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="语音文件为空，请重新录制后重试",
        )
    if len(audio_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"语音文件过大，最大支持 {settings.asr_max_audio_size_mb}MB",
        )

    provider = (settings.asr_provider or "whisper").strip().lower()
    if provider not in {"whisper", "dashscope"}:
        provider = "whisper"

    if provider == "dashscope":
        api_key = settings.dashscope_api_key
        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        default_model = "whisper-v1"
    else:
        api_key = settings.openai_api_key
        base_url = settings.openai_api_base
        default_model = "whisper-1"
        if not api_key and settings.dashscope_api_key:
            provider = "dashscope"
            api_key = settings.dashscope_api_key
            base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            default_model = "whisper-v1"

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="语音识别服务未配置，请联系管理员",
        )

    model = (settings.asr_model or "").strip() or default_model
    language = (settings.asr_default_language or "").strip() or None

    client = _get_asr_client(api_key, base_url)
    audio_buffer = io.BytesIO(audio_bytes)
    audio_buffer.name = audio.filename or "voice.m4a"

    try:
        kwargs: Dict[str, Any] = {
            "model": model,
            "file": audio_buffer,
        }
        if language:
            kwargs["language"] = language

        transcript = await client.audio.transcriptions.create(**kwargs)
    except Exception as e:
        logger.error(
            "Voice transcription failed (provider=%s, model=%s): %s",
            provider,
            model,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="语音转写失败，请稍后重试",
        )

    text = getattr(transcript, "text", None)
    if not text and hasattr(transcript, "model_dump"):
        dump = transcript.model_dump()
        text = dump.get("text") if isinstance(dump, dict) else None
    if not text and isinstance(transcript, dict):
        text = transcript.get("text")

    normalized = (text or "").strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="没有识别到可用语音内容，请重试",
        )

    return {
        "text": normalized,
        "provider": provider,
        "model": model,
        "language": language,
    }


# ==================== Response Models ====================


class ChatJobResponse(BaseModel):
    """Response for non-streaming POST /chat (WebSocket mode)."""
    job_id: str
    session_id: str
    route_type: str


class SignalAcceptedResponse(BaseModel):
    """Response when a user message is routed as an intervention signal."""
    status: str = "signal_accepted"
    signal_id: str
    signal_type: str
    classification_confidence: float


# ==================== Non-Streaming Chat (WebSocket mode) ====================


@router.post("/", response_model=None, include_in_schema=False)
@router.post("", response_model=None)
async def chat_ws(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Non-streaming chat endpoint for WebSocket-based delivery.

    Classifies intent, saves user message, and dispatches processing:
    - Fast path: runs inline as a background task, publishes via PubSub
    - Slow path: enqueues to Redis Streams
    - Hybrid path: fast leg inline + slow leg enqueued
    - Intervention: if active generation exists, classify and inject signal

    Returns immediately with ``{job_id, session_id, route_type}``
    or ``{status, signal_id, signal_type}`` for interventions.
    Results arrive via WebSocket PubSub channel.
    """
    _check_agent_enabled()
    user_id, family_id = require_auth()
    t_start = time.monotonic()
    logger.info(
        "CHAT ws request start: session=%s msg_len=%d",
        request.session_id[:8] if request.session_id else "new",
        len(request.message or ""),
    )

    # Check for intervention routing: if there's an active generation
    # on this session, route through InterventionClassifier instead.
    if request.session_id:
        logger.info(
            "CHAT ws intervention_check start: session=%s",
            request.session_id[:8],
        )
        session_uuid = _validate_uuid(request.session_id, "session_id")
        intervention = await _try_intervention_routing(
            request=request,
            db=db,
            user_id=user_id,
            session_id=session_uuid,
        )
        logger.info(
            "CHAT ws intervention_check done: session=%s handled=%s elapsed_ms=%.0f",
            request.session_id[:8],
            intervention is not None,
            (time.monotonic() - t_start) * 1000,
        )
        if intervention is not None:
            return JSONResponse(
                status_code=202,
                content=intervention.model_dump(),
            )
    try:
        response = await _dispatch_ws_chat_job(
            request=request,
            db=db,
            user_id=user_id,
            family_id=family_id,
        )
        logger.info(
            "CHAT ws request done: session=%s job_id=%s route=%s total_ms=%.0f",
            response.session_id[:8] if response.session_id else "unknown",
            response.job_id,
            response.route_type,
            (time.monotonic() - t_start) * 1000,
        )
        return response
    except asyncio.CancelledError:
        logger.warning(
            "CHAT ws request cancelled: session=%s elapsed_ms=%.0f",
            request.session_id[:8] if request.session_id else "new",
            (time.monotonic() - t_start) * 1000,
        )
        raise


# ==================== Edit Message ====================


@router.post("/edit", response_model=ChatJobResponse)
async def edit_message(
    request: EditMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    """Edit a user message and regenerate from the edited point (WS-only)."""
    from ...modules.conversation.models import ConversationMessage

    _check_agent_enabled()
    user_id, family_id = require_auth()
    message_uuid = _validate_uuid(request.message_id, "message_id")

    result = await db.execute(
        select(ConversationMessage)
        .join(
            AssistantChatSession,
            ConversationMessage.session_id == AssistantChatSession.id,
        )
        .where(
            ConversationMessage.id == message_uuid,
            AssistantChatSession.user_id == user_id,
        )
    )
    target_message = result.scalar_one_or_none()

    if target_message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found or access denied",
        )

    if target_message.role != "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only user messages can be edited",
        )

    request_session_id = request.session_id.strip() if request.session_id else None
    if (
        request_session_id
        and str(target_message.session_id) != request_session_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="message_id does not belong to the provided session_id",
        )

    # Pessimistic lock on the session row to prevent concurrent edit/chat
    # from creating a history fork.
    await db.execute(
        select(AssistantChatSession)
        .where(AssistantChatSession.id == target_message.session_id)
        .with_for_update()
    )

    # Supersede this message and all following messages in the same session.
    tail_result = await db.execute(
        select(ConversationMessage).where(
            ConversationMessage.session_id == target_message.session_id,
            ConversationMessage.created_at >= target_message.created_at,
            ConversationMessage.is_superseded.is_(False),
        )
    )
    for msg in tail_result.scalars():
        msg.is_superseded = True
    await db.commit()

    chat_request = ChatRequest(
        message=request.new_content,
        session_id=str(target_message.session_id),
        force_slow_path=request.force_slow_path,
        latitude=request.latitude,
        longitude=request.longitude,
        location_name=request.location_name,
    )
    return await _dispatch_ws_chat_job(
        request=chat_request,
        db=db,
        user_id=user_id,
        family_id=family_id,
    )


# ==================== Voice Message ====================


@router.post("/voice")
async def voice_message(
    audio: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    force_slow_path: bool = Form(False),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    location_name: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Upload voice audio, transcribe it, then dispatch a WS chat job."""
    _check_agent_enabled()
    user_id, family_id = require_auth()

    normalized_session_id = _validate_optional_session_id(session_id)
    transcription = await _transcribe_voice_upload(audio)

    chat_request = ChatRequest(
        message=transcription["text"],
        session_id=normalized_session_id,
        force_slow_path=force_slow_path,
        latitude=latitude,
        longitude=longitude,
        location_name=location_name,
    )
    job = await _dispatch_ws_chat_job(
        request=chat_request,
        db=db,
        user_id=user_id,
        family_id=family_id,
    )

    return {
        **job.model_dump(),
        "transcription": {
            "text": transcription["text"],
            "language": transcription.get("language"),
            "provider": transcription.get("provider"),
            "model": transcription.get("model"),
        },
    }


# ==================== Regenerate ====================


@router.post("/regenerate")
async def regenerate_message(
    request: RegenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Regenerate an assistant response.

    Returns ``{job_id, session_id, route_type, original_message_id}``
    immediately; results arrive via WebSocket.
    """
    from ...modules.conversation import SessionService
    from .ws_publishers import publish_regenerate

    _check_agent_enabled()
    user_id, family_id = require_auth()

    manager = SessionService(db)
    message_uuid = _validate_uuid(request.message_id, "message_id")

    context = await manager.get_context_before_message(message_uuid, user_id)
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found or access denied",
        )

    await manager.mark_message_superseded(message_uuid)
    await db.commit()

    chat_request = ChatRequest(
        message=context["user_message"],
        session_id=context["session_id"],
    )

    intent = await _classify_intent(chat_request, user_id, db)
    job_id = str(uuid4())

    asyncio.create_task(publish_regenerate(
        intent=intent,
        original_message_id=request.message_id,
        user_message=context["user_message"],
        user_id=str(user_id),
        family_id=str(family_id),
        job_id=job_id,
        session_id=context["session_id"],
    ))

    return {
        "job_id": job_id,
        "session_id": context["session_id"],
        "route_type": intent.route_type.value if hasattr(intent.route_type, "value") else str(intent.route_type),
        "original_message_id": request.message_id,
    }


# ==================== Cancel ====================


@router.post("/cancel")
async def cancel_generation(
    request: CancelRequest,
    db: AsyncSession = Depends(get_db),
):
    """Cancel an in-progress Slow Path generation."""
    _check_agent_enabled()
    user_id, _ = require_auth()

    # Verify the caller owns the session before allowing cancel
    session_uuid = _validate_uuid(request.session_id, "session_id")
    result = await db.execute(
        select(AssistantChatSession).where(
            AssistantChatSession.id == session_uuid,
            AssistantChatSession.user_id == user_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    from ...core.cache import redis_client

    cancel_key = f"cancel:{request.session_id}"
    try:
        await redis_client.set(cancel_key, str(user_id), ttl=60)
    except Exception as e:
        logger.warning("Failed to set cancel flag for session %s: %s", request.session_id, e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to set cancel flag",
        )

    # Also publish InterventionSignal(CANCEL) to the session signal channel
    # so ReactiveSessionActor (warm-CLI path) receives immediate cancel.
    # Non-blocking: if publish fails, Redis key still provides cancel for
    # cold-start AgentWorker path.
    try:
        from ...ai_engine.intervention.types import (
            InterventionSignal,
            InterventionType,
            session_signal_channel,
        )

        signal = InterventionSignal.create(
            signal_type=InterventionType.CANCEL.value,
            session_id=request.session_id,
            job_id="",
            user_id=str(user_id),
            payload={"source": "cancel_endpoint"},
        )
        channel = session_signal_channel(request.session_id)
        if redis_client.client:
            await redis_client.client.publish(channel, signal.to_json())
            logger.info(
                "cancel_signal_published: session=%s channel=%s",
                request.session_id, channel,
            )
    except Exception as e:
        logger.warning(
            "cancel_signal_publish_failed: session=%s error=%s (Redis key fallback active)",
            request.session_id, e,
        )

    return {"status": "cancelled", "session_id": request.session_id}


# ==================== Session Status ====================


@router.get("/status")
async def get_generation_status(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get current generation state for a session.

    Returns the session's generation state, active tool, intervention count,
    and generation count. Useful for clients to decide UI behavior.
    """
    _check_agent_enabled()
    user_id, _ = require_auth()

    session_uuid = _validate_uuid(session_id, "session_id")

    # Verify user owns session
    result = await db.execute(
        select(AssistantChatSession).where(
            AssistantChatSession.id == session_uuid,
            AssistantChatSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    from ...ai_engine.intervention.types import GenerationState

    session_status = await _get_session_status(session_id)

    return {
        "session_id": session_id,
        "generation_state": (
            session_status.state if session_status else GenerationState.IDLE.value
        ),
        "current_job_id": (
            session_status.job_id if session_status else None
        ),
        "active_tool": (
            session_status.active_tool if session_status else None
        ),
        "generation_count": session.generation_count or 0,
        "intervention_count": await _get_intervention_count(db, session_uuid),
    }


# ==================== History ====================


@router.get("/history")
async def get_history(
    session_id: Optional[str] = None,
    before_timestamp: Optional[str] = None,
    before_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Get chat history. If session_id given, returns that session's messages;
    otherwise lazy-loads across all sessions for the user."""
    from ...modules.conversation import SessionService, MessageService

    _check_agent_enabled()
    user_id, _ = require_auth()

    parsed_timestamp = None
    if before_timestamp:
        try:
            parsed_timestamp = datetime.fromisoformat(
                before_timestamp.replace("Z", "+00:00")
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid before_timestamp format. Use ISO 8601.",
            )

    before_uuid = None
    if before_id:
        before_uuid = _validate_uuid(before_id, "before_id")

    if limit < 1 or limit > 100:
        limit = 50

    if session_id:
        session_uuid = _validate_uuid(session_id, "session_id")
        # Verify user owns the session
        result = await db.execute(
            select(AssistantChatSession).where(
                AssistantChatSession.id == session_uuid,
                AssistantChatSession.user_id == user_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )
        msg_svc = MessageService(db)
        messages, has_more = await msg_svc.get_history(
            session_id=session_uuid,
            limit=limit,
            before=parsed_timestamp,
            before_id=before_uuid,
        )
        return {
            "items": [m.to_dict() for m in messages],
            "total": len(messages),
            "limit": limit,
            "offset": offset,
            "has_more": has_more,
        }

    manager = SessionService(db)
    messages = await manager.get_history_messages(
        user_id=user_id,
        before_timestamp=parsed_timestamp,
        before_id=before_uuid,
        limit=limit,
    )

    return {
        "items": messages,
        "total": len(messages),
        "limit": limit,
        "offset": offset,
        "has_more": len(messages) == limit,
    }


@router.get("/daily-summaries")
async def get_daily_summaries(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get daily conversation summaries for a session (cached, generated by background task)."""
    from ...modules.conversation.daily_summary_service import DailySummaryService

    _check_agent_enabled()
    user_id, _ = require_auth()

    session_uuid = _validate_uuid(session_id, "session_id")

    result = await db.execute(
        select(AssistantChatSession).where(
            AssistantChatSession.id == session_uuid,
            AssistantChatSession.user_id == user_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    svc = DailySummaryService(db)
    summaries = await svc.get_summaries(session_uuid)
    return summaries


# ==================== Tool Execution Detail ====================


@router.get("/tool-execution/{execution_id}")
async def get_tool_execution_detail(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get full detail (Layer 3) of a tool execution record."""
    _check_agent_enabled()
    user_id, _ = require_auth()

    exec_uuid = _validate_uuid(execution_id, "execution_id")

    from ...modules.conversation.models import ToolExecutionLog

    result = await db.execute(
        select(ToolExecutionLog)
        .join(
            AssistantChatSession,
            ToolExecutionLog.session_id == AssistantChatSession.id,
        )
        .where(
            ToolExecutionLog.id == exec_uuid,
            AssistantChatSession.user_id == user_id,
        )
    )
    log = result.scalar_one_or_none()

    if log is None:
        raise HTTPException(status_code=404, detail="Tool execution not found")

    return {
        "execution_id": str(log.id),
        "tool_name": log.tool_name,
        "arguments": log.arguments,
        "status": log.status,
        "summary": log.summary,
        "key_results": log.key_results,
        "full_result": log.full_result,
        "execution_time_ms": log.execution_time_ms,
        "iteration": log.iteration,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


# ==================== Session Management ====================


@router.get("/sessions")
async def get_sessions(
    status_filter: str = "active",
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Get user's chat sessions, ordered by most recent activity."""
    _check_agent_enabled()
    user_id, _ = require_auth()

    if limit < 1 or limit > 100:
        limit = 20

    query = (
        select(AssistantChatSession)
        .where(
            AssistantChatSession.user_id == user_id,
            AssistantChatSession.status == status_filter,
        )
        .order_by(sa.desc(AssistantChatSession.last_active_at))
        .limit(limit)
    )
    result = await db.execute(query)
    sessions = result.scalars().all()

    return {
        "sessions": [
            {
                "id": str(s.id),
                "title": s.title,
                "created_at": s.started_at.isoformat() if s.started_at else None,
                "last_active_at": s.last_active_at.isoformat() if s.last_active_at else None,
                "message_count": s.message_count or 0,
            }
            for s in sessions
        ],
    }


@router.delete("/session/{session_id}")
async def clear_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Clear/archive a chat session."""
    _check_agent_enabled()
    user_id, _ = require_auth()

    if not _is_valid_session_id_chars(session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session_id format",
        )

    try:
        session_uuid = UUID(session_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session_id format",
        )

    result = await db.execute(
        select(AssistantChatSession).where(
            AssistantChatSession.id == session_uuid,
            AssistantChatSession.user_id == user_id,
        )
    )
    session_row = result.scalar_one_or_none()
    if session_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    session_row.status = "archived"
    await db.commit()

    # Release SDK pool client for this session (best-effort)
    try:
        from ...ai_engine.sdk.sdk_client_pool import (
            get_sdk_client_pool,
        )

        pool = get_sdk_client_pool()
        if pool is not None:
            await pool.release(session_id)
    except Exception as e:
        logger.warning(
            "Failed to release SDK pool for session %s: %s",
            session_id,
            e,
        )

    return {"message": "Session cleared", "session_id": session_id}


# ==================== Feedback ====================


@router.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit feedback (thumbs up/down) on an assistant message."""
    _check_agent_enabled()
    user_id, _ = require_auth()

    message_uuid = _validate_uuid(request.message_id, "message_id")

    from ...modules.conversation.models import ConversationMessage
    result = await db.execute(
        select(ConversationMessage)
        .join(
            AssistantChatSession,
            ConversationMessage.session_id == AssistantChatSession.id,
        )
        .where(
            ConversationMessage.id == message_uuid,
            AssistantChatSession.user_id == user_id,
        )
    )
    message = result.scalar_one_or_none()
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found or access denied",
        )

    meta = dict(message.message_metadata or {})
    meta["feedback"] = request.feedback
    if request.reason:
        meta["feedback_reason"] = request.reason
    else:
        meta.pop("feedback_reason", None)

    message.message_metadata = meta
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(message, "message_metadata")
    await db.commit()

    return {"status": "ok"}


# ==================== Poll Fallback ====================


@router.get("/poll/{job_id}")
async def poll_job_result(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Poll for Slow Path background job result (WebSocket fallback)."""
    _check_agent_enabled()
    user_id, _ = require_auth()

    job_uuid = _validate_uuid(job_id, "job_id")

    from ...modules.conversation.models import ConversationMessage
    result = await db.execute(
        select(ConversationMessage)
        .join(
            AssistantChatSession,
            ConversationMessage.session_id == AssistantChatSession.id,
        )
        .where(
            AssistantChatSession.user_id == user_id,
            ConversationMessage.role == "assistant",
            ConversationMessage.message_metadata["job_id"].astext == job_id,
        )
        .order_by(ConversationMessage.created_at.desc())
        .limit(1)
    )
    message = result.scalar_one_or_none()

    if message is None:
        # Check Redis error marker written by _on_background_task_error
        try:
            from ...core.cache import redis_client

            raw = await redis_client.get(f"job_status:{job_id}")
            if raw:
                error_info = json.loads(raw)
                return {
                    "status": error_info.get("status", "error"),
                    "job_id": job_id,
                    "error": error_info.get("message", "处理失败"),
                }
        except Exception:
            pass
        return {"status": "pending", "job_id": job_id}

    return {
        "status": "completed",
        "job_id": job_id,
        "message": message.to_dict(),
    }
