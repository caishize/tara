# 时光轴生活秘书化优化设计文档

> 优化目标：让时光轴（未来 + 回忆）的展现从零散的事件列表，变成一个懂你生活的秘书视角叙述。
>
> 核心原则：**生活秘书 ≠ 商务秘书**。不机械计数、不用冷冰冰的标签，而是像一个了解你生活的人那样，帮你理出重点、串起故事。

---

## 1. 问题分析：7 个根因

| ID | 问题 | 表现 | 影响 |
|----|------|------|------|
| **R1** | 机械式日摘要 | `_generate_day_summary` 按事件类型计数拼接，如"3 meetings, 1 medical" | 用户看到的是统计报表，不是生活 |
| **R2** | 商务风格标签 | `_EVENT_TYPE_LABELS` 用"会议/医疗/差旅"等企业术语 | 产品感受像企业协作工具 |
| **R3** | 缺乏生活节奏感知 | 周末/节假日/生日当天和普通工作日展现完全一样 | 重要的日子被埋没在事件流中 |
| **R4** | visibility_tier 未使用 | CuratedEvent 有 focus/standard/detail 分层，但前端完全忽略 | 所有事件同等展示，无法突出重点 |
| **R5** | 回忆标题机械 | 旅行故事和月度故事标题只用 trip_name 或"YYYY-MM" | 没有叙事感，像数据库查询结果 |
| **R6** | "那年今日"叙述单薄 | 只显示事件标题，没有情感上下文 | 回忆缺乏温度，无法唤起共鸣 |
| **R7** | 日分组缺少上下文元数据 | TimelineDayGroup 只有 events + summary | 前端无法做差异化展示 |

---

## 2. 设计方案

### 2.1 总体思路

```
                      Backend (数据富化)              Frontend (差异化展示)
                   ┌─────────────────────┐        ┌──────────────────────┐
  CuratedEvents ──>│  生活语境分析         │──API──>│  视觉层次 + 温暖语调   │
                   │  • 日心情 (day_mood)  │        │  • 重点标记            │
                   │  • 焦点事件           │        │  • 倒计时标签          │
                   │  • 情感标签           │        │  • 情感色彩 pill       │
                   │  • 生活提示           │        │  • 生活化区段标题       │
                   │  • 叙事性标题         │        │                      │
                   └─────────────────────┘        └──────────────────────┘
```

**关键约束**：
- 所有新增字段均为 `Optional`，默认 `None`，完全向后兼容
- 纯规则驱动（无额外 LLM 调用），零延迟增加
- 前端只消费新字段做展示差异化，不改变数据获取逻辑

### 2.2 Schema 变更

#### TimelineEventItem（时光轴事件条目）

| 新增字段 | 类型 | 说明 |
|----------|------|------|
| `visibility_tier` | `Optional[str]` | 来自 CuratedEvent 的 focus/standard/detail 分层 |
| `life_context_hint` | `Optional[str]` | 温暖的生活提示，如"记得准备礼物" |

#### TimelineDayGroup（时光轴日分组）

| 新增字段 | 类型 | 说明 |
|----------|------|------|
| `day_mood` | `Optional[str]` | 这一天的性格标签，如"生日快乐"、"出行日" |
| `highlight_event_id` | `Optional[str]` | 当天最值得关注的事件 ID |

#### StoryGroup（回忆故事组）

| 新增字段 | 类型 | 说明 |
|----------|------|------|
| `emotional_tag` | `Optional[str]` | 温暖情感标签，如"温馨旅途"、"朋友聚会" |

#### KanbanEvent（看板事件）

| 新增字段 | 类型 | 说明 |
|----------|------|------|
| `visibility_tier` | `Optional[str]` | 透传 focus/standard/detail |

---

## 3. 后端核心逻辑

### 3.1 日摘要重写 (`_generate_day_summary`)

**旧逻辑**：按事件类型计数 → 拼接 "3 meetings, 1 medical"
**新逻辑**：锚定当天最重要的事件，用生活化语言概括

