# Design Document: Insight-Centric Timeline Transformation

**Status**: Draft
**Author**: Solution Architect
**Date**: 2026-03-03
**Tone**: Ambitious

---

## Executive Summary

This document defines the architecture for inverting the mobile timeline's information hierarchy: **insights become the primary content unit, events become embedded context within insights.** The current 5-section event-centric kanban becomes a 2-section insight-centric feed. The backend API surface expands to carry rich entity relationships that are currently discarded at the API boundary. The action pipeline connects insight types to domain-specific PendingAction flows.

The transformation targets three ROOT findings, three HIGH issues, and four MEDIUM issues identified during exploration. All changes preserve backward compatibility through a new endpoint + feature flag strategy, enabling incremental rollout.

---

## 1. Architecture Decisions

### AD-1: New API Endpoint vs. Extend Existing Kanban Endpoint

**Context**: The current `GET /kanban/` returns `KanbanResponse` with 4 event buckets + a flat `insights` list. The insight-centric view requires entity-resolved insights with embedded event context — a fundamentally different response shape. Extending the existing endpoint risks breaking the contract for any current consumers and complicates backward compatibility.

**Decision**: **New endpoint `GET /kanban/insight-feed`** returning `InsightFeedResponse`.

The existing `GET /kanban/` remains unchanged. The new endpoint returns insights as primary items, each carrying resolved entity summaries (events, members, trips). The mobile client switches to the new endpoint behind a feature flag. Once adoption is confirmed, the old endpoint is deprecated (not removed).

**Alternatives Rejected**:
- *Extend existing endpoint with query param `?view=insight_feed`*: Rejected because the response shapes diverge significantly (`KanbanResponse` vs `InsightFeedResponse`), and a query-param polymorphic response is harder to type-check and document.
- *GraphQL-style approach with field selection*: Over-engineered for this use case. The entity resolution cost is low (already loaded in the kanban query), and a fixed schema is simpler to cache and optimize.

**Consequences**:
- (+) Zero risk to existing mobile builds — they continue using `GET /kanban/`
- (+) Clean API contract separation
- (-) Two endpoints to maintain during transition period (~2 sprints)
- (-) Shared service logic may need minor refactoring to avoid duplication

---

### AD-2: Section Restructuring — 2-Section "Now / Later"

**Context**: The current 5-section layout (近期重点, 贴心提醒, 别忘了准备, 接下来, 远期安排) creates cognitive fragmentation (HIGH-1). Users must mentally merge scattered signals across sections. The insight-centric model demands a simpler container that lets AI-driven insights flow naturally.

**Decision**: **2-section layout: "Now" (现在关注) + "Later" (稍后查看)**.

"Now" contains:
- Urgent/important insights (urgency = urgent | important) — rendered as `InsightFeedCard` with embedded event context
- Focus events from `this_week` that have no associated insight — rendered as slim `EventMiniCard` rows
- Preparation items that need action — inlined within their parent insight or as standalone prep cards

"Later" contains:
- Normal-urgency insights — collapsible section, initially showing top 3
- Monthly + later events — rendered as a compact timeline, collapsed by default

This reduces the initial viewport to 2 cognitive zones: "things demanding attention" and "everything else."

**Alternatives Rejected**:
- *3-section "Urgent / Insights / Timeline"*: Rejected because the "Insights" middle section would still be below the fold for most loads (replicating ROOT-1). The 2-section model ensures insights are always in the first scroll position.
- *Single infinite feed*: Rejected because it loses the temporal anchoring that makes the timeline useful. Users need a clear "now vs later" boundary.

**Consequences**:
- (+) Dramatic reduction in cognitive load — from 5 sections to 2
- (+) Insights guaranteed above the fold
- (-) "Preparation" items lose their dedicated section — they must be embedded within insight cards or the "Now" zone
- (-) Users accustomed to the current layout need onboarding (mitigated by feature flag + gradual rollout)

---

### AD-3: InsightFeedCard State Management — BLoC-Driven Expansion

**Context**: The current `InsightCard` is a `StatelessWidget` (HIGH-3). The new `InsightFeedCard` needs: expansion/collapse animation, embedded event context loading, action chip state (tapped/pending/confirmed), and adopted-state visual transition. This requires stateful behavior.

**Decision**: **BLoC-driven expansion with `AnimatedCrossFade` for visual transitions.**

Each `InsightFeedCard` reads from a `KanbanBloc` state field `expandedInsightId: String?` (single-expansion model — expanding one collapses others). The card itself remains a `StatelessWidget` that reads expansion state from the BLoC. Animation is handled by wrapping the detail section in `AnimatedCrossFade` with a 250ms duration.

