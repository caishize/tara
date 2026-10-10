"""
Timezone utilities for the Secretary application.

All timestamps are stored in UTC in the database.
User-facing display and parsing uses user-configured timezone (default: system timezone).

Usage:
    from src.core.utils.timezone import utc_now, to_utc, to_local, get_user_timezone

    # Get current UTC time
    now = utc_now()

    # Convert local time to UTC for storage
    utc_dt = to_utc(local_dt, user_tz)

    # Convert UTC to local for display
    local_dt = to_local(utc_dt, user_tz)

    # Group by local date
    local_date = to_local_date(utc_dt, user_tz)
"""
from contextvars import ContextVar, Token
from datetime import datetime, date, timezone, timedelta
from typing import Optional, Tuple, Union
from zoneinfo import ZoneInfo

# Default timezone for users (configurable per user in the future)
DEFAULT_TIMEZONE_NAME = "Asia/Shanghai"
DEFAULT_TIMEZONE = ZoneInfo(DEFAULT_TIMEZONE_NAME)

# UTC timezone constant
UTC = timezone.utc


# Request/task-local timezone override. Used by curation pipelines to ensure
# all helper calls resolve to the same user/family timezone.
_ACTIVE_TIMEZONE: ContextVar[Optional[ZoneInfo]] = ContextVar(
    "active_timezone",
    default=None,
)


def set_active_timezone(user_tz: Union[ZoneInfo, str, None]) -> Optional[Token]:
    """Set task-local timezone override and return context token."""
    if user_tz is None:
        return _ACTIVE_TIMEZONE.set(None)
    if isinstance(user_tz, str):
        try:
            user_tz = ZoneInfo(user_tz)
        except Exception:
            user_tz = DEFAULT_TIMEZONE
    return _ACTIVE_TIMEZONE.set(user_tz)


def reset_active_timezone(token: Optional[Token]) -> None:
    """Reset task-local timezone override using a token from set_active_timezone."""
    if token is None:
        return
    _ACTIVE_TIMEZONE.reset(token)


def utc_now() -> datetime:
    """
    Get current datetime in UTC with timezone info.

    Use this instead of datetime.now() or datetime.utcnow().

    Returns:
        datetime: Current UTC datetime with tzinfo=UTC
    """
    return datetime.now(UTC)


def get_user_timezone(user_id: Optional[str] = None) -> ZoneInfo:
    """
    Get timezone for a specific user.

    TODO: Read from user settings in database.
    Currently returns default timezone (Asia/Shanghai).

    Args:
        user_id: Optional user ID to look up timezone settings

    Returns:
        ZoneInfo: User's configured timezone
    """
    active_tz = _ACTIVE_TIMEZONE.get()
    if active_tz is not None:
        return active_tz

    # TODO: Implement user timezone lookup from database
    # user_settings = await get_user_settings(user_id)
    # if user_settings and user_settings.timezone:
    #     return ZoneInfo(user_settings.timezone)
    return DEFAULT_TIMEZONE


def to_utc(local_dt: datetime, user_tz: Optional[ZoneInfo] = None) -> datetime:
    """
    Convert local datetime to UTC for storage.

    Args:
        local_dt: Local datetime (may or may not have tzinfo)
        user_tz: User's timezone (default: DEFAULT_TIMEZONE)

    Returns:
        datetime: UTC datetime with tzinfo=UTC
    """
    if user_tz is None:
        user_tz = DEFAULT_TIMEZONE

    if local_dt.tzinfo is None:
        # Assume the naive datetime is in user's timezone
        local_dt = local_dt.replace(tzinfo=user_tz)

    return local_dt.astimezone(UTC)


def to_local(utc_dt: datetime, user_tz: Optional[ZoneInfo] = None) -> datetime:
    """
    Convert UTC datetime to local timezone for display.

    Args:
        utc_dt: UTC datetime (may or may not have tzinfo)
        user_tz: User's timezone (default: DEFAULT_TIMEZONE)

    Returns:
        datetime: Local datetime with user's tzinfo
    """
    if user_tz is None:
        user_tz = DEFAULT_TIMEZONE

    if utc_dt.tzinfo is None:
        # Assume naive datetime is UTC
        utc_dt = utc_dt.replace(tzinfo=UTC)

    return utc_dt.astimezone(user_tz)


