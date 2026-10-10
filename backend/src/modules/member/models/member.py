"""Member, MemberProfile, MemberRelation ORM models."""
import uuid
from datetime import date
from typing import Optional

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, Enum, Float,
    ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import UserDefinedType

from ....db.session import Base
from .enums import RelationType


class GenderEnumType(UserDefinedType):
    """PostgreSQL gender_enum type."""
    cache_ok = True

    def get_col_spec(self, **kw):
        return "gender_enum"

    def bind_processor(self, dialect):
        def process(value):
            if value:
                return str(value).lower()
            return value
        return process

    def result_processor(self, dialect, coltype):
        def process(value):
            return value
        return process


class Member(Base):
    """Member entity."""

    __tablename__ = "members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    created_by = Column(UUID(as_uuid=True), nullable=False)

    name = Column(String(100), nullable=False)
    nickname = Column(String(50), nullable=True)
    gender = Column(GenderEnumType, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    age = Column(Integer, nullable=True)

    # RESTRICTED fields (encrypted)
    phone = Column(Text, nullable=True)
    email = Column(Text, nullable=True)
    id_card = Column(Text, nullable=True)
    address = Column(Text, nullable=True)

    avatar_url = Column(String(500), nullable=True)
    tags = Column(JSONB, nullable=True, default=list)

    locations = Column(JSONB, nullable=True, default=dict)
    default_location_type = Column(String(50), nullable=True, default="home")

    profile_completion = Column(Integer, nullable=False, default=0)

    # Trust level (L0-L3) for progressive feature unlock
    trust_level = Column(Integer, nullable=False, default=0, server_default="0")
    trust_updated_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)

    profile = relationship("MemberProfile", back_populates="member", uselist=False, cascade="all, delete-orphan")
    relations_from = relationship(
        "MemberRelation",
        foreign_keys="MemberRelation.from_member_id",
        back_populates="from_member",
        cascade="all, delete-orphan",
    )
    relations_to = relationship(
        "MemberRelation",
        foreign_keys="MemberRelation.to_member_id",
        back_populates="to_member",
        cascade="all, delete-orphan",
    )
    work_histories = relationship(
        "WorkHistory", back_populates="member", cascade="all, delete-orphan"
    )
    professional_relations_from = relationship(
        "ProfessionalRelation",
        foreign_keys="ProfessionalRelation.from_member_id",
        back_populates="from_member",
        cascade="all, delete-orphan",
    )
    professional_relations_to = relationship(
        "ProfessionalRelation",
        foreign_keys="ProfessionalRelation.to_member_id",
        back_populates="to_member",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "profile_completion >= 0 AND profile_completion <= 100",
            name="check_profile_completion",
        ),
        CheckConstraint("age >= 0 AND age <= 150", name="check_age_range"),
        Index(
            "uq_family_id_card",
            "family_id", "id_card",
            unique=True,
            postgresql_where=((id_card.isnot(None)) & (is_deleted == False)),
        ),
        Index("idx_member_family", "family_id", "is_deleted"),
        Index("idx_member_phone", "phone", postgresql_where=(phone.isnot(None))),
        Index(
            "idx_member_name_gin", "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )

    def __repr__(self):
        return f"<Member(id={self.id}, name={self.name}, family_id={self.family_id})>"

    @property
    def primary_location(self) -> Optional[str]:
        """Extract primary location address from the locations JSONB field."""
        if not self.locations or not isinstance(self.locations, dict):
            return None
        loc_type = self.default_location_type or "home"
        loc_data = self.locations.get(loc_type)
        if not loc_data:
            loc_data = next(iter(self.locations.values()), None)
        if loc_data and isinstance(loc_data, dict):
            return loc_data.get("address") or loc_data.get("city")
        return None

    def calculate_age(self) -> Optional[int]:
        """Calculate age from date of birth."""
        if not self.date_of_birth:
            return None
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )


class MemberProfile(Base):
    """MemberProfile entity."""

    __tablename__ = "member_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id = Column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )

    preferences = Column(JSONB, nullable=True)
    habits = Column(JSONB, nullable=True)
    health_summary = Column(Text, nullable=True)
    personality_traits = Column(JSONB, nullable=True)
    special_notes = Column(Text, nullable=True)

    embedding = Column(ARRAY(item_type=Float, dimensions=1536), nullable=True)

    last_enriched_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    member = relationship("Member", back_populates="profile")

    __table_args__ = (
        UniqueConstraint("member_id", name="uq_member_profile"),
        Index("idx_profile_preferences_gin", "preferences", postgresql_using="gin"),
    )

    def __repr__(self):
        return f"<MemberProfile(member_id={self.member_id})>"

    def to_searchable_text(self) -> str:
        """Convert profile to searchable text for embedding."""
        parts = []
        if self.member:
            parts.append(f"姓名: {self.member.name}")
        if self.preferences:
            parts.append(f"偏好: {str(self.preferences)}")
        if self.habits:
            parts.append(f"习惯: {str(self.habits)}")
        if self.health_summary:
            parts.append(f"健康: {self.health_summary}")
        if self.personality_traits:
            parts.append(f"性格: {str(self.personality_traits)}")
        return " ".join(parts)


class MemberRelation(Base):
    """MemberRelation entity."""

    __tablename__ = "member_relations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    from_member_id = Column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_member_id = Column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
    )

    relation_type = Column(
        Enum(
            RelationType,
            name="relation_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    intimacy_level = Column(Integer, nullable=False, default=5)
    notes = Column(Text, nullable=True)
    verified = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    from_member = relationship("Member", foreign_keys=[from_member_id], back_populates="relations_from")
    to_member = relationship("Member", foreign_keys=[to_member_id], back_populates="relations_to")

    __table_args__ = (
        CheckConstraint("from_member_id != to_member_id", name="check_no_self_relation"),
        CheckConstraint("intimacy_level >= 1 AND intimacy_level <= 10", name="check_intimacy_range"),
        UniqueConstraint("from_member_id", "to_member_id", "relation_type", name="uq_relation"),
        Index("idx_relation_from", "from_member_id", "relation_type"),
        Index("idx_relation_to", "to_member_id", "relation_type"),
        Index("idx_relation_family", "family_id"),
    )

    def __repr__(self):
        return f"<MemberRelation(from={self.from_member_id}, to={self.to_member_id}, type={self.relation_type})>"
