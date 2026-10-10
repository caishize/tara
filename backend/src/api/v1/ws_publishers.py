"""WebSocket publishers for Fast/Hybrid chat paths.

These publishers run FastWorker inline and emit each chunk to Redis
PubSub with ``job_id`` and incrementing ``seq``. The WebSocket manager
picks up these messages and forwards them to connected clients.

Usage (from chat.py):
    asyncio.create_task(publish_fast_path(intent, request, user_id, family_id, job_id, session_id))
"""
import logging
import asyncio
import time
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from ...ai_engine.router.types import IntentClassification
from ...core.concurrency import SessionLockManager
from ...core.pubsub.redis_pubsub import get_pubsub_manager
from ...core.pubsub.types import MessageType, PubSubMessage
from ...db.session import async_session_maker

logger = logging.getLogger(__name__)

_session_lock_manager = SessionLockManager()


class _SeqCounter:
    """Thread-safe incrementing sequence counter for a single job."""
    __slots__ = ("_value",)

    def __init__(self) -> None:
        self._value = 0

    def next(self) -> int:
        self._value += 1
        return self._value


async def _pub(
    user_id: str,
    msg_type: MessageType,
    payload: Dict[str, Any],
    job_id: str,
    seq: _SeqCounter,
    session_id: Optional[str] = None,
) -> None:
    """Publish a single PubSub message with job_id and seq."""
    if session_id:
        payload.setdefault("session_id", session_id)

    pubsub = get_pubsub_manager()
    msg = PubSubMessage(
        user_id=user_id,
        message_type=msg_type,
        payload=payload,
        trace_id=job_id,
        job_id=job_id,
        seq=seq.next(),
    )
    await pubsub.publish(user_id, msg)


async def _load_history(
    db: AsyncSession,
    session_id: UUID,
    user_id: UUID,
) -> List[Dict[str, str]]:
    """Load full session context with compression applied."""
    from ...modules.conversation.context_service import ContextService

    try:
        ctx_svc = ContextService(db=db)
        summary = await ctx_svc.get_summary_text(session_id)
        messages = await ctx_svc.build_compressed_history(
            session_id=session_id,
            user_id=user_id,
        )
        history: List[Dict[str, str]] = []
        if summary:
            history.append(
                {
                    "role": "assistant",
                    "content": f"【本会话历史摘要】\n{summary}",
                }
            )
        history.extend(messages)
        return [
            {"role": m["role"], "content": m["content"] or ""}
            for m in history
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]
    except Exception:
        # Fallback: raw full history without compression summary.
        from sqlalchemy import select

        from ...modules.conversation.models import ConversationMessage

        result = await db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.created_at)
        )
        raw = list(result.scalars().all())
        return [
            {"role": m.role, "content": m.content or ""}
            for m in raw
            if m.role in ("user", "assistant") and m.content
        ]


