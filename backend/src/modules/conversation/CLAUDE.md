# Conversation

## Purpose
Chat session lifecycle — manages sessions, messages, PendingAction confirmations, user feedback collection, tool execution tracking, onboarding flows, and daily summaries.

## Layer Rules
- **Layer**: Service
- **Allowed imports**: core.*, .models, ..member.interface
- **Forbidden imports**: ai_engine.* (ai_engine depends on conversation, not reverse), api.*

## Key Files
| File | Purpose |
|------|---------|
| session_service.py | Session CRUD, archival, compression watermark |
| message_service.py | Message persistence and retrieval |
| pending_action_service.py | PendingAction lifecycle (pending→confirmed→executed→expired) |
| pending_action.py | PendingAction model and types |
| feedback_service.py | User feedback collection (thumbs up/down, corrections) |
| context_service.py | Conversation context for LLM cold-start rebuilding |
| tool_execution_store.py | Persists tool call results for audit trail |
| tool_summary_generator.py | Generates human-readable tool execution summaries |
| onboarding_service.py | New user onboarding conversation flow |
| daily_summary_service.py | End-of-day conversation summaries |
| today_service.py | "Today" conversation activity feed |
| tasks.py | Celery tasks: PendingAction expiry (every 2min) |

## Module Conventions
- PendingAction expiry task runs every 2 minutes on default queue
- Session archival triggers post-session reflection (memory extraction)
- `card_normalizer.py` normalizes display cards across different response types
- Feedback types: THUMBS_UP, THUMBS_DOWN, CORRECTION, DEFER, NEVER
