"""Shared SQL utility functions for tool executors."""


def escape_like(value: str) -> str:
    r"""Escape SQL LIKE special characters to prevent pattern injection.

    Backslash must be escaped first to avoid double-escaping.
    Use with ``ilike(..., escape="\\")`` in SQLAlchemy.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
