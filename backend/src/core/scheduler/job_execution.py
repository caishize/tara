"""
Job Execution SQLAlchemy Models

Database models for storing scheduler execution history and configuration.
"""

from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

from ...db.session import Base


class JobExecutionModel(Base):
    """
    SQLAlchemy model for job execution history.

    Stores a record for each job execution, including status,
    timing, and any error information.
    """

    __tablename__ = "job_executions"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Job Identification
    job_name = Column(String(100), nullable=False)
    scheduler_name = Column(String(100), nullable=False)

    # Execution Details
    status = Column(String(20), nullable=False)  # pending, running, completed, failed, cancelled, timeout
    trigger_type = Column(String(20), nullable=False)  # scheduled, manual

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Error Information
    error_message = Column(Text, nullable=True)
    error_traceback = Column(Text, nullable=True)

    # Result
    result_summary = Column(JSONB, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Indexes for efficient querying
    __table_args__ = (
        Index("idx_job_executions_job", "job_name", "created_at"),
        Index("idx_job_executions_scheduler", "scheduler_name", "created_at"),
        Index("idx_job_executions_status", "status", "created_at"),
    )

    def __repr__(self):
        return f"<JobExecution(id={self.id}, job={self.job_name}, status={self.status})>"


class SchedulerConfigModel(Base):
    """
    SQLAlchemy model for scheduler configuration.

    Stores persistent configuration for schedulers, allowing
    runtime updates without code changes.
    """

    __tablename__ = "scheduler_configs"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Configuration
    name = Column(String(100), unique=True, nullable=False)
    scheduler_type = Column(String(20), nullable=False)  # interval, cron
    config = Column(JSONB, nullable=False)  # {"interval_seconds": 60} or {"cron_expression": "0 3 * * *"}
    is_enabled = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<SchedulerConfig(name={self.name}, type={self.scheduler_type}, enabled={self.is_enabled})>"