```
单事件:
  "团队午餐"                    # 直接用标题
  "体检，在协和医院"              # 有地点就加上
  "买菜，已完成"                  # 已完成加后缀

多事件 (有特殊事件):
  "妈妈生日，还有1件事"           # 特殊事件做锚点
  "三亚的行程，另有2件事"          # 旅行事件做锚点

多事件 (普通):
  "开会，还有一件事"              # 2件事
  "开会等3件事"                   # 3件事
  "充实的一天，5件事"             # 4+件事，用 day_mood
  "周末安排丰富，5件事"           # 周末多事件

完成后缀:
  "开会等3件事——都已完成"
```

### 3.2 焦点事件选择 (`_find_focus_event`)

按优先级链逐层匹配，选出当天最值得关注的事件：

```
1. 特殊场合 (birthday, anniversary, holiday)    ← 最高优先
2. 焦点层级 (visibility_tier == "focus")
3. 出行事件 (trip, travel, business_trip)
4. 高优先级 (priority in high, critical)
5. 第一个事件                                    ← 兜底
```

### 3.3 日心情计算 (`_compute_day_mood`)

给每一天一个"性格标签"，帮助用户快速感知这一天的性质：

| 条件 | 心情标签 | 优先级 |
|------|----------|--------|
| 有生日事件 | 生日快乐 | 1 |
| 有纪念日 | 纪念日 | 2 |
| 有节假日 | 节日 | 3 |
| 有出行事件 | 出行日 | 4 |
| 有医疗事件 | 健康日 | 5 |
| 周末 + 家庭活动 | 家庭日 | 6 |
| 周末 + 少量事件 | 休闲周末 | 7 |
| 工作日 4+ 事件 | 充实的一天 | 8 |
| 其他 | _(无)_ | — |

### 3.4 高亮事件选择 (`_pick_highlight_event`)

与 `_find_focus_event` 不同，高亮只选择**真正值得视觉强调**的事件：

```
1. 焦点层级 (visibility_tier == "focus")
2. 特殊场合 (birthday, anniversary, holiday)
3. 高优先级 (high, critical)
4. 都不是 → None (不高亮任何事件)
```

> 设计决策：普通事件不高亮。`_find_focus_event` 用于日摘要锚点（总需要一个），`_pick_highlight_event` 用于视觉强调（可以没有）。

### 3.5 生活上下文提示 (`_build_life_context_hint`)

基于事件类型生成一句温暖的提醒：

| 事件类型 | 提示 |
|----------|------|
| birthday | 记得准备礼物 |
| anniversary | 特别的日子 |
| medical | 记得带病历和证件 |
| travel/trip | 目的地: {location} |
| favor | 人情往来 |

### 3.6 旅行故事标题 (`_build_trip_story_title`)

```
优先级: trip_name > location > 事件标题

短途 (≤2天):  "那次去丽江"
长途 (>2天):  "丽江5天之旅"
无目的地:     使用第一个事件标题
```

### 3.7 月度故事标题 (`_build_month_story_title`)

从事件类型组成推导主题词：

| 主导类型 | 主题词 |
|----------|--------|
| social/meeting | 聚会 |
| travel/trip | 旅行 |
| birthday | 庆祝 |
| anniversary | 纪念 |
| medical | 健康 |
| favor | 人情往来 |

```
单事件:       直接用标题 → "和老朋友聚餐"
特殊分组:     直接用标题 → "妈妈生日"
有主题:       "2025年6月的聚会时光"
无主题:       "2025年12月的回忆"
```

### 3.8 "那年今日"叙述 (`_build_on_this_day_narrative`)

```
时间前缀:
  1年前 → "去年的今天"
  N年前 → "3年前的今天"

叙述丰富化:
  有参与者 + 社交:  "去年的今天，和小明、小红聚了聚"
  有参与者 + 旅行:  "2年前的今天，和爸爸去了旅行"
  有记忆碎片:       "2年前的今天，三亚之旅——「海边的日落真美」"
  默认:             "去年的今天，聚餐"
```

### 3.9 情感标签 (`_compute_emotional_tag`)

为回忆故事组打上温暖标签：

| 事件构成 | 标签 |
|----------|------|
| 纯出差 | 出差记录 |
| 含旅行/出行 | 温馨旅途 |
| 含生日/纪念日 | 特别的日子 |
| 含社交/聚会 | 朋友聚会 |
| 含人情 | 人情往来 |
| 含医疗 | 健康记录 |
| 其他 | _(无)_ |

---

## 4. 前端展示变更

