"""Gift dedup analyzer — duplicate gift detection and analysis.

Analyzes gift history to warn about repeated categories and suggest exclusions.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .recommendation_repositories import HistoryRepository


@dataclass
class DedupWarning:
    level: str  # info, warning, critical
    category: str
    message: str
    count: int = 0
    last_date: Optional[date] = None
    similar_items: List[str] = field(default_factory=list)


@dataclass
class DedupAnalysis:
    category_stats: Dict[str, Dict[str, Any]]
    excluded_categories: List[str]
    warnings: List[DedupWarning]
    total_history_count: int
    time_weighted_stats: Dict[str, float]


class DedupAnalyzer:
    """Dedup analysis for gift history."""

    TIME_WEIGHTS = {1: 1.0, 2: 0.5, 3: 0.25}
    HIGH_FREQUENCY_THRESHOLD = 3
    RECENT_REPEAT_THRESHOLD = 2

    def __init__(self, session: AsyncSession):
        self.session = session
        self.history_repo = HistoryRepository(session)

    async def analyze(
        self,
        member_id: UUID,
        family_id: UUID,
        occasion: Optional[str] = None,
        years_back: int = 3,
    ) -> DedupAnalysis:
        history = await self.history_repo.get_by_recipient(member_id, years_back=years_back)
        category_stats: Dict[str, Dict[str, Any]] = {}
        time_weighted_stats: Dict[str, float] = {}
        today = date.today()

        for h in history:
            cat = h.gift_category
            if cat not in category_stats:
                category_stats[cat] = {
                    "count": 0, "last_date": None, "items": [], "occasions": set(), "years": {}
                }
            stats = category_stats[cat]
            stats["count"] += 1
            stats["items"].append(h.gift_name)
            stats["occasions"].add(h.occasion)
            if stats["last_date"] is None or h.occasion_date > stats["last_date"]:
                stats["last_date"] = h.occasion_date
            years_ago = (today - h.occasion_date).days // 365 + 1
            stats["years"][years_ago] = stats["years"].get(years_ago, 0) + 1

        for cat, stats in category_stats.items():
            weighted = sum(
                count * self.TIME_WEIGHTS.get(year, 0.1) for year, count in stats["years"].items()
            )
            time_weighted_stats[cat] = round(weighted, 2)
            stats["occasions"] = list(stats["occasions"])

        excluded: List[str] = []
        warnings: List[DedupWarning] = []
        for cat, stats in category_stats.items():
            count = stats["count"]
            last_date = stats["last_date"]
            days_since = (today - last_date).days if last_date else 999
            if count >= self.HIGH_FREQUENCY_THRESHOLD:
                excluded.append(cat)
                warnings.append(DedupWarning(
                    level="critical", category=cat,
                    message=f"该类别已送过{count}次，强烈建议尝试其他类别",
                    count=count, last_date=last_date, similar_items=stats["items"][-3:],
                ))
            elif days_since < 365 and count >= self.RECENT_REPEAT_THRESHOLD:
                excluded.append(cat)
                warnings.append(DedupWarning(
                    level="warning", category=cat,
                    message=f"该类别1年内已送过{count}次，建议考虑其他选择",
                    count=count, last_date=last_date, similar_items=stats["items"][-2:],
                ))
            elif count >= 1:
                warnings.append(DedupWarning(
                    level="info", category=cat, message=f"该类别已送过{count}次",
                    count=count, last_date=last_date,
                ))

        level_order = {"critical": 0, "warning": 1, "info": 2}
        warnings.sort(key=lambda w: level_order.get(w.level, 3))
        return DedupAnalysis(
            category_stats=category_stats, excluded_categories=excluded,
            warnings=warnings, total_history_count=len(history),
            time_weighted_stats=time_weighted_stats,
        )

    def to_dict(self, analysis: DedupAnalysis) -> Dict[str, Any]:
        return {
            "category_stats": analysis.category_stats,
            "excluded_categories": analysis.excluded_categories,
            "warnings": [
                {
                    "level": w.level, "category": w.category, "message": w.message,
                    "count": w.count,
                    "last_date": w.last_date.isoformat() if w.last_date else None,
                    "similar_items": w.similar_items,
                }
                for w in analysis.warnings
            ],
            "total_history_count": analysis.total_history_count,
            "time_weighted_stats": analysis.time_weighted_stats,
        }
