"""Relationship decay and intimacy algorithms.

Canonical location. Moved from relationship_management/algorithms/relationship_decay.py.
"""
from datetime import date
from typing import Optional, Dict, List
from enum import Enum


class RelationshipCategory(str, Enum):
    """Relationship category for different scoring logic."""
    FAMILY = "family"  # 家人圈
    NETWORK = "network"  # 人脉圈


# Family relationship types (家人圈)
FAMILY_RELATION_TYPES = {
    "self", "spouse", "father", "mother", "parent", "son", "daughter", "child",
    "brother", "sister", "sibling", "grandfather_paternal", "grandmother_paternal",
    "grandfather_maternal", "grandmother_maternal", "grandparent", "grandson",
    "granddaughter", "grandchild", "uncle_paternal", "aunt_paternal",
    "uncle_maternal", "aunt_maternal", "uncle_aunt", "nephew", "niece",
    "nephew_niece", "cousin", "father_in_law", "mother_in_law", "parent_in_law",
    "son_in_law", "daughter_in_law", "child_in_law", "brother_in_law",
    "sister_in_law", "sibling_in_law", "spouse_grandfather_paternal",
    "spouse_grandmother_paternal", "spouse_grandfather_maternal",
    "spouse_grandmother_maternal", "spouse_uncle_paternal", "spouse_aunt_paternal",
    "spouse_uncle_maternal", "spouse_aunt_maternal"
}

# Network relationship types (人脉圈)
NETWORK_RELATION_TYPES = {
    "friend", "colleague", "classmate", "neighbor", "caregiver", "other"
}