Action chip state is tracked in the BLoC as `Map<String, InsightActionState>` where `InsightActionState` is `{idle, pending, confirmed, failed}`.

**Alternatives Rejected**:
- *StatefulWidget with AnimationController per card*: Rejected because it scatters state management across N widget instances, makes testing harder, and requires manual disposal of controllers. The BLoC approach centralizes state.
- *Separate InsightDetailBloc*: Over-scoped. The expansion/collapse and action state are tightly coupled to the kanban view state — they should live in the existing `KanbanBloc`.

**Consequences**:
- (+) Single source of truth for all insight card state
- (+) Testable via BLoC unit tests without widget test overhead
- (+) Automatic collapse of other cards when one expands (accordion UX)
- (-) `KanbanLoaded` state grows larger — mitigated by keeping the new fields nullable/defaulted

---

### AD-4: Backend Entity Resolution — Resolve at API

**Context**: ROOT-2 identifies that `related_event_ids`, `related_member_ids`, `related_trip_ids`, and `related_memory_ids` from `MemoryInsight` are discarded during the kanban mapping. The mobile client has no way to display contextual event/member information within insights. Two strategies: resolve entities server-side and embed summaries in the API response, or return IDs and let mobile lazy-load.

**Decision**: **Resolve at API — server-side entity resolution with embedded summaries.**

The new `InsightFeedResponse` includes `InsightFeedItem` objects, each carrying:
- `related_events: List[InsightRelatedEvent]` — resolved from `related_event_ids` with title, date, type
- `related_members: List[InsightRelatedMember]` — resolved from `related_member_ids` with name, relationship
- `related_trip: Optional[InsightRelatedTrip]` — resolved from `related_trip_ids[0]` with name, dates, status
- `source_context: Optional[str]` — a pre-rendered human-readable context string

Resolution happens in a single batch query during the kanban service call (the events and members are already partially loaded).

**Alternatives Rejected**:
- *Return raw IDs, lazy-load from mobile*: Rejected because it would require N additional API calls per insight view, adding latency and complexity. The data is already available in the service layer.
- *Full entity embedding (entire event/member objects)*: Over-fetching. The mobile card only needs title + date + type for events, name + relationship for members. Lightweight summary models are sufficient.

**Consequences**:
- (+) Zero additional round-trips from mobile
- (+) Server controls what context is shown (can evolve without mobile deploy)
- (-) Slightly larger API response (~200 bytes per insight with 2-3 related entities)
- (-) Server does more work per request (mitigated: batch queries, already-loaded data)

---

### AD-5: Backward Compatibility — New Endpoint + Feature Flag

**Context**: The transformation is a breaking UX change. Mobile users on older versions must continue using the current kanban. The transition should be measurable (A/B testable) and reversible.

**Decision**: **New endpoint + client-side feature flag.**

Backend:
- `GET /kanban/` — unchanged, serves current `KanbanResponse`
- `GET /kanban/insight-feed` — new, serves `InsightFeedResponse`

Mobile:
- Feature flag `insight_feed_enabled` (default `false`, controlled via remote config)
- When enabled, `KanbanBloc` dispatches `LoadInsightFeed` instead of `LoadKanbanView`
- Two widget subtrees: `_buildKanban(state)` (existing) and `_buildInsightFeed(state)` (new)

Deprecation timeline: after 2 sprint cycles with >80% flag-on, the old endpoint is marked deprecated.

**Alternatives Rejected**:
- *Replace in-place with version header*: Risky. A version header on the same endpoint means accidental misrouting breaks the client.
- *Server-side A/B via user cohort*: The server shouldn't know about mobile layout preferences. Feature flags belong in the mobile layer.

**Consequences**:
- (+) Zero-risk rollout with instant rollback (flip flag)
- (+) A/B testable — can measure engagement metrics on both layouts
- (-) Temporary code duplication in the mobile kanban page
- (-) Feature flag management overhead

---

## 2. Acceptance Criteria

### ROOT-1: Information Architecture Inversion

| # | Criterion | Verification |
|---|-----------|-------------|
| R1-AC1 | When `insight_feed_enabled` is true, the first visible content in the "Now" section is an InsightFeedCard (not an event card) | UI test: load kanban with 1+ insight + 1+ event, assert first child of "Now" section is `InsightFeedCard` |
| R1-AC2 | Events appear ONLY as embedded context within InsightFeedCards or as secondary rows below all insights in the "Now" section | Widget test: verify no standalone `FocusCard` renders above any `InsightFeedCard` |
| R1-AC3 | The "Later" section is collapsed by default and does not push insights below the fold | Integration test: measure scroll offset — all "Now" insights visible without scrolling on a 667pt viewport (iPhone SE) |
| R1-AC4 | Insights with urgency "urgent" or "important" always appear at the top of "Now", regardless of creation time | Unit test on BLoC state sorting |

