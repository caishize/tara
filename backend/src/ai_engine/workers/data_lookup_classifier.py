"""
Data Lookup Types and router-target mapping.

DataLookupType is used by DataLookupService for routing queries.
"""

from enum import Enum

from ..router.types import LookupTarget


class DataLookupType(str, Enum):
    """Types of data lookups that FastWorker can handle."""
    TASK = "task"
    REMINDER = "reminder"
    TODAY = "today"
    FAMILY_MEMBER = "family_member"
    SCHEDULE = "schedule"
    TRIP = "trip"
    UNKNOWN = "unknown"


# Mapping from LookupTarget (router) to DataLookupType (service)
LOOKUP_TARGET_TO_TYPE = {
    LookupTarget.TASK: DataLookupType.TASK,
    LookupTarget.REMINDER: DataLookupType.REMINDER,
    LookupTarget.SCHEDULE: DataLookupType.SCHEDULE,
    LookupTarget.TRIP: DataLookupType.TRIP,
    LookupTarget.MEMBER: DataLookupType.FAMILY_MEMBER,
    LookupTarget.TODAY: DataLookupType.TODAY,
    LookupTarget.UNKNOWN: DataLookupType.UNKNOWN,
}


def lookup_target_to_type(target: LookupTarget) -> DataLookupType:
    """Convert a LookupTarget enum to DataLookupType."""
    return LOOKUP_TARGET_TO_TYPE.get(target, DataLookupType.UNKNOWN)
