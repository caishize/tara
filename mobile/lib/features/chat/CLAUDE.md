# Chat Module

## Purpose
Main conversation UI with real-time AI assistant messaging, WebSocket streaming, voice input, intervention signals (correction/cancel/additive), and rich bubble rendering for tools, pending actions, briefings, and structured cards.

## Layer Rules
- **Layer**: feature (`features/chat/`)
- **Allowed imports**: `core/` (network, location, error), `shared/`, `domain/` and `data/` within this feature
- **Forbidden imports**: other `features/` modules (kanban, profile, trip)

## Key Files
| File | Purpose |
|------|---------|
| `presentation/bloc/assistant_bloc.dart` | Main BLoC; uses `part` files for stream + action handlers |
| `presentation/bloc/daily_briefing_bloc.dart` | Daily briefing card loading |
| `presentation/pages/conversation_page.dart` | Chat list view with message bubbles |
| `presentation/pages/main_shell.dart` | App shell with bottom navigation |
| `data/datasources/assistant_remote_datasource.dart` | WebSocket + SSE streaming, 20+ event types |
| `data/datasources/pending_action_datasource.dart` | Confirm/reject sensitive operations |
| `domain/repositories/assistant_repository.dart` | Abstract chat + history contract |
| `domain/entities/chat_message.dart` | MessageRole, ToolExecution, progress steps |

## Module Conventions
- WebSocket-only chat (`useWebSocketChat = true`), no HTTP fallback
- Intervention signals: correction, cancel, additive, confirm, digression
- BLoC split via `part` directive: `assistant_stream_handlers.dart`, `assistant_action_handlers.dart`
- All stream event types defined in `StreamEventType` enum (datasource)
- Rich bubbles: each structured response type has a dedicated `*_bubble.dart` widget
- Chinese UI labels for signal hints (`_signalHintLabels`)
