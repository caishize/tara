# AI Engine

## Purpose
The system's "brain" — handles dual-brain intent routing (Haiku fast / Sonnet slow), LLM orchestration, SDK client pooling, tool execution, intervention signals, and streaming workers.

## Layer Rules
- **Layer**: AI Engine (above Service, below API)
- **Allowed imports**: core.*, modules.*.interface, modules.*.models
- **Forbidden imports**: modules.*.services (use interface contracts), api.*

## Key Files
| File | Purpose |
|------|---------|
| router/intent_router.py | Two-axis classification (difficulty x action) → FAST/SLOW/HYBRID |
| sdk/sdk_client_pool.py | Persistent CLI process pool per session (avoids ~80s cold start) |
| sdk/mcp_tool_server.py | In-process MCP server exposing tools as `mcp__secretary__*` |
| workers/reactive_session_actor.py | State machine (IDLE/GENERATING/TOOL_EXECUTING/WAITING_USER) + signal handling |
| workers/fast_worker.py | Haiku direct `messages.create()` for fast path |
| workers/sidekick_worker.py | Background insight injection with 4-gate filtering |
| intervention/classifier.py | Classifies mid-conversation user input into 5 intervention types |
| intervention/debouncer.py | 1.5s last-write-wins debouncing (CANCEL skips) |
| context_assembler.py | 5-layer system prompt context (notes, history, memory, recall, schedule) |
| tools/registry.py | Tool registration and execution dispatch |

## Module Conventions
- Agents are **ephemeral** — state rebuilt from DB on cold start, reused in-process on warm path
- Sensitive operations must produce `PendingAction`, never execute directly
- Async communication via Redis Stream; results pushed over WebSocket
- Tool names follow `mcp__secretary__<tool_name>` format
- SDK hooks intercept `PreToolUse` for sandbox enforcement (`/tmp/secretary/{session_id}/`)