**Edge Cases**:
- Zero insights, N events: "Now" shows events directly (graceful degradation)
- N insights, zero events: "Now" shows insight cards without embedded events
- All insights dismissed: "Now" falls back to event-only view, show "让AI帮我整理" prompt

### ROOT-2: Insight Metadata Preservation at API Boundary

| # | Criterion | Verification |
|---|-----------|-------------|
| R2-AC1 | `InsightFeedItem` in API response includes `related_events` resolved from `MemoryInsight.related_event_ids` | Backend integration test: create MemoryInsight with 2 related_event_ids, call `/kanban/insight-feed`, assert `related_events` has 2 items with correct titles |
| R2-AC2 | `InsightFeedItem` includes `related_members` resolved from `MemoryInsight.related_member_ids` | Same pattern — assert member names present |
| R2-AC3 | `InsightFeedItem` includes `related_trip` resolved from first entry in `MemoryInsight.related_trip_ids` | Assert trip name + start_date present |
| R2-AC4 | Mobile `KanbanInsightModel` has `relatedEvents`, `relatedMembers`, `relatedTrip` fields populated from API response | Dart unit test: deserialize mock JSON, assert fields populated |
| R2-AC5 | When related entity IDs reference deleted/invalid entities, the resolved list simply omits them (no error) | Backend test: insert insight with nonexistent event_id, assert `related_events` is empty, no 500 |

**Edge Cases**:
- Insight with empty `related_event_ids`: `related_events` returns `[]`
- Insight referencing a cancelled event: event still appears in `related_events` (with `status: "cancelled"`)
- Member no longer in family: omitted from `related_members`

### ROOT-3: Action Pipeline Connection

| # | Criterion | Verification |
|---|-----------|-------------|
| R3-AC1 | InsightFeedCard's action chips dispatch domain-specific actions: `SUGGEST_MEETING` opens meeting scheduling flow, `SUGGEST_GREETING` opens greeting composer, `SUGGEST_GIFT` navigates to gift recommendations | Widget test per action type |
| R3-AC2 | Tapping an action chip creates a `PendingAction` via API (not just visual feedback) | Integration test: tap "安排见面" chip, assert `POST /pending-actions` called with `action_type: "suggest_meeting"` |
| R3-AC3 | Action chip shows loading state while PendingAction is being created, then transitions to confirmed state | Widget test with mock BLoC |
| R3-AC4 | InsightDetailSheet (expanded view) shows domain-specific action buttons based on `actionType`, not generic feedback-only buttons | Widget test: render sheet for insight with `actionType: "suggest_meeting"`, assert "安排见面" button present alongside feedback buttons |
| R3-AC5 | Insights without any `actionType` still render correctly (feedback-only mode) | Widget test: render insight with `actionType: null`, assert only feedback buttons shown |

**Edge Cases**:
- Action chip tapped while offline: show error toast, revert chip to idle state
- PendingAction already exists for this insight: API returns existing action, chip shows "已安排"
- User dismisses insight after creating PendingAction: action persists (not cascade-deleted)

---

## 3. Component Architecture

### 3.1 New Widget Tree

```
CuratedTimelinePage
├── _buildHeader()                      (unchanged)
├── _buildSegmentedControl()            (unchanged)
├── _buildInsightFeed(InsightFeedLoaded) ← NEW (replaces _buildKanban when flag on)
│   ├── SliverToBoxAdapter: "Now" Section Header
│   ├── SliverList: InsightFeedCard[]   ← NEW (urgent/important insights + focus events)
│   │   └── InsightFeedCard
│   │       ├── _InsightHeader (emoji + label + urgency badge)
│   │       ├── _InsightBody (title + content, maxLines based on expansion)
│   │       ├── _EmbeddedEventList      ← NEW (resolved related events as chips)
│   │       ├── _RelatedMemberRow       ← NEW (avatar circles for related members)
│   │       ├── _ActionChipRow          ← NEW (domain-specific action buttons)
│   │       └── AnimatedCrossFade → _InsightExpandedDetail
│   │           ├── Full content text
│   │           ├── Related trip card   ← NEW
│   │           ├── Context hint
│   │           └── Feedback buttons
│   ├── SliverToBoxAdapter: Standalone Events (this_week without insights)
│   │   └── EventMiniCard[]             ← NEW (compact event row)
│   ├── SliverToBoxAdapter: "Later" Section (collapsed)
│   │   ├── Normal-urgency InsightFeedCard[] (top 3)
│   │   ├── "Show more" expand button
│   │   └── Timeline event rows (monthly + later)
│   └── SliverPadding (bottom: 80)
└── _buildMemoryLaneTab()               (unchanged)
```

