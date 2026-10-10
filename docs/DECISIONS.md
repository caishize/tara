# Architecture Decision Records (ADRs)

> Status flow: Proposed → Accepted → Superseded/Deprecated

## ADR-001: Dual-Brain Routing Architecture
**Status**: Accepted (2025)
**Decision**: Split LLM processing into Fast Path (Haiku 4.5, ~80%) and Slow Path (Sonnet 4 via Claude Agent SDK, ~20%).
**Why**: Most user queries are simple and don't need expensive reasoning. Haiku handles them in <500ms. Complex queries that need tool use or multi-step reasoning go through the Agent SDK.
**Alternatives considered**: Single model for all queries (too slow/expensive), fine-tuned model (maintenance burden).

## ADR-002: Ephemeral Agents with State Rehydration
**Status**: Accepted (2025)
**Decision**: No long-lived in-memory agents. All agent state is rehydrated from DB on cold start.
**Why**: Long-lived agents accumulate stale context and are hard to recover from crashes. Ephemeral agents with DB-backed state are more resilient and debuggable.
**Trade-off**: Cold start overhead (~1-2s to rebuild context) accepted for reliability.

## ADR-003: PendingAction Pattern for Sensitive Operations
**Status**: Accepted (2025)
**Decision**: Agents cannot directly execute sensitive operations. Must generate `PendingAction` for user confirmation.
**Why**: Prevents AI from making irreversible changes (booking, sending messages, spending money) without human approval.

## ADR-004: Outbox Pattern for Event Processing
**Status**: Accepted (2025)
**Decision**: Use transactional outbox pattern for domain events. Events written to `outbox` table in same transaction as domain changes, then relayed by Celery task every 5s.
**Why**: Guarantees at-least-once delivery without distributed transactions. Events are never lost even if Redis is temporarily down.

## ADR-005: Feature-Based Module Organization
**Status**: Accepted (2025)
**Decision**: Backend organized by business domain (`modules/trip`, `modules/gift`, etc.) not by technical layer.
**Why**: Each module is self-contained with its own models, services, repositories. Reduces cross-module coupling. New features don't touch unrelated modules.

## ADR-006: BLoC Pattern for Mobile State Management
**Status**: Accepted (2025)
**Decision**: Use flutter_bloc for state management with strict BLoC pattern (Events in, States out).
**Why**: Predictable state flow, testable business logic, clear separation of UI and logic.

## ADR-007: Redis Stream for Async Agent Communication
**Status**: Accepted (2025)
**Decision**: Slow Path and Hybrid responses go through Redis Stream async queue, results pushed via WebSocket.
**Why**: Never block the HTTP request thread waiting for LLM responses. Users get immediate acknowledgment (HTTP 202) and results are pushed when ready.

## ADR-008: Intervention Signal System
**Status**: Accepted (2026)
**Decision**: 6-type intervention signal system with priority-based handling, debouncing, and budget limits.
**Why**: Users need to correct, cancel, or supplement AI responses mid-generation. Without a structured system, race conditions and context corruption occur.
