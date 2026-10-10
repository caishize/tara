# Requirements Document

## Introduction

本文档定义了智能秘书系统的日程整理优化需求。系统包含三个核心功能：事件图谱（Event Graph）、时光轴（Timeline）和简报（Daily Briefing）。优化目标是提升用户体验，采用秘书思维，提供行动导向的信息展示，实现渐进式披露和智能预判。

## Glossary

- **System**: 智能秘书系统
- **Event_Graph**: 事件图谱模块，以行程为中心展示关联信息
- **Timeline**: 时光轴模块，以日期为中心按时间顺序展示日程
- **Daily_Briefing**: 简报模块，每日晨报汇总今日事项和提醒
- **Curated_Events**: 经过整理的事件数据源（Single Source of Truth）
- **Association**: 事件之间的关联关系（人物、待办、提醒等）
- **Trip**: 行程，包含多个相关事件的时间段
- **Conflict**: 时间冲突，两个或多个事件在时间上重叠
- **Alert**: 预警，需要用户注意的重要信息
- **Action_Item**: 行动项，用户可执行的具体操作

## Requirements

### Requirement 1: 事件图谱分类体系优化

**User Story:** 作为用户，我希望事件图谱使用清晰的分类体系，以便快速理解信息的重要性和类型。

#### Acceptance Criteria

1. THE Event_Graph SHALL classify all associations using a three-tier urgency system: blocking, recommended, and reference
2. WHEN displaying associations, THE Event_Graph SHALL show data type as a secondary label (person, task, memory, reminder)
3. THE Event_Graph SHALL NOT mix urgency classification with data type classification in the primary grouping
4. WHEN an association is created, THE System SHALL assign both an urgency level and a data type
5. THE Event_Graph SHALL display urgency levels in a visually distinct manner

### Requirement 2: 关联质量控制

**User Story:** 作为用户，我希望看到高价值的关联信息，避免被通用或低价值的关联干扰。

#### Acceptance Criteria

1. WHEN generating associations, THE System SHALL calculate a value score for each association
2. THE System SHALL filter out associations with value scores below a defined threshold
3. WHEN an association is too generic, THE System SHALL exclude it from display
4. THE System SHALL prioritize associations that provide actionable information
5. WHEN multiple similar associations exist, THE System SHALL deduplicate and keep the highest value one

### Requirement 3: 行程智能分组

**User Story:** 作为用户，我希望系统智能地将相关事件分组为行程，避免不合理的日期范围。

#### Acceptance Criteria

1. WHEN grouping events into trips, THE System SHALL ensure date ranges are logically continuous
2. THE System SHALL NOT create trips with gaps longer than 2 days between events
3. WHEN events are geographically related, THE System SHALL consider location proximity in trip grouping
4. THE System SHALL allow manual adjustment of trip boundaries
5. WHEN displaying trip options, THE System SHALL present them in chronological order

### Requirement 4: 图谱分层展示

**User Story:** 作为用户，我希望默认只看到最重要的信息，次要信息可以按需展开。

#### Acceptance Criteria

1. WHEN loading an event graph, THE Event_Graph SHALL display only blocking-level associations by default
2. THE Event_Graph SHALL provide an expand control for recommended-level associations
3. THE Event_Graph SHALL provide a separate expand control for reference-level associations
4. WHEN a user expands a level, THE System SHALL persist the expansion state for that session
5. THE Event_Graph SHALL display a count badge showing the number of hidden items in each collapsed level

### Requirement 5: 多天事件强制拆解

**User Story:** 作为用户，我希望多天事件在时光轴上被正确拆解为每日条目，以便清晰查看每天的安排。

#### Acceptance Criteria

1. WHEN storing a multi-day event, THE System SHALL decompose it into individual daily entries
2. THE System SHALL NOT rely on LLM for multi-day event decomposition
3. WHEN decomposing events, THE System SHALL preserve the original event reference
4. THE System SHALL handle timezone transitions correctly during multi-day event decomposition
5. WHEN an event spans midnight, THE System SHALL split it at the day boundary in the user's local timezone