async def publish_fast_path(
    intent: IntentClassification,
    message: str,
    user_id: str,
    family_id: str,
    job_id: str,
    session_id: str,
    context: Optional[Dict[str, Any]] = None,
    _locked: bool = False,
) -> None:
    """Run FastWorker inline and publish each chunk to PubSub.

    This function is designed to be called via ``asyncio.create_task()``
    from the POST /chat endpoint.  It opens its own DB session.
    """
    seq = _SeqCounter()
    str_session_id = str(session_id)
    if not _locked:
        async with _session_lock_manager.acquire(str_session_id):
            await publish_fast_path(
                intent=intent,
                message=message,
                user_id=user_id,
                family_id=family_id,
                job_id=job_id,
                session_id=session_id,
                context=context,
                _locked=True,
            )
        return

    try:
        t_fast_start = time.monotonic()

        # Emit session event
        await _pub(
            user_id, MessageType.CONTENT,
            {"type": "session", "session_id": str_session_id},
            job_id, seq, str_session_id,
        )

        # Emit thinking_start IMMEDIATELY so the client shows a
        # "思考中..." indicator while we do the heavy setup work
        # (save message, load history, assemble context, create bridge).
        await _pub(
            user_id, MessageType.THINKING,
            {"content": "正在分析您的问题...", "phase": "start"},
            job_id, seq, str_session_id,
        )
        _early_thinking_emitted = True

        async with async_session_maker() as db:
            from ...ai_engine.workers.fast_worker import FastWorker
            from ...modules.conversation import MessageService

            msg_svc = MessageService(db)

            # Persist user message
            await msg_svc.save_user_message(
                session_id=UUID(session_id),
                content=message,
                path_type="fast",
                intent=intent.intent_category.value if intent.intent_category else None,
                metadata={"job_id": job_id, "route_type": "fast"},
            )
            await db.commit()

            history = await _load_history(
                db,
                UUID(session_id),
                UUID(user_id),
            )
            t_history = time.monotonic()

            worker = FastWorker()
            worker.set_conversation_history(history)

            logger.info(
                "publish_fast_path setup: history_ms=%.0f, msg=%.60s",
                (t_history - t_fast_start) * 1000,
                message,
            )

            collected_text: List[str] = []
            tool_calls: List[Dict[str, Any]] = []

            async for chunk in worker.handle(
                user_input=message,
                intent=intent,
                user_id=user_id,
                family_id=family_id,
                context=context,
                session_id=str_session_id,
                path_type="fast",
            ):
                chunk_type = chunk.get("type", "content")

                # Deduplicate: skip the first thinking_start from the
                # worker since we already emitted one above.
                if chunk_type == "thinking_start" and _early_thinking_emitted:
                    _early_thinking_emitted = False
                    continue

                if chunk_type == "content":
                    if chunk.get("content"):
                        collected_text.append(chunk["content"])
                    await _pub(
                        user_id, MessageType.CONTENT, chunk,
                        job_id, seq, str_session_id,
                    )

                elif chunk_type == "tool_start":
                    tool_calls.append(chunk)
                    await _pub(
                        user_id, MessageType.TOOL_EXECUTION,
                        {**chunk, "status": "start"},
                        job_id, seq, str_session_id,
                    )

                elif chunk_type == "tool_result":
                    tool_calls.append(chunk)
                    status = "error" if chunk.get("error") else "success"
                    await _pub(
                        user_id, MessageType.TOOL_EXECUTION,
                        {**chunk, "status": status},
                        job_id, seq, str_session_id,
                    )

                elif chunk_type == "tool_progress":
                    await _pub(
                        user_id, MessageType.TOOL_EXECUTION,
                        {**chunk, "status": "progress"},
                        job_id, seq, str_session_id,
                    )

                elif chunk_type == "error":
                    await _pub(
                        user_id, MessageType.ERROR,
                        {"message": chunk.get("content", ""), "code": "FAST_ERROR"},
                        job_id, seq, str_session_id,
                    )

                elif chunk_type in ("thinking", "thinking_start", "thinking_end"):
                    await _pub(
                        user_id, MessageType.THINKING,
                        {"content": chunk.get("content", ""), "phase": chunk_type.replace("thinking_", "").replace("thinking", "chunk")},
                        job_id, seq, str_session_id,
                    )

                elif chunk_type == "upgrade_to_slow":
                    # Fast worker exhausted its tool budget and is upgrading
                    # to the Slow (Agent) path. Notify the client, then
                    # enqueue a SLOW task carrying partial_context so the
                    # AgentWorker can continue where FastWorker left off.
                    upgrade_reason = chunk.get("reason", "complexity_detected")
                    partial_context = chunk.get("partial_context", [])

                    await _pub(
                        user_id, MessageType.CONTENT,
                        {
                            "type": "upgrade_notice",
                            "content": "正在升级到深度思考模式，请稍候...",
                            "reason": upgrade_reason,
                        },
                        job_id, seq, str_session_id,
                    )

                    from ...core.observability.metrics import route_upgrades_total
                    route_upgrades_total.labels(reason=upgrade_reason).inc()

                    # Enqueue a SLOW task (same pattern as _dispatch_ws_chat_job)
                    from ...ai_engine.queue.task_queue import TaskPayload, get_task_queue

                    upgrade_job_id = str(uuid4())
                    upgrade_context: Dict[str, Any] = {
                        "partial_context": partial_context,
                        "upgraded_from": "fast",
                        "upgrade_reason": upgrade_reason,
                        "user_message_saved": True,
                    }
                    if intent.skill_hint:
                        upgrade_context["skill_hint"] = intent.skill_hint
                        upgrade_context["skill"] = intent.skill_hint

                    upgrade_task = TaskPayload(
                        job_id=upgrade_job_id,
                        user_id=user_id,
                        family_id=family_id,
                        user_input=message,
                        route_type="slow",
                        session_id=str_session_id,
                        context_snapshot=upgrade_context,
                        metadata={"user_message_saved": True},
                    )

                    queue = get_task_queue()
                    try:
                        await queue.enqueue(upgrade_task)
                        logger.info(
                            "Fast→Slow upgrade enqueued: job_id=%s → %s, reason=%s",
                            job_id, upgrade_job_id, upgrade_reason,
                        )
                    except Exception as enq_err:
                        logger.error(
                            "Failed to enqueue upgrade task: %s", enq_err,
                        )

                    # C4: Persist Fast-stage content before handing off to Slow
                    upgrade_text = "".join(collected_text)
                    if upgrade_text:
                        try:
                            await msg_svc.save_assistant_message(
                                session_id=UUID(session_id),
                                content=upgrade_text,
                                path_type="fast",
                                tool_calls=tool_calls if tool_calls else None,
                                metadata={
                                    "upgraded_to_slow": True,
                                    "job_id": job_id,
                                },
                            )
                            await db.commit()
                        except Exception as save_err:
                            logger.warning(
                                "C4: Failed to persist fast content before upgrade: %s",
                                save_err,
                            )
                    return  # Stop processing fast path; slow worker takes over

                else:
                    # Forward other chunk types as CONTENT
                    await _pub(
                        user_id, MessageType.CONTENT, chunk,
                        job_id, seq, str_session_id,
                    )

            # Persist assistant response
            full_text = "".join(collected_text)
            if full_text:
                await msg_svc.save_assistant_message(
                    session_id=UUID(session_id),
                    content=full_text,
                    path_type="fast",
                    tool_calls=tool_calls if tool_calls else None,
                    intent=intent.intent_category.value if intent.intent_category else None,
                )
                await db.commit()
                # C5: Context cache invalidation is now handled inside
                # MessageService.save_assistant_message() at the service layer.
                try:
                    from ...modules.conversation.context_service import ContextService
                    await ContextService(db=db).compress_if_needed(
                        session_id=UUID(session_id),
                        user_id=UUID(user_id),
                        family_id=UUID(family_id),
                    )
                except Exception as e:
                    logger.warning("WS fast compression skipped: %s", e)

        # Post-hoc classification verification (observation-only)
        try:
            from ...ai_engine.router.classification_verifier import ClassificationVerifier
            from ...core.observability.metrics import classification_mismatches_total

            tool_start_count = sum(1 for tc in tool_calls if tc.get("type") == "tool_start")
            verifier = ClassificationVerifier()
            vresult = verifier.verify(
                classification=intent,
                worker_status="complete",
                tool_count=tool_start_count,
                user_response=message,
            )
            if not vresult.is_correct:
                classification_mismatches_total.labels(reason=vresult.reason, path="fast").inc()
        except Exception:
            pass  # observation-only, never block fast path

        # Emit done event
        t_fast_done = time.monotonic()
        logger.info(
            "publish_fast_path complete: total_ms=%.0f, text_len=%d, "
            "tool_calls=%d, msg=%.60s",
            (t_fast_done - t_fast_start) * 1000,
            len(full_text),
            len(tool_calls),
            message,
        )

        await _pub(
            user_id, MessageType.COMPLETE,
            {"type": "done", "path": "fast", "route_type": "fast", "is_final": True},
            job_id, seq, str_session_id,
        )

    except Exception as e:
        logger.error("publish_fast_path failed for job %s: %s", job_id, e, exc_info=True)
        try:
            await _pub(
                user_id, MessageType.ERROR,
                {"message": "处理请求时出现错误，请稍后重试。", "code": "FAST_PATH_ERROR"},
                job_id, seq, str_session_id,
            )
        except Exception:
            pass


