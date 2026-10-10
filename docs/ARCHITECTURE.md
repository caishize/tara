# Secretary Architecture

> Status: Living document. Last updated: 2026-03-20

## System Overview

AI-Powered Family Secretary with a **dual-brain routing** architecture: Fast Path (Haiku 4.5, ~80%) for simple queries, Slow Path (Sonnet 4 via Claude Agent SDK, ~20%) for complex reasoning. Agents are **ephemeral** — state is rehydrated from DB on cold start.

## Layer Model

```
Types/Models → Config → Repository → Service → AI Engine → API/Runtime
                                                              ↕
                                                           Mobile (sibling)
```

| Layer | Path | Allowed Imports |
|-------|------|-----------------|
| **Types/Models** | `backend/src/db/`, `backend/src/modules/*/models.py` | stdlib only |
| **Config** | `backend/src/config/` | Types |
| **Repository** | `backend/src/modules/*/repositories.py` | Types, Config |
| **Service** | `backend/src/modules/*/services/`, `*/*_service.py` | Types, Config, Repository |
| **AI Engine** | `backend/src/ai_engine/` | Types, Config, Repository, Service |
| **API/Runtime** | `backend/src/api/v1/` | All layers |
| **Core (cross-cutting)** | `backend/src/core/` | Types, Config (peer to Service) |
| **Mobile (sibling)** | `mobile/lib/` | Independent — communicates via REST/WebSocket |

## Dual-Brain Routing

```
Message Sources                    Routing Path
────────────────────────────────────────────────────────────────
① User message (IDLE)          → IntentRouter (Haiku) → FAST/SLOW/HYBRID
② User message (busy)          → InterventionClassifier (Haiku) → 6 signal types
③ System insight (sidekick)    → SidekickWorker → SIDEKICK_INSIGHT (bypasses IntentRouter)
```

### Normal Routing (session IDLE)
`chat.py` checks `session:status:{session_id}` → IDLE → IntentRouter classifies `difficulty × action` → FAST (Haiku API) / SLOW (Agent SDK + Sonnet) / HYBRID (Fast first + Slow background) → WebSocket push

### Intervention Routing (session busy)
`chat.py` detects GENERATING/TOOL_EXECUTING/WAITING_USER → `InterventionClassifier` (Haiku, <150ms) → Redis PUBLISH `session:signal:{session_id}` → `ReactiveSessionActor` event loop → HTTP 202

### Sidekick Injection (system-initiated)
`InsightOrchestrator.generate_all()` → `SidekickWorker.evaluate_and_inject()` with 4 gates (expiry, active session, context relevance, rate limit) → Redis PUBLISH directly to signal channel (bypasses IntentRouter)

## Intervention Signal System

| Signal | Priority | Source | Handling |
|--------|----------|--------|----------|
| **CORRECTION** | 1 | User | Interrupt → save context → re-generate with correction |
| **CANCEL** | 1 | User | Immediate interrupt, skip debounce, clear buffer |
| **ADDITIVE** | 2 | User | Generating→buffer; Tool executing→inject `[SUPPLEMENTARY_INFO]` |
| **CONFIRM** | 2 | User | Generating→buffer; WAITING_USER→interrupt+confirm re-generate |
| **DIGRESSION** | 3 | User | Queue as new request, process after current completes |
| **SIDEKICK_INSIGHT** | 3 | System | IDLE→inject directly; busy→buffer (high urgency can penetrate) |

**Mechanisms**: 1.5s last-write-wins debounce (CANCEL skips), per-session budget (5 interventions, 3 corrections), non-interruptible tools (`create_trip`, `book_ticket`, `send_message`), confidence < 0.6 → downgrade to ADDITIVE.

## Claude Agent SDK Usage

- **Slow Path**: `ClaudeSDKClient` + `ClaudeAgentOptions` (model, system_prompt, max_turns, mcp_servers, hooks)
- **Tools**: In-process MCP Server, tool names: `mcp__secretary__<tool_name>`
- **Client Pool**: Per-session persistent `ClaudeSDKClient` (avoids ~80s CLI startup)
- **Hooks**: `HookMatcher` intercepts sensitive ops (PreToolUse), sub-agent delegation, sandbox enforcement
- **Filesystem Sandbox**: CLI cwd = `/tmp/secretary/{session_id}/`, PreToolUse hook blocks absolute path escape

### SDK Streaming Input Behavior

| Scenario | Behavior |
|----------|----------|
| **Inter-turn query** | After ResultMessage → `query()` = independent new turn |
| **During tool execution** | Message merged into current turn (uncontrollable) |
| **interrupt() + query()** | `interrupt()` <10ms → error ResultMessage → new independent turn |

## Context Reconstruction

### Warm Path (reuse existing CLI process)
`has_active_client(session_id)` → skip IntentRouter → route SLOW directly. Only send `user_input`, CLI already has full multi-turn context.

### Cold Start (new CLI process)
`build_cold_start_conversation()` rebuilds history (20k token budget, 7-day window):
1. Recent uncompressed messages (from compression watermark)
2. Compressed session summaries if budget remains
3. Assemble as `<conversation_history>` + `<current_user_message>` XML

### System Prompt Context (ContextAssembler)

| Layer | Content | Token Budget |
|-------|---------|-------------|
| L1 | Secretary Notes + curation associations + proactive triggers | 500 fixed |
| L2 | Recent conversation turns (dynamic 5-25) | 2000 fixed |
| L3 | Memory summary / persona profile | 500-1500 elastic |
| L4 | Semantic + FTS hybrid long-term memory retrieval | 500-2000 elastic |
| L5 | Today's orchestrated schedule + annotations + DayTheme | 800 fixed |

## Session State Machine

```
IDLE → GENERATING ⇄ TOOL_EXECUTING
GENERATING → WAITING_USER
GENERATING → IDLE (ResultMessage)
```

## Celery Task Queues

| Queue | Routes |
|-------|--------|
| `default` | events.*, scheduler.*, reminder.*, gift.* |
| `secretary` | curation.*, secretary.* |
| `assistant` | assistant.* |

**Key Scheduled Tasks**: outbox relay (5s), dispatch (30s), PendingAction expiry (2min), holiday prep (daily 06:00), proactive insights (daily 08:00), memory compression (daily 04:30), meal window inference (Sunday 03:00)

## Prohibitions

| Prohibited | Reason |
|------------|--------|
| Long-lived in-memory Agent | Violates state rehydration principle |
| Agent direct sensitive operations | Must use PendingAction + user confirmation |
| Synchronous deep thinking | Must use Redis Stream async queue |
| Agent holding external API keys | Internal token only, via ToolGateway |

## Related Documents

- [V8 Architecture Proposal](V8-AI-Architecture-Proposal.md)
- [Architecture V8 Secretary Brain](architecture-v8-secretary-brain.md)
- [AI Assistant Architecture](AI_ASSISTANT_ARCHITECTURE.md)
- [Curation Evolution Plan](curation-evolution-plan.md)