### Requirement 6: 时光轴智能标签

**User Story:** 作为用户，我希望时光轴上的事件标签更加友好和直观，而不是简单的"Day 1"。

#### Acceptance Criteria

1. WHEN displaying a multi-day event, THE Timeline SHALL generate descriptive labels based on event type and content
2. THE Timeline SHALL include the day sequence and key activities in the label
3. THE Timeline SHALL NOT use generic labels like "Day 1" without context
4. WHEN an event is part of a trip, THE Timeline SHALL include the trip name in the label
5. THE Timeline SHALL limit label length to maintain readability

### Requirement 7: 冲突实时检测与展示

**User Story:** 作为用户，我希望在查看时光轴时立即看到时间冲突，而不仅仅在写入时检测，并且系统应该记住我已经确认或忽略的冲突，避免重复通知。

#### Acceptance Criteria

1. WHEN loading the timeline, THE Timeline SHALL detect all time conflicts among displayed events
2. THE Timeline SHALL mark conflicting events with a visual indicator
3. WHEN a user hovers over a conflict indicator, THE System SHALL display details of the conflicting events
4. THE Timeline SHALL calculate conflict severity based on event priorities
5. THE Timeline SHALL provide a quick action to resolve or acknowledge conflicts
6. WHEN a conflict is acknowledged or dismissed by the user, THE System SHALL record the status and not notify again
7. WHEN a conflict is resolved (events adjusted), THE System SHALL mark it as resolved
8. THE System SHALL only notify users about new or unacknowledged conflicts
9. WHEN the same conflict has been notified within 24 hours, THE System SHALL NOT send duplicate notifications
10. WHEN events involved in a conflict are modified, THE System SHALL recalculate the conflict ID and treat it as a new conflict if the overlap changes

### Requirement 8: 时光轴行程视图

**User Story:** 作为用户，我希望能够按行程分组查看时光轴，以便更好地理解事件的上下文。

#### Acceptance Criteria

1. THE Timeline SHALL provide a view mode toggle between date-based and trip-based grouping
2. WHEN in trip-based view, THE Timeline SHALL group events by their associated trips
3. THE Timeline SHALL display trip metadata (name, date range, location) as group headers
4. WHEN switching view modes, THE Timeline SHALL preserve the current scroll position context
5. THE Timeline SHALL allow filtering to show only specific trips

### Requirement 16: 冲突状态管理

**User Story:** 作为用户，我希望系统能够记住我对冲突的处理状态，避免对同一个冲突反复通知，影响使用体验。

#### Acceptance Criteria

1. THE System SHALL maintain a status for each detected conflict (pending, acknowledged, resolved, dismissed)
2. WHEN a user views a conflict notification, THE System SHALL mark it as acknowledged
3. WHEN a user explicitly dismisses a conflict, THE System SHALL mark it as dismissed and not notify again
4. WHEN a user resolves a conflict by adjusting event times, THE System SHALL mark it as resolved
5. THE System SHALL calculate a unique conflict ID based on involved event IDs and overlap time range
6. WHEN events in a conflict are modified, THE System SHALL recalculate the conflict ID
7. IF the conflict ID changes after modification, THE System SHALL treat it as a new conflict
8. THE System SHALL implement a notification cooldown period (default 24 hours) for the same conflict
9. WHEN checking whether to notify, THE System SHALL skip conflicts with status acknowledged, resolved, or dismissed
10. WHEN checking whether to notify, THE System SHALL skip conflicts notified within the cooldown period

### Requirement 9: 简报优先级排序

**User Story:** 作为用户，我希望简报按照重要性排序，优先看到最需要关注的信息。

#### Acceptance Criteria