### 3.2 InsightFeedCard Architecture

```dart
// New file: mobile/lib/features/kanban/presentation/widgets/insight_feed_card.dart

class InsightFeedCard extends StatelessWidget {
  final InsightFeedItemModel insight;
  final bool isExpanded;
  final InsightActionState actionState;  // idle | pending | confirmed | failed
  final VoidCallback? onTap;            // expand/collapse
  final VoidCallback? onDismiss;        // swipe to dismiss
  final void Function(String actionType)? onActionTap;
  final void Function(String feedbackType)? onFeedback;
  final void Function(String eventId)? onEventTap;  // tap embedded event
  final void Function(String memberId)? onMemberTap; // tap related member
}
```

**States**:
1. **Collapsed** (default): Header + title + 2-line content preview + action chips + embedded event chips (max 2)
2. **Expanded**: Full content + all related events + related members + trip card + context hint + feedback buttons
3. **Adopted**: 50% opacity with checkmark overlay (existing behavior, improved with proper AnimatedOpacity)
4. **Action Pending**: Action chip shows CircularProgressIndicator, other chips disabled
5. **Action Confirmed**: Action chip shows check icon with "已安排" label, auto-transition to adopted after 2s

### 3.3 Data Model Changes (Dart)

```dart
// Additions to kanban_models.dart or new file: insight_feed_models.dart

/// Lightweight summary of a related event within an insight
class InsightRelatedEventModel {
  final String id;
  final String title;
  final String? eventType;
  final DateTime? startTime;
  final String? location;

  const InsightRelatedEventModel({...});

  factory InsightRelatedEventModel.fromJson(Map<String, dynamic> json) {...}
}

/// Lightweight summary of a related member
class InsightRelatedMemberModel {
  final String id;
  final String name;
  final String? relationship;  // "spouse", "parent", "child", "friend"
  final String? avatarUrl;

  const InsightRelatedMemberModel({...});

  factory InsightRelatedMemberModel.fromJson(Map<String, dynamic> json) {...}
}

/// Lightweight summary of a related trip
class InsightRelatedTripModel {
  final String id;
  final String name;
  final DateTime? startDate;
  final DateTime? endDate;
  final String? status;

  const InsightRelatedTripModel({...});

  factory InsightRelatedTripModel.fromJson(Map<String, dynamic> json) {...}
}

/// Extended insight model for insight-feed view (replaces KanbanInsightModel when flag on)
class InsightFeedItemModel {
  final String id;
  final String title;
  final String content;
  final String insightType;
  final int priority;
  final String urgency;
  final DateTime? createdAt;
  final String? actionType;
  final Map<String, dynamic>? actionData;
  final List<String> actionOptions;
  final String? contextHint;
  // NEW: Resolved entity relationships
  final List<InsightRelatedEventModel> relatedEvents;
  final List<InsightRelatedMemberModel> relatedMembers;
  final InsightRelatedTripModel? relatedTrip;
  final String? sourceContext;  // Pre-rendered context string

  const InsightFeedItemModel({...});

  factory InsightFeedItemModel.fromJson(Map<String, dynamic> json) {...}
}

/// Response model for insight-feed endpoint
class InsightFeedResponseModel {
  final List<InsightFeedItemModel> insights;
  final List<KanbanEventModel> standaloneEvents; // this_week events without insights
  final List<KanbanEventModel> laterEvents;      // monthly + later merged
  final List<KanbanEventModel> needsPreparation; // unchanged

  const InsightFeedResponseModel({...});

  factory InsightFeedResponseModel.fromJson(Map<String, dynamic> json) {...}
}
```

### 3.4 BLoC State Extensions

```dart
// Extensions to kanban_state.dart

/// Insight feed loaded (parallel state to KanbanLoaded)
class InsightFeedLoaded extends KanbanState {
  final InsightFeedResponseModel feed;
  final bool isRefreshing;
  final Set<String> adoptedInsightIds;
  final String? expandedInsightId;  // single-expansion accordion
  final Map<String, InsightActionState> actionStates;  // per-insight action state

  const InsightFeedLoaded({
    required this.feed,
    this.isRefreshing = false,
    this.adoptedInsightIds = const {},
    this.expandedInsightId,
    this.actionStates = const {},
  });

  InsightFeedLoaded copyWith({...});
}

enum InsightActionState { idle, pending, confirmed, failed }
```

### 3.5 BLoC Event Extensions

```dart
// Extensions to kanban_event.dart

class LoadInsightFeed extends KanbanEvent { const LoadInsightFeed(); }
class ExpandInsight extends KanbanEvent { final String insightId; ... }
class CollapseInsight extends KanbanEvent { const CollapseInsight(); }
class ExecuteInsightAction extends KanbanEvent {
  final String insightId;
  final String actionType;
  ...
}
```

