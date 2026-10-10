"""Skill base definition — intent-triggered context enhancement."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Skill:
    """Immutable skill definition that enhances the main agent with
    domain-specific instructions when a matching intent is detected.

    A Skill is injected into the main agent's system prompt at runtime.
    It does NOT create a separate session — it enriches the existing one.

    Attributes:
        name: Unique identifier (e.g. "travel_planning")
        description: Human-readable description for logging/debugging
        system_prompt_addon: Markdown instructions appended to the system prompt
        required_tools: Tool names that MUST be available for this skill.
                       The agent factory will verify these exist.
        output_format_hint: Optional hint appended to guide output structure.
        max_turns_override: If set, overrides the default max_turns for
                           this skill's execution (e.g. travel planning
                           may need more tool-call rounds).
        builtin_tools: Additional builtin tools needed (e.g. WebSearch).
        metadata: Arbitrary metadata for debugging/analytics.
    """

    name: str
    description: str
    system_prompt_addon: str
    required_tools: List[str] = field(default_factory=list)
    output_format_hint: Optional[str] = None
    max_turns_override: Optional[int] = None
    builtin_tools: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    def build_prompt_section(self) -> str:
        """Build the full prompt section to inject into the system prompt."""
        parts = [
            f"\n\n## 技能激活: {self.description}\n",
            self.system_prompt_addon,
        ]
        if self.output_format_hint:
            parts.append(f"\n\n### 输出格式要求\n{self.output_format_hint}")
        return "\n".join(parts)