class RelationshipDecayCalculator:
    """Calculate relationship maintenance thresholds and intimacy scores."""

    # Contact frequency thresholds by importance level
    CONTACT_THRESHOLDS = {
        5: 30,    # Very important: contact every 30 days
        4: 60,    # Important: every 60 days
        3: 90,    # Medium: every 90 days
        2: 180,   # Low: every 180 days
        1: 365,   # Very low: yearly contact OK
    }

    # Family intimacy thresholds (different from network)
    FAMILY_CONTACT_THRESHOLDS = {
        5: 14,    # Core family (parents, spouse, children): bi-weekly
        4: 30,    # Close family (siblings): monthly
        3: 60,    # Extended family (grandparents, uncles): bi-monthly
        2: 90,    # Distant family (cousins): quarterly
        1: 180,   # Remote family: semi-annually
    }

    # Relation type to default importance mapping
    RELATION_IMPORTANCE = {
        # Core family - highest importance
        "spouse": 5, "father": 5, "mother": 5, "parent": 5,
        "son": 5, "daughter": 5, "child": 5,
        # Close family
        "brother": 4, "sister": 4, "sibling": 4,
        "grandfather_paternal": 4, "grandmother_paternal": 4,
        "grandfather_maternal": 4, "grandmother_maternal": 4, "grandparent": 4,
        # Extended family
        "uncle_paternal": 3, "aunt_paternal": 3, "uncle_maternal": 3,
        "aunt_maternal": 3, "uncle_aunt": 3,
        "father_in_law": 3, "mother_in_law": 3, "parent_in_law": 3,
        # Distant family
        "cousin": 2, "nephew": 2, "niece": 2, "nephew_niece": 2,
        "brother_in_law": 2, "sister_in_law": 2, "sibling_in_law": 2,
        "grandson": 3, "granddaughter": 3, "grandchild": 3,
        "son_in_law": 3, "daughter_in_law": 3, "child_in_law": 3,
        # Network
        "friend": 3, "colleague": 2, "classmate": 2, "neighbor": 1,
        "caregiver": 4, "other": 1, "self": 5
    }

    def should_remind_contact(
        self,
        importance_level: int,
        last_interaction_date: date,
        today: Optional[date] = None
    ) -> bool:
        """Check if reminder is needed based on decay threshold."""
        if today is None:
            today = date.today()

        threshold_days = self.CONTACT_THRESHOLDS.get(importance_level, 90)
        days_since = (today - last_interaction_date).days

        return days_since >= threshold_days

    def calculate_decay_score(
        self,
        importance_level: int,
        last_interaction_date: date
    ) -> float:
        """
        Calculate relationship decay score (0-1).
        0 = no decay, 1 = maximum decay.
        """
        threshold = self.CONTACT_THRESHOLDS.get(importance_level, 90)
        days_since = (date.today() - last_interaction_date).days

        score = min(days_since / threshold, 1.0)
        return round(score, 2)

    def calculate_health_percentage(
        self,
        importance_level: int,
        last_interaction_date: date,
        favor_balance: int = 0
    ) -> int:
        """
        Calculate relationship health percentage (0-100).

        Factors:
        1. Contact frequency (70% weight) - based on decay
        2. Favor balance (30% weight) - positive balance = healthier
        """
        # Contact frequency component (70% weight)
        decay = self.calculate_decay_score(importance_level, last_interaction_date)
        contact_health = (1.0 - decay) * 70

        # Favor balance component (30% weight)
        if favor_balance == 0:
            favor_health = 30
        elif favor_balance > 0:
            favor_health = max(15, 30 - abs(favor_balance) * 5)
        else:
            favor_health = max(5, 30 - abs(favor_balance) * 10)

        total = int(contact_health + favor_health)
        return min(100, max(0, total))

    def get_health_bar(self, health_percentage: int, bar_length: int = 10) -> str:
        """Generate a visual health bar for display."""
        filled = int(bar_length * health_percentage / 100)
        empty = bar_length - filled
        return "\u2588" * filled + "\u2591" * empty + f" {health_percentage}%"

    @staticmethod
    def get_category(relation_type: str) -> RelationshipCategory:
        """Determine if relation is family or network."""
        if relation_type in FAMILY_RELATION_TYPES:
            return RelationshipCategory.FAMILY
        return RelationshipCategory.NETWORK

    def get_default_importance(self, relation_type: str) -> int:
        """Get default importance level for a relation type."""
        return self.RELATION_IMPORTANCE.get(relation_type, 2)

    def calculate_intimacy_score(
        self,
        relation_type: str,
        last_interaction_date: Optional[date],
        profile_completion: int = 0,
        important_dates_remembered: int = 0,
        total_important_dates: int = 0,
        care_actions_count: int = 0,
    ) -> Dict:
        """
        Calculate intimacy score for family members (家人圈).

        Formula: 亲密度 = 联络分(40%) + 关怀分(30%) + 了解分(30%)
        """
        importance = self.get_default_importance(relation_type)
        threshold = self.FAMILY_CONTACT_THRESHOLDS.get(importance, 60)

        # 1. Contact score (40%)
        if last_interaction_date:
            days_since = (date.today() - last_interaction_date).days
            contact_decay = min(days_since / threshold, 1.0)
            contact_score = (1.0 - contact_decay) * 40
        else:
            contact_score = 0

        # 2. Care score (30%) - based on remembered dates and care actions
        if total_important_dates > 0:
            dates_score = (important_dates_remembered / total_important_dates) * 15
        else:
            dates_score = 15  # Full score if no dates to remember

        # Care actions (max 15 points)
        care_score = min(care_actions_count * 3, 15)
        total_care_score = dates_score + care_score

        # 3. Understanding score (30%) - based on profile completion
        understanding_score = (profile_completion / 100) * 30

        total = int(contact_score + total_care_score + understanding_score)
        total = min(100, max(0, total))

        return {
            "total": total,
            "contact_score": round(contact_score, 1),
            "care_score": round(total_care_score, 1),
            "understanding_score": round(understanding_score, 1),
            "category": RelationshipCategory.FAMILY.value,
            "days_since_contact": (date.today() - last_interaction_date).days if last_interaction_date else None,
            "threshold_days": threshold
        }

    def calculate_network_health(
        self,
        importance_level: int,
        last_interaction_date: Optional[date],
        favor_balance: int = 0,
        mutual_introductions: int = 0
    ) -> Dict:
        """
        Calculate relationship health for network contacts (人脉圈).

        Formula: 健康度 = 联络分(50%) + 人情分(30%) + 互惠分(20%)
        """
        threshold = self.CONTACT_THRESHOLDS.get(importance_level, 90)

        # 1. Contact score (50%)
        if last_interaction_date:
            days_since = (date.today() - last_interaction_date).days
            contact_decay = min(days_since / threshold, 1.0)
            contact_score = (1.0 - contact_decay) * 50
        else:
            contact_score = 0

        # 2. Favor balance score (30%)
        if favor_balance == 0:
            favor_score = 30  # Balanced is best
        elif favor_balance > 0:
            favor_score = max(10, 30 - abs(favor_balance) * 2)
        else:
            favor_score = max(5, 30 - abs(favor_balance) * 3)

        # 3. Mutual benefit score (20%)
        mutual_score = min(mutual_introductions * 5, 20)

        total = int(contact_score + favor_score + mutual_score)
        total = min(100, max(0, total))

        return {
            "total": total,
            "contact_score": round(contact_score, 1),
            "favor_score": round(favor_score, 1),
            "mutual_score": round(mutual_score, 1),
            "category": RelationshipCategory.NETWORK.value,
            "days_since_contact": (date.today() - last_interaction_date).days if last_interaction_date else None,
            "threshold_days": threshold,
            "favor_balance": favor_balance
        }

    def get_health_status(self, score: int) -> Dict:
        """Get health status with color and label."""
        if score >= 90:
            return {"level": "excellent", "color": "#22C55E", "label": "关系稳固"}
        elif score >= 70:
            return {"level": "good", "color": "#84CC16", "label": "关系良好"}
        elif score >= 50:
            return {"level": "warning", "color": "#EAB308", "label": "需要维护"}
        elif score >= 30:
            return {"level": "attention", "color": "#F97316", "label": "亟需联络"}
        else:
            return {"level": "critical", "color": "#EF4444", "label": "关系危机"}

    def get_suggested_actions(
        self,
        relation_type: str,
        score: int,
        days_since_contact: Optional[int],
        upcoming_dates: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """Get suggested actions based on relationship status."""
        actions = []
        category = self.get_category(relation_type)

        # Contact suggestions
        if days_since_contact and days_since_contact > 14:
            if category == RelationshipCategory.FAMILY:
                actions.append({
                    "type": "contact",
                    "priority": "high" if days_since_contact > 30 else "medium",
                    "title": "打个电话问候",
                    "description": f"已有{days_since_contact}天未联络，建议问候近况",
                    "icon": "phone"
                })
            else:
                actions.append({
                    "type": "contact",
                    "priority": "high" if days_since_contact > 60 else "medium",
                    "title": "维护关系",
                    "description": f"已有{days_since_contact}天未联络，建议约见或问候",
                    "icon": "message"
                })

        # Upcoming date reminders
        if upcoming_dates:
            for d in upcoming_dates[:2]:
                days_until = d.get("days_until", 0)
                if days_until <= 7:
                    actions.append({
                        "type": "reminder",
                        "priority": "high",
                        "title": f"{d.get('title', '重要日期')}即将到来",
                        "description": f"还有{days_until}天，记得准备",
                        "icon": "calendar"
                    })

        # Score-based suggestions
        if score < 50:
            if category == RelationshipCategory.FAMILY:
                actions.append({
                    "type": "care",
                    "priority": "medium",
                    "title": "增进了解",
                    "description": "完善档案信息，记录偏好",
                    "icon": "heart"
                })
            else:
                actions.append({
                    "type": "favor",
                    "priority": "medium",
                    "title": "关系维护",
                    "description": "考虑送礼或帮忙引荐",
                    "icon": "gift"
                })

        return actions[:3]  # Return top 3 actions
