"""
InterventionClassifier — classifies incoming user messages against
the currently executing task to determine the appropriate intervention type.

Uses Claude Haiku for sub-150ms single-call classification with max_tokens=80.

F1 enhancement: Always injects ``<current_agent_state>`` block into the
classification prompt, giving the classifier richer context about the agent's
current activity (active tool, generation state, partial text summary).
"""

import json
import logging
import time
from typing import Optional

from anthropic import AsyncAnthropic

from ...config.settings import settings
from ...core.llm.haiku_client import get_haiku_client
from .types import ClassificationResult, InterventionType


logger = logging.getLogger(__name__)


CLASSIFICATION_PROMPT = """你是一个消息意图分类器。判断用户的新消息与当前正在执行的任务之间的关系。

当前任务摘要: {current_task_summary}
用户上条消息: {last_user_message}
用户新消息: {new_user_message}
{agent_state_block}
分类规则:
- CORRECTION: 用户在纠正或修改当前任务的方向，需要中断当前执行重新开始
- ADDITIVE: 用户在补充当前任务的额外信息或条件，可以注入当前上下文
- CANCEL: 用户想取消或终止当前操作
- CONFIRM: 用户在确认一个待执行的操作（如购买、预订、发送）
- DIGRESSION: 用户转移了话题，与当前正在执行的任务无关

输出JSON: {{"type":"CORRECTION|ADDITIVE|CANCEL|CONFIRM|DIGRESSION","confidence":0.0-1.0}}"""


_DEFAULT_TYPE = InterventionType.ADDITIVE.value
_DEFAULT_CONFIDENCE = 0.5


class InterventionClassifier:
    """Classifies user messages arriving during active generation.

    Determines whether the new message is a correction, additive info,
    cancellation, confirmation, or topic digression relative to the
    current task being processed by the agent.

    Uses Claude Haiku with max_tokens=80 for sub-150ms classification.
    """

    def __init__(
        self,
        client: Optional[AsyncAnthropic] = None,
        model: Optional[str] = None,
    ):
        self._custom_client = client
        self._model = model or settings.intent_router_model
        if not self._model:
            raise ValueError(
                "InterventionClassifier model not configured — "
                "set intent_router_model in settings"
            )

    @property
    def client(self) -> AsyncAnthropic:
        """Return the injected client or the shared Haiku singleton."""
        if self._custom_client is not None:
            return self._custom_client
        return get_haiku_client()

    async def classify(
        self,
        current_task_summary: str,
        last_user_message: str,
        new_user_message: str,
        active_tool: Optional[str] = None,
        generation_state: str = "",
        partial_text_summary: str = "",
    ) -> ClassificationResult:
        """Classify a new user message against the current task.

        Args:
            current_task_summary: Brief description of what the agent is doing.
            last_user_message: The previous user message that triggered the task.
            new_user_message: The newly arrived user message to classify.
            active_tool: Name of the tool currently being executed, if any.
            generation_state: Current agent state (e.g. GENERATING, TOOL_EXECUTING).
            partial_text_summary: Tail of partially generated text for context.

        Returns:
            ClassificationResult with type, confidence, and latency_ms.
        """
        t_start = time.monotonic()
        try:
            result = await self._call_classifier(
                current_task_summary,
                last_user_message,
                new_user_message,
                active_tool,
                generation_state,
                partial_text_summary,
            )

            latency_ms = int((time.monotonic() - t_start) * 1000)

            classified_type = self._parse_type(result.get("type"))
            confidence = self._parse_confidence(result.get("confidence"))

            classification = ClassificationResult(
                type=classified_type,
                confidence=confidence,
                latency_ms=latency_ms,
            )

            logger.info(
                "Intervention classification: type=%s, confidence=%.2f, "
                "effective_type=%s, latency_ms=%d, audit=%s, "
                "new_message=%.60s",
                classification.type,
                classification.confidence,
                classification.effective_type,
                classification.latency_ms,
                classification.requires_audit,
                new_user_message,
            )

            return classification

        except Exception as e:
            latency_ms = int((time.monotonic() - t_start) * 1000)
            logger.error(
                "Intervention classification failed (latency_ms=%d): %s",
                latency_ms,
                e,
            )
            return ClassificationResult(
                type=_DEFAULT_TYPE,
                confidence=_DEFAULT_CONFIDENCE,
                latency_ms=latency_ms,
            )

    async def _call_classifier(
        self,
        current_task_summary: str,
        last_user_message: str,
        new_user_message: str,
        active_tool: Optional[str],
        generation_state: str = "",
        partial_text_summary: str = "",
    ) -> dict:
        """Make the Haiku API call for classification."""
        # Build agent state context block (F1: always render to ensure
        # active_tool info is present regardless of generation_state)
        partial_tail = partial_text_summary[-100:] if partial_text_summary else ""
        agent_state_block = (
            "<current_agent_state>\n"
            f"状态: {generation_state or '未知'}\n"
            f"已生成内容摘要: {partial_tail}\n"
            f"正在执行的工具: {active_tool or '无'}\n"
            "</current_agent_state>\n"
        )

        prompt = CLASSIFICATION_PROMPT.format(
            current_task_summary=current_task_summary,
            last_user_message=last_user_message,
            new_user_message=new_user_message,
            agent_state_block=agent_state_block,
        )

        try:
            response = await self.client.messages.create(
                model=self._model,
                max_tokens=80,
                messages=[{"role": "user", "content": prompt}],
            )

            text_parts = [
                block.text for block in response.content
                if hasattr(block, "text")
            ]
            if not text_parts:
                logger.warning("No TextBlock in classifier response")
                return {"type": _DEFAULT_TYPE, "confidence": _DEFAULT_CONFIDENCE}

            content = text_parts[0].strip()
            content = self._strip_markdown_fence(content)
            parsed = json.loads(content)

            return {
                "type": parsed.get("type", _DEFAULT_TYPE),
                "confidence": parsed.get("confidence", _DEFAULT_CONFIDENCE),
            }

        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON from intervention classifier: %s", e)
            return {"type": _DEFAULT_TYPE, "confidence": _DEFAULT_CONFIDENCE}

    @staticmethod
    def _strip_markdown_fence(content: str) -> str:
        """Strip markdown code fence wrapper if present."""
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])
        return content.strip()

    @staticmethod
    def _parse_type(raw: Optional[str]) -> str:
        """Parse and validate intervention type string."""
        if not raw:
            return _DEFAULT_TYPE
        normalized = raw.strip().lower()
        valid_types = {t.value for t in InterventionType}
        if normalized in valid_types:
            return normalized
        logger.warning("Unknown intervention type: %s, defaulting to ADDITIVE", raw)
        return _DEFAULT_TYPE

    @staticmethod
    def _parse_confidence(raw: Optional[object]) -> float:
        """Parse confidence value, clamping to [0.0, 1.0]."""
        if raw is None:
            return _DEFAULT_CONFIDENCE
        try:
            value = float(raw)
            return max(0.0, min(1.0, value))
        except (ValueError, TypeError):
            return _DEFAULT_CONFIDENCE


# -- Singleton --

_classifier: Optional[InterventionClassifier] = None


def get_intervention_classifier() -> InterventionClassifier:
    """Get or create the global InterventionClassifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = InterventionClassifier()
    return _classifier
