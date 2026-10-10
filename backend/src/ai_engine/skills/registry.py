"""Skill registry — maps intent signals to Skill definitions."""

import logging
from typing import Dict, List, Optional

from .base import Skill

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Registry of all available skills.

    Skills are registered at startup and looked up at runtime based on
    intent classification signals (action type, lookup target, keywords).
    """

    def __init__(self) -> None:
        self._skills: Dict[str, Skill] = {}
        self._action_map: Dict[str, List[str]] = {}  # action -> [skill_names]
        self._keyword_map: Dict[str, str] = {}  # keyword -> skill_name

    def register(
        self,
        skill: Skill,
        trigger_actions: Optional[List[str]] = None,
        trigger_keywords: Optional[List[str]] = None,
    ) -> None:
        """Register a skill with its trigger conditions.

        Args:
            skill: The Skill definition
            trigger_actions: ActionType values that activate this skill
                           (e.g. ["plan"] for travel planning)
            trigger_keywords: Keywords in user input that activate this skill
                            (e.g. ["旅行", "出差", "攻略"])
        """
        self._skills[skill.name] = skill

        for action in (trigger_actions or []):
            action_lower = action.lower()
            if action_lower not in self._action_map:
                self._action_map[action_lower] = []
            self._action_map[action_lower].append(skill.name)

        for keyword in (trigger_keywords or []):
            self._keyword_map[keyword] = skill.name

        logger.info(
            "Registered skill '%s' (actions=%s, keywords=%d)",
            skill.name,
            trigger_actions or [],
            len(trigger_keywords or []),
        )

    def get(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return self._skills.get(name)

    def resolve(
        self,
        action: str,
        user_input: str,
    ) -> Optional[Skill]:
        """Resolve the best matching skill for a given intent.

        Matching priority:
        1. Action type match + keyword confirmation
        2. Keyword-only match (fallback)

        Args:
            action: The classified ActionType value (e.g. "plan", "lookup")
            user_input: Raw user input for keyword matching

        Returns:
            The matching Skill, or None if no skill applies.
        """
        action_lower = action.lower()

        # Priority 1: Action match + keyword confirmation
        candidates = self._action_map.get(action_lower, [])
        for skill_name in candidates:
            skill = self._skills[skill_name]
            # Check if any trigger keyword appears in user input
            if self._has_keyword_match(skill_name, user_input):
                logger.debug(
                    "Skill '%s' matched via action='%s' + keyword",
                    skill_name, action_lower,
                )
                return skill

        # Priority 2: Keyword-only match
        for keyword, skill_name in self._keyword_map.items():
            if keyword in user_input:
                logger.debug(
                    "Skill '%s' matched via keyword='%s'",
                    skill_name, keyword,
                )
                return self._skills[skill_name]

        return None

    def _has_keyword_match(self, skill_name: str, user_input: str) -> bool:
        """Check if any keyword mapped to this skill appears in user input."""
        for keyword, mapped_name in self._keyword_map.items():
            if mapped_name == skill_name and keyword in user_input:
                return True
        return False

    def list_skills(self) -> List[str]:
        """List all registered skill names."""
        return list(self._skills.keys())


# ── Global singleton ──────────────────────────────────────────────────

_skill_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """Get or create the global skill registry.

    On first call, registers all built-in skills.
    """
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry()
        _register_builtin_skills(_skill_registry)
    return _skill_registry


def _register_builtin_skills(registry: SkillRegistry) -> None:
    """Register all built-in skills."""
    from .travel_search import TRAVEL_SEARCH_SKILL, TRAVEL_SEARCH_KEYWORDS
    from .travel_planning import TRAVEL_PLANNING_SKILL, TRAVEL_PLANNING_KEYWORDS

    registry.register(
        skill=TRAVEL_SEARCH_SKILL,
        trigger_actions=["lookup"],
        trigger_keywords=TRAVEL_SEARCH_KEYWORDS,
    )

    registry.register(
        skill=TRAVEL_PLANNING_SKILL,
        trigger_actions=["plan", "create"],
        trigger_keywords=TRAVEL_PLANNING_KEYWORDS,
    )