### 4.1 区段标题调整

| 区段 | 旧标题 | 新标题 | 设计意图 |
|------|--------|--------|----------|
| 本周重点 | 近期安排 | **近期重点** | 强调"重点"而非"安排" |
| 需要准备 | 需要准备 | **别忘了准备** | 更亲切的提醒语气 |
| AI 洞察 | AI智能洞察 | **贴心提醒** | 隐藏"AI"技术感 |
| 月度计划 | 后续安排 | **接下来** | 更自然的过渡 |
| 远期 | 更多 | **远期安排** | 更明确的含义 |

### 4.2 焦点卡片状态徽章

| 状态 | 旧展示 | 新展示 | 颜色 |
|------|--------|--------|------|
| 有待办准备项 | _(无)_ | `2项待备` | 橙色警示 |
| 焦点事件 | _(无)_ | `重点` | 暖色强调 |
| 已确认 | 已预约 | `已安排` | 绿色 |
| ≤3天内 | _(无)_ | `今天`/`明天`/`后天` | 绿色 |
| 默认 | 未准备 | `待安排` | 橙色 |

### 4.3 故事卡片情感标签

在故事标题右侧展示一个小 pill 徽章：

```
┌──────────────────────────────────────┐
│ 丽江5天之旅          [温馨旅途]       │
│ 2025年8月 · 3人 · 5天                │
└──────────────────────────────────────┘
```

- 颜色：`accentWarm` 文字 + `accentWarmLight` 背景
- 圆角：8px
- 仅在 `emotional_tag` 非空时显示

### 4.4 时光轴事件行

焦点事件（`isFocusEvent`）的时间轴圆点使用 `accentWarm` 暖色，普通事件保持默认色。

---

## 5. 测试覆盖

共 55 个单元测试，覆盖所有 9 个纯函数 helper：

| 测试类 | 方法 | 测试数 |
|--------|------|--------|
| `TestComputeDayMood` | `_compute_day_mood` | 11 |
| `TestFindFocusEvent` | `_find_focus_event` | 6 |
| `TestGenerateDaySummary` | `_generate_day_summary` | 11 |
| `TestPickHighlightEvent` | `_pick_highlight_event` | 4 |
| `TestBuildTripStoryTitle` | `_build_trip_story_title` | 4 |
| `TestBuildMonthStoryTitle` | `_build_month_story_title` | 6 |
| `TestBuildOnThisDayNarrative` | `_build_on_this_day_narrative` | 6 |
| `TestComputeEmotionalTag` | `_compute_emotional_tag` | 7 |

关键测试场景：
- 特殊事件优先级高于旅行事件高于普通事件
- 出差和旅行的情感标签区分
- 周末与工作日的日心情差异
- trip_name 优先于 location 作为目的地
- "去年的今天" vs "N年前的今天" 的叙述差异
- 空事件列表的边界处理

---

## 6. 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `backend/src/modules/views/kanban_schemas.py` | 修改 | +6 个 Optional 字段 |
| `backend/src/modules/views/services/timeline_service.py` | 重写 | 重写日摘要 + 新增 4 个 helper |
| `backend/src/modules/views/services/memory_lane_service.py` | 重写 | 重写标题/叙述生成 + 新增 4 个 helper |
| `backend/src/modules/views/services/_event_converter.py` | 修改 | 透传 visibility_tier |
| `mobile/.../curated_timeline_page.dart` | 修改 | 区段标题调整 |
| `mobile/.../focus_card.dart` | 修改 | 状态徽章逻辑重写 |
| `mobile/.../story_card.dart` | 修改 | 新增情感标签 pill |
| `mobile/.../timeline_event_row.dart` | 修改 | 焦点事件暖色圆点 |
| `mobile/.../kanban_models.dart` | 修改 | +visibilityTier 字段 |
| `mobile/.../memory_lane.dart` | 修改 | +emotionalTag 字段 |
| `mobile/.../memory_lane_model.dart` | 修改 | JSON 解析 emotional_tag |
| `mobile/.../curated_timeline_datasource.dart` | 修改 | 内联解析 emotional_tag |
| `backend/tests/.../test_timeline_presentation.py` | 新增 | 30 个测试 |
| `backend/tests/.../test_memory_lane_presentation.py` | 新增 | 25 个测试 |
