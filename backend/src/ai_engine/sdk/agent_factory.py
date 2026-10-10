"""
Agent Factory - Creates immutable AgentConfig for Slow Path execution.

The factory encapsulates:
1. Model selection (Sonnet for deep reasoning)
2. System prompt construction (with context injection)
3. Tool registration (from ToolBridge via MCP server)
4. Sub-agent delegation setup

Each call returns a frozen AgentConfig dataclass.
Execution is handled by AgentRunner.run(config=...).
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..agent_context import AgentContext
from ..skills.base import Skill

logger = logging.getLogger(__name__)

def _get_model_sonnet() -> str:
    """Get Sonnet model from settings. Raises if not configured."""
    try:
        from ...config.settings import settings
        model = settings.effective_anthropic_model
        if not model:
            raise ValueError("effective_anthropic_model is not configured")
        return model
    except Exception as e:
        logger.error("Failed to load Sonnet model from settings: %s", e)
        raise ValueError("Anthropic Sonnet model not configured — set effective_anthropic_model in settings") from e


def _get_model_haiku() -> str:
    """Get Haiku model from settings. Raises if not configured."""
    try:
        from ...config.settings import settings
        model = settings.intent_router_model or settings.fast_worker_model
        if not model:
            raise ValueError("intent_router_model / fast_worker_model is not configured")
        return model
    except Exception as e:
        logger.error("Failed to load Haiku model from settings: %s", e)
        raise ValueError("Anthropic Haiku model not configured — set intent_router_model in settings") from e


def _get_agent_idle_timeout_seconds() -> int:
    """Get SDK idle timeout from settings (0 disables idle timeout)."""
    try:
        from ...config.settings import settings
        return int(settings.agent_idle_timeout_seconds)
    except Exception:
        return 0


def _get_default_max_turns() -> int:
    """Get default max turns from settings. Falls back to 20."""
    try:
        from ...config.settings import settings
        return int(settings.claude_agent_max_turns)
    except Exception:
        return 20

DEFAULT_MAX_TURNS = _get_default_max_turns()
DEFAULT_MAX_TOKENS = 8192
DEFAULT_TEMPERATURE = 0.7

# Idle timeout: max seconds of silence (no SDK messages) before aborting.
# Set to 0 to disable stream idle timeout checks entirely.
SUB_AGENT_IDLE_TIMEOUT_SECONDS = _get_agent_idle_timeout_seconds()
MAIN_AGENT_IDLE_TIMEOUT_SECONDS = _get_agent_idle_timeout_seconds()


@dataclass(frozen=True)
class AgentConfig:
    """Immutable configuration for an Agent execution."""
    model: str
    system_prompt: str
    tools: List[Dict[str, Any]]
    max_turns: int = DEFAULT_MAX_TURNS
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float = DEFAULT_TEMPERATURE
    idle_timeout_seconds: int = MAIN_AGENT_IDLE_TIMEOUT_SECONDS
    builtin_tools: Tuple[str, ...] = ()
    metadata: Dict[str, Any] = field(default_factory=dict)
    mcp_server_name: str = "secretary"


SYSTEM_PROMPT_TEMPLATE = """你是这个家庭的私人秘书，已经服务这个家庭一段时间了。

## 你的性格
- 温暖但专业，像一位值得信赖的管家
- 主动但不打扰，在合适的时机提供合适的信息
- 记忆力出色，能自然地引用过去的对话和经历
- 对家庭成员的关系和喜好有深入了解

## 工作原则
1. **先理解情绪**: 永远先感知用户当前的情绪状态，再决定回复的语气和内容
2. **忙碌时简洁**: 用户忙碌时精简回复，用户悠闲时可以多聊几句
3. **说明为什么**: 提到准备事项时，说明为什么现在该做，而非简单列出
4. **有温度的建议**: 提到联系人时，引用具体记忆让建议有温度
5. **工具驱动**: 需要数据时主动调用工具查询，不要凭记忆回答
6. **家庭视角**: 始终站在家庭整体的角度考虑

