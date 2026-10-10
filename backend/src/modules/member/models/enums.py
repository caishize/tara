"""Enums for member module."""
from enum import Enum as PyEnum


class Gender(str, PyEnum):
    """Gender enum."""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNSPECIFIED = "unspecified"


class RelationType(str, PyEnum):
    """Relationship type enum."""
    # Self
    SELF = "self"

    # Core family relationships
    SPOUSE = "spouse"
    FATHER = "father"
    MOTHER = "mother"
    PARENT = "parent"
    SON = "son"
    DAUGHTER = "daughter"
    CHILD = "child"
    BROTHER = "brother"
    SISTER = "sister"
    SIBLING = "sibling"

    # Grandparents - Paternal
    GRANDFATHER_PATERNAL = "grandfather_paternal"
    GRANDMOTHER_PATERNAL = "grandmother_paternal"
    # Grandparents - Maternal
    GRANDFATHER_MATERNAL = "grandfather_maternal"
    GRANDMOTHER_MATERNAL = "grandmother_maternal"
    GRANDPARENT = "grandparent"

    # Grandchildren
    GRANDSON = "grandson"
    GRANDDAUGHTER = "granddaughter"
    GRANDCHILD = "grandchild"

    # Uncles/Aunts - Paternal
    UNCLE_PATERNAL = "uncle_paternal"
    AUNT_PATERNAL = "aunt_paternal"
    # Uncles/Aunts - Maternal
    UNCLE_MATERNAL = "uncle_maternal"
    AUNT_MATERNAL = "aunt_maternal"
    UNCLE_AUNT = "uncle_aunt"

    # Nephews/Nieces
    NEPHEW = "nephew"
    NIECE = "niece"
    NEPHEW_NIECE = "nephew_niece"

    # Cousins
    COUSIN = "cousin"

    # In-law relationships
    FATHER_IN_LAW = "father_in_law"
    MOTHER_IN_LAW = "mother_in_law"
    PARENT_IN_LAW = "parent_in_law"
    SON_IN_LAW = "son_in_law"
    DAUGHTER_IN_LAW = "daughter_in_law"
    CHILD_IN_LAW = "child_in_law"
    BROTHER_IN_LAW = "brother_in_law"
    SISTER_IN_LAW = "sister_in_law"
    SIBLING_IN_LAW = "sibling_in_law"

    # Spouse's extended family - Grandparents
    SPOUSE_GRANDFATHER_PATERNAL = "spouse_grandfather_paternal"
    SPOUSE_GRANDMOTHER_PATERNAL = "spouse_grandmother_paternal"
    SPOUSE_GRANDFATHER_MATERNAL = "spouse_grandfather_maternal"
    SPOUSE_GRANDMOTHER_MATERNAL = "spouse_grandmother_maternal"

    # Spouse's extended family - Uncles/Aunts
    SPOUSE_UNCLE_PATERNAL = "spouse_uncle_paternal"
    SPOUSE_AUNT_PATERNAL = "spouse_aunt_paternal"
    SPOUSE_UNCLE_MATERNAL = "spouse_uncle_maternal"
    SPOUSE_AUNT_MATERNAL = "spouse_aunt_maternal"

    # Non-family relationships
    FRIEND = "friend"
    COLLEAGUE = "colleague"
    CLASSMATE = "classmate"
    NEIGHBOR = "neighbor"
    CAREGIVER = "caregiver"
    OTHER = "other"


# Relationship types that count as "family" (血缘/姻亲关系)
NON_FAMILY_RELATION_TYPES = frozenset({
    RelationType.FRIEND,
    RelationType.COLLEAGUE,
    RelationType.CLASSMATE,
    RelationType.NEIGHBOR,
    RelationType.OTHER,
})

FAMILY_RELATION_TYPES = frozenset(
    rt for rt in RelationType if rt not in NON_FAMILY_RELATION_TYPES
)


class SessionStatus(str, PyEnum):
    """Conversation session status."""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class ProfessionalRelationType(str, PyEnum):
    """Professional relationship type."""
    BOSS = "boss"
    SUBORDINATE = "subordinate"
    PEER = "peer"
    MENTOR = "mentor"
    MENTEE = "mentee"
    CLIENT = "client"
    VENDOR = "vendor"
    PARTNER = "partner"
    OTHER = "other"


class ProfileStatus(str, PyEnum):
    """Status of a person profile."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    MERGED = "merged"


class RelationshipType(str, PyEnum):
    """Types of relationships between persons in the knowledge graph."""
    COLLEAGUE = "colleague"
    FRIEND = "friend"
    FAMILY = "family"
    CLASSMATE = "classmate"
    NEIGHBOR = "neighbor"
    BUSINESS = "business"
    KNOWS = "knows"
    INTRODUCED_BY = "introduced_by"
    REPORTS_TO = "reports_to"
