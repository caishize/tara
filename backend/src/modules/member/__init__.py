"""Member module - unified person management core.

Manages family members and external contacts (colleagues, friends, etc.)
via a two-layer model: members (family core) + person_profiles (all people).
"""

from .interface import (
    IMemberService,
    IPersonService,
    IProfileEnrichment,
    FamilyInfo,
    MemberInfo,
    MemberProfileInfo,
    PersonProfile,
)
from .member_service import MemberService
from .person_service import PersonService
from .profile_enrichment import ProfileEnrichment

__all__ = [
    "IMemberService",
    "IPersonService",
    "IProfileEnrichment",
    "FamilyInfo",
    "MemberInfo",
    "MemberProfileInfo",
    "PersonProfile",
    "MemberService",
    "PersonService",
    "ProfileEnrichment",
]