async def publish_hybrid_path(
    intent: IntentClassification,
    message: str,
    user_id: str,
    family_id: str,
    job_id: str,
    session_id: str,
    context: Optional[Dict[str, Any]] = None,
    _locked: bool = False,
) -> None:
    """Run FastWorker leg-1 inline via PubSub, then enqueue leg-2 to Redis Streams.

    Leg 1: FastWorker streams chunks via PubSub (same as publish_fast_path).
    Leg 2: Enqueue a ``hybrid_background`` task for AgentWorker.
    """
    seq = _SeqCounter()
    str_session_id = str(session_id)
    if not _locked:
        async with _session_lock_manager.acquire(str_session_id):
            await publish_hybrid_path(
                intent=intent,
                message=message,
                user_id=user_id,
                family_id=family_id,
                job_id=job_id,
                session_id=session_id,
                context=context,
                _locked=True,
            )
        return

    try:
        # Emit session event
        await _pub(
            user_id, MessageType.CONTENT,
            {"type": "session", "session_id": str_session_id},
            job_id, seq, str_session_id,
        )

        # Emit thinking_start IMMEDIATELY so the client shows a
        # "思考中..." indicator while we do the heavy setup work.
        await _pub(
            user_id, MessageType.THINKING,
            {"content": "正在分析您的问题...", "phase": "start"},
            job_id, seq, str_session_id,
        )
        _early_thinking_emitted = True

        collected_text: List[str] = []
        tool_calls: List[Dict[str, Any]] = []

        async with async_session_maker() as db:
            from ...ai_engine.workers.fast_worker import FastWorker
            from ...modules.conversation import MessageService

            msg_svc = MessageService(db)

            await msg_svc.save_user_message(
                session_id=UUID(session_id),
                content=message,
                path_type="hybrid",
                intent=intent.intent_category.value if intent.intent_category else None,
                metadata={"job_id": job_id, "route_type": "hybrid"},
            )
            await db.commit()

            history = await _load_history(
                db,
                UUID(session_id),
                UUID(user_id),
            )

            worker = FastWorker()
            worker.set_conversation_history(history)

            async for chunk in worker.handle(
                user_input=message,
                intent=intent,
                user_id=user_id,
                family_id=family_id,
                context=context,
                session_id=str_session_id,
                path_type="hybrid",
            ):
                chunk_type = chunk.get("type", "content")

                # Deduplicate: skip the first thinking_start from the
                # worker since we already emitted one above.
                if chunk_type == "thinking_start" and _early_thinking_emitted:
                    _early_thinking_emitted = False
                    continue

                if chunk_type == "content" and chunk.get("content"):
                    collected_text.append(chunk["content"])

                if chunk_type in ("tool_start", "tool_result"):
                    tool_calls.append(chunk)

                # Publish all chunks (same mapping as fast path)
                if chunk_type in ("tool_start", "tool_result"):
                    status = "start" if chunk_type == "tool_start" else ("error" if chunk.get("error") else "success")
                    await _pub(
                        user_id, MessageType.TOOL_EXECUTION,
                        {**chunk, "status": status},
                        job_id, seq, str_session_id,
                    )
                elif chunk_type == "tool_progress":
                    await _pub(
                        user_id, MessageType.TOOL_EXECUTION,
                        {**chunk, "status": "progress"},
                        job_id, seq, str_session_id,
                    )
                elif chunk_type == "error":
                    await _pub(
                        user_id, MessageType.ERROR,
                        {"message": chunk.get("content", ""), "code": "HYBRID_ERROR"},
                        job_id, seq, str_session_id,
                    )
                elif chunk_type in ("thinking", "thinking_start", "thinking_end"):
                    await _pub(
                        user_id, MessageType.THINKING,
                        {"content": chunk.get("content", ""), "phase": chunk_type.replace("thinking_", "").replace("thinking", "chunk")},
                        job_id, seq, str_session_id,
                    )
                elif chunk_type == "upgrade_to_slow":
                    # Same upgrade handling as fast path — enqueue to slow
                    upgrade_reason = chunk.get("reason", "complexity_detected")
                    partial_context = chunk.get("partial_context", [])

                    await _pub(
                        user_id, MessageType.CONTENT,
                        {
                            "type": "upgrade_notice",
                            "content": "正在升级到深度思考模式，请稍候...",
                            "reason": upgrade_reason,
                        },
                        job_id, seq, str_session_id,
                    )

                    from ...core.observability.metrics import route_upgrades_total
                    route_upgrades_total.labels(reason=upgrade_reason).inc()

                    from ...ai_engine.queue.task_queue import TaskPayload as _TP, get_task_queue as _gtq

                    upgrade_job_id = str(uuid4())
                    upgrade_context: Dict[str, Any] = {
                        "partial_context": partial_context,
                        "upgraded_from": "hybrid",
                        "upgrade_reason": upgrade_reason,
                        "user_message_saved": True,
                    }
                    if intent.skill_hint:
                        upgrade_context["skill_hint"] = intent.skill_hint
                        upgrade_context["skill"] = intent.skill_hint

                    upgrade_task = _TP(
                        job_id=upgrade_job_id,
                        user_id=user_id,
                        family_id=family_id,
                        user_input=message,
                        route_type="slow",
                        session_id=str_session_id,
                        context_snapshot=upgrade_context,
                        metadata={"user_message_saved": True},
                    )
                    try:
                        await _gtq().enqueue(upgrade_task)
                        logger.info(
                            "Hybrid→Slow upgrade enqueued: job_id=%s → %s, reason=%s",
                            job_id, upgrade_job_id, upgrade_reason,
                        )
                    except Exception as enq_err:
                        logger.error("Failed to enqueue hybrid upgrade task: %s", enq_err)

                    # C4: Persist hybrid Fast-stage content before handing off to Slow
                    upgrade_text = "".join(collected_text)
                    if upgrade_text:
                        try:
                            await msg_svc.save_assistant_message(
                                session_id=UUID(session_id),
                                content=upgrade_text,
                                path_type="hybrid",
                                tool_calls=tool_calls if tool_calls else None,
                                metadata={
                                    "upgraded_to_slow": True,
                                    "job_id": job_id,
                                },
                            )
                            await db.commit()
                        except Exception as save_err:
                            logger.warning(
                                "C4: Failed to persist hybrid content before upgrade: %s",
                                save_err,
                            )

                    # Skip hybrid leg-2 — slow worker takes over
                    await _pub(
                        user_id, MessageType.COMPLETE,
                        {"type": "done", "path": "hybrid", "route_type": "hybrid", "is_final": True},
                        job_id, seq, str_session_id,
                    )
                    return
                else:
                    await _pub(
                        user_id, MessageType.CONTENT, chunk,
                        job_id, seq, str_session_id,
                    )

            full_text = "".join(collected_text)
            if full_text:
                await msg_svc.save_assistant_message(
                    session_id=UUID(session_id),
                    content=full_text,
                    path_type="hybrid",
                    tool_calls=tool_calls if tool_calls else None,
                    intent=intent.intent_category.value if intent.intent_category else None,
                )
                await db.commit()
                # C5: Context cache invalidation is now handled inside
                # MessageService.save_assistant_message() at the service layer.
                try:
                    from ...modules.conversation.context_service import ContextService
                    await ContextService(db=db).compress_if_needed(
                        session_id=UUID(session_id),
                        user_id=UUID(user_id),
                        family_id=UUID(family_id),
                    )
                except Exception as e:
                    logger.warning("WS hybrid compression skipped: %s", e)

        # --- Leg 2: Enqueue background enrichment ---
        bg_job_id = str(uuid4())

        # Build fast_tool_calls summary for Leg 2 context (C1)
        fast_tool_calls_summary: List[Dict[str, str]] = []
        for tc in tool_calls:
            tc_type = tc.get("type", "")
            if tc_type == "tool_start":
                fast_tool_calls_summary.append({
                    "name": tc.get("name", ""),
                    "result": "",
                })
            elif tc_type == "tool_result" and fast_tool_calls_summary:
                result_text = str(tc.get("result", ""))[:200]
                fast_tool_calls_summary[-1]["result"] = result_text

        context_snapshot: Dict[str, Any] = {
            "hybrid_hint": True,
            "fast_action": intent.action.value if getattr(intent, "action", None) else "",
            "fast_lookup_filter": intent.lookup_filter or "",
            "fast_location": (
                context.get("location_name") if context else ""
            ) or "",
            "fast_result_summary": full_text[:2000] if full_text else "",
            "fast_response_text": full_text[:2000] if full_text else "",
            "fast_tool_calls": fast_tool_calls_summary,
        }
        if context:
            context_snapshot.update(context)
        if intent.skill_hint:
            context_snapshot["skill_hint"] = intent.skill_hint
            context_snapshot["skill"] = intent.skill_hint
        context_snapshot["user_message_saved"] = True

        from ...ai_engine.queue.task_queue import TaskPayload, get_task_queue

        bg_task = TaskPayload(
            job_id=bg_job_id,
            user_id=user_id,
            family_id=family_id,
            user_input=message,
            route_type="hybrid_background",
            session_id=str_session_id,
            context_snapshot=context_snapshot,
            metadata={"user_message_saved": True},
        )

        queue = get_task_queue()
        try:
            await queue.enqueue(bg_task)
            await _pub(
                user_id, MessageType.BACKGROUND_JOB,
                {
                    "type": "background_job",
                    "message": "正在思考是否还有关联事项...",
                    "job_id": bg_job_id,
                },
                job_id, seq, str_session_id,
            )
        except Exception as e:
            logger.error("Failed to enqueue hybrid background task: %s", e)

        # Emit done for the fast leg
        await _pub(
            user_id, MessageType.COMPLETE,
            {"type": "done", "path": "hybrid", "route_type": "hybrid", "job_id": bg_job_id, "is_final": True},
            job_id, seq, str_session_id,
        )

    except Exception as e:
        logger.error("publish_hybrid_path failed for job %s: %s", job_id, e, exc_info=True)
        try:
            await _pub(
                user_id, MessageType.ERROR,
                {"message": "处理请求时出现错误，请稍后重试。", "code": "HYBRID_PATH_ERROR"},
                job_id, seq, str_session_id,
            )
        except Exception:
            pass


