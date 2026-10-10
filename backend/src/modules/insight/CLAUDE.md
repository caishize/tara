# Insight

## Purpose
Unified insight system with 3 generation engines (rule-based, LLM deep reasoning, trend detection), lifecycle management, deduplication, delivery timing, and feedback learning.

## Layer Rules
- **Layer**: Service
- **Allowed imports**: core.*, .models, ..member.interface, ..memory.interface, ..curation.interface
- **Forbidden imports**: ai_engine.*, api.*, ..memory.services (use `__getattr__` lazy import for bridge)

## Key Files
| File | Purpose |
|------|---------|
| rule_engine_insights.py | Fast rule-based insight generation (~80% of insights) |
| deep_reasoning_engine.py | Sonnet-powered deep analysis for complex insights |
| insight_trend_detector.py | Pattern/trend detection across time series |
| insight_pipeline.py | 3-engine orchestration pipeline |
| insight_dedup_aware.py | Cross-engine deduplication |
| insight_repository.py | DB persistence with soft-delete and expiry |
| insight_feedback_service.py | User feedback processing and preference learning |
| delivery_timing_engine.py | Optimal push timing based on user patterns |
| insight_lifecycle.py | State machine: draft → active → delivered → expired |
| insight_llm_client.py | LLM client wrapper for insight generation |
| tasks.py | Celery tasks: proactive scan (daily 08:00) |

## Module Conventions
- Circular dependency with memory module resolved via `__getattr__` lazy import
- Insights have `ActionSpec` with typed action chips (OPEN_CHAT, NAVIGATE, etc.)
- `disposition` field controls lifecycle (KEEP, DELETE, MERGE)
- Dedup uses content hash + entity overlap scoring
- Holiday insights routed through LLM path with DELETE disposition
