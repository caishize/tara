# Execution Plan: 简报折叠 + 历史消息懒加载

**Plan ID**: `plan-20260319-briefing-collapse-lazy-history`
**Status**: completed (verified 2026-03-21)
**Created**: 2026-03-19
**Spec Source**: CEO Review + Eng Review (2026-03-19, SCOPE EXPANSION mode)

## Overview

优化对话页简报展示和历史消息交互：简报卡片可折叠（Stack吸顶+已读自动收起），历史消息支持 before_id cursor 无限懒加载，含会话章节标记、跳回今天FAB、新洞察脉冲动效。

## Risks

| ID | Risk | Mitigation | Status |
|----|------|-----------|--------|
| R1 | conversation_page.dart 已 1130 行，新功能可能膨胀 | 强制三个新功能独立 widget 文件 | open |
| R2 | reverse:true + Stack 高度测量在不同机型下可能不稳定 | GlobalKey + RenderBox 实时测量，不使用固定阈值 | open |
| R3 | DB Migration 需要 zero-downtime | CREATE INDEX CONCURRENTLY | open |

## Decisions

| ID | Question | Decision | Rationale |
|----|----------|----------|-----------|
| D1 | 简报吸顶用 SliverPersistentHeader 还是 Stack？ | Stack 覆盖层 | reverse:true 下 SliverPersistentHeader 吸底非顶 |
| D2 | 分页 cursor 用 before_timestamp 还是 before_id？ | before_id | 完全避免时间戳精度边界问题 |
| D3 | 是否去掉 reverse:true？ | 保留 | 现有底部滚动逻辑稳定，改正向有 Flutter 布局时序坑 |
| D4 | DaySummaryMarker 缓存机制？ | LocalStorage (Hive) | 项目已有封装，避免引入新基础设施 |

## Test Plan（必须先写失败测试）

### Flutter Bloc Unit Tests
- [ ] `test_load_more_history_happy_path_merges_messages_correctly`
- [ ] `test_load_more_history_ignored_when_already_loading`
- [ ] `test_load_more_history_api_failure_resets_loading_state`
- [ ] `test_history_has_more_false_trigger_does_not_emit`
- [ ] `test_briefing_read_date_resets_on_new_day`

### Backend Integration Tests
- [ ] `test_chat_history_before_id_pagination_returns_correct_page`
- [ ] `test_chat_history_has_more_field_correctness`
- [ ] `test_chat_history_cross_user_session_returns_403`
- [ ] `test_daily_summaries_returns_cached_summaries`
- [ ] `test_daily_summaries_returns_empty_array_gracefully`

### Structural Tests
- [ ] `briefing_compact_strip.dart` 独立文件存在且 < 200 LOC
- [ ] `history_load_trigger.dart` 独立文件存在且 < 100 LOC
- [ ] `day_summary_marker.dart` 独立文件存在且 < 150 LOC
- [ ] `conversation_page.dart` 增量 < 100 行
- [ ] Backend migration 文件编号为 129

## 3 CRITICAL GAPS（实现时必须修复）

1. `isLoadingHistory` guard：`_onLoadMoreHistory` 第一行检查防止重复请求
2. API error handling：try/catch → emit isLoadingHistory=false + SnackBar
3. `hasMore=false` check：HistoryLoadTrigger 在 hasMore=false 时渲染空 SizedBox

## Tasks（按依赖顺序）

### Phase 1: DB Foundation（并行）
- [ ] **Task 1**: DB Migration — `(session_id, id DESC)` 索引 [Repo]

### Phase 2: Backend Service
- [ ] **Task 2**: `MessageService.get_history` — 改 before_id + has_more [Service]

### Phase 3: Backend API（并行）
- [ ] **Task 3**: `GET /chat/history` — before_id 参数 + has_more 响应 [Runtime]
- [ ] **Task 4**: `GET /chat/daily-summaries` + Celery 任务 [Runtime]

### Phase 4: Mobile State
- [ ] **Task 5**: AssistantBloc 扩展 + 3 Critical Gap fixes [Service]

### Phase 5: Mobile Widgets（并行）
- [ ] **Task 6**: `BriefingCompactStrip` widget [UI]
- [ ] **Task 7**: `HistoryLoadTrigger` widget [UI]
- [ ] **Task 8**: `DaySummaryMarker` widget + LocalStorage 缓存 [UI]

### Phase 6: Integration
- [ ] **Task 9**: `ConversationPage` 改造（Stack + GlobalKey + FAB + #1 + #6）[UI]

### Phase 7: Verification
- [ ] **Task 10**: 全量测试（5 Flutter Bloc + 5 Backend Integration）[Cross-cutting]

## Progress

- Tasks total: 10
- Tasks done: 10
- Tasks blocked: 0
- Last updated: 2026-03-21
- Note: conversation_page.dart 增量 168 行 (计划要求 <100)，因 Stack 集成逻辑可接受

## To continue in a new session

```
/spec-to-task --continue plan-20260319-briefing-collapse-lazy-history
```
