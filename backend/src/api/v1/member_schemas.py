"""
Pydantic schemas for member-related API endpoints.

Shared across members.py, people.py, and user_services.py.
Split from members.py to keep file sizes under 800 lines.
"""
from typing import List, Optional
from pydantic import BaseModel, validator, ConfigDict


# Request/Response Models
class LocationInfo(BaseModel):
    """Location information."""
    lat: Optional[float] = None  # Latitude
    lng: Optional[float] = None  # Longitude
    address: Optional[str] = None  # Human-readable address


class CreateMemberRequest(BaseModel):
    """Create member request."""
    name: str
    nickname: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[str] = None  # Frontend uses birth_date
    relation: Optional[str] = None  # Frontend relation field (not stored in member table)
    phone: Optional[str] = None
    email: Optional[str] = None
    id_card: Optional[str] = None  # Added to match frontend
    # Location fields
    locations: Optional[dict] = None  # {"home": LocationInfo, "work": LocationInfo, ...}
    default_location_type: Optional[str] = None  # "home", "work", etc.

    @validator('gender')
    def validate_gender(cls, v):
        """Ensure gender is lowercase."""
        if v:
            return v.lower()
        return v

    @validator('relation')
    def validate_relation(cls, v):
        """Normalize relation to lowercase to match enum values."""
        if v:
            return v.lower()
        return v


class MemberResponse(BaseModel):
    """Member response."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    nickname: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[str] = None  # Frontend expects birth_date
    age: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    id_card: Optional[str] = None
    relation: Optional[str] = "other"  # Default relation
    profile_completion: int = 0
    # Location fields
    locations: Optional[dict] = None  # {"home": LocationInfo, "work": LocationInfo, ...}
    default_location_type: Optional[str] = None  # "home", "work", etc.
    # Professional fields
    current_company: Optional[str] = None
    current_position: Optional[str] = None
    # PersonProfile fields (injected from person_profiles table)
    favor_balance: float = 0.0
    last_mentioned_at: Optional[str] = None
    importance: float = 0.0
    organization: Optional[str] = None


class MemberDetailResponse(MemberResponse):
    """Detailed member response with relations."""
    occupation: Optional[str]
    workplace: Optional[str]
    tags: Optional[List[str]]
    current_company: Optional[str] = None
    current_position: Optional[str] = None
    created_at: str
    updated_at: str


# Work History Request/Response Models
class CreateWorkHistoryRequest(BaseModel):
    """Create work history request."""
    company_name: str
    position: Optional[str] = None
    department: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    notes: Optional[str] = None


class WorkHistoryResponse(BaseModel):
    """Work history response."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    member_id: str
    family_id: str
    company_name: str
    position: Optional[str] = None
    department: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool
    notes: Optional[str] = None
    created_at: str
    updated_at: str


# Professional Relation Request/Response Models
class CreateProfessionalRelationRequest(BaseModel):
    """Create professional relation request."""
    from_member_id: str
    to_member_id: str
    relation_type: str
    company_name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = True
    notes: Optional[str] = None

    @validator('relation_type')
    def validate_relation_type(cls, v):
        """Normalize relation type."""
        if v:
            return v.lower()
        return v


class ProfessionalRelationResponse(BaseModel):
    """Professional relation response."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    family_id: str
    from_member_id: str
    to_member_id: str
    relation_type: str
    relation_type_label: str
    company_name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool
    notes: Optional[str] = None
    from_member_name: Optional[str] = None
    to_member_name: Optional[str] = None
    created_at: str
    updated_at: str


class ProfessionalRelationTypeResponse(BaseModel):
    """Professional relation type option."""
    value: str
    label: str


class MemberProfileExtResponse(BaseModel):
    """Extended member profile response (sizes/health/preferences)."""
    member_id: str
    preferences: Optional[dict] = None
    habits: Optional[dict] = None
    health_summary: Optional[str] = None
    personality_traits: Optional[dict] = None
    special_notes: Optional[str] = None


class MemberProfileExtRequest(BaseModel):
    """Update extended member profile."""
    preferences: Optional[dict] = None
    habits: Optional[dict] = None
    health_summary: Optional[str] = None
    personality_traits: Optional[dict] = None
    special_notes: Optional[str] = None


class PersonProfileResponse(BaseModel):
    """Person profile response."""
    id: str
    family_id: str
    name: str
    member_id: Optional[str] = None
    aliases: Optional[List[str]] = None
    relationship: Optional[str] = None
    relationship_context: Optional[str] = None
    organization: Optional[str] = None
    location: Optional[str] = None
    preferences: Optional[dict] = None
    favor_balance: float = 0.0
    mention_count: int = 0
    last_mentioned_at: Optional[str] = None
    importance: float = 0.0
    needs_contact: bool = False
    owes_favor: bool = False
    status: str = "active"