## 工具使用指南
- 查询数据前先用对应的查询工具
- 修改数据前先确认目标存在
- 复杂任务可以分步执行多个工具
- 工具上下文中 [#xxxxxxxx] 是执行记录短ID，需要详情时用 view_tool_details 传入完整 UUID
- **农历日期**：当用户提到农历日期（如"初二"、"正月十五"、"腊月廿三"等），必须调用 `convert_lunar_date` 工具进行转换，禁止自行推算！
- **成员信息完整录入**：调用 update_member_info 时，从对话上下文中最大化提取可推断的字段，一次录入。特别注意：
  - 从称呼/代词/名字推断 gender（如"强哥"/"他"→male，"姐姐"/"她"→female）
  - 从语境推断 relation_type（如"老领导"→mentor，"我带过的人"→subordinate）
  - work_history 录入完整时间线，每段经历独立一条，日期要准确反映用户描述（注意区分离职年份和入职年份，不要把空窗期算入下一段）

## 敏感操作
涉及支付、删除等敏感操作时，系统会自动生成待确认操作，由用户确认后执行。

## 回复示例
- 用户问"明天有什么安排" → 不只列事件，而是说"明天上午有两个会，间隔有点紧，建议提前准备好XX。下午比较轻松，可以处理一下周三出差的准备。"
- 用户说"好累啊" → 不急着推待办，先共情，再视情况建议轻松的安排
- 用户问"周末干什么" → 结合家庭成员情况给出有温度的建议，而非罗列选项

{l5_orchestration_context}

{emotional_trend}

{context}

{person_profiles}

{memories}"""


class AgentFactory:
    """
    Factory for creating Agent configurations.

    Usage:
        factory = AgentFactory()
        config = factory.create_main_agent(
            context=agent_context,
            tool_definitions=tool_defs,
            memories=formatted_memories,
        )
        runner = AgentRunner(client=anthropic_client)
        result = await runner.run(config=config, messages=..., ...)
    """

    def __init__(
        self,
        default_model: Optional[str] = None,
        effective_model: Optional[str] = None,
    ):
        self._default_model = default_model or _get_model_sonnet()
        self._effective_model = effective_model

    def create_main_agent(
        self,
        context: AgentContext,
        tool_definitions: List[Dict[str, Any]],
        memories: Optional[str] = None,
        person_profiles: Optional[str] = None,
        emotional_trend: Optional[str] = None,
        l5_orchestration_context: Optional[str] = None,
        route_type: str = "slow",
        max_turns: Optional[int] = None,
        include_sub_agent_tool: bool = True,
        skill: Optional[Skill] = None,
    ) -> AgentConfig:
        """
        Create the main agent configuration for Slow Path execution.

        Args:
            context: Rehydrated agent context
            tool_definitions: Anthropic-format tool definitions
            memories: Formatted cross-session memories for system prompt
            person_profiles: Formatted family member profiles
            emotional_trend: Formatted emotional trend section
            l5_orchestration_context: Formatted orchestration context (today's schedule)
            route_type: "slow" or "hybrid_background"
            max_turns: Override default max turns
            include_sub_agent_tool: Whether to add the delegate_to_sub_agent tool
            skill: Optional Skill to inject into the system prompt
        """
        _valid_route_types = {"slow", "fast", "hybrid", "hybrid_background"}
        if route_type not in _valid_route_types:
            raise ValueError(
                f"Invalid route_type '{route_type}', must be one of {_valid_route_types}"
            )
        if max_turns is not None and (max_turns < 1 or max_turns > 100):
            raise ValueError(f"max_turns must be between 1 and 100, got {max_turns}")

        system_prompt = self._build_system_prompt(
            context, memories, person_profiles, emotional_trend,
            l5_orchestration_context,
        )

        # Inject skill prompt addon if a skill is active
        if skill is not None:
            system_prompt += skill.build_prompt_section()
            logger.info("Skill '%s' injected into system prompt", skill.name)

        model = self._select_model(route_type)

        # Determine max_turns: skill override > explicit arg > default
        effective_max_turns = max_turns
        if effective_max_turns is None and skill is not None and skill.max_turns_override:
            effective_max_turns = skill.max_turns_override

        # Optionally add sub-agent delegation tool
        all_tools = list(tool_definitions)
        if include_sub_agent_tool:
            try:
                from .sub_agents import get_delegate_tool_definition
                all_tools.append(get_delegate_tool_definition())
            except ImportError:
                logger.debug("Sub-agent module not available, skipping delegate tool")

        # Merge builtin tools from skill (if any).
        # Skip SDK builtin WebSearch/WebFetch when using a proxy (e.g. DashScope)
        # that does not support server-side search connectors — the MCP
        # web_search tool (backed by Tavily/Serper) is used instead.
        base_builtins: List[str] = []
        if not self._is_using_api_proxy():
            base_builtins = ["WebSearch", "WebFetch"]
        if skill is not None:
            for bt in skill.builtin_tools:
                if bt not in base_builtins:
                    base_builtins.append(bt)

        metadata = {
            "route_type": route_type,
            "user_id": str(context.user_id),
            "session_id": context.session_id,
        }
        if skill is not None:
            metadata["active_skill"] = skill.name

        return AgentConfig(
            model=model,
            system_prompt=system_prompt,
            tools=all_tools,
            max_turns=effective_max_turns or DEFAULT_MAX_TURNS,
            max_tokens=DEFAULT_MAX_TOKENS,
            temperature=DEFAULT_TEMPERATURE,
            idle_timeout_seconds=MAIN_AGENT_IDLE_TIMEOUT_SECONDS,
            builtin_tools=tuple(base_builtins),
            metadata=metadata,
        )

    def create_sub_agent(
        self,
        name: str,
        system_prompt: str,
        tool_definitions: List[Dict[str, Any]],
        context: AgentContext,
        max_turns: int = 30,
    ) -> AgentConfig:
        """
        Create a sub-agent configuration for specialized tasks.

        Sub-agents have:
        - Independent max_turns (typically higher)
        - Longer idle timeout (for complex tasks)
        - Specialized system prompt
        - Subset of tools relevant to the task
        """
        context_section = context.to_system_prompt_context()
        full_prompt = f"{system_prompt}\n\n{context_section}"

        return AgentConfig(
            model=self._default_model,
            system_prompt=full_prompt,
            tools=tool_definitions,
            max_turns=max_turns,
            max_tokens=DEFAULT_MAX_TOKENS,
            temperature=DEFAULT_TEMPERATURE,
            idle_timeout_seconds=SUB_AGENT_IDLE_TIMEOUT_SECONDS,
            metadata={"sub_agent": name},
        )

    @staticmethod
    def _is_using_api_proxy() -> bool:
        """Check if the API endpoint is a third-party proxy (not official Anthropic).

        Proxies like DashScope do not support server-side connectors
        (WebSearch, WebFetch), so the SDK builtin tools should be disabled.
        """
        try:
            from ...config.settings import settings
            base_url = settings.anthropic_base_url
            if not base_url:
                return False
            # Known proxies that don't support server-side connectors
            proxy_indicators = ("dashscope", "aliyun")
            return any(indicator in base_url for indicator in proxy_indicators)
        except Exception:
            return False

    def _select_model(self, route_type: str) -> str:
        """Select model based on route type."""
        if self._effective_model:
            return self._effective_model
        return self._default_model

    def _build_system_prompt(
        self,
        context: AgentContext,
        memories: Optional[str] = None,
        person_profiles: Optional[str] = None,
        emotional_trend: Optional[str] = None,
        l5_orchestration_context: Optional[str] = None,
    ) -> str:
        """Build complete system prompt with context, memories, profiles, emotional trend, and orchestration."""
        context_section = context.to_system_prompt_context()

        memories_section = ""
        if memories:
            memories_section = f"## 你对这个家庭的了解\n{memories}"

        profiles_section = ""
        if person_profiles:
            profiles_section = f"## 家庭成员画像\n{person_profiles}"

        emotional_section = emotional_trend or ""

        orchestration_section = ""
        if l5_orchestration_context:
            orchestration_section = f"## 当前状态\n{l5_orchestration_context}"

        return SYSTEM_PROMPT_TEMPLATE.format(
            context=context_section,
            memories=memories_section,
            person_profiles=profiles_section,
            emotional_trend=emotional_section,
            l5_orchestration_context=orchestration_section,
        )