### 3.6 InsightStyle Unification (MEDIUM-4 Fix)

Extract duplicated style resolution from `InsightCard._insightStyle` and `InsightDetailSheet._styleForType` into a shared utility:

```dart
// New file: mobile/lib/features/kanban/presentation/utils/insight_style.dart

class InsightStyle {
  final Color accentColor;
  final List<Color> bgGradient;
  final Color borderColor;
  final String emoji;
  final String label;

  const InsightStyle({...});

  /// Single source of truth for insight visual styling
  static InsightStyle resolve({
    required String insightType,
    required String urgency,
  }) {
    if (urgency == 'urgent') return _urgentStyle;
    if (urgency == 'important') return _importantStyle;
    return _typeStyles[insightType] ?? _defaultStyle;
  }

  static const _typeStyles = <String, InsightStyle>{
    'reminder': InsightStyle(...),
    'suggestion': InsightStyle(...),
    // ... all type mappings, defined once
  };
}
```

This resolves MEDIUM-4 (DRY violation) and ensures `InsightCard`, `InsightDetailSheet`, and the new `InsightFeedCard` all share the same style definitions.

---

## 4. API Changes

### 4.1 New Pydantic Schemas

```python
# Additions to backend/src/modules/views/kanban_schemas.py

class InsightRelatedEvent(BaseModel):
    """Lightweight event summary embedded in insight feed items."""
    id: str
    title: str
    event_type: Optional[str] = None
    start_time: Optional[datetime] = None
    location: Optional[str] = None
    status: str = "pending"

class InsightRelatedMember(BaseModel):
    """Lightweight member summary embedded in insight feed items."""
    id: str
    name: str
    relationship: Optional[str] = None

class InsightRelatedTrip(BaseModel):
    """Lightweight trip summary embedded in insight feed items."""
    id: str
    name: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None

class InsightFeedItem(BaseModel):
    """Primary content unit in the insight-centric feed."""
    id: str
    title: str
    content: str
    insight_type: str
    priority: int = 5
    urgency: str = "normal"
    action_type: Optional[str] = None
    action_data: Optional[dict] = None
    action_options: List[str] = Field(default_factory=list)
    context_hint: Optional[str] = None
    created_at: Optional[datetime] = None
    # Resolved entity relationships (ROOT-2 fix)
    related_events: List[InsightRelatedEvent] = Field(default_factory=list)
    related_members: List[InsightRelatedMember] = Field(default_factory=list)
    related_trip: Optional[InsightRelatedTrip] = None
    source_context: Optional[str] = None

class InsightFeedResponse(BaseModel):
    """Response for the insight-centric feed endpoint."""
    insights: List[InsightFeedItem] = Field(default_factory=list)
    standalone_events: List[KanbanEvent] = Field(default_factory=list)
    later_events: List[KanbanEvent] = Field(default_factory=list)
    needs_preparation: List[KanbanEvent] = Field(default_factory=list)
```

### 4.2 New API Endpoint

```python
# Addition to backend/src/api/v1/kanban.py

@router.get("/insight-feed", response_model=InsightFeedResponse)
async def get_insight_feed(
    limit: int = Query(100, ge=1, le=500),
    family_id: Optional[UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get insight-centric feed view of future events."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    service = KanbanService(db)
    return await service.get_insight_feed(
        family_id=effective_family_id,
        user_id=user_id,
        limit=limit,
    )
```

### 4.3 Service Logic Changes

**New method: `KanbanService.get_insight_feed()`**

This method reuses the existing `get_kanban_view()` event-fetching and insight-loading logic, but adds:

1. **Entity resolution step** after `_map_db_insights()`:
   - Collect all `related_event_ids`, `related_member_ids`, `related_trip_ids` from the `MemoryInsight` objects
   - Batch-query `CuratedEvent`, `FamilyMember`, `TripPlan` tables
   - Map into `InsightRelatedEvent`, `InsightRelatedMember`, `InsightRelatedTrip`

2. **Standalone event classification**:
   - Events in `this_week` that are NOT referenced by any insight's `related_event_ids` become `standalone_events`
   - Events referenced by insights are embedded within the insight (not duplicated)

3. **Merged "later" events**:
   - `monthly` + `later` from the original kanban merge into a single `later_events` list

