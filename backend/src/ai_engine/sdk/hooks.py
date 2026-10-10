"""
SDK Hooks - PreToolUse and PostToolUse hooks for the Claude Agent SDK.

PreToolUse hooks:
- Sensitive action interception (PendingAction flow)
- Sub-agent delegation interception
- Sandbox path enforcement (filesystem tools)

PostToolUse hooks:
- Builtin tool persistence (WebSearch, WebFetch → tool_execution_logs)
"""

import logging
import os
from typing import Any, Callable, Coroutine, Dict, FrozenSet, Optional

from .tool_persistence import ToolPersistenceHandler

logger = logging.getLogger(__name__)


def create_sensitive_action_hook(
    sensitive_actions: FrozenSet[str],
    handler_fn: Callable[[str, Dict[str, Any]], Coroutine[Any, Any, str]],
) -> Callable:
    """Create a PreToolUse hook that intercepts sensitive tool calls.

    When a tool in sensitive_actions is invoked by the agent, the hook:
    1. Calls handler_fn to create a PendingAction for user confirmation
    2. Returns a 'deny' decision so the SDK does not execute the tool
    3. The denial reason includes the PendingAction ID

    Args:
        sensitive_actions: Frozenset of tool names requiring confirmation
        handler_fn: Async callable(tool_name, tool_input) -> str
            Should create PendingAction and return confirmation message

    Returns:
        An async hook callback compatible with SDK HookMatcher
    """
    async def check_sensitive_action(
        input_data: Dict[str, Any],
        tool_use_id: Any,
        context: Any,
    ) -> Dict[str, Any]:
        tool_name = input_data.get("tool_name", "")

        # MCP tool names are prefixed: mcp__secretary__<tool_name>
        # Extract the actual tool name for checking
        actual_tool_name = _extract_tool_name(tool_name)

        if actual_tool_name not in sensitive_actions:
            return {}

        tool_input = input_data.get("tool_input", {})

        try:
            result_message = await handler_fn(actual_tool_name, tool_input)
        except Exception as e:
            logger.error(
                "Sensitive action handler failed for %s: %s",
                actual_tool_name, e,
            )
            result_message = f"敏感操作处理失败: {e}"

        return {
            "hookSpecificOutput": {
                "hookEventName": input_data.get("hook_event_name", "PreToolUse"),
                "permissionDecision": "deny",
                "permissionDecisionReason": result_message,
            },
        }

    return check_sensitive_action


def create_sub_agent_intercept_hook(
    handler_fn: Callable[[Dict[str, Any]], Coroutine[Any, Any, str]],
) -> Callable:
    """Create a PreToolUse hook that intercepts delegate_to_sub_agent calls.

    Since the SDK handles tool execution internally, sub-agent delegation
    needs to be intercepted via hook, executed externally, and the result
    returned as the denial reason (which the agent sees as the tool output).

    Args:
        handler_fn: Async callable(tool_input) -> str result

    Returns:
        An async hook callback compatible with SDK HookMatcher
    """
    async def intercept_sub_agent(
        input_data: Dict[str, Any],
        tool_use_id: Any,
        context: Any,
    ) -> Dict[str, Any]:
        tool_name = input_data.get("tool_name", "")
        actual_tool_name = _extract_tool_name(tool_name)

        if actual_tool_name != "delegate_to_sub_agent":
            return {}

        tool_input = input_data.get("tool_input", {})

        try:
            result_text = await handler_fn(tool_input)
        except Exception as e:
            logger.error("Sub-agent delegation failed: %s", e, exc_info=True)
            result_text = "子Agent执行失败，请稍后重试"

        return {
            "hookSpecificOutput": {
                "hookEventName": input_data.get("hook_event_name", "PreToolUse"),
                "permissionDecision": "deny",
                "permissionDecisionReason": result_text,
            },
        }

    return intercept_sub_agent


# ── Tool name → path parameter mapping for sandbox enforcement ────────
_TOOL_PATH_PARAMS: Dict[str, list] = {
    "Read": ["file_path"],
    "Write": ["file_path"],
    "Edit": ["file_path"],
    "Grep": ["path"],
    "Glob": ["path"],
    "LS": ["path"],
    "NotebookEdit": ["notebook_path"],
    "NotebookRead": ["file_path"],
}


