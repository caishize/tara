# Secretary Project Constitution

<!--
SYNC IMPACT REPORT
==================
Version: 1.0.0 (Initial Constitution)
Date: 2025-01-14
Change Type: MAJOR - Initial constitution establishment

Modified Principles: N/A (Initial version)
Added Sections:
  - Core Principles (6 principles)
  - Architecture & Technology Standards
  - Development Workflow
  - Governance

Templates Status:
  ✅ spec-template.md - Aligned with conversation-first and testability principles
  ✅ plan-template.md - Aligned with plugin architecture and security standards
  ✅ tasks-template.md - Aligned with test-first discipline
  ✅ checklist-template.md - Aligned with quality gates
  ✅ agent-file-template.md - Ready for use

Follow-up TODOs: None
-->

## Core Principles

### I. Conversation-First Design (NON-NEGOTIABLE)

**Rule**: Every user-facing feature MUST prioritize natural language interaction (voice/text) as the primary interface. Forms and structured UI are secondary fallbacks.

**Rationale**: The Secretary application is designed to act as a human assistant. Real assistants communicate through conversation, not forms. Users should be able to say "我老婆叫李女士,今年32岁" instead of filling out fields. This reduces friction, enables hands-free operation, and creates a more natural user experience.

**Enforcement**:
- All user stories MUST include conversation flow examples
- Every feature spec MUST define natural language intents and entities
- LLM integration MUST be present for intent recognition and slot filling
- UI forms may only be used when conversation fails or for bulk editing scenarios

### II. Plugin Architecture for All External Dependencies

**Rule**: All third-party services (LLM providers, databases, ASR/TTS, OCR, etc.) MUST be abstracted behind interfaces with runtime-swappable implementations.

**Rationale**: AI technology evolves rapidly. Vendor lock-in poses risks to cost, availability, and flexibility. Plugin architecture enables:
- Technology migration without core code changes
- Cost optimization by switching providers
- Local/cloud hybrid deployment
- Mock implementations for testing

**Enforcement**:
- No direct vendor SDK calls in business logic
- All providers MUST implement standardized interfaces (e.g., `LLMProvider`, `ASRProvider`, `VectorDBProvider`)
- Configuration-driven provider selection via `config/providers.yaml`
- Every provider MUST have a mock implementation for testing

### III. Privacy-First & Data Security (NON-NEGOTIABLE)

**Rule**: User privacy and data security are paramount. Sensitive data MUST be encrypted, access-controlled, and minimally exposed.