```python
# Pseudocode for the resolution step
async def _resolve_insight_entities(
    self,
    insights: List[MemoryInsight],
    mapped_insights: List[KanbanInsight],
) -> List[InsightFeedItem]:
    # Collect all entity IDs across all insights
    all_event_ids = set()
    all_member_ids = set()
    all_trip_ids = set()
    for ins in insights:
        all_event_ids.update(ins.related_event_ids or [])
        all_member_ids.update(ins.related_member_ids or [])
        all_trip_ids.update(ins.related_trip_ids or [])

    # Batch resolve (3 parallel queries via asyncio.gather)
    events_by_id, members_by_id, trips_by_id = await asyncio.gather(
        self._batch_resolve_events(all_event_ids),
        self._batch_resolve_members(all_member_ids),
        self._batch_resolve_trips(all_trip_ids),
    )

    # Map to InsightFeedItem with resolved entities
    feed_items = []
    for ins, kanban_ins in zip(insights, mapped_insights):
        feed_items.append(InsightFeedItem(
            # ... copy all fields from kanban_ins ...
            related_events=[
                events_by_id[eid] for eid in (ins.related_event_ids or [])
                if eid in events_by_id
            ],
            related_members=[
                members_by_id[mid] for mid in (ins.related_member_ids or [])
                if mid in members_by_id
            ],
            related_trip=(
                trips_by_id.get((ins.related_trip_ids or [None])[0])
                if ins.related_trip_ids else None
            ),
        ))
    return feed_items
```

### 4.4 Backward Compatibility

- `GET /kanban/` response shape: **unchanged**
- `KanbanInsight` schema: **unchanged** (no fields added or removed)
- `InsightFeedItem` is a **superset** of `KanbanInsight` — clients parsing the old shape would simply ignore the new fields
- No database migrations required — all data already exists in the `memory_insights` columns
- No Celery task changes — insight generation pipeline is untouched

---

## 5. Risk Assessment

### 5.1 ROOT-1 (IA Inversion) — Widget Tree Restructuring

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Regression in existing kanban** | Medium | Feature flag isolates new code path. Old `_buildKanban` is untouched. Both paths tested independently. |
| **Empty state handling** | Low | Explicit empty-state logic: 0 insights → fallback to event-centric view with prompt. Tested via dedicated widget test. |
| **Scroll performance with expanded cards** | Medium | `AnimatedCrossFade` is lightweight. `SliverList` (not `Column`) used for insight list. Profile on iPhone SE before merge. |
| **Rollback complexity** | Low | Flip feature flag off → instant revert to `_buildKanban`. No data changes to undo. |

### 5.2 ROOT-2 (Metadata Preservation) — API Entity Resolution

| Risk | Severity | Mitigation |
|------|----------|------------|
| **N+1 query on entity resolution** | Medium | Batch resolution via `asyncio.gather` with 3 single-batch queries. Max entities per insight is bounded (~5 events, ~3 members, 1 trip). |
| **Stale entity references** | Low | IDs referencing deleted entities are silently omitted. No exception path. |
| **API response size increase** | Low | ~200 bytes per insight (entity summaries). 10 insights = ~2KB. Negligible on any connection. |
| **Rollback complexity** | Low | New endpoint can be removed. No schema changes to existing endpoint. |

### 5.3 ROOT-3 (Action Pipeline) — PendingAction Integration

| Risk | Severity | Mitigation |
|------|----------|------------|
| **PendingAction creation failure** | Medium | Optimistic UI: show loading state, revert on failure, show error toast. Backend returns 409 if duplicate action exists. |
| **Action type mismatch** | Low | Strict enum mapping: `actionType` from API must match `ActionType` enum. Unknown types fall back to "查看详情" (view detail). |
| **Accidental double-creation** | Medium | Backend enforces unique constraint on `(insight_id, action_type, status=pending)`. Mobile disables chip after first tap. |
| **Rollback complexity** | Low | Action chip logic is additive. Removing it leaves feedback-only buttons (current behavior). |

### 5.4 HIGH-2 (Visual Weight) — Style Normalization

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Breaking existing InsightCard styling** | Low | `InsightStyle.resolve()` produces identical output to current `_insightStyle` getter. Pixel-diff test before merge. |
| **Color palette reduction (18 → fewer)** | Medium | Phase this separately. First unify the resolver, then reduce palette in a follow-up PR with designer review. |

### 5.5 MEDIUM-1 (Pagination)

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Insight list grows unbounded** | Low | Current cap is 10 (after dedup). If we increase to 20 for the feed view, add cursor-based pagination. Backend already has `limit` param. |
| **Scroll position reset on load-more** | Low | Use `SliverList` with proper keys. Load-more appends to existing list in BLoC state. |

---

## 6. Implementation Groups

### Group 1: Foundation (Prerequisites)

**Goal**: Lay groundwork without any visible UX change. All changes backward-compatible.

