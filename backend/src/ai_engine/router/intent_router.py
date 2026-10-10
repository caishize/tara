"""
Intent Router using Claude Haiku for unified single-call classification.

Routes requests to Fast Path (80%), Slow Path (20%), or Hybrid Path
based on difficulty + action analysis.

V8 optimization: merged two sequential LLM calls (classify + recover_lookup)
into a single unified call, reducing routing latency from ~400ms to ~200ms.
"""
import json
import logging
import time
from datetime import datetime, timezone

from ...core.utils.timezone import utc_now
from typing import Optional
from uuid import UUID

from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.settings import settings
from ...core.cache import redis_client
from ...core.llm.haiku_client import get_haiku_client
from .types import (
    RouteType,
    Difficulty,
    ActionType,
    LookupTarget,
    IntentCategory,
    IntentClassification,
    CATEGORY_TOOLS_MAP,
    resolve_route,
    map_to_intent_category,
)


logger = logging.getLogger(__name__)


UNIFIED_CLASSIFICATION_PROMPT = """你是家庭助手的请求分类器。一次性完成所有分类和实体提取。

## 第一步：难度（这个请求我能立刻回答吗？）
- immediate: 能立刻回答。包括：问候、查看已有数据（日程/任务/行程/提醒/成员）、天气、时间、简单问答、闲聊
- thinking: 需要思考。包括：创建新事物、规划安排、分析对比、购买预订

判断依据：
- "查看/查询/我的/有什么/怎么样了" → immediate
- "帮我安排/规划/创建/添加/提醒我" → thinking
- "分析/对比/建议/推荐" → thinking

## 第二步：动作类型
- lookup: 查看已有数据
- create: 创建新事物（包括设置提醒、添加待办）
- greet: 问候
- chat: 闲聊或简单问答
- weather: 天气
- time: 时间日期
- plan: 多步骤规划
- analyze: 复杂分析
- transact: 购买预订

## 第三步：是否需要深度建议 (enhance)
如果 difficulty=immediate，判断用户是否隐含需要更深入的建议：
- true: 用户可能需要额外建议（如：问天气→可能需要穿衣建议；查日程→可能需要时间优化；查行程→可能需要准备提醒）
- false: 用户只需要直接回答

判断依据：
- 问"怎么样/准备得如何/满不满" → 通常 enhance=true（暗示需要建议）
- 问"查看/有什么/几点" → 通常 enhance=false（只查数据）

## 第四步：查询目标和过滤条件（所有 action 都必须填写）
- lookup_target: 如果 action=lookup，判断查什么：task/reminder/schedule/trip/member/today/unknown。非 lookup 动作设为 unknown。
- lookup_filter: 关键实体或过滤条件。适用于所有 action，不仅限 lookup。例如：天气→城市名；查日程→日期；查行程→目的地；创建→相关实体。没有则为 null。

**关键规则（实体提取）**：
1. 如果用户当前消息包含明确实体（城市名/日期/人名等），直接提取。
2. 如果用户当前消息缺少关键实体，**必须从对话上下文中推断**。例如：用户之前在讨论"南澳行程"，现在问"天气怎样"，lookup_filter 应为"南澳"而非 null。
3. 优先使用最近一轮对话里明确提及且与当前问题相关的实体。
4. 只在有明确依据时填写；无法确定时保持 unknown/null。

{context_block}

## 输出（严格JSON，不要额外文字）：
{{"difficulty":"immediate|thinking|unsure","action":"lookup|create|greet|chat|weather|time|plan|analyze|transact","enhance":true|false,"confidence":0.0-1.0,"lookup_target":"task|reminder|schedule|trip|member|today|unknown","lookup_filter":null,"reasoning":"一句话解释"}}
"""


