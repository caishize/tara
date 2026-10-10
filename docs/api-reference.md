# Secretary Backend API Reference

> Auto-generated 2026-02-20 from source code analysis of 24 API route files.

Base URL: `/api/v1`

All endpoints require JWT authentication via `Authorization: Bearer <token>` header unless noted otherwise.

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Chat (Dual-Brain Routing)](#2-chat-dual-brain-routing)
3. [Actions (Human-in-the-Loop)](#3-actions-human-in-the-loop)
4. [Assistant](#4-assistant)
5. [Briefing](#5-briefing)
6. [Connections](#6-connections)
7. [Curation](#7-curation)
8. [Data Management](#8-data-management)
9. [Dates](#9-dates)
10. [Devices](#10-devices)
11. [Gifts](#11-gifts)
12. [Gift Browse](#12-gift-browse)
13. [Gift Memory](#13-gift-memory)
14. [Graph](#14-graph)
15. [Kanban](#15-kanban)
16. [Members](#16-members)
17. [Memory](#17-memory)
18. [Notes (Secretary Notes)](#18-notes-secretary-notes)
19. [People](#19-people)
20. [Relationships](#20-relationships)
21. [Report](#21-report)
22. [Trips - Plans](#22-trips---plans)
23. [Trips - Itinerary](#23-trips---itinerary)
24. [Trips - Itinerary Versions](#24-trips---itinerary-versions)
25. [Trips - Expenses](#25-trips---expenses)
26. [Trips - Destinations](#26-trips---destinations)
27. [User Services](#27-user-services)
28. [WebSocket](#28-websocket)

---

## 1. Authentication

Prefix: `/auth` | Tag: `Authentication` | Module: `member`
Source: `backend/src/api/v1/auth.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| POST | `/auth/register` | Register a new user and return JWT token pair | No | `RegisterRequest` | `LoginResponse` | 201 Created, 400 (missing email/phone), 409 (duplicate) |
| POST | `/auth/login` | Login with email/phone and password | No | `LoginRequest` | `LoginResponse` | 401 (invalid credentials) |
| POST | `/auth/refresh` | Exchange refresh token for new token pair | No | `RefreshRequest` | `LoginResponse` | 401 (expired/invalid token) |
| POST | `/auth/logout` | Logout (stateless, client discards tokens) | Yes | -- | `MessageResponse` | |
| GET | `/auth/me` | Get current user profile from JWT | Yes | -- | `UserResponse` | 401 (not found/deactivated) |
| PUT | `/auth/profile` | Update user profile fields | Yes | `UpdateProfileRequest` | `UserResponse` | 422 (empty username, no contact method) |
| POST | `/auth/change-password` | Change password (verify old, set new) | Yes | `ChangePasswordRequest` | `MessageResponse` | 401 (wrong current password), 400 (password too short) |
| DELETE | `/auth/account` | Soft-delete account (set is_active=False) | Yes | `DeleteAccountRequest` | `MessageResponse` | 401 (wrong password) |

**Models:**
- `RegisterRequest`: username, password, email?, phone?, nickname?
- `LoginRequest`: login? | username?, password
- `LoginResponse`: access_token, refresh_token, token_type
- `UserResponse`: id, username, nickname?, email?, phone?, family_id, timezone

---

## 2. Chat (Dual-Brain Routing)

Prefix: `/chat` | Tag: `Chat` | Module: `conversation`
Source: `backend/src/api/v1/chat.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/chat/history` | Get chat history (all sessions or specific session) | Yes | query: session_id?, before_timestamp?, limit, offset | `{items, total, limit, offset}` | 400 (invalid timestamp) |
| GET | `/chat/tool-execution/{execution_id}` | Get Layer 3 detail of a tool execution | Yes | -- | Tool execution detail object | 404 |
| GET | `/chat/poll/{job_id}` | Poll for background job result (WebSocket fallback) | Yes | -- | `{status, job_id, message?}` | |
| POST | `/chat` | Non-streaming chat via dual-brain routing (results via WebSocket) | Yes | `ChatRequest` | `ChatJobResponse` | 503 (agent disabled, no API key), 503 (enqueue failed) |
| POST | `/chat/edit` | Edit a user message and regenerate from edited point | Yes | `EditMessageRequest` | `ChatJobResponse` | 404 (message not found), 400 (non-user message, session mismatch) |
| POST | `/chat/voice` | Upload voice audio, transcribe, then dispatch chat job | Yes | multipart: audio (File), session_id?, force_slow_path?, latitude?, longitude?, location_name? | `ChatJobResponse` + transcription | 413 (oversized audio), 502 (ASR failure), 422 (empty transcription) |
| POST | `/chat/regenerate` | Regenerate an assistant response | Yes | `RegenerateRequest` | `{job_id, session_id, route_type, original_message_id}` | 404 |
| POST | `/chat/cancel` | Cancel an in-progress Slow Path generation | Yes | `CancelRequest` | `{status, session_id}` | 404 (session not found), 503 (Redis unavailable) |
| POST | `/chat/feedback` | Submit thumbs up/down on an assistant message | Yes | `FeedbackRequest` | `{status}` | 404 |
| DELETE | `/chat/session/{session_id}` | Archive a chat session and release SDK pool client | Yes | -- | `{message, session_id}` | 404, 400 (invalid format) |

**Dual-Brain Routing:**
- **Fast Path** (~80%): Claude Haiku 4 handles simple queries, runs inline as background task
- **Slow Path** (~20%): Claude Sonnet 4 handles complex reasoning, enqueued to Redis Streams
- **Hybrid Path**: fast leg inline + slow leg enqueued
- Results delivered via WebSocket PubSub channel; `/chat/poll/{job_id}` is the fallback

**Models:**
- `ChatRequest`: message (1-10000 chars), session_id?, force_slow_path, latitude?, longitude?, location_name?
- `ChatJobResponse`: job_id, session_id, route_type (fast|slow|hybrid)
- `EditMessageRequest`: message_id, new_content, session_id?, force_slow_path, latitude?, longitude?, location_name?
- `RegenerateRequest`: message_id
- `CancelRequest`: session_id
- `FeedbackRequest`: message_id, feedback (positive|negative), reason?

---

## 3. Actions (Human-in-the-Loop)

Prefix: `/actions` | Tag: `Actions` | Module: `conversation`
Source: `backend/src/api/v1/actions.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/actions/pending` | List user's pending actions awaiting confirmation | Yes | query: limit (default 20) | `List[PendingActionResponse]` | |
| GET | `/actions/{action_id}` | Get details of a specific action | Yes | -- | `PendingActionResponse` | 404 |
| POST | `/actions/{action_id}/confirm` | Confirm and optionally execute an action | Yes | `ActionConfirmRequest` | `ActionExecutionResponse` | 404, 410 (expired), 409 (already processed) |
| POST | `/actions/{action_id}/reject` | Reject a pending action | Yes | -- | `{success, action_id, status}` | 404, 409 (already processed) |
| POST | `/actions/{action_id}/execute` | Execute a previously confirmed action | Yes | -- | `ActionExecutionResponse` | 404, 409 (already processed) |
| POST | `/actions/answer-question` | Submit answer to an agent's AskUserQuestion | Yes | `AnswerQuestionRequest` | `{success, question_id}` | 503 (Redis unavailable) |

**Human-in-the-Loop Pattern:**
1. Agent creates `PendingAction` with display data
2. Action sent to client via WebSocket (`confirm_card` message type)
3. User reviews and confirms/rejects via these endpoints
4. Confirmed actions executed via Tool Gateway

**Models:**
- `PendingActionResponse`: id, action_type, status, display_title, display_details, expires_at, can_confirm, is_expired
- `ActionConfirmRequest`: execute_immediately (default true), payload_overrides?
- `ActionExecutionResponse`: success, action_id, status, result?, error?
- `AnswerQuestionRequest`: question_id, answers (list of {question, answer})

---

## 4. Assistant

Prefix: `/assistant` | Tag: `Assistant` | Modules: `conversation`, `member`
Source: `backend/src/api/v1/assistant.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/assistant/onboarding` | Get onboarding stage, welcome card, and daily question | Yes | -- | `{stage, suppress_proactive, welcome_card?, daily_question?}` | 404 (user not found) |

**Onboarding Stages:**
- `FIRST_CHAT`: includes welcome card (V8)
- `FIRST_WEEK`: includes guided daily question
- Later stages: normal operation

---

## 5. Briefing

Prefix: `/briefing` | Tag: `Briefing` | Module: `briefing`
Source: `backend/src/api/v1/briefing.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/briefing/daily` | Get AI-generated daily briefing with events, insights, suggestions | Yes | query: target_date?, period?, family_id? | `DailyBriefing` | 400 (date > 90 days from today) |
| GET | `/briefing/suggestions` | Get smart suggestions based on schedules, memories, relationships | Yes | query: limit (1-50), family_id? | `{suggestions}` | |
| GET | `/briefing/settings` | Get briefing schedule settings | Yes | query: family_id? | Settings object | |
| POST | `/briefing/suggestions/{suggestion_id}/action` | Execute/acknowledge a suggestion action | Yes | `SuggestionActionRequest` | Action result | |
| POST | `/briefing/suggestions/{suggestion_id}/dismiss` | Dismiss a suggestion | Yes | -- | `{success, suggestion_id, message}` | 404 |
| PUT | `/briefing/settings` | Update briefing schedule settings | Yes | `BriefingSettingsRequest` | Updated settings | |

**Models:**
- `BriefingSettingsRequest`: morning_hour?, afternoon_hour?, evening_hour?, timezone?, enabled_modules?
- `SuggestionActionRequest`: action, params?

---

## 6. Connections

Prefix: `/connections` | Tag: `Connections` | Module: `member`
Source: `backend/src/api/v1/connections.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/connections/` | List all active data connections | Yes | -- | `List[ConnectionResponse]` | |
| GET | `/connections/available` | Get available provider catalog grouped by type | Yes | -- | `List[ProviderGroup]` | |
| GET | `/connections/{provider}/callback` | Handle OAuth callback, store credentials | Yes | query: code, state | `ConnectionResponse` | 400, 500 |
| POST | `/connections/{provider}/authorize` | Start OAuth flow, get authorization URL | Yes | `OAuthAuthorizeRequest` | `OAuthAuthorizeResponse` | 400 |
| POST | `/connections/{connection_id}/sync` | Trigger manual sync for a connection | Yes | -- | `SyncResponse` | |
| POST | `/connections/custom` | Create a custom MCP data connection | Yes | `CreateCustomConnectionRequest` | `ConnectionResponse` | 201 Created |
| PATCH | `/connections/{connection_id}` | Update connection scopes or configuration | Yes | `UpdateConnectionRequest` | `ConnectionResponse` | 404 |
| DELETE | `/connections/{connection_id}` | Soft-delete a connection | Yes | -- | -- | 204 No Content, 404 |

**Models:**
- `ConnectionResponse`: id, user_id, family_id, provider_type, provider_name, display_name, connection_status, auth_type, scopes, mcp_server_url?, last_sync_at?, ...
- `CreateCustomConnectionRequest`: provider_name, display_name?, auth_type?, scopes?, mcp_server_url?, mcp_server_config?

---

## 7. Curation

Prefix: `/curation` | Tag: `curation` | Module: `curation`
Source: `backend/src/api/v1/curation.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/curation/jobs/{job_id}` | Get status of a curation job | Yes | -- | `CurationJobResponse` | 404 |
| GET | `/curation/work-report` | Get curation work report with summary statistics | Yes | query: days (1-90, default 7) | Work report object | |
| POST | `/curation/trigger` | Trigger curation pipeline (async via Celery) | Yes | `TriggerCurationRequest` | `{job_id, status, message}` | 202 Accepted, 400 (invalid date format) |

**Models:**
- `TriggerCurationRequest`: start_date? (YYYY-MM-DD), end_date? (YYYY-MM-DD)
- `CurationJobResponse`: job_id, status (pending|running|completed|failed), trigger_type, events_processed, events_curated, created_at?, completed_at?

---

## 8. Data Management

Prefix: `/data` | Tag: `Data Management` | Modules: `conversation`, `curation`, `gift`, `insight`, `member`, `memory`, `trip`
Source: `backend/src/api/v1/data.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/data/stats` | Get counts of all user data categories | Yes | -- | `DataStatsResponse` | |
| DELETE | `/data/chat-history` | Delete all chat history (requires password) | Yes | `DeleteRequest` | `DeleteResponse` | 403 (wrong password), 404 (user not found) |
| DELETE | `/data/memories` | Delete all memories and related data (requires password) | Yes | `DeleteRequest` | `DeleteResponse` | 403 (wrong password) |
| DELETE | `/data/events` | Delete all curated events and related data (requires password) | Yes | `DeleteRequest` | `DeleteResponse` | 403 (wrong password) |
| DELETE | `/data/all` | Delete all user data (requires password) | Yes | `DeleteRequest` | `DeleteResponse` | 403 (wrong password) |

**Models:**
- `DataStatsResponse`: chat_sessions, chat_messages, memories, insights, events, trips, gifts
- `DeleteRequest`: password
- `DeleteResponse`: success, message, deleted_count

---

## 9. Dates

Prefix: `/dates` | Tag: `Dates` | Module: `date_manager`
Source: `backend/src/api/v1/dates.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/dates/` | List important dates with optional filters | Yes | query: member_id?, date_type?, from_date?, to_date? | `List[DateResponse]` | |
| GET | `/dates/upcoming` | Get upcoming dates in the next N days | Yes | query: days_ahead (1-365, default 30) | `List[DateResponse]` | |
| GET | `/dates/holidays` | Get public holidays for a given year | Yes | query: year? | `List[HolidayResponse]` | |
| GET | `/dates/{date_id}` | Get date details | Yes | -- | `DateDetailResponse` | 404 |
| POST | `/dates/` | Create a new important date | Yes | `CreateDateRequest` | `DateResponse` | 201 Created |
| POST | `/dates/convert/solar-to-lunar` | Convert solar (Gregorian) date to lunar date | Yes | `ConvertSolarToLunarRequest` | `ConvertSolarToLunarResponse` | 400 (invalid date) |
| POST | `/dates/convert/lunar-to-solar` | Convert lunar date to solar (Gregorian) date | Yes | `ConvertLunarToSolarRequest` | `ConvertLunarToSolarResponse` | 400 (invalid date) |
| POST | `/dates/holidays/{holiday_type}/plan` | Create a preparation plan for a holiday | Yes | `HolidayPlanRequest` | Plan result object | |
| PUT | `/dates/{date_id}` | Update an existing date | Yes | `UpdateDateRequest` | `DateDetailResponse` | 404 |
| DELETE | `/dates/{date_id}` | Delete a date | Yes | -- | -- | 204 No Content, 404 |

**Models:**
- `CreateDateRequest`: title, date_type, solar_date (YYYY-MM-DD), member_id?, is_lunar, lunar_year?, lunar_month?, lunar_day?, is_recurring, reminder_offsets?, reminder_time?, notes?
- `DateResponse`: id, title, date_type, date_value, calendar_type, is_lunar, is_recurring, importance_level, member_id?, lunar_month?, lunar_day?, reminder_offsets?, days_until?
- `DateDetailResponse`: extends DateResponse + lunar_year?, reminder_time?, notes?, created_at

---

## 10. Devices

Prefix: `/devices` | Tag: `devices` | Module: `member`
Source: `backend/src/api/v1/devices.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| POST | `/devices/` | Register or update a push notification device token | Yes | `RegisterDeviceRequest` | `DeviceTokenResponse` | 201 Created |
| DELETE | `/devices/{token}` | Unregister a device token (on logout) | Yes | -- | `DeviceTokenResponse` | 404 |

**Models:**
- `RegisterDeviceRequest`: token, platform (ios|android), device_name?
- `DeviceTokenResponse`: success, message

---

## 11. Gifts

Prefix: `/gifts` | Tag: `gifts` | Module: `gift`
Source: `backend/src/api/v1/gifts.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/gifts/recommendations` | List gift recommendations with optional filters | Yes | query: status?, member_id?, limit, offset | `{recommendations, total}` | |
| GET | `/gifts/recommendations/{recommendation_id}` | Get a specific recommendation | Yes | -- | Recommendation object | 404 |
| GET | `/gifts/history` | List all gift history for the family | Yes | query: limit, offset | Gift history list | |
| GET | `/gifts/history/record/{history_id}` | Get a specific gift history record | Yes | -- | Gift history object | 404 |
| GET | `/gifts/history/{member_id}` | Get gift history for a specific member | Yes | query: years_back (default 3) | Gift history list | |
| POST | `/gifts/recommendations` | Generate gift recommendation for a member | Yes | `GenerateRecommendationRequest` | Recommendation object | 201 Created |
| POST | `/gifts/recommendations/{recommendation_id}/view` | Mark recommendation as viewed | Yes | -- | Recommendation object | 404 |
| POST | `/gifts/recommendations/{recommendation_id}/select` | Select a gift option from recommendations | Yes | `SelectOptionRequest` | Recommendation object | 404 |
| POST | `/gifts/history` | Record a gift in history | Yes | `RecordGiftRequest` | Gift history object | 201 Created |
| POST | `/gifts/history/{history_id}/feedback` | Add feedback to a gift history record | Yes | `AddFeedbackRequest` | Gift history object | 404 |

**Models:**
- `GenerateRecommendationRequest`: member_id, occasion, budget_min?, budget_max?, preferences?, exclude_categories?, urgency?, related_date_id?
- `RecordGiftRequest`: member_id, gift_name, category, occasion, date_given, price?, purchase_url?, image_url?, notes?
- `AddFeedbackRequest`: feedback_rating (love_it|like_it|neutral|dislike|hate_it), feedback_text?

---

## 12. Gift Browse

Prefix: `/gifts` | Tag: `gifts` | Modules: `gift`, `member`
Source: `backend/src/api/v1/gift_browse.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/gifts/saved` | Get current user's saved gifts | Yes | -- | Saved gift list | |
| GET | `/gifts/popular` | Get popular/trending gifts with optional personalization | Yes | query: category?, member_id?, limit (default 20) | Gift list (sorted by preference if member_id) | |
| POST | `/gifts/{gift_id}/save` | Save a gift to user's collection | Yes | -- | `{status, gift_id}` | 201 Created, 404 |
| DELETE | `/gifts/{gift_id}/save` | Remove a gift from saved collection | Yes | -- | -- | 204 No Content, 404 |

---

## 13. Gift Memory

Prefix: `/gifts` | Tag: `gifts` | Module: `gift`
Source: `backend/src/api/v1/gift_memory.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/gifts/memory/{member_id}` | Get comprehensive gift memory for a member | Yes | -- | Memory object (stats, preferences, insights) | |
| GET | `/gifts/memory/{member_id}/context` | Get full recommendation context for LLM | Yes | query: occasion? | Context object | |
| GET | `/gifts/memory/{member_id}/dedup` | Get deduplication context (gifts to avoid, category frequencies) | Yes | -- | Dedup context object | |
| GET | `/gifts/smart-dates/{member_id}` | Get smart date suggestions for a member | Yes | query: days_ahead (default 90) | Smart dates object | |
| GET | `/gifts/budget-suggestion/{member_id}` | Get intelligent budget suggestion | Yes | query: occasion? | Budget suggestion object | |
| POST | `/gifts/memory/context` | Manually add a context entry for a member | Yes | `AddContextRequest` | Context entry object | |
| POST | `/gifts/memory/extract` | Extract gift-related context from conversation text | Yes | `ExtractContextRequest` | `{extracted_count, contexts}` | |
| POST | `/gifts/memory/{member_id}/notes` | Add a special note about a member for gift recommendations | Yes | query: note | `{status, note}` | |

**Models:**
- `AddContextRequest`: member_id, context_type (preference|dislike|constraint|brand_preference|special_note), value, categories?
- `ExtractContextRequest`: member_id?, text

---

## 14. Graph

Prefix: `/graph` | Tag: `Graph` | Module: `views`
Source: `backend/src/api/v1/graph.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/graph/trips/upcoming` | Get upcoming trips for graph trip selector | Yes | query: limit (1-20, default 5), family_id? | `List[TripSummary]` | |
| GET | `/graph/trip/{trip_id}` | Get event graph for a specific trip | Yes | query: family_id? | `EventGraphResponse` | 400 (invalid trip_id) |
| GET | `/graph/event/{event_id}` | Get event graph centered on a specific event | Yes | query: family_id? | `EventGraphResponse` | |
| GET | `/graph/event/{event_id}/context` | Get enriched context (associations + related memories) | Yes | query: family_id? | `EventDetailResponse` | 404 |
| POST | `/graph/associations` | Create a new association for an event | Yes | `CreateAssociationRequest` | `AssociationDetail` | 400 (invalid event_id), 404 (event not found) |
| POST | `/graph/associations/{association_id}/confirm` | Confirm an association | Yes | query: family_id? | `{success, association_id}` | 404 |
| POST | `/graph/associations/{association_id}/dismiss` | Dismiss an association | Yes | query: family_id? | `{success, association_id}` | 404 |

**Models:**
- `CreateAssociationRequest`: event_id, target_type, target_id, association_type, title?, reason?, priority?
- `EventGraphResponse`: nodes and edges for graph visualization

---

## 15. Kanban

Prefix: `/kanban` | Tag: `Kanban` | Modules: `curation`, `views`
Source: `backend/src/api/v1/kanban.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/kanban/` | Get semantic kanban view of future events | Yes | query: limit (1-500, default 100), family_id? | `KanbanResponse` | |
| GET | `/kanban/memory-lane` | Get memory lane with story groups and yearly stats | Yes | query: limit (1-200), offset, year?, family_id? | `MemoryLaneResponse` | |
| GET | `/kanban/on-this-day` | Get events from previous years on same calendar day | Yes | query: family_id? | `OnThisDayResponse` | |
| GET | `/kanban/search` | Full-text search across curated events | Yes | query: q (1-200 chars), event_types?, limit (1-100), family_id? | `EventSearchResponse` | |
| GET | `/kanban/events/search` | Search curated events (mobile alias for /search) | Yes | query: q, event_types?, limit, family_id? | `EventSearchResponse` | |
| GET | `/kanban/events/{event_id}/context` | Get enriched context for a single event | Yes | query: family_id? | `EventDetailResponse` | 404 |
| GET | `/kanban/curated-timeline` | Get AI-curated timeline of deduplicated events | Yes | query: start_date?, end_date?, limit, offset, tier?, family_id? | `CuratedTimelineResponse` | |
| GET | `/kanban/directional-timeline` | Get directional timeline with day groups | Yes | query: direction (past|future), days (1-30), cursor?, family_id? | `TimelineResponse` | |
| GET | `/kanban/curation-status/{job_id}` | Get status of a curation job | Yes | -- | `CurationJobResponse` | 404 |
| POST | `/kanban/events` | Create a new curated event via mini-curation | Yes | `CreateEventRequest` | `{id, title, status}` | 500 (failed) |
| POST | `/kanban/request-curation` | Trigger a manual curation job (async via Celery) | Yes | query: start_date?, end_date?, family_id? | `CurationRequestResponse` | |
| POST | `/kanban/events/{event_id}/preparation` | Add a new preparation item to an event | Yes | `PreparationAddRequest` | `{success, preparation_items}` | 404 |
| PATCH | `/kanban/events/{event_id}/preparation` | Toggle done status of a preparation item | Yes | `PreparationUpdateRequest` | `{success, preparation_items}` | 404 |
| PATCH | `/kanban/events/{event_id}/status` | Update the status of a curated event | Yes | `UpdateEventStatusRequest` | `{success, id, status}` | 404 |
| DELETE | `/kanban/events/{event_id}` | Cancel (soft-delete) a curated event | Yes | -- | `{success, id}` | 404 |
| DELETE | `/kanban/events/{event_id}/preparation` | Remove a preparation item from an event | Yes | `PreparationRemoveRequest` | `{success, preparation_items}` | 404 |

**Models:**
- `CreateEventRequest`: title (max 500), start_time, end_time?, event_type?, location?, priority (default "normal"), notes?, tags
- `PreparationUpdateRequest`: item_key?, item_index?, done
- `PreparationAddRequest`: item, source (default "manual")
- `PreparationRemoveRequest`: item_key?, item_index?

---

## 16. Members

Prefix: `/members` | Tag: `Members` | Module: `member`
Source: `backend/src/api/v1/members.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/members/` | List family members with full profile data | Yes | query: include_deleted?, min_profile_completion? | `List[MemberResponse]` | |
| GET | `/members/features` | Get progressive feature tiers and available features | Yes | -- | `FeatureTiersResponse` | 404 (user not found) |
| GET | `/members/stats` | Get member statistics broken down by relation type | Yes | -- | `MemberStatsResponse` | |
| GET | `/members/family` | Get current family information | Yes | -- | Family object | 404 |
| GET | `/members/professional-relation-types` | Get all professional relation type options | Yes | -- | `List[ProfessionalRelationTypeResponse]` | |
| GET | `/members/{member_id}` | Get member details | Yes | -- | `MemberDetailResponse` | 404, 403 |
| GET | `/members/{member_id}/work-history` | List all work history for a member | Yes | query: include_past (default true) | `List[WorkHistoryResponse]` | 404, 403 |
| GET | `/members/{member_id}/professional-relations` | List all professional relations for a member | Yes | query: include_past (default true) | `List[ProfessionalRelationResponse]` | 404, 403 |
| GET | `/members/{member_id}/profile` | Get extended profile (sizes, health, preferences) | Yes | -- | `MemberProfileExtResponse` | 404 |
| POST | `/members/` | Create a new member | Yes | `CreateMemberRequest` | `MemberResponse` | 201 Created, 403 |
| POST | `/members/professional-relations` | Create a professional relation between two members | Yes | `CreateProfessionalRelationRequest` | `ProfessionalRelationResponse` | 201 Created, 400, 403 |
| POST | `/members/{member_id}/work-history` | Create a work history entry | Yes | `CreateWorkHistoryRequest` | `WorkHistoryResponse` | 201 Created, 404, 403 |
| PUT | `/members/{member_id}` | Update a member | Yes | `CreateMemberRequest` | `MemberResponse` | 404, 403 |
| PUT | `/members/{member_id}/work-history/{work_history_id}` | Update a work history entry | Yes | `CreateWorkHistoryRequest` | `WorkHistoryResponse` | 404, 403 |
| PUT | `/members/professional-relations/{relation_id}` | Update a professional relation | Yes | `CreateProfessionalRelationRequest` | `ProfessionalRelationResponse` | 404, 403 |
| PUT | `/members/{member_id}/profile` | Update extended profile | Yes | `MemberProfileExtRequest` | `MemberProfileExtResponse` | 404 |
| DELETE | `/members/{member_id}` | Delete member (soft delete) | Yes | -- | -- | 204 No Content, 404, 403 |
| DELETE | `/members/{member_id}/work-history/{work_history_id}` | Delete a work history entry | Yes | -- | -- | 204 No Content, 404, 403 |
| DELETE | `/members/professional-relations/{relation_id}` | Delete a professional relation | Yes | -- | -- | 204 No Content, 404, 403 |

**Progressive Feature Tiers (4-tier system):**
- BASIC: conversation, reminders, weather (registration)
- ADVANCED: + kanban, briefing, memory (7 days + 2 family members)
- PREMIUM: + trip_planning, gifts, relationships (30 days or manual)
- EXPERT: + graph_view, global_orchestration (manual only)

**Models:**
- `MemberResponse`: id, name, nickname?, gender?, birth_date?, age?, phone?, email?, id_card?, relation, profile_completion, locations?, current_company?, current_position?
- `MemberDetailResponse`: extends MemberResponse + occupation?, workplace?, tags, created_at, updated_at

---

## 17. Memory

Prefix: `/memory` | Tag: `Memory` | Modules: `briefing`, `insight`, `memory`
Source: `backend/src/api/v1/memory.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/memory/list` | Get conversation memories with filters | Yes | query: memory_type?, status (default "active"), limit (1-100), offset | `MemoryListResponse` | |
| GET | `/memory/recall` | Recall memories related to a query | Yes | query: query, limit (1-20) | `MemoryRecallResponse` | |
| GET | `/memory/search` | Search memories with various filters | Yes | query: location?, person?, tags?, text?, limit | `{memories, total}` | 400 (no search param) |
| GET | `/memory/insights` | Get insights with optional filters | Yes | query: unread_only?, include_all?, min_importance?, type?, limit | `InsightListResponse` | |
| GET | `/memory/stats` | Get memory statistics broken down by type | Yes | -- | `MemoryStatsResponse` | |
| GET | `/memory/detail/{memory_id}` | Get a single memory by ID | Yes | -- | `MemoryResponse` | 404 |
| POST | `/memory/insights/{insight_id}/action` | Execute an action on an insight | Yes | body: action (embed) | `{success, message, next_step?}` | 404 |
| POST | `/memory/insights/{insight_id}/feedback` | Submit feedback on an insight | Yes | `InsightFeedbackRequest` | `{success, message}` | 400, 404 |
| POST | `/memory/consolidate` | Trigger insight generation / memory consolidation | Yes | -- | `{message, insight_count, insight_ids}` | |
| PATCH | `/memory/{memory_id}/status` | Update memory status | Yes | body: status (embed) | `{message, memory_id}` | 400, 404 |
| DELETE | `/memory/{memory_id}` | Delete a memory | Yes | -- | `{message, memory_id}` | 404 |

**Models:**
- `MemoryResponse`: id, memory_type, content, summary, entities, tags, importance, confidence, status, created_at, expires_at?, recall_count, source_session_id?
- `InsightResponse`: id, insight_type, title, content, priority, urgency, related_memory_ids, action_options, action_data, status, created_at
- `InsightFeedbackRequest`: feedback_type (useful|not_useful|too_frequent)

---

## 18. Notes (Secretary Notes)

Prefix: `/notes` | Tag: `Notes` | Module: `memory`
Source: `backend/src/api/v1/notes.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/notes` | List secretary notes with optional category/status filter | Yes | query: category?, status (default "active"), limit (1-100), offset | `NoteListResponse` | 400 (invalid category/status) |
| GET | `/notes/{note_id}` | Get a single secretary note by ID | Yes | -- | `NoteResponse` | 404 |
| POST | `/notes` | Create a new manual secretary note | Yes | `NoteCreateRequest` | `NoteResponse` | 201 Created, 400 (invalid category) |
| POST | `/notes/{note_id}/confirm` | User confirms note accuracy (sets confidence=1.0) | Yes | -- | `NoteResponse` | 404 |
| PUT | `/notes/{note_id}` | Update a secretary note (full update, increments version) | Yes | `NoteUpdateRequest` | `NoteResponse` | 404 |
| PATCH | `/notes/{note_id}` | Partial update (increments version on content/title change) | Yes | `NoteUpdateRequest` | `NoteResponse` | 404 |
| DELETE | `/notes/{note_id}` | Archive (soft-delete) a secretary note | Yes | -- | `NoteResponse` | 404 |

**L1 Facts (Secretary Notes):**
- AI-extracted facts that feed into the ContextAssembler L1 layer
- Categories: preference, routine, important, todo, observation
- Statuses: active, completed, archived, superseded

**Models:**
- `NoteCreateRequest`: category, title (1-200), content, trigger_keywords?, priority (1-10, default 5)
- `NoteUpdateRequest`: title?, content?, category?, priority?, trigger_keywords?
- `NoteResponse`: id, category, title, content, confidence, is_user_confirmed, priority, status, life_type, valid_until?, version, observation_count, trigger_keywords, created_at?, updated_at?, superseded_by?, contradiction_flags?

---

## 19. People

Prefix: `/members` | Tag: `People` | Module: `member`
Source: `backend/src/api/v1/people.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/members/people` | Get all person profiles | Yes | -- | `List[PersonProfileResponse]` | |
| GET | `/members/people/neglected` | Get neglected contacts (not contacted recently) | Yes | -- | Neglected contacts list | |
| GET | `/members/people/favors` | Get favor balances for all contacts | Yes | -- | Favor balance list | |
| GET | `/members/people/{person_id}` | Get a single person profile by ID | Yes | -- | `PersonProfileResponse` | |

---

## 20. Relationships

Prefix: `/relationships` | Tag: `relationships` | Modules: `member`, `relationship`
Source: `backend/src/api/v1/relationships.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/relationships/health` | Get relationship health overview | Yes | -- | Health overview object | |
| GET | `/relationships/health/members` | Get all family members with health scores | Yes | query: category?, sort_by, sort_order | `{family, network, summary}` | |
| GET | `/relationships/health/members/{member_id}` | Get single member health details | Yes | -- | Member health detail | 404 |
| GET | `/relationships/health/attention` | Get members needing attention | Yes | query: limit (default 10) | List of members | |
| GET | `/relationships/health/graph` | Get relationship graph data (nodes + edges) | Yes | query: center_member_id? | `{nodes, edges}` | |
| GET | `/relationships/health/contacts` | Get per-contact relationship health scores | Yes | -- | `{contacts}` | |
| GET | `/relationships/suggestions` | Get smart care suggestions | Yes | query: limit (default 5) | `List[CareSuggestionResponse]` | |
| GET | `/relationships/favors/statistics` | Get favor statistics summary | Yes | -- | Statistics object | |
| GET | `/relationships/favors/pending` | Get pending favor records (awaiting return) | Yes | -- | Pending favor list | |
| GET | `/relationships/favors` | List favor records with optional filters | Yes | query: direction?, status?, page, page_size | `{items}` | |
| GET | `/relationships/favors/balance` | Get favor balance overview | Yes | query: person_id? | Balance list | |
| POST | `/relationships/health/interactions` | Record an interaction with a member | Yes | -- | `{status}` | |
| POST | `/relationships/favors/quick` | Quick-create a favor record from mobile ledger | Yes | `QuickFavorRequest` | Favor record | 201 Created |
| POST | `/relationships/favors` | Record a favor exchange | Yes | `RecordFavorRequest` | `FavorRecordResponse` | 201 Created |

**Models:**
- `RecordFavorRequest`: person_id, direction (gave|received), type (help|gift|money|meal|other), amount?, description?, date?
- `QuickFavorRequest`: contact_name, contact_id?, amount, direction (give|receive), event_type (wedding|funeral|birthday|baby|housewarming|other)
- `FavorRecordResponse`: id, person_id, family_id, direction, favor_type, amount?, description?, weight, date?
- `CareSuggestionResponse`: person_id, person_name, suggestion_type, content, urgency

---

## 21. Report

Prefix: `/report` | Tag: `Report` | Modules: `conversation`, `curation`, `date_manager`, `gift`, `insight`, `memory`
Source: `backend/src/api/v1/report.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/report/summary` | Get aggregated report summary for a time range | Yes | query: range (today|week|month) | `ReportSummaryResponse` | |
| GET | `/report/timeline` | Get chronological activity timeline | Yes | query: range, page, limit (1-100) | `TimelineResponse` | |

**Models:**
- `ReportSummaryResponse`: range, total_actions, breakdown (`ReportBreakdown`), comparison (`ReportComparison`)
- `ReportBreakdown`: memories_extracted, events_managed, insights_generated, reminders_sent, briefings_run, gifts_tracked
- `TimelineResponse`: items (`List[TimelineItem]`), total, page

---

## 22. Trips - Plans

Prefix: `/trips/plans` | Tag: `trip-plans` | Module: `trip`
Source: `backend/src/modules/trip/api/trip_plan.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/trips/plans/` | List trip plans for the family | Yes | query: status?, limit, offset | `TripPlanListResponse` | |
| GET | `/trips/plans/itinerary-styles/list` | Get available itinerary style presets | Yes | -- | List of style presets | |
| GET | `/trips/plans/{trip_id}` | Get a specific trip plan | Yes | -- | `TripPlanResponse` | 404 |
| GET | `/trips/plans/{trip_id}/context` | Get trip context for AI generation | Yes | -- | Trip context object | 404 |
| GET | `/trips/plans/{trip_id}/detail` | Get full trip detail with itinerary | Yes | -- | Detailed trip object | 404 |
| POST | `/trips/plans/` | Create a new trip plan | Yes | `TripPlanCreate` | `TripPlanResponse` | |
| PUT | `/trips/plans/{trip_id}` | Update a trip plan | Yes | `TripPlanUpdate` | `TripPlanResponse` | 404 |
| DELETE | `/trips/plans/{trip_id}` | Delete (soft-delete) a trip plan | Yes | -- | `{message}` | 404 |

**Models:**
- `TripPlanCreate`: destination, start_date, end_date, budget?, travelers?, travel_style?, preferences?
- `TripPlanResponse`: trip_id, destination, start_date, end_date, status, budget?, actual_expense, ...

---

## 23. Trips - Itinerary

Prefix: `/trips/plans/{trip_id}/itinerary` | Tag: `trip-itinerary` | Module: `trip`
Source: `backend/src/modules/trip/api/itinerary.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/trips/plans/{trip_id}/itinerary/` | Get trip itinerary | Yes | -- | `TripItineraryResponse` | 404 |
| GET | `/trips/plans/{trip_id}/itinerary/styles` | Get itinerary generation style presets | Yes | -- | Style presets list | |
| POST | `/trips/plans/{trip_id}/itinerary/generate` | Generate a basic itinerary via LLM | Yes | -- | Generated itinerary | 404, 500 |
| POST | `/trips/plans/{trip_id}/itinerary/generate-smart` | Generate smart itinerary with style tags | Yes | `SmartItineraryRequest` | `SmartItineraryResponse` | 404, 500 |
| POST | `/trips/plans/{trip_id}/itinerary/adjust` | AI-powered itinerary adjustment | Yes | `ItineraryAdjustmentRequest` | `ItineraryAdjustmentResponse` | 404, 500 |
| POST | `/trips/plans/{trip_id}/itinerary/swap-days` | Swap two days in the itinerary | Yes | `DaySwapRequest` | `IncrementalUpdateResponse` | 404, 400 |
| PUT | `/trips/plans/{trip_id}/itinerary/day/{day_number}/activity` | Update an activity within a day | Yes | `ActivityUpdateRequest` | `IncrementalUpdateResponse` | 404 |
| POST | `/trips/plans/{trip_id}/itinerary/day/{day_number}/activity` | Add a new activity to a day | Yes | `ActivityCreateRequest` | `IncrementalUpdateResponse` | 404 |
| DELETE | `/trips/plans/{trip_id}/itinerary/day/{day_number}/activity/{index}` | Delete an activity from a day | Yes | -- | `IncrementalUpdateResponse` | 404 |

**Models:**
- `SmartItineraryRequest`: style_tags?, priorities?, special_requirements?
- `ItineraryAdjustmentRequest`: adjustment_type, description
- `DaySwapRequest`: day_a, day_b
- `ActivityUpdateRequest`: activity_index, updates (dict)
- `ActivityCreateRequest`: activity data fields

---

## 24. Trips - Itinerary Versions

Prefix: `/trips/plans/{trip_id}/versions` | Tag: `trip-itinerary-versions` | Module: `trip`
Source: `backend/src/modules/trip/api/itinerary_version.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/trips/plans/{trip_id}/versions` | Get all itinerary versions for a trip | Yes | -- | `ItineraryVersionListResponse` | 404 (trip not found) |
| GET | `/trips/plans/{trip_id}/versions/{version_id}` | Get a specific itinerary version | Yes | -- | `ItineraryVersionResponse` | 404 |
| POST | `/trips/plans/{trip_id}/versions/activate` | Activate a specific version and apply to main itinerary | Yes | `ActivateVersionRequest` | `{message, version_id, version_name}` | 404 |
| PUT | `/trips/plans/{trip_id}/versions/{version_id}` | Update version name or activate it | Yes | `ItineraryVersionUpdate` | `ItineraryVersionResponse` | 404 |
| DELETE | `/trips/plans/{trip_id}/versions/{version_id}` | Delete a version (cannot delete active version) | Yes | -- | `{message, version_id}` | 404, 400 (active version) |

**Models:**
- `ItineraryVersionResponse`: version_id, trip_id, version_number, version_name, style_tags, is_active, total_estimated_cost, schedules, generation_config, created_at, updated_at, total_days, total_activities
- `ActivateVersionRequest`: version_id
- `ItineraryVersionUpdate`: version_name?, is_active?

---

## 25. Trips - Expenses

Prefix: `/trips/plans/{trip_id}/expenses` | Tag: `trip-expenses` | Module: `trip`
Source: `backend/src/modules/trip/api/expense.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/trips/plans/{trip_id}/expenses` | List all expenses for a trip | Yes | query: page, page_size | `TripExpenseListResponse` | |
| GET | `/trips/plans/{trip_id}/expenses/budget-status` | Get budget usage status for a trip | Yes | -- | `BudgetStatusResponse` | 404 |
| POST | `/trips/plans/{trip_id}/expenses` | Create a new travel expense | Yes | `TripExpenseCreate` | `TripExpenseResponse` | 400 (invalid category), 404 (trip not found) |
| DELETE | `/trips/plans/{trip_id}/expenses/{expense_id}` | Delete an expense | Yes | -- | `{message, expense_id}` | 404 |

**Models:**
- `TripExpenseCreate`: expense_date?, category (transportation|accommodation|tickets|food|shopping|other), amount, description?, location?, payment_method?, receipt_url?
- `TripExpenseResponse`: expense data with computed fields
- `BudgetStatusResponse`: budget vs actual spending comparison

---

## 26. Trips - Destinations

Prefix: `/trips` | Tag: `trip-destination` | Module: `trip`
Source: `backend/src/modules/trip/api/destination.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/trips/destinations/search` | Search destination knowledge base (semantic search) | Yes | query: query, top_k (default 5) | `{query, results, count}` | |
| POST | `/trips/recommend` | Get intelligent destination recommendations | Yes | `DestinationRecommendationRequest` | `DestinationRecommendationResponse` | 400, 500 |

**Models:**
- `DestinationRecommendationRequest`: family_id, occasion?, budget_min?, budget_max?, duration_days (1-30, default 3), season?, user_input?
- `DestinationRecommendationResponse`: recommendations, family_composition, generation_time_ms

---

## 27. User Services

Prefix: `/members` | Tag: `User Services` | Modules: `date_manager`, `gift`, `member`, `trip`
Source: `backend/src/api/v1/user_services.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/members/stats` | Get user statistics (days used, records count, etc.) | Yes | -- | `UserStatsResponse` | |
| GET | `/members/smart-services` | Get all smart services with their status | Yes | -- | `SmartServicesResponse` | |
| GET | `/members/features` | Get available features and tier status (V8 progressive unlock) | Yes | -- | `{available_features, tiers, days_active, family_member_count}` | |
| POST | `/members/feedback` | Submit user feedback | Yes | `FeedbackRequest` | `FeedbackResponse` | |

**Models:**
- `UserStatsResponse`: days_since_joined, total_records, completed_goals, family_member_count, upcoming_events_count, active_services_count, member_counts_by_type
- `SmartServicesResponse`: services (`List[SmartServiceInfo]`), total_count, active_count
- `FeedbackRequest`: content, contact_info?

---

## 28. WebSocket

Prefix: `/ws` | Tags: `WebSocket`
Source: `backend/src/api/v1/websocket.py`

| Method | Path | Description | Auth | Request | Response | Status |
|--------|------|-------------|------|---------|----------|--------|
| GET | `/ws/status` | Get WebSocket service status | No (public) | -- | `{status, connections, pubsub_healthy}` | |
| WS | `/ws/{user_id}` | WebSocket connection for real-time updates | Yes (query param: token) | query: token, device_id? | Real-time messages | 4001 (invalid token), 4003 (user ID mismatch) |

**WebSocket Authentication:**
- JWT token passed as query parameter: `/ws/{user_id}?token=<jwt>`
- Token user_id must match path user_id

**WebSocket Message Types (server -> client):**

| Type | Description |
|------|-------------|
| `content` | Streaming response content from agent |
| `progress` | Processing progress updates |
| `confirm_card` | Action confirmation requests (Human-in-the-Loop) |
| `ask_user_question` | Agent asking user a question (requires answer via `/actions/answer-question`) |
| `error` | Error notifications |
| `complete` | Task completion |
| `keepalive` | Connection keepalive (every 30s) |

**Multi-Device Support:**
- Multiple concurrent WebSocket connections per user
- Messages broadcast to all devices for the same user
- Each device maintains its own connection
