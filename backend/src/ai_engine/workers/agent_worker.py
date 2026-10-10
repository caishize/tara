"""
Agent Worker - Ephemeral worker for complex tasks with state rehydration.

Each worker is stateless and can scale horizontally.
The agentic reasoning loop is delegated to AgentRunner (SDK-based).
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
from uuid import UUID

try:
    from claude_agent_sdk import HookMatcher
except ImportError as _import_err:
    raise ImportError(
        "claude-agent-sdk is required for AgentWorker. "
        "Install it with: pip install claude-agent-sdk>=0.1.0"
    ) from _import_err
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.settings import settings
from ...core.pubsub import RedisPubSubManager
from ..queue import TaskPayload
from ..sdk.agent_factory import AgentFactory, AgentConfig
from ..sdk.agent_runner import AgentRunner
from ..sdk.hooks import (
    create_sensitive_action_hook,
    create_sub_agent_intercept_hook,
    create_builtin_tool_persistence_hook,
    create_ask_user_question_hook,
)
from ..sdk.mcp_tool_server import create_secretary_mcp_server
from ..sdk.sdk_stream_handler import SDKStreamHandler
from ..sdk.tool_persistence import ToolPersistenceHandler
from .agent_helpers import create_pending_action, extract_card_enrichment
from .agent_pool_executor import execute_with_pool_or_fallback
from .hybrid_enrichment import format_hybrid_section
from .pending_action_helpers import SENSITIVE_ACTIONS
from .worker_callbacks import WorkerCallbacksMixin


logger = logging.getLogger(__name__)


class AgentWorker(WorkerCallbacksMixin):
    """Ephemeral agent worker for complex task processing.

    Delegates the agentic reasoning loop to AgentRunner, which uses
    the Claude Agent SDK (ClaudeSDKClient) for tool execution and
    turn management.

    Usage: worker = AgentWorker(db_session); await worker.process(task, pubsub)
    """

    MAX_TURNS = 20
    THINKING_BUDGET_TOKENS = 5000
    ACTION_TTL_MINUTES = 15
    HEARTBEAT_INTERVAL_SECONDS = 10
    CANCEL_CHECK_INTERVAL_SECONDS = 3
    CANCEL_KEY_PREFIX = "cancel:"

    # ToolExecutionLog only accepts these path_type values
    _VALID_PERSIST_PATH_TYPES = frozenset({"fast", "slow", "hybrid"})

    @staticmethod
    def _normalize_path_type(route_type: str) -> str:
        """Normalize route_type for DB persistence.

        Maps ``hybrid_background`` → ``hybrid`` so that
        ToolExecutionLog validation does not reject it.
        """
        if route_type == "hybrid_background":
            return "hybrid"
        return route_type

    def __init__(
        self,
        db: AsyncSession,
        model: Optional[str] = None,
    ):
        self.db = db
        if not (model or settings.effective_anthropic_model):
            raise ValueError(
                "AgentWorker model not configured — "
                "set effective_anthropic_model in settings"
            )
        self._model = model or settings.effective_anthropic_model
        self._rehydration_service = None
        self._context_assembler = None
        self._tool_bridge = None
        self._agent_factory = AgentFactory(
            default_model=self._model,
            effective_model=settings.effective_anthropic_model,
        )

        # Last ContextMetadata from ContextAssembler (for observability)
        self._context_metadata = None

        # Collected during execution for saving
        self._collected_text: List[str] = []
        self._collected_tool_calls: List[Dict[str, Any]] = []
        # Tracks builtin tools completed via PostToolUse hook (shared with publish fn)
        self._completed_builtin_tools: set = set()
        # Tracks builtin tools awaiting completion (shared with heartbeat task)
        self._pending_builtin_tools: List[Dict[str, Any]] = []
        # Tracks MCP tools currently executing (for keepalive signaling)
        self._pending_mcp_tools: List[Dict[str, Any]] = []
        # Sequence counter for PubSub dual-write (A2)
        self._pubsub_seq: int = 0
        # Cancel flag — set when Redis cancel key is detected
        self._cancelled: bool = False
        # Timeout flag — set when SDK idle timeout fires; suppresses further PubSub events
        self._timed_out: bool = False
        # Keepalive event — signaled during tool execution to prevent SDK idle timeout
        self._keepalive: Optional[asyncio.Event] = None

    def _next_seq(self) -> int:
        """Return the next PubSub sequence number for dual-write ordering."""
        self._pubsub_seq += 1
        return self._pubsub_seq

    @property
    def rehydration_service(self):
        """Lazy-load rehydration service."""
        if self._rehydration_service is None:
            from ...modules.conversation.context_service import ContextService
            from ...db.session import async_session_maker
            self._rehydration_service = ContextService(async_session_maker)
        return self._rehydration_service

    @property
    def context_assembler(self):
        """Lazy-load ContextAssembler for V8 unified context pipeline.

        Injects concrete data-fetcher functions so the pipeline actually
        fetches from the DB instead of returning empty layers.
        """
        if self._context_assembler is None:
            from ..context_assembler import ContextAssembler
            from ..context_fetchers import (
                fetch_curation_hints,
                fetch_l1_notes,
                fetch_l2_messages,
                fetch_l3_summaries,
                fetch_l4_memories,
                fetch_l5_orchestration,
            )
            from ..entity_resolver import resolve_entities
            from ...core.feedback import FeedbackAggregator

            async def _combined_l1_fetcher(
                uid: UUID, fid: UUID, db=None,
            ) -> list:
                notes = await fetch_l1_notes(uid, fid, db=db)
                hints = await fetch_curation_hints(uid, fid, db=db)
                return notes + hints

            self._context_assembler = ContextAssembler(
                l1_fetcher=_combined_l1_fetcher,
                l2_fetcher=fetch_l2_messages,
                l3_fetcher=fetch_l3_summaries,
                l4_fetcher=fetch_l4_memories,
                l5_fetcher=fetch_l5_orchestration,
                entity_resolver=resolve_entities,
                feedback_aggregator=FeedbackAggregator(self.db),
            )
        return self._context_assembler

    async def _get_tool_bridge(self):
        """Lazy-load and initialize tool bridge with all registered tools."""
        if self._tool_bridge is None:
            from ..tools.tool_bridge import create_tool_bridge
            self._tool_bridge = await create_tool_bridge(self.db)
        return self._tool_bridge

    async def _check_cancel(
        self, session_id: Optional[str], expected_user_id: Optional[str] = None,
    ) -> bool:
        """Check if a cancel flag has been set for this session in Redis.

        When *expected_user_id* is supplied the cancel key value (the user who
        requested cancellation) must match.  A mismatch means someone other than
        the session owner tried to cancel -- the key is deleted and False is
        returned.
        """
        if not session_id:
            return False
        try:
            from ...core.cache import redis_client
            cancel_key = f"{self.CANCEL_KEY_PREFIX}{session_id}"
            cancel_value = await redis_client.get(cancel_key)
            if cancel_value is None:
                return False

            # Ownership check: cancel_value stores the user_id who requested cancel
            if expected_user_id and cancel_value != expected_user_id:
                logger.warning(
                    "Cancel ownership mismatch for session %s: "
                    "cancel_user=%s, task_user=%s -- ignoring",
                    session_id, cancel_value, expected_user_id,
                )
                await redis_client.delete(cancel_key)
                return False

            # Consume the cancel key so it doesn't affect future requests
            await redis_client.delete(cancel_key)
            self._cancelled = True
            return True
        except Exception as e:
            logger.debug("Cancel check failed (non-fatal): %s", e)
        return False

    async def _publish_cancelled(
        self,
        task: TaskPayload,
        pubsub: RedisPubSubManager,
    ) -> None:
        """Publish a done event with cancelled=true so the client knows generation was stopped."""
        payload = {
            "content": "",
            "is_final": True,
            "cancelled": True,
        }
        if task.session_id:
            payload["session_id"] = task.session_id
        from ...core.pubsub.types import PubSubMessage, MessageType
        msg = PubSubMessage(
            user_id=task.user_id,
            message_type=MessageType.COMPLETE,
            payload=payload,
            trace_id=task.job_id,
            job_id=task.job_id,
            seq=self._next_seq(),
        )
        await pubsub.publish(task.user_id, msg)

    async def process(
        self,
        task: TaskPayload,
        pubsub: RedisPubSubManager,
    ) -> None:
        """
        Process a task from the queue.

        This is the main entry point for the worker.
        After completion, the worker can be discarded.
        """
        t_start = time.monotonic()
        logger.info(
            "AgentWorker processing: job_id=%s, user_id=%s, route=%s",
            task.job_id, task.user_id, task.route_type,
        )

        self._collected_text.clear()
        self._collected_tool_calls.clear()
        self._completed_builtin_tools.clear()
        self._pending_builtin_tools.clear()
        self._pending_mcp_tools.clear()
        self._pubsub_seq = 0
        self._timed_out = False
        self._keepalive = asyncio.Event()

        # Publish immediate progress so the client knows the worker picked up the task.
        # This prevents the "stuck at thinking" feeling during cold SDK startup.
        try:
            from ...core.pubsub.types import PubSubMessage, MessageType
            progress_message = (
                "正在思考是否还有关联事项..."
                if task.route_type == "hybrid_background"
                else "正在处理您的请求..."
            )
            progress_msg = PubSubMessage(
                user_id=task.user_id,
                message_type=MessageType.PROGRESS,
                payload={
                    "stage": "processing",
                    "message": progress_message,
                    "session_id": task.session_id,
                },
                trace_id=task.job_id,
            )
            await pubsub.publish(task.user_id, progress_msg)
        except Exception:
            pass  # Best-effort, don't block processing

        try:
            # 1. Rehydrate context (V8 ContextAssembler is PRIMARY; legacy is fallback)
            assembled_context_text = None
            action_type = self._extract_action_type(task)
            assembled_context_text = await self._try_assemble_context(
                task, action_type,
            )

            # Legacy rehydration is used as fallback when assembler fails,
            # or to provide agent_context / person_profiles for AgentFactory.
            # C2: Skip conversation history if ContextAssembler already provided L2.
            context = await self._rehydrate_context(
                task,
                skip_conversation_history=bool(assembled_context_text),
            )
            t_rehydrated = time.monotonic()

            # 2. Build persistence handler and MCP server
            bridge = await self._get_tool_bridge()
            persisted_path_type = self._normalize_path_type(task.route_type or "slow")

            persistence = ToolPersistenceHandler(
                db=self.db,
                user_id=task.user_id,
                family_id=task.family_id,
                session_id=task.session_id or "",
                path_type=persisted_path_type,
                on_tool_start=self._make_tool_start_callback(task, pubsub),
                on_tool_end=self._make_tool_end_callback(task, pubsub),
                on_tool_progress=self._make_tool_progress_callback(task, pubsub),
            )

            mcp_server = create_secretary_mcp_server(bridge, persistence)

            # 3. Resolve skill from context_snapshot (set by IntentRouter)
            active_skill = self._resolve_skill(task)

            # 4. Compute emotional trend for agent prompt
            emotional_trend_section = None
            try:
                from ...modules.memory.emotional_trend_service import compute_emotional_trend
                trend = await compute_emotional_trend(self.db, task.user_id)
                emotional_trend_section = trend.to_prompt_section() or None
            except Exception:
                logger.debug("Emotional trend computation skipped", exc_info=True)

            # Create agent configuration (with memories + profiles + skill)
            tool_definitions = bridge.get_tool_definitions()
            agent_config = self._agent_factory.create_main_agent(
                context=context.agent_context,
                tool_definitions=tool_definitions,
                memories=context.cross_session_memories or None,
                person_profiles=context.person_profiles or None,
                emotional_trend=emotional_trend_section,
                l5_orchestration_context=assembled_context_text,
                route_type=task.route_type or "slow",
                skill=active_skill,
            )

            # 4b. Build system prompt with route-specific hints.
            # If ContextAssembler produced richer context, append it.
            system_prompt = self._build_system_prompt(
                task=task,
                base_prompt=agent_config.system_prompt,
                assembled_context=assembled_context_text,
            )

            # 5. Save user message BEFORE reasoning (fixes cross-path context gap)
            await self._save_user_message(task)
            # Commit early to release the FOR UPDATE row lock on
            # assistant_chat_sessions.  The lock is acquired by
            # _next_sequence_number inside save_user_message, and without
            # this commit it would be held for the entire SDK execution
            # duration, blocking any concurrent intervention message saves.
            try:
                await self.db.commit()
            except Exception:
                logger.warning(
                    "Early commit after user message failed: job_id=%s",
                    task.job_id,
                    exc_info=True,
                )

            # 6. Build SDK stream handler
            sdk_stream_handler = SDKStreamHandler(
                publish_fn=self._make_pubsub_publish_fn(pubsub, task),
                channel=f"agent:result:{task.job_id}",
                job_id=task.job_id,
            )

            # 7. Build SDK hooks (including PostToolUse for builtin tool persistence)
            hooks = self._build_sdk_hooks(
                task, pubsub, mcp_server, sdk_stream_handler, persistence,
                keepalive=self._keepalive,
            )

            # 8. Override system prompt in config for hybrid hints
            run_config = AgentConfig(
                model=agent_config.model,
                system_prompt=system_prompt,
                tools=agent_config.tools,
                max_turns=agent_config.max_turns,
                max_tokens=agent_config.max_tokens,
                temperature=agent_config.temperature,
                idle_timeout_seconds=agent_config.idle_timeout_seconds,
                builtin_tools=agent_config.builtin_tools,
                metadata=agent_config.metadata,
                mcp_server_name=agent_config.mcp_server_name,
            )

            # 9. Execute reasoning via AgentRunner (SDK-based)
            runner = AgentRunner(
                thinking_budget_tokens=self.THINKING_BUDGET_TOKENS,
            )
            t_pre_exec = time.monotonic()

            # Try to use pooled client for CLI process reuse (reduces ~68s delay to ~12s)
            # Run a heartbeat task concurrently to keep the WebSocket alive
            # during long-running SDK tool executions (Task, Skill, etc.)
            heartbeat_task = asyncio.create_task(
                self._run_heartbeat(pubsub, task)
            )
            try:
                result = await execute_with_pool_or_fallback(
                    worker=self,
                    runner=runner,
                    run_config=run_config,
                    task=task,
                    bridge=bridge,
                    persistence=persistence,
                    pubsub=pubsub,
                    mcp_server=mcp_server,
                    sdk_stream_handler=sdk_stream_handler,
                    hooks=hooks,
                    keepalive=self._keepalive,
                )
            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

            t_executed = time.monotonic()
            self._collected_text = [result.text] if result.text else []

            # 9a. Handle error_max_turns gracefully — generate fallback text
            # when the SDK exhausted all turns on tool calls without producing
            # any text output for the user.
            if result.stop_reason == "error_max_turns" and not result.text:
                logger.warning(
                    "AgentWorker: SDK hit max_turns (%d) without text output "
                    "(job_id=%s, tool_calls=%d)",
                    run_config.max_turns,
                    task.job_id,
                    len(result.tool_calls),
                )
                fallback_text = self._generate_max_turns_fallback(result)
                self._collected_text = [fallback_text]

            # Digression interrupt: Actor interrupted current generation to handle a
            # DIGRESSION signal (WAITING_USER state). Treat as graceful completion.
            if result.stop_reason == "digression_interrupt":
                logger.info(
                    "AgentWorker: generation interrupted by DIGRESSION signal, "
                    "treating as normal completion (job_id=%s)",
                    task.job_id,
                )

            # If the SDK timed out, the error event was already published
            # via sdk_stream_handler.emit_error(). Do NOT publish the partial
            # text again as a COMPLETE event — that would create a duplicate
            # message on the frontend.
            if result.stop_reason == "timeout":
                self._timed_out = True
                self._pending_builtin_tools.clear()
                self._pending_mcp_tools.clear()
                logger.warning(
                    "AgentWorker: SDK timed out, skipping final content "
                    "publish (job_id=%s, partial_text_len=%d)",
                    task.job_id, len(result.text or ""),
                )
            else:
                # Emit buffered thinking if SDK didn't stream it (CLI fallback).
                await sdk_stream_handler.emit_missing_thinking()

                # 10. Publish final content marker.
                # Always include full text so mobile can reconcile lost chunks.
                # The mobile reconciliation logic uses the done event's content
                # only when it's longer than the streamed content (dedup-safe).
                final_content = result.text or ""

                card_enrichment = self._extract_card_enrichment()
                stream_failed_events = (
                    sdk_stream_handler.failed_events
                    if sdk_stream_handler.failed_events
                    else None
                )
                await self._publish_content(
                    task, pubsub, final_content, is_final=True,
                    card_enrichment=card_enrichment,
                    failed_events=stream_failed_events,
                )

                # E8: Push notification when hybrid_background completes
                actual_content = final_content or (result.text or "")
                if task.route_type == "hybrid_background" and len(actual_content) > 50:
                    try:
                        from ...core.push.fcm_service import send_to_user
                        from ...modules.member.device_token_service import DeviceTokenService
                        from ...db.session import async_session_maker

                        async with async_session_maker() as push_db:
                            token_svc = DeviceTokenService(push_db)
                            tokens = await token_svc.get_active_tokens(
                                UUID(task.user_id),
                            )
                            if tokens:
                                body_preview = actual_content[:100]
                                if len(actual_content) > 100:
                                    body_preview += "..."
                                await send_to_user(
                                    tokens=[t.token for t in tokens],
                                    title="秘书有补充内容",
                                    body=body_preview,
                                    data={
                                        "session_id": task.session_id or "",
                                        "type": "hybrid_supplement",
                                    },
                                )
                    except Exception:
                        pass  # Best-effort, never block processing

            # 11. Save assistant response via UnifiedMessageSaver
            # (save even on timeout so partial content isn't lost)
            await self._save_conversation_unified(task)
            # C5: Context cache invalidation is now handled inside
            # MessageService.save_assistant_message() at the service layer.

            # 11.1 Persist SDK session id for future reuse
            if result.session_id:
                await self._persist_sdk_session_context(task, result.session_id)

            # 12. Trigger context compression if needed
            await self._try_compress_context(task)

            # 13. Post-hoc classification verification (observation-only)
            self._verify_classification(task, result)

            t_done = time.monotonic()
            ctx_meta_info = ""
            if self._context_metadata is not None:
                ctx_meta_info = (
                    f", ctx_tokens={self._context_metadata.total_tokens_used}"
                    f", ctx_assembly_ms={self._context_metadata.assembly_time_ms:.0f}"
                )
            logger.info(
                "AgentWorker completed: job_id=%s "
                "(rehydrate_ms=%.0f, setup_ms=%.0f, sdk_exec_ms=%.0f, "
                "save_ms=%.0f, total_ms=%.0f, stop_reason=%s%s)",
                task.job_id,
                (t_rehydrated - t_start) * 1000,
                (t_pre_exec - t_rehydrated) * 1000,
                (t_executed - t_pre_exec) * 1000,
                (t_done - t_executed) * 1000,
                (t_done - t_start) * 1000,
                result.stop_reason,
                ctx_meta_info,
            )

        except asyncio.CancelledError:
            logger.info(
                "AgentWorker cancelled: job_id=%s, session=%s",
                task.job_id, task.session_id,
            )
            # Save partial content if any was collected before cancellation
            if self._collected_text:
                try:
                    await self._save_conversation_unified(task)
                except Exception:
                    pass
            # Do not re-raise — cancellation is a normal user action
        except Exception as e:
            logger.error("AgentWorker error: job_id=%s, error=%s", task.job_id, e)
            safe_message = "处理请求时出现错误，请稍后重试。"
            try:
                await self._publish_error(task, pubsub, safe_message)
            except Exception as pub_err:
                logger.error(
                    "Failed to publish error for job_id=%s: %s",
                    task.job_id, pub_err,
                )
            raise

    # ── Heartbeat ──────────────────────────────────────────────────────

    async def _run_heartbeat(
        self,
        pubsub: RedisPubSubManager,
        task: TaskPayload,
    ) -> None:
        """Publish periodic progress events for pending tools and signal keepalive.

        During long-running SDK tool executions (MCP tools, builtin tools,
        sub-agents), no SDK messages are emitted, which causes the idle
        timeout to fire prematurely. This heartbeat:

        1. Publishes tool_execution(progress) events to keep the WebSocket alive
        2. Signals the SDK keepalive event to prevent SDK idle timeout
        3. Periodically checks the cancel flag

        Also periodically checks the cancel flag to enable cancellation
        during long-running tool executions.
        """
        try:
            # E2: Check cancel every 3s, but only publish progress every 10s
            last_progress_time = time.monotonic()
            while True:
                await asyncio.sleep(self.CANCEL_CHECK_INTERVAL_SECONDS)
                try:
                    if self._timed_out:
                        return

                    # Check cancel flag during heartbeat (with ownership verification)
                    if await self._check_cancel(task.session_id, task.user_id):
                        logger.info(
                            "Cancel detected in heartbeat for job_id=%s",
                            task.job_id,
                        )
                        await self._publish_cancelled(task, pubsub)
                        return

                    has_pending_tools = bool(
                        self._pending_builtin_tools or self._pending_mcp_tools
                    )

                    # Signal SDK keepalive to prevent idle timeout during tool execution
                    if has_pending_tools and self._keepalive is not None:
                        self._keepalive.set()

                    # Only publish progress at the original 10s interval
                    now = time.monotonic()
                    if now - last_progress_time < self.HEARTBEAT_INTERVAL_SECONDS:
                        continue
                    last_progress_time = now

                    if not has_pending_tools:
                        continue

                    # Hybrid background should not leak intermediate tool UX.
                    # Keep heartbeat for SDK liveness/cancel checks, but skip
                    # progress publishing to frontend.
                    if task.route_type == "hybrid_background":
                        continue

                    # Publish progress for the most recent pending tool
                    # (prefer MCP tools as they are user-visible)
                    if self._pending_mcp_tools:
                        entry = self._pending_mcp_tools[-1]
                    else:
                        entry = self._pending_builtin_tools[-1]
                    tool_name = entry["name"]
                    await pubsub.publish_tool_execution(
                        user_id=task.user_id,
                        tool_name=tool_name,
                        status="progress",
                        trace_id=task.job_id,
                        session_id=task.session_id,
                        summary=f"正在执行 {tool_name}...",
                        job_id=task.job_id,
                        seq=self._next_seq(),
                    )
                except Exception as e:
                    # Do not let heartbeat die on transient publish/cache errors.
                    logger.warning(
                        "Heartbeat tick failed for job_id=%s: %s",
                        task.job_id,
                        e,
                    )
                    if self._keepalive is not None:
                        self._keepalive.set()
        except asyncio.CancelledError:
            pass

    # ── Skill Resolution ─────────────────────────────────────────────

    @staticmethod
    def _resolve_skill(task: TaskPayload):
        """Resolve a Skill from the task's context_snapshot hint.

        Returns the Skill instance if found, otherwise None.
        """
        skill_hint = (
            task.context_snapshot.get("skill_hint")
            or task.context_snapshot.get("skill")
        )
        if not skill_hint:
            return None

        try:
            from ..skills.registry import get_skill_registry
            registry = get_skill_registry()
            skill = registry.get(skill_hint)
            if skill:
                logger.info(
                    "Skill '%s' activated for job_id=%s",
                    skill.name, task.job_id,
                )
            return skill
        except Exception as e:
            logger.warning("Failed to resolve skill '%s': %s", skill_hint, e)
            return None

    # ── SDK Hooks ──────────────────────────────────────────────────

    def _build_sdk_hooks(
        self,
        task: TaskPayload,
        pubsub: RedisPubSubManager,
        mcp_server: Any,
        sdk_stream_handler: SDKStreamHandler,
        persistence: Optional[ToolPersistenceHandler] = None,
        keepalive: Optional[asyncio.Event] = None,
    ) -> Dict[str, List[HookMatcher]]:
        """Build SDK hooks for sensitive actions, sub-agent interception, and builtin tool persistence."""
        pre_tool_hooks: List[HookMatcher] = []

        # Sensitive action hook
        sensitive_handler = self._make_sensitive_action_handler(task, pubsub)
        sensitive_hook = create_sensitive_action_hook(
            sensitive_actions=SENSITIVE_ACTIONS,
            handler_fn=sensitive_handler,
        )
        pre_tool_hooks.append(HookMatcher(hooks=[sensitive_hook]))

        # Sub-agent delegation hook
        sub_agent_handler = self._make_sub_agent_sdk_handler(
            task, mcp_server, sdk_stream_handler, keepalive=keepalive,
        )
        sub_agent_hook = create_sub_agent_intercept_hook(
            handler_fn=sub_agent_handler,
        )
        pre_tool_hooks.append(
            HookMatcher(matcher="delegate_to_sub_agent", hooks=[sub_agent_hook])
        )

        # AskUserQuestion interception — publish to WebSocket, wait for answer
        ask_user_hook = self._make_ask_user_question_hook(task, pubsub)
        pre_tool_hooks.append(
            HookMatcher(matcher="AskUserQuestion", hooks=[ask_user_hook])
        )

        hooks: Dict[str, List[HookMatcher]] = {"PreToolUse": pre_tool_hooks}

        # PostToolUse: persist builtin tool executions (WebSearch, WebFetch)
        if persistence is not None:
            builtin_persistence_hook = create_builtin_tool_persistence_hook(persistence)
            hooks["PostToolUse"] = [
                HookMatcher(hooks=[builtin_persistence_hook]),
            ]

        return hooks

    # ── Context & Prompt ──────────────────────────────────────────────

    async def _rehydrate_context(
        self,
        task: TaskPayload,
        skip_conversation_history: bool = False,
    ):
        """Rehydrate context from database (legacy path).

        When this task was upgraded from the Fast path, ``partial_context``
        in context_snapshot carries the message history accumulated during
        the fast agentic loop.  We prepend a summary so the Slow worker
        can continue where the Fast worker left off.

        Args:
            skip_conversation_history: When True (C2), skip conversation
                history loading because ContextAssembler already provided it.
        """
        # C2: Skip conversation history when assembler already provided L2
        max_turns = 0 if skip_conversation_history else 10
        context = await self.rehydration_service.build_context(
            user_id=UUID(task.user_id),
            family_id=UUID(task.family_id),
            session_id=task.session_id,
            max_conversation_turns=max_turns,
        )

        partial_context = (task.context_snapshot or {}).get("partial_context")
        if partial_context and isinstance(partial_context, list):
            logger.info(
                "Prepending %d partial_context messages from Fast→Slow upgrade "
                "(job_id=%s)",
                len(partial_context),
                task.job_id,
            )
            summary_lines = self._summarize_partial_context(partial_context)
            if summary_lines:
                fast_summary = (
                    "【Fast Path 已完成的对话和工具调用摘要】\n"
                    + "\n".join(summary_lines)
                )
                # RehydratedContext is immutable; inject Fast→Slow summary into
                # conversation context preface rather than mutating agent_context.
                context = context.with_conversation_preface(fast_summary)

        return context

    @staticmethod
    def _summarize_partial_context(
        partial_context: List[Dict[str, Any]],
    ) -> List[str]:
        """Summarize partial_context messages into readable lines."""
        lines: List[str] = []
        for msg in partial_context:
            role = msg.get("role", "unknown")
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                lines.append(f"[{role}]: {content[:500]}")
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type", "")
                    if btype == "tool_use":
                        lines.append(
                            f"[{role}]: called tool {block.get('name', '?')}"
                        )
                    elif btype == "tool_result":
                        lines.append(
                            f"[tool_result]: {str(block.get('content', ''))[:200]}"
                        )
                    elif btype == "text" and block.get("text"):
                        lines.append(f"[{role}]: {block['text'][:500]}")
        return lines

    async def _try_assemble_context(
        self,
        task: TaskPayload,
        action_type: Optional[str] = None,
    ) -> Optional[str]:
        """Try V8 ContextAssembler pipeline; return None on failure (graceful fallback).

        On success, stores ContextMetadata in self._context_metadata for observability.
        """
        try:
            from ..context_fetchers import aggregate_dismissed_entities

            assembler = self.context_assembler
            dismissed = await aggregate_dismissed_entities(
                user_id=UUID(task.user_id),
                family_id=UUID(task.family_id),
            )
            prompt_text, metadata = await assembler.assemble(
                user_id=UUID(task.user_id),
                family_id=UUID(task.family_id),
                session_id=task.session_id or "",
                user_message=task.user_input or "",
                action_type=action_type,
                dismissed_entity_ids=dismissed if dismissed else None,
            )
            self._context_metadata = metadata
            if prompt_text:
                logger.debug(
                    "ContextAssembler produced %d tokens for job_id=%s",
                    metadata.total_tokens_used,
                    task.job_id,
                )
                return prompt_text
            return None
        except Exception as e:
            logger.warning(
                "ContextAssembler failed for job_id=%s, using legacy path: %s",
                task.job_id,
                e,
            )
            return None

    @staticmethod
    def _extract_action_type(task: TaskPayload) -> Optional[str]:
        """Extract action_type string from task context for budget adjustment."""
        snapshot = task.context_snapshot or {}
        action = snapshot.get("action_type") or snapshot.get("action")
        if action is None:
            return None
        raw = str(action).lower()
        if hasattr(action, "value"):
            raw = str(action.value).lower()
        return raw

    async def _persist_sdk_session_context(self, task: TaskPayload, sdk_session_id: str) -> None:
        """Persist SDK session id for later reuse."""
        if not task.session_id or not sdk_session_id:
            return
        try:
            from ...modules.conversation.models import AssistantChatSession
            from ...core.utils.timezone import utc_now

            session = await self.db.get(AssistantChatSession, UUID(task.session_id))
            if session is None:
                return

            context = session.context or {}
            context["sdk_session_id"] = sdk_session_id
            context["sdk_session_route"] = "slow" if task.route_type in ("slow", "hybrid_background") else task.route_type
            context["sdk_session_updated_at"] = utc_now().isoformat()

            session.context = context
            session.last_active_at = utc_now()
            await self.db.commit()
            logger.debug(
                "Persisted SDK session id for session_id=%s",
                task.session_id,
            )
        except Exception as e:
            logger.warning("Failed to persist SDK session id: %s", e)

    def _build_system_prompt(
        self,
        task: Optional[TaskPayload] = None,
        base_prompt: Optional[str] = None,
        assembled_context: Optional[str] = None,
    ) -> str:
        """Build system prompt with assembled context as primary knowledge source.

        When the ContextAssembler produces output, it becomes the primary
        context section (replacing legacy supplementary treatment).
        """
        if not base_prompt:
            raise ValueError("base_prompt is required — AgentFactory must provide it")
        prompt = base_prompt

        if assembled_context:
            prompt += f"\n\n## 用户上下文 (Context)\n{assembled_context}"

        if task and task.route_type == "hybrid_background":
            prompt += format_hybrid_section(task)

            # C1: Include Fast leg results so Slow leg avoids duplicate queries
            snapshot = task.context_snapshot or {}
            fast_text = snapshot.get("fast_response_text", "")
            fast_tools = snapshot.get("fast_tool_calls", [])
            if fast_text or fast_tools:
                parts: List[str] = []
                parts.append("\n\n## 快速回复已完成的内容（请勿重复查询或重复回答）")
                if fast_tools:
                    tool_lines = []
                    for tc in fast_tools:
                        name = tc.get("name", "")
                        result = tc.get("result", "")
                        if name:
                            line = f"- 工具: {name}"
                            if result:
                                line += f" → {result}"
                            tool_lines.append(line)
                    if tool_lines:
                        parts.append("### 已调用工具\n" + "\n".join(tool_lines))
                if fast_text:
                    parts.append(f"### 快速回复内容\n{fast_text}")
                parts.append("请在此基础上提供补充分析或建议，不要重复上述内容。")
                prompt += "\n".join(parts)

        return prompt

    # ── Message Persistence ───────────────────────────────────────────

    async def _save_user_message(self, task: TaskPayload) -> None:
        """Save user message via UnifiedMessageSaver."""
        try:
            if task.metadata.get("user_message_saved") or task.context_snapshot.get("user_message_saved"):
                logger.debug(
                    "User message already saved for job_id=%s, skipping duplicate save",
                    task.job_id,
                )
                return
            from ...modules.conversation import MessageService
            saver = MessageService(self.db)

            session_id = UUID(task.session_id) if task.session_id else None
            if session_id is None:
                logger.warning("No session_id for task %s, skipping user message save", task.job_id)
                return

            await saver.save_user_message(
                session_id=session_id,
                content=task.user_input,
                path_type=self._normalize_path_type(task.route_type or "slow"),
                metadata={
                    "job_id": task.job_id,
                    "route_type": task.route_type,
                },
            )
            logger.debug("Saved user message for job_id=%s", task.job_id)
        except Exception as e:
            logger.warning("Failed to save user message (unified): %s", e)
            # Rollback aborted transaction so subsequent DB operations succeed.
            try:
                await self.db.rollback()
            except Exception:
                pass

    async def _save_conversation_unified(self, task: TaskPayload) -> None:
        """Save assistant message via UnifiedMessageSaver."""
        try:
            from ...modules.conversation import MessageService
            saver = MessageService(self.db)

            assistant_content = "".join(self._collected_text)
            if not assistant_content and not self._collected_tool_calls:
                return

            session_id = UUID(task.session_id) if task.session_id else None
            if session_id is None:
                logger.warning("No session_id for task %s, skipping save", task.job_id)
                return

            await saver.save_assistant_message(
                session_id=session_id,
                content=assistant_content,
                path_type=self._normalize_path_type(task.route_type or "slow"),
                tool_calls=self._collected_tool_calls if self._collected_tool_calls else None,
                metadata={
                    "job_id": task.job_id,
                    "route_type": task.route_type,
                },
            )
            logger.debug("Saved conversation via UnifiedMessageSaver for job_id=%s", task.job_id)
        except Exception as e:
            logger.warning("Failed to save conversation (unified): %s, falling back", e)
            # Rollback the aborted transaction so the fallback (and subsequent
            # DB operations like _persist_sdk_session_context) can succeed.
            try:
                await self.db.rollback()
            except Exception:
                pass
            from .conversation_save_fallback import save_conversation_fallback
            await save_conversation_fallback(
                db=self.db,
                user_id=task.user_id,
                family_id=task.family_id,
                session_id=task.session_id,
                job_id=task.job_id,
                route_type=task.route_type,
                user_input=task.user_input,
                collected_text=self._collected_text,
                collected_tool_calls=self._collected_tool_calls,
            )

    # ── Pending Actions ───────────────────────────────────────────────

    async def _create_pending_action(
        self,
        task: TaskPayload,
        tool_name: str,
        tool_input: Dict[str, Any],
        pubsub: RedisPubSubManager,
    ) -> str:
        """Create a pending action for user confirmation."""
        return await create_pending_action(
            db=self.db,
            task=task,
            tool_name=tool_name,
            tool_input=tool_input,
            pubsub=pubsub,
            action_ttl_minutes=self.ACTION_TTL_MINUTES,
        )

    # ── Card Enrichment ─────────────────────────────────────────────

    def _extract_card_enrichment(self) -> Optional[Dict[str, Any]]:
        """Pick the most relevant card-producing tool result."""
        return extract_card_enrichment(self._collected_tool_calls)

    # ── PubSub Helpers ────────────────────────────────────────────────

    async def _publish_content(
        self,
        task: TaskPayload,
        pubsub: RedisPubSubManager,
        content: str,
        is_final: bool,
        card_enrichment: Optional[Dict[str, Any]] = None,
        failed_events: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Publish content via Pub/Sub."""
        seq = self._next_seq()
        receivers = await pubsub.publish_content(
            user_id=task.user_id,
            content=content,
            trace_id=task.job_id,
            is_final=is_final,
            session_id=task.session_id,
            card_enrichment=card_enrichment,
            failed_events=failed_events,
            job_id=task.job_id,
            seq=seq,
        )
        logger.info(
            "Worker publish_content: job_id=%s session=%s route=%s type=%s seq=%s "
            "content_len=%d receivers=%d",
            task.job_id,
            task.session_id,
            task.route_type,
            "complete" if is_final else "content",
            seq,
            len(content or ""),
            receivers,
        )

    async def _publish_error(
        self,
        task: TaskPayload,
        pubsub: RedisPubSubManager,
        error: str,
    ) -> None:
        """Publish error via Pub/Sub."""
        seq = self._next_seq()
        receivers = await pubsub.publish_error(
            user_id=task.user_id,
            error_message=error,
            error_code="AGENT_ERROR",
            trace_id=task.job_id,
            job_id=task.job_id,
            seq=seq,
        )
        logger.info(
            "Worker publish_error: job_id=%s session=%s route=%s seq=%s "
            "error_len=%d receivers=%d",
            task.job_id,
            task.session_id,
            task.route_type,
            seq,
            len(error or ""),
            receivers,
        )

    # ── Max-turns fallback ─────────────────────────────────────────────

    @staticmethod
    def _generate_max_turns_fallback(result) -> str:
        """Generate a user-friendly fallback when max_turns is exhausted."""
        tool_names = [tc.get("name", "") for tc in (result.tool_calls or [])]
        # Dedupe while preserving order
        unique_tools = list(dict.fromkeys(tool_names))
        # Strip MCP prefix for readability
        display = [
            t.replace("mcp__secretary__", "") for t in unique_tools if t
        ]
        if display:
            tools_str = "、".join(display[:3])
            return (
                f"已为您完成了相关查询（{tools_str}），"
                "请查看上方结果。如需更多分析，请继续追问。"
            )
        return "已完成处理，请查看上方结果。如需更多信息，请继续追问。"

    # ── Context Compression ──────────────────────────────────────────

    async def _try_compress_context(self, task: TaskPayload) -> None:
        """Trigger context compression if the session has enough messages."""
        if not task.session_id:
            return
        try:
            from ...modules.conversation.context_service import ContextService
            snapshot = task.context_snapshot or {}
            intent_cat = snapshot.get("intent_category")
            tool_count = int(snapshot.get("active_tool_count", 0))
            service = ContextService(db=self.db)
            compressed = await service.compress_if_needed(
                session_id=UUID(task.session_id),
                user_id=UUID(task.user_id),
                family_id=UUID(task.family_id),
                intent_classification=intent_cat,
                active_tool_count=tool_count,
            )
            if compressed:
                logger.info("Context compressed for session %s", task.session_id)
        except Exception as e:
            logger.warning("Context compression failed for session %s: %s", task.session_id, e)

    def _verify_classification(self, task: TaskPayload, result: Any) -> None:
        """Run post-hoc classification verification (observation-only).

        Logs misclassification signals and increments Prometheus counters.
        Never alters routing behavior.
        """
        try:
            from ..router.classification_verifier import ClassificationVerifier
            from ..router.types import (
                ActionType,
                Difficulty,
                IntentCategory,
                IntentClassification,
                RouteType,
            )
            from ...core.observability.metrics import classification_mismatches_total

            snapshot = task.context_snapshot or {}

            # Reconstruct classification from task metadata
            difficulty_str = snapshot.get("difficulty", "thinking")
            action_str = snapshot.get("action", "chat")
            route_str = task.route_type or "slow"

            try:
                difficulty = Difficulty(difficulty_str)
            except ValueError:
                difficulty = Difficulty.THINKING
            try:
                action = ActionType(action_str)
            except ValueError:
                action = ActionType.CHAT
            try:
                route_type = RouteType(route_str)
            except ValueError:
                route_type = RouteType.SLOW

            classification = IntentClassification(
                route_type=route_type,
                intent_category=IntentCategory.UNKNOWN,
                confidence=float(snapshot.get("confidence", 1.0)),
                difficulty=difficulty,
                action=action,
            )

            tool_count = len(result.tool_calls) if hasattr(result, "tool_calls") else 0
            worker_status = "complete"

            verifier = ClassificationVerifier()
            vresult = verifier.verify(
                classification=classification,
                worker_status=worker_status,
                tool_count=tool_count,
                user_response=task.user_input,
            )
            if not vresult.is_correct:
                classification_mismatches_total.labels(
                    reason=vresult.reason,
                    path="slow",
                ).inc()
        except Exception as e:
            logger.debug("Classification verification skipped: %s", e)
