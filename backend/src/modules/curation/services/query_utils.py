"""
Query utilities for safe SQL pattern matching.

Provides helpers for escaping LIKE/ILIKE wildcard characters
to prevent unintended broad matches from user-supplied strings.
"""


def escape_like(value: str) -> str:
    """
    Escape SQL LIKE wildcard characters in a user-supplied string.

    Escapes %, _, and \\ so they are treated as literal characters
    in ILIKE/LIKE patterns. Use with SQLAlchemy's escape parameter:

        Column.ilike(f"%{escape_like(user_input)}%", escape='\\\\')
    """
    return (
        value
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def ilike_contains(value: str) -> str:
    """
    Build a safe ILIKE contains pattern from user input.

    Returns a pattern like '%escaped_value%' ready for use with
    Column.ilike(pattern, escape='\\\\').
    """
    return f"%{escape_like(value)}%"