class IntentRouter:
    """
    Intent-based request router using Claude Haiku.

    Uses two-axis classification:
    1. Difficulty (immediate/thinking) -> route decision
    2. Action type -> handler selection
    3. Enhance flag -> HYBRID trigger
    """

    DEFAULT_MODEL = None  # Must come from settings; no hardcoded fallback
    FREQ_CACHE_PREFIX = "intent_router:freq"
    HYBRID_COOLDOWN_HOURS = 0.5  # 30 minutes — keep short so agent can do proactive lookups

    def __init__(
        self,
        client: Optional[AsyncAnthropic] = None,
        model: Optional[str] = None,
        hybrid_cooldown_hours: int = HYBRID_COOLDOWN_HOURS,
    ):
        self._custom_client = client
        if model:
            self._model = model
        else:
            self._model = settings.intent_router_model
        if not self._model:
            raise ValueError(
                "IntentRouter model not configured — "
                "set intent_router_model or effective_anthropic_model in settings"
            )
        self._hybrid_cooldown_hours = hybrid_cooldown_hours

    @property
    def client(self) -> AsyncAnthropic:
        """Return the injected client or the shared Haiku singleton."""
        if self._custom_client is not None:
            return self._custom_client
        return get_haiku_client()

    async def classify(
        self,
        user_input: str,
        user_id: str,
        session_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> IntentClassification:
        """
        Classify user intent via a single unified Haiku call.

        All fields (difficulty, action, enhance, lookup_target, lookup_filter)
        are extracted in one pass. Context-based entity recovery is handled
        within the unified prompt — no second LLM call needed.

        Args:
            user_input: User's message
            user_id: User ID for frequency control
            session_id: Optional session ID for loading conversation context
            db: Optional database session for context loading
        """
        try:
            t_classify_start = time.monotonic()

            # Load recent conversation context if session available
            recent_context = await self._load_context(session_id, db, user_id)
            t_context = time.monotonic()

            # Single unified Haiku call for classification + entity extraction
            result = await self._call_unified_classifier(user_input, recent_context)
            t_llm = time.monotonic()

            logger.info(
                "Intent classification timing: context_ms=%.0f, llm_ms=%.0f, "
                "total_ms=%.0f, model=%s, user_input=%.60s",
                (t_context - t_classify_start) * 1000,
                (t_llm - t_context) * 1000,
                (t_llm - t_classify_start) * 1000,
                self._model,
                user_input,
            )

            # Parse unified result
            difficulty = self._parse_difficulty(result.get("difficulty"))
            action = self._parse_action(result.get("action"))
            enhance = bool(result.get("enhance", False))
            confidence = float(result.get("confidence", 0.5))
            lookup_target = self._parse_lookup_target(result.get("lookup_target"))
            lookup_filter = self._normalize_lookup_filter(result.get("lookup_filter"))
            reasoning = result.get("reasoning")

            # Apply HYBRID frequency control (topic includes filter for granularity)
            if enhance and difficulty == Difficulty.IMMEDIATE:
                target_part = lookup_target.value if lookup_target else "none"
                filter_part = lookup_filter or "none"
                topic = f"{action.value}:{target_part}:{filter_part}"
                if not await self._check_hybrid_frequency(user_id, topic):
                    enhance = False

            # Resolve route from two axes
            route_type = resolve_route(difficulty, enhance)

            # Low-confidence FAST decisions should upgrade to HYBRID so the
            # background agent can verify / enrich the quick response.
            if (
                route_type == RouteType.FAST
                and confidence < 0.8
                and not enhance
            ):
                logger.info(
                    "Low-confidence FAST (%.2f) upgraded to HYBRID for user_input=%.60s",
                    confidence,
                    user_input,
                )
                route_type = RouteType.HYBRID
                enhance = True

            # Map to intent category for stream events
            intent_category = map_to_intent_category(difficulty, action, enhance)

            # Get required tools for this category
            requires_tools = CATEGORY_TOOLS_MAP.get(intent_category, [])

            # Check if confirmation needed
            requires_confirmation = self._check_confirmation_required(action, user_input)

            # Resolve skill hint via SkillRegistry
            skill_hint = self._resolve_skill(action, user_input)

            # Instrument route distribution metric
            from ...core.observability.metrics import route_requests_total
            route_requests_total.labels(path_type=route_type.value).inc()

            return IntentClassification(
                route_type=route_type,
                intent_category=intent_category,
                confidence=confidence,
                difficulty=difficulty,
                action=action,
                enhance=enhance,
                lookup_target=lookup_target if action == ActionType.LOOKUP else None,
                lookup_filter=lookup_filter,
                requires_tools=requires_tools,
                requires_confirmation=requires_confirmation,
                reasoning=reasoning,
                skill_hint=skill_hint,
            )

        except Exception as e:
            logger.error("Classification failed: %s", e)
            return IntentClassification(
                route_type=RouteType.SLOW,
                intent_category=IntentCategory.UNKNOWN,
                confidence=0.0,
                difficulty=Difficulty.UNSURE,
                action=ActionType.CHAT,
                reasoning=f"Classification error: {str(e)}",
            )

    async def _load_context(
        self,
        session_id: Optional[str],
        db: Optional[AsyncSession],
        user_id: str,
    ) -> Optional[str]:
        """Load recent conversation context from database."""
        if not session_id or not db:
            return None

        try:
            from ...modules.conversation.context_service import ContextService
            session_uuid = UUID(session_id)
            try:
                user_uuid = UUID(user_id)
            except Exception:
                user_uuid = UUID(int=0)
            svc = ContextService(db=db)
            summary = await svc.get_summary_text(session_uuid)
            recent = await svc.build_compressed_history(session_uuid, user_uuid)

            lines = []
            if summary:
                lines.append(f"会话摘要: {summary}")
            for msg in recent:
                role_label = "用户" if msg.get("role") == "user" else "助手"
                lines.append(f"{role_label}: {msg.get('content')}")
            return "\n".join(lines)

        except Exception as e:
            logger.warning("Failed to load conversation context: %s", e)
            return None

    async def _call_unified_classifier(
        self,
        user_input: str,
        recent_context: Optional[str],
    ) -> dict:
        """Single unified Haiku call for classification + entity extraction.

        Combines what was previously two separate calls (classify + recover_lookup)
        into one prompt, reducing latency by ~50%.
        """
        context_block = ""
        if recent_context:
            context_block = f"""## 对话上下文（参考上文理解用户意图并推断缺失实体）：
{recent_context}
"""

        system_prompt = UNIFIED_CLASSIFICATION_PROMPT.format(
            context_block=context_block,
        )
        user_message = f"用户输入：{user_input}"

        try:
            response = await self.client.messages.create(
                model=self._model,
                max_tokens=256,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            # Extract text from the first TextBlock, skipping ThinkingBlock(s)
            text_parts = [
                block.text for block in response.content
                if hasattr(block, "text")
            ]
            if not text_parts:
                raise ValueError("No TextBlock found in API response")
            content = text_parts[0].strip()
            parsed = json.loads(self._strip_markdown_fence(content))

            # Ensure all expected keys exist with safe defaults
            return {
                "difficulty": parsed.get("difficulty", "unsure"),
                "action": parsed.get("action", "chat"),
                "enhance": parsed.get("enhance", False),
                "confidence": parsed.get("confidence", 0.5),
                "lookup_target": parsed.get("lookup_target", "unknown"),
                "lookup_filter": parsed.get("lookup_filter"),
                "reasoning": parsed.get("reasoning"),
            }

        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON from unified classifier: %s", e)
            return {
                "difficulty": "unsure",
                "action": "chat",
                "confidence": 0.5,
                "lookup_target": "unknown",
                "lookup_filter": None,
                "reasoning": "JSON parse error",
            }
        except Exception as e:
            logger.error("Unified classifier API call failed: %s", e)
            raise

    @staticmethod
    def _strip_markdown_fence(content: str) -> str:
        """Strip markdown code fence wrapper if present."""
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])
        return content.strip()

    @staticmethod
    def _normalize_lookup_filter(raw_value: Optional[object]) -> Optional[str]:
        """Normalize lookup_filter values from model output."""
        if raw_value is None:
            return None
        text = str(raw_value).strip()
        if not text:
            return None
        if text.lower() in {"null", "none", "unknown", "n/a"}:
            return None
        return text

    @staticmethod
    def _has_lookup_filter(value: Optional[str]) -> bool:
        """Return True when lookup_filter contains an effective value."""
        return bool(value and value.strip())

    def _parse_difficulty(self, value: Optional[str]) -> Difficulty:
        """Parse difficulty string to enum."""
        if not value:
            return Difficulty.UNSURE
        try:
            return Difficulty(value.lower())
        except ValueError:
            logger.warning("Unknown difficulty: %s", value)
            return Difficulty.UNSURE

    def _parse_action(self, value: Optional[str]) -> ActionType:
        """Parse action string to enum."""
        if not value:
            return ActionType.CHAT
        try:
            return ActionType(value.lower())
        except ValueError:
            logger.warning("Unknown action type: %s", value)
            return ActionType.CHAT

    def _parse_lookup_target(self, value: Optional[str]) -> Optional[LookupTarget]:
        """Parse lookup target string to enum."""
        if not value:
            return None
        try:
            return LookupTarget(value.lower())
        except ValueError:
            logger.warning("Unknown lookup target: %s", value)
            return LookupTarget.UNKNOWN

    async def _check_hybrid_frequency(self, user_id: str, topic: str) -> bool:
        """
        Check if we can send a hybrid notification.
        Prevents over-notification by enforcing a cooldown period.
        """
        cache_key = f"{self.FREQ_CACHE_PREFIX}:{user_id}:{topic}"

        try:
            if await redis_client.exists(cache_key):
                return False

            await redis_client.set(
                cache_key,
                utc_now().isoformat(),
                ttl=int(self._hybrid_cooldown_hours * 3600),
            )
            return True

        except Exception as e:
            logger.warning("Frequency check failed: %s", e)
            return True

    @staticmethod
    def _resolve_skill(action: ActionType, user_input: str) -> Optional[str]:
        """Resolve a skill hint based on action type and user input keywords."""
        try:
            from ..skills.registry import get_skill_registry
            registry = get_skill_registry()
            skill = registry.resolve(
                action=action.value,
                user_input=user_input,
            )
            return skill.name if skill else None
        except Exception as e:
            logger.warning("Skill resolution failed: %s", e)
            return None

    def _check_confirmation_required(
        self,
        action: ActionType,
        user_input: str,
    ) -> bool:
        """Check if the intent requires user confirmation."""
        if action == ActionType.TRANSACT:
            return True

        sensitive_keywords = {"买", "购买", "下单", "订票", "预订", "转账", "支付"}
        return any(kw in user_input for kw in sensitive_keywords)

    async def get_route_stats(self, user_id: str) -> dict:
        """Get routing statistics for a user (for debugging)."""
        return {
            "user_id": user_id,
            "hybrid_cooldown_hours": self._hybrid_cooldown_hours,
            "model": self._model,
        }


# Global instance
_intent_router: Optional[IntentRouter] = None


def get_intent_router() -> IntentRouter:
    """Get or create the global intent router."""
    global _intent_router
    if _intent_router is None:
        _intent_router = IntentRouter()
    return _intent_router
