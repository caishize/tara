"""Shared XML escaping and SQL LIKE escaping utilities."""


def escape_xml(text: str) -> str:
    """Escape XML special characters in user-controlled data.

    Must be applied to any user-originating string before interpolation
    into XML template constructions (LLM prompts, context XML, etc.).
    """
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def escape_like(value: str) -> str:
    """Escape SQL LIKE/ILIKE wildcard characters.

    Prevents user-supplied values containing % or _ from matching
    unintended rows when used in LIKE/ILIKE patterns.
    """
    return (
        value
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