| # | Task | Files | Scope |
|---|------|-------|-------|
| G1-1 | Create `InsightStyle` shared utility, migrate `InsightCard` and `InsightDetailSheet` to use it | `insight_style.dart` (new), `insight_card.dart`, `insight_detail_sheet.dart` | MEDIUM-4 fix |
| G1-2 | Add `InsightFeedItem`, `InsightRelatedEvent`, `InsightRelatedMember`, `InsightRelatedTrip` Pydantic schemas to `kanban_schemas.py` | `kanban_schemas.py` | Schema only, no endpoint |
| G1-3 | Add `_resolve_insight_entities()` and `_batch_resolve_*` methods to `KanbanService` | `kanban_service.py` | Service logic, no endpoint |
| G1-4 | Create `InsightFeedItemModel`, `InsightRelatedEventModel`, `InsightRelatedMemberModel`, `InsightRelatedTripModel` Dart models | `insight_feed_models.dart` (new) | Dart models only |
| G1-5 | Add `InsightFeedLoaded` state, `InsightActionState` enum, new events to `KanbanBloc` | `kanban_state.dart`, `kanban_event.dart`, `kanban_bloc.dart` | BLoC extension |
| G1-6 | Add feature flag `insight_feed_enabled` to remote config / local config | Config layer | Flag infrastructure |

**Dependencies**: None (all foundation work is independent).
**Verification**: Existing tests pass. New schemas serialize/deserialize correctly. BLoC emits `InsightFeedLoaded` from mock data.

### Group 2: Core Transformation

**Goal**: The insight-centric feed becomes functional end-to-end.

| # | Task | Files | Scope |
|---|------|-------|-------|
| G2-1 | Implement `GET /kanban/insight-feed` endpoint and `get_insight_feed()` service method | `kanban.py` (API), `kanban_service.py` | Backend endpoint (ROOT-2 fix) |
| G2-2 | Add `getInsightFeed()` to `CuratedTimelineRepository` and datasource | `curated_timeline_repository.dart`, `curated_timeline_datasource.dart`, `curated_timeline_repository_impl.dart` | Mobile data layer |
| G2-3 | Implement `_onLoadInsightFeed` handler in `KanbanBloc` | `kanban_bloc.dart` | BLoC handler |
| G2-4 | Build `InsightFeedCard` widget with collapsed/expanded states, embedded events, action chips | `insight_feed_card.dart` (new) | Core new widget (ROOT-1 fix) |
| G2-5 | Build `_buildInsightFeed()` in `CuratedTimelinePage` with 2-section "Now/Later" layout | `curated_timeline_page.dart` | Page integration (HIGH-1 fix) |
| G2-6 | Implement `ExecuteInsightAction` BLoC handler → `POST /pending-actions` | `kanban_bloc.dart`, `curated_timeline_datasource.dart` | Action pipeline (ROOT-3 fix) |
| G2-7 | Wire feature flag toggle: `LoadInsightFeed` vs `LoadKanbanView` based on config | `curated_timeline_page.dart` | Flag integration |

**Dependencies**: G1 complete.
**Verification**: End-to-end flow: load insight feed → see insights with embedded events → tap action chip → PendingAction created → chip shows confirmed state. Feature flag off → old kanban renders unchanged.

### Group 3: Polish & Optimization

**Goal**: Visual refinement, edge case handling, performance.

| # | Task | Files | Scope |
|---|------|-------|-------|
| G3-1 | Insight title `fontSize: 14` → `16`, event title remains `16` (visual weight parity, HIGH-2) | `insight_feed_card.dart`, `insight_style.dart` | Visual fix |
| G3-2 | Replace adopted-state `Stack+Opacity` hack with `AnimatedOpacity` + proper state in BLoC (MEDIUM-3) | `insight_feed_card.dart`, `kanban_bloc.dart` | Animation fix |
| G3-3 | Add cursor-based pagination for insights when count exceeds 10 (MEDIUM-1) | `kanban_service.py`, `kanban_schemas.py`, `kanban_bloc.dart` | Pagination |
| G3-4 | Unify event-driven and DB insight pipelines into single `InsightFeedItem` mapping (MEDIUM-2) | `kanban_service.py` | Backend unification |
| G3-5 | Add `EventMiniCard` widget for standalone events (not covered by insights) | `event_mini_card.dart` (new) | New widget |
| G3-6 | Add shimmer loading skeleton for InsightFeedCard during load | `insight_feed_card.dart` or `insight_feed_skeleton.dart` (new) | UX polish |
| G3-7 | Accessibility: add semantics labels to insight cards, action chips, embedded events | Multiple widget files | A11y |

**Dependencies**: G2 complete.
**Verification**: Visual diff test (golden files). Pagination loads page 2 correctly. Shimmer shows during loading. VoiceOver reads insight content correctly.

