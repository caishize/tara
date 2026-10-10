# Secretary

> AI-Powered Family Secretary (智能家庭助手)

## Bootstrap
```bash
./scripts/bootstrap.sh  # From zero to running
```

## Commands
| Command | Purpose |
|---------|---------|
| `cd backend && uvicorn src.main:app --reload` | Start backend API |
| `cd backend && python -m src.ai_engine.worker_main` | Start Agent Worker |
| `cd backend && pytest` | Run backend tests |
| `cd backend && black --check src/ && flake8 src/ && mypy src/` | Lint + type check |
| `cd mobile && flutter run` | Start mobile app |
| `cd mobile && flutter test` | Run mobile tests |
| `cd backend && alembic upgrade head` | Run DB migrations |
| `./scripts/start.sh all` | Start all services |

## Architecture
Dual-brain routing: Haiku 4.5 Fast Path (~80%) + Sonnet 4 Slow Path (~20%) via Claude Agent SDK. Agents are ephemeral with DB state rehydration. Full details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

Layer model: Types/DB(0) → Config(1) → External APIs(2) → Service/Core(3) → AI Engine(4) → API(5)
Core is a peer layer to Service (both layer 3). Mobile is independent (REST/WebSocket).
See `backend/tests/test_architecture.py` for mechanical enforcement.

## Key Conventions (Top 5)
1. **Relative imports** within `backend/src/`; absolute in `tests/`
2. **UTC everywhere**: `DateTime(timezone=True)`, `utc_now()` only time source
3. **No hardcoding**: All config via env vars / `config/settings.py`
4. **No mock data in production**: Fail explicitly, mock only in `tests/`
5. **PendingAction for sensitive ops**: Agents never execute directly, user confirms first

Full conventions: [docs/CONVENTIONS.md](docs/CONVENTIONS.md)

## Module Map
| Module | Path | Purpose | CLAUDE.md |
|--------|------|---------|-----------|
| AI Engine | `backend/src/ai_engine/` | Dual-brain routing, SDK, tools, workers | Yes |
| Curation | `backend/src/modules/curation/` | Event strategy, conflict detection | Yes |
| Insight | `backend/src/modules/insight/` | 3-engine insight generation | Yes |
| Trip | `backend/src/modules/trip/` | Travel planning, itineraries | Yes |
| Briefing | `backend/src/modules/briefing/` | Daily briefings, recommendations | Yes |
| Gift | `backend/src/modules/gift/` | Gift recommendations, scrapers | Yes |
| Member | `backend/src/modules/member/` | Family, devices, trust | Yes |
| Memory | `backend/src/modules/memory/` | Extraction, compression, GraphRAG | Yes |
| Date Manager | `backend/src/modules/date_manager/` | Holidays, reminders, lunar calendar | Yes |
| Views | `backend/src/modules/views/` | Kanban, timeline, knowledge graph | Yes |
| Conversation | `backend/src/modules/conversation/` | Sessions, PendingAction, feedback | Yes |
| Relationship | `backend/src/modules/relationship/` | Favor tracking, care suggestions, relationship health | Yes |
| Core | `backend/src/core/` | Auth, events, scheduler, WebSocket | Yes |
| API Routes | `backend/src/api/v1/` | REST endpoints | Yes |
| Mobile Chat | `mobile/lib/features/chat/` | Conversation UI | Yes |
| Mobile Kanban | `mobile/lib/features/kanban/` | Curation timeline | Yes |
| Mobile Profile | `mobile/lib/features/profile/` | User profile | Yes |
| Mobile Trip | `mobile/lib/features/trip/` | Trip planning UI | Yes |

## Workflow (Research → Plan → Execute → Verify)

Full lifecycle: [docs/WORKFLOW.md](docs/WORKFLOW.md)

| Phase | Command | Purpose |
|-------|---------|---------|
| Ideate | `/office-hours` | Product diagnostic, design doc |
| Plan | `/plan-ceo-review` | Strategy & scope review |
| Plan | `/plan-eng-review` | Architecture & eng review |
| Plan | `/plan-design-review` | Design & UX review |
| Decompose | `/spec-to-task` | Layer-aware execution plan |
| Execute | develop + hooks | Implement with automatic enforcement |
| Verify | `/verify` | Build, test, lint, arch check |
| Review | `/review` | PR structural review (SQL, LLM safety) |
| Review | `/harness-review` | Four-pillar harness review |
| Ship | `/ship` | Version, changelog, PR |
| Docs | `/document-release` | Post-ship doc sync |
| Retro | `/retro` + `/harness-dashboard` | Eng metrics + harness health |
| Guard | `/encode-mistake` | Convert failures to rules |
| Sweep | `/entropy-sweep` | Weekly codebase health scan |

## Documentation
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Conventions: [docs/CONVENTIONS.md](docs/CONVENTIONS.md)
- Testing: [docs/TESTING.md](docs/TESTING.md)
- Linting: [docs/LINTING.md](docs/LINTING.md)
- Decisions (ADRs): [docs/DECISIONS.md](docs/DECISIONS.md)
- Providers: [docs/PROVIDERS.md](docs/PROVIDERS.md)
- Observability: [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md)
- Workflow: [docs/WORKFLOW.md](docs/WORKFLOW.md)
- PRD: [docs/PRD-生活秘书-统一版.md](docs/PRD-生活秘书-统一版.md)
- API Reference: [docs/api-reference.md](docs/api-reference.md)
- Design Docs: [docs/design-docs/](docs/design-docs/)
- Execution Plans: [docs/exec-plans/](docs/exec-plans/)
- Historical References: [docs/references/](docs/references/)

**Env vars**: `DATABASE_HOST`, `DATABASE_PASSWORD`, `REDIS_HOST`, `JWT_SECRET`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`
