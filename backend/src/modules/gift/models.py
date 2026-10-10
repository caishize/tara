"""Gift module SQLAlchemy models — re-export hub.

All model classes and enums are defined in sub-modules and re-exported here
so that existing ``from .models import X`` imports continue to work.

Sub-modules:
    models_enums.py           — shared enum definitions
    models_recommendation.py  — recommendation / task / preference / history models
    models_trending.py        — trending gift / occasion / data-source models
"""
# Enums
from .models_enums import (  # noqa: F401
    DateType,
    FeedbackRating,
    GiftCategory,
    GiftType,
    OccasionType,
    RecommendStatus,
    TaskStatus,
    TriggerSource,
    UpdateStatus,
    WarningLevel,
)

# Recommendation-side models
from .models_recommendation import (  # noqa: F401
    GiftConversationContext,
    GiftHistory,
    GiftPreference,
    GiftRecommendation,
    GiftTask,
    MemberGiftMemory,
)

# Trending-side models
from .models_trending import (  # noqa: F401
    DataSource,
    Occasion,
    OccasionGift,
    TrendingGift,
    UpdateLog,
    UserGiftSave,
)

__all__ = [
    # Enums
    "DateType",
    "FeedbackRating",
    "GiftCategory",
    "GiftType",
    "OccasionType",
    "RecommendStatus",
    "TaskStatus",
    "TriggerSource",
    "UpdateStatus",
    "WarningLevel",
    # Recommendation models
    "GiftConversationContext",
    "GiftHistory",
    "GiftPreference",
    "GiftRecommendation",
    "GiftTask",
    "MemberGiftMemory",
    # Trending models
    "DataSource",
    "Occasion",
    "OccasionGift",
    "TrendingGift",
    "UpdateLog",
    "UserGiftSave",
]