### Group 4: Stretch Goals

**Goal**: Next-level UX enhancements if time permits.

| # | Task | Files | Scope |
|---|------|-------|-------|
| G4-1 | Insight-to-insight linking: "Related insights" section in expanded view | `insight_feed_card.dart`, `kanban_service.py` | Cross-insight navigation |
| G4-2 | Haptic feedback on action chip confirmation | `insight_feed_card.dart` | Micro-interaction |
| G4-3 | Animated transition when insight is adopted (card shrinks + slides to "Later" section) | `curated_timeline_page.dart` | Advanced animation |
| G4-4 | Real-time insight injection via WebSocket (sidekick insight appears without pull-to-refresh) | `kanban_bloc.dart`, WebSocket layer | Live updates |
| G4-5 | Color palette reduction: 18 accent colors → 6 semantic colors with light/dark mode support | `insight_style.dart`, `app_colors.dart` | Design system refinement |

**Dependencies**: G3 complete. These are independent of each other.
**Verification**: Per-feature testing. G4-4 requires coordination with the sidekick WebSocket infrastructure.

---

## 7. File Change Summary

### New Files

| File | Purpose |
|------|---------|
| `mobile/lib/features/kanban/presentation/widgets/insight_feed_card.dart` | Primary insight card widget with expansion, embedded events, action chips |
| `mobile/lib/features/kanban/presentation/widgets/event_mini_card.dart` | Compact event row for standalone events |
| `mobile/lib/features/kanban/presentation/utils/insight_style.dart` | Shared InsightStyle resolver (DRY fix) |
| `mobile/lib/features/kanban/data/models/insight_feed_models.dart` | Dart models for insight feed API response |

### Modified Files

| File | Changes |
|------|---------|
| `backend/src/modules/views/kanban_schemas.py` | +4 new schemas (`InsightFeedItem`, related entity models, `InsightFeedResponse`) |
| `backend/src/api/v1/kanban.py` | +1 endpoint (`GET /kanban/insight-feed`) |
| `backend/src/modules/views/services/kanban_service.py` | +`get_insight_feed()`, +`_resolve_insight_entities()`, +3 batch resolver methods |
| `mobile/lib/features/kanban/presentation/pages/curated_timeline_page.dart` | +`_buildInsightFeed()`, feature flag routing |
| `mobile/lib/features/kanban/presentation/bloc/kanban_bloc.dart` | +`_onLoadInsightFeed`, +`_onExpandInsight`, +`_onExecuteInsightAction` |
| `mobile/lib/features/kanban/presentation/bloc/kanban_state.dart` | +`InsightFeedLoaded`, +`InsightActionState` |
| `mobile/lib/features/kanban/presentation/bloc/kanban_event.dart` | +`LoadInsightFeed`, +`ExpandInsight`, +`CollapseInsight`, +`ExecuteInsightAction` |
| `mobile/lib/features/kanban/domain/repositories/curated_timeline_repository.dart` | +`getInsightFeed()` method |
| `mobile/lib/features/kanban/data/repositories/curated_timeline_repository_impl.dart` | +`getInsightFeed()` implementation |
| `mobile/lib/features/kanban/data/datasources/curated_timeline_datasource.dart` | +`fetchInsightFeed()` HTTP call |
| `mobile/lib/features/kanban/presentation/widgets/insight_card.dart` | Migrate to shared `InsightStyle` |
| `mobile/lib/features/kanban/presentation/widgets/insight_detail_sheet.dart` | Migrate to shared `InsightStyle`, add domain action buttons |

### Unchanged Files

- All backend models (`insight/models.py`, `pending_action.py`, `curation/models.py`)
- All Celery tasks
- All database migrations (no schema changes needed)
- Memory lane tab (segment 1)
- All existing API endpoints

---

## 8. Key Constraints Checklist

| Constraint | How Addressed |
|------------|---------------|
| Immutable patterns (copyWith, no mutation) | All Dart models use `copyWith`. BLoC emits new state objects, never mutates. |
| Relative imports within `backend/src/` | All new backend imports use relative paths. |
| `DateTime(timezone=True)` | No new DateTime columns. Existing columns already use `timezone=True`. |
| SQLAlchemy ORM, FastAPI | New endpoint follows existing pattern: `router.get → service method → ORM queries`. |
| Flutter BLoC pattern | New states/events extend existing `KanbanState`/`KanbanEvent`. No deviation from pattern. |
| No hardcoded values | All thresholds (insight cap, pagination size) defined as named constants or config values. |
| No mock data in production | Entity resolution returns empty lists on failure, never fabricated data. |
| `utc_now()` as sole time source | All new time comparisons use `utc_now()`. |