**Rationale**: The application handles highly sensitive family information (health records, financial data, ID numbers, children's data). Data breaches or privacy violations would destroy user trust irreparably.

**Enforcement**:
- Sensitive fields (SSN, ID numbers, health data, biometrics) MUST use AES-256 encryption at rest
- Field-level access control via sensitivity classification (PUBLIC, PRIVATE, RESTRICTED, CONFIDENTIAL)
- Privacy-aware LLM usage: No RESTRICTED/CONFIDENTIAL data in external LLM calls without explicit user consent
- Data minimization: Only collect what's necessary, anonymize when possible
- GDPR/CCPA compliance: Right to deletion, data export, consent management
- Regular security audits for all features handling sensitive data

### IV. Test-First Development (NON-NEGOTIABLE)

**Rule**: Tests MUST be written BEFORE implementation. No code ships without tests.

**Rationale**: The Secretary application handles critical family information where errors have real-world consequences (missed medication reminders, forgotten birthdays, financial mistakes). Test-first development ensures reliability and prevents regressions.

**Enforcement**:
- TDD workflow: Write test → User approval → Watch test fail → Implement → Test passes → Refactor
- Unit tests for all business logic (target: >80% coverage)
- Integration tests for cross-module workflows (e.g., member creation → birthday reminder)
- E2E tests for critical user journeys (conversation flows)
- Tests MUST run in CI/CD pipeline before merge
- No PR approval without passing tests

### V. Incremental Delivery & User Validation

**Rule**: Features MUST be delivered in independently testable increments with user validation at each stage.

**Rationale**: Building a complex multi-module system risks wasting effort on unwanted features. Incremental delivery enables early feedback, course correction, and faster time-to-value.

**Enforcement**:
- User stories MUST include "Independent Test" criteria
- Each story MUST be deliverable without dependencies on incomplete features
- Priority system (P0-P4) ensures MVP scope is clear
- User acceptance testing MUST occur before marking features complete
- Features ship behind feature flags for gradual rollout

### VI. Observability & Debuggability

**Rule**: All system behavior MUST be observable through structured logs, metrics, and traces. Silent failures are unacceptable.

**Rationale**: With 15 modules, complex LLM chains, and multi-provider integrations, debugging production issues requires comprehensive observability.

**Enforcement**:
- Structured logging (JSON format) with correlation IDs for all requests
- Error tracking with full context (user input, LLM responses, provider failures)
- Metrics for latency, error rates, provider costs
- Distributed tracing for cross-service calls
- No silent exception swallowing (`try-except-pass` is forbidden)
- User-facing errors MUST be actionable (e.g., "ASR provider unavailable, please type your message")

## Architecture & Technology Standards

### Tech Stack

**Backend**: Python 3.11+ (FastAPI for API layer, Celery for async tasks)

**Database**:
- PostgreSQL (primary relational data, family members, relationships)
- Redis (caching, session state, Celery broker)
- Vector DB (Milvus/Qdrant/pgvector, plugin-based for semantic search)
- Optional: Neo4j/NetworkX (relationship graphs, if needed for complex family trees)

**AI/ML**:
- LLM: Plugin-based (OpenAI GPT-4, Anthropic Claude, local Llama/Qwen)
- Embeddings: Plugin-based (OpenAI, BGE local)
- ASR: Plugin-based (Whisper, Azure, Baidu, Mock)
- TTS: Plugin-based (OpenAI TTS, Azure, Edge-TTS, Mock)
- OCR: Plugin-based (PaddleOCR, Tesseract, Baidu, Mock)

**Frontend**: React/Next.js with mobile-first responsive design

**Infrastructure**:
- Docker + Docker Compose for local dev
- Kubernetes for production (optional, future)
- CI/CD: GitHub Actions
- Monitoring: Prometheus + Grafana (or equivalent)

### Non-Functional Requirements

**Performance**:
- Conversation response latency: <3 seconds (P95)
- Database queries: <500ms (P95)
- API endpoint latency: <1 second (P95)

**Scalability**:
- Support 1000+ concurrent users
- Support families with 50+ members
- Vector DB: Handle 1M+ document embeddings

**Availability**:
- Target: 99.9% uptime (not enforced in MVP)
- Graceful degradation: If LLM fails, fall back to structured forms
- Offline support: Core data viewing must work without internet

### Security Standards

**Authentication**: OAuth 2.0 + JWT for API access, support social login (Google, WeChat)

**Authorization**: Role-based (family admin, member, viewer), field-level access control

**Data Encryption**:
- In transit: TLS 1.3
- At rest: AES-256 for sensitive fields
- Key management: Cloud KMS or HashiCorp Vault

**Compliance**: GDPR, CCPA (right to deletion, data export)

## Development Workflow

### Feature Development Process

1. **Specification** (`/speckit.specify`): Create detailed spec from user stories, acceptance scenarios, edge cases
2. **Planning** (`/speckit.plan`): Architecture design, data models, API contracts, dependency analysis
3. **Task Breakdown** (`/speckit.tasks`): Generate ordered, testable tasks
4. **Analysis** (`/speckit.analyze`): Cross-artifact consistency check against this constitution
5. **Implementation** (`/speckit.implement`): TDD cycle with user validation at each increment
6. **Review**: Code review, test coverage check, security audit
7. **Deployment**: Feature flag enabled, gradual rollout, monitoring

### Branching Strategy

- `main`: Production-ready code
- `001-member-management`, `002-date-time`, etc.: Feature branches named by spec ID
- PRs require: Passing tests, code review approval, constitution compliance check

### Quality Gates

**Before Merge**:
- All tests pass (unit, integration, E2E)
- Code coverage ≥80%
- No security vulnerabilities (automated SAST scan)
- Constitution compliance verified (`/speckit.analyze` shows no CRITICAL issues)
- User acceptance criteria met

**Before Production**:
- Manual QA on staging environment
- Performance benchmarks met
- Observability dashboards configured
- Rollback plan documented

## Governance

### Amendment Procedure

This constitution can be amended through:
1. Proposal: Document proposed change with rationale
2. Review: Team discussion, impact analysis on existing specs/plans
3. Approval: Consensus (or project owner decision if team disagrees)
4. Migration: Update dependent templates, re-analyze affected features
5. Version bump: Follow semantic versioning (MAJOR for breaking changes, MINOR for additions, PATCH for clarifications)

### Constitution Authority

- This constitution supersedes all other project guidelines
- Features violating MUST principles cannot be merged
- When spec/plan conflicts with constitution, constitution wins
- If constitution principles need exceptions, amend the constitution first (do not bypass)

### Compliance Review

- Every `/speckit.analyze` run MUST check constitutional alignment
- CRITICAL severity issues MUST be resolved before implementation
- Product owner reviews constitution compliance quarterly

### Runtime Guidance

For day-to-day development decisions not covered by this constitution, refer to:
- Architecture docs: `docs/architecture/*.md`
- API contracts: Generated from specs
- Testing guide: `docs/testing-guide.md` (to be created)

---

**Version**: 1.0.0 | **Ratified**: 2025-01-14 | **Last Amended**: 2025-01-14