def create_sandbox_enforcement_hook(sandbox_dir: str) -> Callable:
    """Create a PreToolUse hook that blocks filesystem access outside sandbox.

    Validates that all file paths used by filesystem tools (Read, Write,
    Edit, Grep, Glob, LS, NotebookEdit, NotebookRead) resolve within
    ``sandbox_dir``.  Relative paths are allowed (they resolve within
    the CLI's cwd, which is set to sandbox_dir).  Absolute paths are
    checked against the resolved sandbox boundary.

    Args:
        sandbox_dir: Absolute path to the session sandbox directory.

    Returns:
        An async hook callback compatible with SDK HookMatcher
    """
    resolved_sandbox = os.path.realpath(sandbox_dir)

    async def enforce_sandbox(
        input_data: Dict[str, Any],
        tool_use_id: Any,
        context: Any,
    ) -> Dict[str, Any]:
        tool_name = input_data.get("tool_name", "")
        actual_name = _extract_tool_name(tool_name)

        params = _TOOL_PATH_PARAMS.get(actual_name)
        if not params:
            return {}

        tool_input = input_data.get("tool_input", {})
        for param in params:
            path = tool_input.get(param, "")
            if not path:
                continue  # Empty/missing → uses cwd (sandbox)
            if not os.path.isabs(path):
                continue  # Relative paths resolve within cwd (sandbox)

            resolved = os.path.realpath(path)
            if resolved != resolved_sandbox and not resolved.startswith(
                resolved_sandbox + os.sep
            ):
                logger.warning(
                    "Sandbox violation: tool=%s param=%s path=%s sandbox=%s",
                    actual_name, param, path, sandbox_dir,
                )
                return {
                    "hookSpecificOutput": {
                        "hookEventName": input_data.get(
                            "hook_event_name", "PreToolUse",
                        ),
                        "permissionDecision": "deny",
                        "permissionDecisionReason": (
                            f"访问被拒绝：路径 {path} 超出沙箱目录。"
                            "请使用沙箱内的相对路径。"
                        ),
                    },
                }
        return {}

    return enforce_sandbox


# Redis key prefix for AskUserQuestion answer channel
_ASK_USER_ANSWER_PREFIX = "ask_user_answer:"
# Timeout for waiting on user answer (seconds)
_ASK_USER_TIMEOUT_SECONDS = 120


def create_ask_user_question_hook(
    publish_fn: Callable[
        [str, list], Coroutine[Any, Any, int]
    ],
    redis_getter: Callable[[], Any],
    user_id: str,
    trace_id: str,
) -> Callable:
    """Create a PreToolUse hook that intercepts AskUserQuestion calls.

    Instead of letting the SDK handle it (which requires interactive TTY),
    this hook:
    1. Publishes the question(s) to the user via PubSub → WebSocket
    2. Waits on a Redis key for the user's answer (BLPOP with timeout)
    3. Returns the answer as the denial reason (agent sees it as tool output)

    Args:
        publish_fn: Async callable(question_id, questions) -> int receivers
        redis_getter: Callable returning an async Redis client
        user_id: Current user ID (for generating unique keys)
        trace_id: Current trace/job ID
    """
    import uuid
    import json as _json

    async def intercept_ask_user(
        input_data: Dict[str, Any],
        tool_use_id: Any,
        context: Any,
    ) -> Dict[str, Any]:
        tool_name = input_data.get("tool_name", "")
        actual_name = _extract_tool_name(tool_name)

        if actual_name != "AskUserQuestion":
            return {}

        tool_input = input_data.get("tool_input", {})
        questions = tool_input.get("questions", [])

        if not questions:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "没有需要提问的内容。",
                },
            }

        question_id = str(uuid.uuid4())
        answer_key = f"{_ASK_USER_ANSWER_PREFIX}{question_id}"

        # Publish question to user via WebSocket
        try:
            receivers = await publish_fn(question_id, questions)
            logger.info(
                "AskUserQuestion published: question_id=%s, receivers=%d",
                question_id, receivers,
            )
        except Exception as e:
            logger.error("Failed to publish AskUserQuestion: %s", e)
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        "无法向用户发送问题，请改为直接在对话中文字提问。"
                    ),
                },
            }

        # Wait for the user's answer on Redis
        try:
            r = redis_getter()
            result = await r.blpop(answer_key, timeout=_ASK_USER_TIMEOUT_SECONDS)
        except Exception as e:
            logger.error("Redis BLPOP failed for %s: %s", answer_key, e)
            result = None

        if result is None:
            # Timeout — user didn't respond
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        "用户在2分钟内未回答。请改为直接在对话中文字提问。"
                    ),
                },
            }

        # Parse the answer
        try:
            raw_answer = result[1]
            if isinstance(raw_answer, bytes):
                raw_answer = raw_answer.decode("utf-8")
            answer_data = _json.loads(raw_answer)
        except Exception:
            answer_data = {"text": str(result[1])}

        # Format answer for the agent
        answer_parts = []
        for q_answer in answer_data.get("answers", [answer_data]):
            question_text = q_answer.get("question", "")
            answer_text = q_answer.get("answer", q_answer.get("text", ""))
            if question_text:
                answer_parts.append(f"Q: {question_text}\nA: {answer_text}")
            else:
                answer_parts.append(answer_text)

        formatted_answer = "用户回答:\n" + "\n\n".join(answer_parts)

        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": formatted_answer,
            },
        }

    return intercept_ask_user