1. WHEN generating the daily briefing, THE Daily_Briefing SHALL order sections as: alerts, must-do items, preparation reminders, suggestions
2. THE Daily_Briefing SHALL limit the number of items in each section to prevent information overload
3. WHEN there are no items in a section, THE Daily_Briefing SHALL hide that section
4. THE Daily_Briefing SHALL display a summary count at the top showing total items by priority
5. THE Daily_Briefing SHALL allow users to customize section order preferences

### Requirement 10: 智能预警增强

**User Story:** 作为用户，我希望简报能够提供更智能的预警，包括天气、交通和证件提醒。

#### Acceptance Criteria

1. WHEN generating alerts, THE Daily_Briefing SHALL check weather conditions for events with outdoor activities
2. THE Daily_Briefing SHALL generate traffic alerts for events requiring travel during peak hours
3. WHEN an event requires identification documents, THE Daily_Briefing SHALL remind the user to bring them
4. THE Daily_Briefing SHALL check for flight/train schedule changes and alert accordingly
5. THE Daily_Briefing SHALL prioritize alerts by potential impact on the user's schedule

### Requirement 11: 行动按钮生成

**User Story:** 作为用户，我希望每条简报信息都有明确的行动建议，以便快速采取行动。

#### Acceptance Criteria

1. WHEN displaying an item in the briefing, THE Daily_Briefing SHALL include at least one actionable button
2. THE System SHALL generate context-appropriate actions (e.g., "Navigate", "Call", "Reschedule")
3. WHEN a user clicks an action button, THE System SHALL execute the corresponding action or open the relevant interface
4. THE Daily_Briefing SHALL prioritize the most relevant action as the primary button
5. THE Daily_Briefing SHALL support quick actions without leaving the briefing view

### Requirement 12: 数据源简化

**User Story:** 作为开发者，我希望简化外部数据源的整合逻辑，优先使用curated_events作为单一数据源。

#### Acceptance Criteria

1. THE System SHALL use curated_events as the primary data source for all three modules
2. WHEN external calendar data is available, THE System SHALL sync it into curated_events before processing
3. THE System SHALL reduce fallback logic complexity by standardizing data access patterns
4. WHEN external data sources are unavailable, THE System SHALL continue functioning with curated_events only
5. THE System SHALL provide clear error messages when data synchronization fails

### Requirement 13: 关联价值评分算法

**User Story:** 作为开发者，我需要实现一个关联价值评分算法，以便过滤低价值关联。

#### Acceptance Criteria

1. THE System SHALL calculate association value scores based on relevance, actionability, and specificity
2. THE System SHALL assign higher scores to associations with specific action items
3. THE System SHALL assign lower scores to generic or obvious associations
4. WHEN an association references external context, THE System SHALL increase its value score
5. THE System SHALL allow configuration of minimum value score thresholds per urgency level

### Requirement 14: 时区一致性处理

**User Story:** 作为用户，我希望系统在所有模块中一致地处理时区，避免时间显示错误。

#### Acceptance Criteria

1. THE System SHALL store all timestamps in UTC in curated_events
2. WHEN displaying times, THE System SHALL convert to the user's local timezone
3. THE System SHALL handle daylight saving time transitions correctly
4. WHEN an event occurs in a different timezone, THE System SHALL display both local and event timezones
5. THE System SHALL preserve timezone information when decomposing multi-day events

### Requirement 15: 性能优化

**User Story:** 作为用户，我希望系统响应迅速，即使有大量事件数据。

#### Acceptance Criteria

1. WHEN loading the event graph, THE System SHALL respond within 500ms for up to 100 associated items
2. THE Timeline SHALL support lazy loading for date ranges beyond the visible viewport
3. THE Daily_Briefing SHALL generate within 1 second for a typical day with 10-20 events
4. THE System SHALL cache computed associations and invalidate cache only when source data changes
5. WHEN processing LLM requests, THE System SHALL implement timeout and fallback mechanisms