async def publish_regenerate(
    intent: IntentClassification,
    original_message_id: str,
    user_message: str,
    user_id: str,
    family_id: str,
    job_id: str,
    session_id: str,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """Publish a regenerate sequence: emit regenerate marker then delegate to fast/hybrid/slow."""
    seq = _SeqCounter()
    str_session_id = str(session_id)

    # Emit regenerate marker
    await _pub(
        user_id, MessageType.CONTENT,
        {"type": "regenerate", "original_message_id": original_message_id},
        job_id, seq, str_session_id,
    )

    from ...ai_engine.router import RouteType

    if intent.route_type == RouteType.FAST:
        await publish_fast_path(
            intent, user_message, user_id, family_id,
            job_id, session_id, context,
        )
    elif intent.route_type == RouteType.SLOW:
        # Slow path: enqueue to Redis Streams.
        from ...ai_engine.queue.task_queue import TaskPayload, get_task_queue
        from ...modules.conversation import MessageService

        # Persist user message before enqueue so a queue/worker failure
        # does not lose the user's latest input.
        try:
            async with async_session_maker() as db:
                msg_svc = MessageService(db)
                await msg_svc.save_user_message(
                    session_id=UUID(str_session_id),
                    content=user_message,
                    path_type="slow",
                    intent=intent.intent_category.value if intent.intent_category else None,
                    metadata={
                        "job_id": job_id,
                        "route_type": "slow",
                        "regenerate": True,
                    },
                )
                await db.commit()
        except Exception as e:
            logger.warning(
                "Failed to persist regenerate slow user message before enqueue: %s",
                e,
            )

        context_snapshot: Dict[str, Any] = {}
        if context:
            context_snapshot.update(context)
        if intent.skill_hint:
            context_snapshot["skill_hint"] = intent.skill_hint
            context_snapshot["skill"] = intent.skill_hint
        context_snapshot["user_message_saved"] = True

        task = TaskPayload(
            job_id=job_id,
            user_id=user_id,
            family_id=family_id,
            user_input=user_message,
            route_type="slow",
            session_id=str_session_id,
            context_snapshot=context_snapshot,
            metadata={"user_message_saved": True},
        )

        queue = get_task_queue()
        try:
            await queue.enqueue(task)
            await _pub(
                user_id, MessageType.CONTENT,
                {"type": "thinking", "message": "正在深度思考中...", "job_id": job_id},
                job_id, seq, str_session_id,
            )
        except Exception as e:
            logger.error("Failed to enqueue slow regenerate task: %s", e)
            await _pub(
                user_id, MessageType.ERROR,
                {"message": "任务排队失败，请稍后重试", "code": "ENQUEUE_ERROR"},
                job_id, seq, str_session_id,
            )
    else:
        await publish_hybrid_path(
            intent, user_message, user_id, family_id,
            job_id, session_id, context,
        )
