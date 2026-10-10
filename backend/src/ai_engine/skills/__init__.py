"""Skills - prompt-level capability enhancements (same session, no extra API calls).

A Skill is NOT a sub-agent. It injects additional system prompt instructions
into the main agent's session, guiding it to use existing tools (web_search,
data tools) in a structured way for domain-specific tasks.

Key difference from sub-agents:
- Skill: same session, shared context, prompt-level guidance
- Sub-Agent: independent session, independent context, separate API calls
"""

from .base import Skill
from .registry import SkillRegistry, get_skill_registry

__all__ = [
    "Skill",
    "SkillRegistry",
    "get_skill_registry",
]