def to_local_date(utc_dt: datetime, user_tz: Optional[ZoneInfo] = None) -> date:
    """
    Convert UTC datetime to local date for grouping.

    Use this instead of utc_dt.date() which doesn't account for timezone.

    Args:
        utc_dt: UTC datetime
        user_tz: User's timezone (default: DEFAULT_TIMEZONE)

    Returns:
        date: Local date in user's timezone
    """
    return to_local(utc_dt, user_tz).date()


def parse_local_date(date_str: str, user_tz: Optional[ZoneInfo] = None) -> datetime:
    """
    Parse a date string as local date and return start of day in UTC.

    Args:
        date_str: Date string in YYYY-MM-DD format
        user_tz: User's timezone (default: DEFAULT_TIMEZONE)

    Returns:
        datetime: Start of the local date in UTC
    """
    if user_tz is None:
        user_tz = DEFAULT_TIMEZONE

    local_date = datetime.strptime(date_str, "%Y-%m-%d")
    local_start = local_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=user_tz)
    return local_start.astimezone(UTC)


def local_date_range_to_utc(
    start_date: date,
    end_date: date,
    user_tz: Optional[ZoneInfo] = None
) -> Tuple[datetime, datetime]:
    """
    Convert local date range to UTC datetime range for database queries.

    Args:
        start_date: Local start date (inclusive)
        end_date: Local end date (inclusive)
        user_tz: User's timezone (default: DEFAULT_TIMEZONE)

    Returns:
        tuple: (start_utc, end_utc) - UTC datetime range
    """
    if user_tz is None:
        user_tz = DEFAULT_TIMEZONE

    # Start of start_date in user's timezone
    start_local = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=user_tz)
    start_utc = start_local.astimezone(UTC)

    # End of end_date in user's timezone (23:59:59.999999)
    end_local = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=user_tz)
    end_utc = end_local.astimezone(UTC)

    return start_utc, end_utc


def local_date_to_utc(
    d: date,
    user_tz: Optional[ZoneInfo] = None,
) -> datetime:
    """Convert a local calendar date to UTC datetime (midnight in user's tz → UTC).

    Use this for API output of Date columns: the resulting UTC timestamp
    correctly represents the start of that calendar day in the user's timezone.

    Args:
        d: Local calendar date.
        user_tz: User's timezone (default: DEFAULT_TIMEZONE).

    Returns:
        datetime: Midnight of ``d`` in *user_tz*, expressed in UTC.
    """
    if user_tz is None:
        user_tz = DEFAULT_TIMEZONE
    local_midnight = datetime.combine(d, datetime.min.time()).replace(tzinfo=user_tz)
    return local_midnight.astimezone(UTC)


def format_local_datetime(
    utc_dt: datetime,
    format_str: str = "%Y年%m月%d日 %H:%M",
    user_tz: Optional[ZoneInfo] = None
) -> str:
    """
    Format UTC datetime as local time string.

    Args:
        utc_dt: UTC datetime
        format_str: strftime format string
        user_tz: User's timezone (default: DEFAULT_TIMEZONE)

    Returns:
        str: Formatted local datetime string
    """
    local_dt = to_local(utc_dt, user_tz)
    return local_dt.strftime(format_str)


def format_iso_utc(dt: datetime) -> str:
    """
    Format datetime as ISO 8601 UTC string for API responses.

    Args:
        dt: datetime (will be converted to UTC if needed)

    Returns:
        str: ISO 8601 string with Z suffix (e.g., "2026-01-28T00:00:00Z")
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    utc_dt = dt.astimezone(UTC)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def local_today(user_tz: Optional[ZoneInfo] = None) -> date:
    """
    Get today's date in user's local timezone.

    Args:
        user_tz: User's timezone (default: DEFAULT_TIMEZONE)

    Returns:
        date: Today's date in user's timezone
    """
    return to_local(utc_now(), user_tz).date()


def local_now(user_tz: Optional[ZoneInfo] = None) -> datetime:
    """
    Get current datetime in user's local timezone.

    Args:
        user_tz: User's timezone (default: DEFAULT_TIMEZONE)

    Returns:
        datetime: Current datetime in user's timezone
    """
    return to_local(utc_now(), user_tz)