async def _persist_builtin_tool_impl(
    persistence: ToolPersistenceHandler,
    input_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Core logic shared by pooled and non-pooled builtin persistence hooks.

    Persists builtin tool executions (WebSearch, WebFetch, etc.) that bypass
    the MCP server.  Returns ``{}`` to signal no hook override.
    """
    tool_name = input_data.get("tool_name", "")

    # Skip MCP tools — they are persisted via the MCP server already
    if tool_name.startswith("mcp__"):
        return {}

    tool_input = input_data.get("tool_input", {})
    tool_response = input_data.get("tool_response", "")

    logger.info(
        "PostToolUse builtin tool '%s': input=%s, response_type=%s, response_len=%s",
        tool_name,
        str(tool_input)[:200],
        type(tool_response).__name__,
        len(str(tool_response)) if tool_response else 0,
    )
    if not tool_response:
        logger.warning(
            "PostToolUse builtin tool '%s' returned EMPTY response. "
            "This may indicate the tool is not supported by the current API endpoint.",
            tool_name,
        )

    execution_id = _generate_execution_id()
    short_id = str(execution_id).split("-")[0]

    summary, key_results = _extract_builtin_tool_summary(
        tool_name, tool_input, tool_response,
    )

    full_result = {
        "tool_input": tool_input,
        "tool_response": (
            tool_response[:5000]
            if isinstance(tool_response, str)
            else tool_response
        ),
    }

    try:
        await persistence._persist_execution(
            execution_id=execution_id,
            tool_name=tool_name,
            arguments=tool_input,
            status="success",
            summary=summary,
            key_results=key_results,
            full_result=full_result,
            execution_time_ms=None,
        )
        logger.debug("Persisted builtin tool execution: %s", tool_name)
    except Exception as e:
        logger.error(
            "Failed to persist builtin tool %s: %s", tool_name, e,
        )

    if persistence._on_tool_end:
        try:
            await persistence._on_tool_end(
                execution_id=str(execution_id),
                short_id=short_id,
                tool_name=tool_name,
                status="success",
                summary=summary,
                key_results=key_results,
                duration_ms=0,
            )
        except Exception as e:
            logger.warning(
                "Failed to publish builtin tool event %s: %s",
                tool_name, e,
            )

    return {}


def create_builtin_tool_persistence_hook(
    persistence: ToolPersistenceHandler,
) -> Callable:
    """Create a PostToolUse hook that persists builtin tool executions.

    Builtin tools (WebSearch, WebFetch) are executed by the SDK directly,
    bypassing the MCP server and its ToolPersistenceHandler. This hook
    captures their results and writes them to tool_execution_logs.

    MCP tools (prefixed ``mcp__``) are skipped because they are already
    persisted by the MCP server's ToolPersistenceHandler.

    Args:
        persistence: ToolPersistenceHandler for DB writes

    Returns:
        An async hook callback compatible with SDK PostToolUse HookMatcher
    """
    async def persist_builtin_tool(
        input_data: Dict[str, Any],
        tool_use_id: Any,
        context: Any,
    ) -> Dict[str, Any]:
        return await _persist_builtin_tool_impl(persistence, input_data)

    return persist_builtin_tool


def create_builtin_tool_persistence_hook_pooled(
    ctx: Any,
) -> Callable:
    """Pooled variant — reads ``ctx.persistence`` at call time.

    When the pool reuses a CLI client, the hook closures created at
    initial connection time still reference this function's closure.
    By reading ``ctx.persistence`` (instead of a captured ``persistence``),
    every invocation uses the fresh DB session from the current request.

    Args:
        ctx: PooledToolContext with a ``persistence`` attribute

    Returns:
        An async hook callback compatible with SDK PostToolUse HookMatcher
    """
    async def persist_builtin_tool(
        input_data: Dict[str, Any],
        tool_use_id: Any,
        context: Any,
    ) -> Dict[str, Any]:
        return await _persist_builtin_tool_impl(ctx.persistence, input_data)

    return persist_builtin_tool


def _extract_builtin_tool_summary(
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_response: Any,
) -> tuple:
    """Extract summary and key_results for builtin tools.

    Returns:
        (summary: str, key_results: Optional[Dict])
    """
    if tool_name == "WebSearch":
        query = tool_input.get("query", "")
        summary = f"搜索: {query}" if query else "WebSearch 执行完成"
        key_results = {"query": query}
        if isinstance(tool_response, str) and tool_response:
            key_results["result_preview"] = tool_response[:500]
        return (summary, key_results)

    if tool_name == "WebFetch":
        url = tool_input.get("url", "")
        summary = f"获取网页: {url[:80]}" if url else "WebFetch 执行完成"
        key_results = {"url": url}
        if isinstance(tool_response, str) and tool_response:
            key_results["result_preview"] = tool_response[:500]
        return (summary, key_results)

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        summary = f"执行命令: {command[:80]}" if command else "Bash 执行完成"
        key_results: Dict[str, Any] = {"command": command}
        if isinstance(tool_response, str) and tool_response:
            key_results["output_preview"] = tool_response[:500]
        return (summary, key_results)

    if tool_name == "Read":
        file_path = tool_input.get("file_path", "")
        summary = f"读取文件: {file_path}" if file_path else "Read 执行完成"
        return (summary, {"file_path": file_path})

    if tool_name == "Grep":
        pattern = tool_input.get("pattern", "")
        path = tool_input.get("path", "")
        parts = [f"搜索: {pattern}"]
        if path:
            parts.append(f"在 {path}")
        summary = " ".join(parts) if pattern else "Grep 执行完成"
        return (summary, {"pattern": pattern, "path": path})

    if tool_name == "Glob":
        pattern = tool_input.get("pattern", "")
        summary = f"查找文件: {pattern}" if pattern else "Glob 执行完成"
        return (summary, {"pattern": pattern})

    if tool_name in ("Write", "Edit"):
        file_path = tool_input.get("file_path", "")
        action = "写入" if tool_name == "Write" else "编辑"
        summary = f"{action}文件: {file_path}" if file_path else f"{tool_name} 执行完成"
        return (summary, {"file_path": file_path})

    if tool_name == "Task":
        desc = tool_input.get("description", tool_input.get("prompt", ""))
        summary = f"子任务完成: {desc[:60]}" if desc else "子任务执行完成"
        key_results: Dict[str, Any] = {}
        if desc:
            key_results["description"] = desc[:200]
        if isinstance(tool_response, str) and tool_response:
            key_results["result_preview"] = tool_response[:500]
        return (summary, key_results or None)

    if tool_name in ("TodoWrite", "TaskCreate"):
        subject = tool_input.get("subject", "")
        summary = f"已创建: {subject}" if subject else "任务列表已更新"
        return (summary, {"subject": subject} if subject else None)

    if tool_name == "TaskUpdate":
        task_id = tool_input.get("taskId", "")
        status = tool_input.get("status", "")
        summary = f"任务 #{task_id} → {status}" if task_id else "任务状态已更新"
        return (summary, {"taskId": task_id, "status": status})

    if tool_name == "TaskList":
        return ("任务列表已获取", None)

    if tool_name == "Skill":
        skill = tool_input.get("skill", "")
        summary = f"{skill} 执行完成" if skill else "技能执行完成"
        return (summary, {"skill": skill} if skill else None)

    if tool_name == "AskUserQuestion":
        return ("已向用户提问", None)

    # Generic fallback for any other builtin tools
    summary = f"{tool_name} 执行完成"
    return (summary, None)


def _generate_execution_id():
    """Generate a new UUID for builtin tool execution tracking."""
    import uuid
    return uuid.uuid4()


def _extract_tool_name(sdk_tool_name: str) -> str:
    """Extract the actual tool name from SDK MCP tool name.

    MCP tools are named: mcp__<server>__<tool_name>
    Non-MCP tools are passed through as-is.
    """
    if sdk_tool_name.startswith("mcp__"):
        parts = sdk_tool_name.split("__", 2)
        if len(parts) == 3:
            return parts[2]
    return sdk_tool_name


def generate_start_summary(
    tool_name: str, arguments: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate a human-readable summary for a tool start event.

    Used to display what's being done while the tool executes,
    similar to Claude Code's real-time output.
    """
    args = arguments or {}

    # SDK builtin tools
    if tool_name == "WebSearch":
        q = args.get("query", "")
        return f"正在搜索: {q}" if q else "正在搜索..."
    if tool_name == "WebFetch":
        url = args.get("url", "")
        return f"正在获取: {url[:60]}" if url else "正在获取网页..."
    if tool_name == "Task":
        desc = args.get("description", args.get("prompt", ""))
        return f"正在执行子任务: {desc[:60]}" if desc else "正在执行子任务..."
    if tool_name in ("TodoWrite", "TaskCreate"):
        subject = args.get("subject", "")
        return f"正在创建: {subject}" if subject else "正在更新任务"
    if tool_name == "TaskUpdate":
        return "正在更新任务状态"
    if tool_name == "TaskList":
        return "正在获取任务列表"
    if tool_name == "Skill":
        skill = args.get("skill", "")
        return f"正在执行 {skill}" if skill else "正在执行技能"
    if tool_name == "AskUserQuestion":
        return "正在等待用户回答"

    # MCP secretary tools
    if tool_name == "search_memory":
        q = args.get("query", "")
        return f"正在回忆: {q[:60]}" if q else "正在搜索记忆..."
    if tool_name == "search_events":
        return "正在查询日程"
    if tool_name == "query_trips":
        return "正在查询行程"
    if tool_name == "add_trip_itinerary":
        dest = args.get("destination", "")
        return f"正在规划 {dest} 行程" if dest else "正在规划行程..."
    if tool_name == "query_members":
        return "正在查询成员信息"
    if tool_name == "query_tasks":
        return "正在查询任务"
    if tool_name == "create_task":
        title = args.get("title", "")
        return f"正在创建任务: {title}" if title else "正在创建任务..."
    if tool_name == "web_search":
        query = args.get("query", "")
        return f"正在搜索: {query}" if query else "正在搜索..."
    if tool_name == "save_memory":
        return "正在保存记忆"
    if tool_name == "recommend_gift":
        return "正在推荐礼物"
    if tool_name == "set_reminder":
        return "正在设置提醒"
    if tool_name == "add_member":
        name = args.get("name", "")
        return f"正在添加成员: {name}" if name else "正在添加成员"
    if tool_name == "update_trip":
        name = args.get("trip_name", args.get("name", ""))
        return f"正在保存行程: {name}" if name else "正在保存行程..."

    return f"正在执行 {tool_name}"


def generate_end_summary(
    tool_name: str, arguments: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate a human-readable summary for a tool auto-complete event.

    Used when PostToolUse hook didn't fire and we need to auto-complete
    the tool with a meaningful summary based on its arguments.
    """
    args = arguments or {}

    if tool_name == "WebSearch":
        q = args.get("query", "")
        return f"搜索完成: {q}" if q else "搜索完成"
    if tool_name == "WebFetch":
        url = args.get("url", "")
        return f"获取完成: {url[:60]}" if url else "获取完成"
    if tool_name == "Task":
        desc = args.get("description", args.get("prompt", ""))
        return f"子任务完成: {desc[:60]}" if desc else "子任务完成"
    if tool_name in ("TodoWrite", "TaskCreate"):
        subject = args.get("subject", "")
        return f"已创建: {subject}" if subject else "任务已更新"
    if tool_name == "TaskUpdate":
        return "任务状态已更新"
    if tool_name == "TaskList":
        return "任务列表已获取"
    if tool_name == "Skill":
        skill = args.get("skill", "")
        return f"{skill} 执行完成" if skill else "技能执行完成"
    if tool_name == "AskUserQuestion":
        return "已向用户提问"

    return f"{tool_name} 执行完成"
