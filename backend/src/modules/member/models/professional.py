"""ProfessionalRelation and WorkHistory ORM models."""
import uuid

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey, Index, String, Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ....db.session import Base
from .enums import ProfessionalRelationType


class ProfessionalRelation(Base):
    """Professional relationship entity."""

    __tablename__ = "professional_relations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    from_member_id = Column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_member_id = Column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    relation_type = Column(
        Enum(
            ProfessionalRelationType,
            name="professional_relation_type_enum",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    company_name = Column(String(200), nullable=True)

    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    is_current = Column(Boolean, nullable=False, default=True)

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    from_member = relationship(
        "Member", foreign_keys=[from_member_id], back_populates="professional_relations_from"
    )
    to_member = relationship(
        "Member", foreign_keys=[to_member_id], back_populates="professional_relations_to"
    )

    __table_args__ = (
        Index("idx_prof_rel_from_member", "from_member_id"),
        Index("idx_prof_rel_to_member", "to_member_id"),
        Index("idx_prof_rel_family", "family_id"),
        Index("idx_prof_rel_company", "company_name"),
        Index("idx_prof_rel_type", "relation_type"),
        Index("idx_prof_rel_current", "from_member_id", "is_current"),
    )

    def __repr__(self):
        return (
            f"<ProfessionalRelation(id={self.id}, from={self.from_member_id}, "
            f"to={self.to_member_id}, type={self.relation_type})>"
        )

    @property
    def relation_type_display(self) -> str:
        """Get display text for relation type in Chinese."""
        display_map = {
            ProfessionalRelationType.BOSS: "上级",
            ProfessionalRelationType.SUBORDINATE: "下属",
            ProfessionalRelationType.PEER: "同事",
            ProfessionalRelationType.MENTOR: "导师",
            ProfessionalRelationType.MENTEE: "学员",
            ProfessionalRelationType.CLIENT: "客户",
            ProfessionalRelationType.VENDOR: "供应商",
            ProfessionalRelationType.PARTNER: "合作伙伴",
            ProfessionalRelationType.OTHER: "其他",
        }
        return display_map.get(self.relation_type, "其他")


class WorkHistory(Base):
    """Work history entity."""

    __tablename__ = "work_histories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    member_id = Column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    company_name = Column(String(200), nullable=False)
    position = Column(String(100), nullable=True)
    department = Column(String(100), nullable=True)

    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    is_current = Column(Boolean, nullable=False, default=False)

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    member = relationship("Member", back_populates="work_histories")

    __table_args__ = (
        Index("idx_work_history_member", "member_id"),
        Index("idx_work_history_family", "family_id"),
        Index("idx_work_history_company", "company_name"),
        Index("idx_work_history_current", "member_id", "is_current"),
    )

    def __repr__(self):
        return f"<WorkHistory(id={self.id}, member_id={self.member_id}, company={self.company_name})>"
