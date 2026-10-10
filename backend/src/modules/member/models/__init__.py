"""Member module models package.

Canonical model definitions for member-related tables.
"""
from .enums import (
    Gender,
    ProfessionalRelationType,
    ProfileStatus,
    RelationType,
    RelationshipType,
)
from .family import Family
from .member import GenderEnumType, Member, MemberProfile, MemberRelation
from .user import User
from .person_profile import PersonProfile
from .relationship import ProactiveInsight, RelationshipEdge
from .professional import ProfessionalRelation, WorkHistory
from .device_token import DeviceToken
from .connection import UserDataConnection

__all__ = [
    # Enums
    "Gender",
    "ProfessionalRelationType",
    "ProfileStatus",
    "RelationType",
    "RelationshipType",
    # Family
    "Family",
    # Member tables
    "GenderEnumType",
    "Member",
    "MemberProfile",
    "MemberRelation",
    # User
    "User",
    # Person profile
    "PersonProfile",
    # Relationship graph
    "ProactiveInsight",
    "RelationshipEdge",
    # Professional
    "ProfessionalRelation",
    "WorkHistory",
    # Device token
    "DeviceToken",
    # Data connections
    "UserDataConnection",
]
