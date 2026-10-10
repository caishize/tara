"""Standardized error types and utilities for tool executors."""

from typing import Any, Dict, Optional


class ToolErrorType:
    """Error types that help LLM understand what went wrong and how to recover."""

    VALIDATION = "validation"
    NOT_FOUND = "not_found"
    ALREADY_EXISTS = "already_exists"
    PERMISSION = "permission"
    EXTERNAL = "external"
    INTERNAL = "internal"
    RATE_LIMIT = "rate_limit"


class ToolExecutionError(Exception):
    """Raised by domain executors to signal a structured tool error.

    ToolBridge.execute_tool catches this and converts it to a dict response.
    """

    def __init__(
        self,
        error_type: str,
        message: str,
        hint: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.hint = hint
        self.details = details

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "success": False,
            "error_type": self.error_type,
            "message": self.message,
        }
        if self.hint:
            result["recovery_hint"] = self.hint
        if self.details:
            result["details"] = self.details
        return result


def tool_error(
    error_type: str,
    message: str,
    hint: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a standardized error response dict for tools."""
    result: Dict[str, Any] = {
        "success": False,
        "error_type": error_type,
        "message": message,
    }
    if hint:
        result["recovery_hint"] = hint
    if details:
        result["details"] = details
    return result
