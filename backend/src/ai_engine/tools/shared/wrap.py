"""Adapter to bridge domain executor methods to the ToolExecutor signature."""

from typing import Any, Awaitable, Callable, Dict

from ..registry import ToolExecutionContext

# Type alias for tool executor functions
ToolExecutorFunc = Callable[
    [str, Dict[str, Any], ToolExecutionContext],
    Awaitable[Dict[str, Any]],
]


def wrap_method(method: Callable) -> ToolExecutorFunc:
    """Wrap a domain executor method into the ToolExecutor signature.

    Adapts (args, family_id, user_id, progress_cb) -> result
    to     (name, args, context) -> result
    """

    async def _exec(
        name: str,
        args: Dict[str, Any],
        ctx: ToolExecutionContext,
    ) -> Dict[str, Any]:
        return await method(args, ctx.family_id, ctx.user_id, ctx.progress_callback)

    return _exec
