"""Data classes used by the curation service."""
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from ..schemas import UnconfirmedItem


class CurationResult:
    """Result of a curation operation."""

    def __init__(
        self,
        job_id: UUID,
        events_processed: int,
        events_curated: int,
        associations_created: int,
        unconfirmed_items: List[UnconfirmedItem],
        conflicts_detected: int = 0,
    ):
        self.job_id = job_id
        self.events_processed = events_processed
        self.events_curated = events_curated
        self.associations_created = associations_created
        self.unconfirmed_items = unconfirmed_items
        self.conflicts_detected = conflicts_detected


class RawEvent:
    """Intermediate representation of a raw event from any source."""

    def __init__(
        self,
        id: str,
        source_type: str,
        title: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        location: Optional[str] = None,
        description: Optional[str] = None,
        event_type: Optional[str] = None,
        participants: Optional[List[str]] = None,
    ):
        self.id = id
        self.source_type = source_type
        self.title = title
        self.start_time = start_time
        self.end_time = end_time
        self.location = location
        self.description = description
        self.event_type = event_type
        self.participants = participants or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_type": self.source_type,
            "title": self.title,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "location": self.location,
            "description": self.description,
            "event_type": self.event_type,
            "participants": self.participants,
        }
