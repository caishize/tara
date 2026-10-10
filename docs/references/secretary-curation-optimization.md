# 秘书整理模块优化方案

> 多角色团队讨论输出 · 2026-02-24

---

## 团队讨论摘要

本方案基于四个视角的深度讨论：**资深秘书**（15年高管秘书经验）、**真实用户**（创业CEO，3个月使用体验）、**AI上下文工程专家**、**研发架构师**。核心结论高度一致：

- 当前系统在"记录"和"规则匹配"上建立了良好基础，但在"语义理解"、"实时响应"和"从发现到行动"三个环节存在系统性缺口。
- 问题不是功能缺失，而是**认知模型偏差**：把秘书工作建模为"批处理信息流水线"，而真实秘书工作是"基于关系和情境的持续判断"。

---

## 问题清单（已验证为真实问题）

### P0：直接损害信任的问题

**问题1：住宿检测误报（hygiene_service.py:485-489）**

```python
# 当前实现 — 硬编码关键字匹配
if any(kw in combined for kw in [
    "酒店", "住宿", "hotel", "民宿", "公寓",
    "入住", "check-in", "checkin", "旅馆",
]):
    has_accommodation = True
```

用户说"住老朋友家"→ 触发"建议预订住宿"误报。用户说"公司安排住宿"→ 同样误报。用户明确告知的信息被忽略，**信任崩塌**。

真实漏洞矩阵：

| 用户表达 | 实际状态 | 系统判断 |
|---------|---------|---------|
| "住朋友家" | 私人安排，已解决 | 未检测到 → 误报警告 |
| "公司包酒店" | 已安排，无需操作 | 未检测到 → 误报警告 |
| "租了Airbnb" | 已预订 | 未检测到 → 误报警告 |
| "当天往返" | 无需住宿 | 未检测到 → 误报警告 |
| "北京我有公寓" | 长期住所 | 未检测到 → 误报警告 |

住宿状态实际存在三种，不是布尔值：`booked`（有预订记录）、`private`（私人/公司安排，无需预订）、`unknown`（真正缺失）。当前实现把后两种都归入"缺失"。

**问题2：行程完整性检测严重滞后（hygiene_service.py:370-523）**

检测触发时机：每日凌晨3点。

场景：用户周四下午3点确认周五早上的出差行程（无返程无住宿）→ 周五凌晨才收到提醒 → 此时用户已在出租车上，提醒完全无用。

这是触发机制的架构缺陷：`trip_created`（T1触发）→ 只触发mini_curate和关联发现，**不触发行程完整性检查**。完整性检查被放在T3（每日）层级，与行程CRUD事件解耦。

**问题3：返程检测的硬编码关键字（hygiene_service.py:438-451）**

```python
if any(kw in title_lower for kw in ["出发", "去程", "departure"]):
    has_departure = True
if any(kw in title_lower for kw in ["返程", "回程", "return"]):
    has_return = True
```

漏洞：
- "飞上海虹桥"：有"飞"但无关键字，不识别为出发
- "当天往返上海"：无返程关键字，但语义上返程已隐含
- 英文"flight back"/"homebound"：不在词表

### P1：影响产品价值感知的问题

**问题4：关联发现止步于hint，不产生行动（association_service.py）**

`EventAssociation`生成的`sync_hint`（如"张总也在上海，可以顺便见面"）：
- 只传递信息，把后续决策和执行完全交回用户
- 用户收到后需要：自行联系张总 → 协商时间 → 自行创建新事件
- AI做了"发现"这个最容易的部分，放弃了"执行"这个最有价值的部分

从用户角度：**发现了金矿却只给看了一眼**。

**问题5：用餐窗口硬编码（orchestrator.py:40-43）**

```python
_MEAL_WINDOWS = [
    (12, 0, 13, 30),   # lunch
    (18, 0, 19, 30),   # dinner
]
```

不同用户作息差异极大。商务人士的工作午餐可能在13:30开始，晚餐可能在20:00。健身人士可能18:00前就吃完晚餐。固定窗口导致"利用此时段用餐"提示失准。

**问题6：对话结束后缺乏即时深度整理**

Session归档触发链（`session_service.py:93`）：
```
archive_session() → _extract_memories_background()
```

只触发记忆提取，**不触发**：
- 本次对话涉及行程的完整性检查
- 本次对话涉及人物的关联发现
- 本次对话产生的insight生成

这些都等到下一次T3（每日定时）才执行，最多延迟24小时。

**问题7：简报无主题，是流水账而非注意力导航（briefing_service.py）**

`OrchestratedDay`数据结构无`day_theme`字段。简报输出是按时间排序的事件列表。

用户每天早上收到的不是"今天核心战场是XX，需要重点准备YY"，而是"09:00 会议，10:30 会议，12:00 午餐..."。用户仍然需要自己判断重要性，这正是雇秘书想解决的问题。

### P2：精度和个性化问题

**问题8：关系温度计未驱动优先级核心逻辑**

`RelationshipThermometer`的冷/热状态目前只对关联优先级有微弱加成（rule_engine.py中的bonus），没有进入`HybridPriorityEngine`的核心计算。

真人秘书的判断逻辑：老板爱人的生日 > 普通商务会议，因为亲密关系的`irrecoverability`是绝对的（错过了就是错过了），而商务会议的`irrecoverability`通常可以通过道歉和改期缓解。

**问题9：`_batch_get_temperature_statuses`是伪批量（rule_engine.py:72-85）**

```python
for mid in member_ids:
    status = await self._get_member_temperature_status(user_id, mid)
```

名为批量，实为串行循环。对多成员家庭（5+人）造成不必要的串行延迟。

---

## 优化方案

### 方案一：语义化行程完整性检测

**目标**：用LLM语义理解替代硬编码关键字，同时将触发时机从T3（每日）提升到T1（行程变更即时）。

**触发时机变更**：

在`trigger_dispatcher.py`的T1触发处理中，新增`detect_trip_completeness`调用：

```python
# trigger_dispatcher.py — T1处理器扩展
async def handle_trip_created(self, trip_id: UUID, family_id: UUID, ...):
    await self._mini_curate(...)          # 现有逻辑
    await self._check_trip_completeness(trip_id, family_id)  # 新增

async def handle_trip_updated(self, trip_id: UUID, family_id: UUID, ...):
    await self._mini_curate(...)
    await self._check_trip_completeness(trip_id, family_id)  # 新增
```

**LLM语义检测设计**：

模型：`claude-haiku-4-5`（低延迟，低成本，单次调用）

输入：行程元数据 + 当前所有curated_events列表（只含trip_id匹配的事件）

```python
@dataclass(frozen=True)
class TripCompletenessResult:
    trip_id: UUID
    has_departure: bool
    has_return: bool
    return_type: str        # "explicit" | "same_day" | "missing"
    has_accommodation: bool
    accommodation_type: str # "booked" | "private" | "missing"
    gaps: list[dict]        # [{gap_type, suggestion, urgency}]
    input_hash: str         # 防止重复检测
```

Prompt设计原则（只展示结构，不展示完整文本）：

```
系统角色：你是行程完整性审核员。
任务：分析以下行程事件列表，判断行程是否完整。

判断规则（语义级别，不依赖关键字）：
- 出发：任何表示用户离开当前城市的事件（含"飞""坐高铁""开车去""驱车前往"等）
- 返程：任何表示用户回到出发城市的事件，OR 行程标注为"当天往返"
- 住宿已安排：明确的酒店/民宿预订 OR 用户明确说明住处（朋友家/公寓/公司安排/活动提供）
- 住宿不需要：当天往返行程

输入：
- 行程信息：{trip_json}
- 行程关联事件：{events_json}

输出严格JSON：
{
  "has_departure": bool,
  "has_return": bool,
  "return_type": "explicit|same_day|missing",
  "has_accommodation": bool,
  "accommodation_type": "booked|private|missing",
  "gaps": [{"gap_type": "no_return|no_accommodation", "suggestion": "...", "urgency": "high|medium"}],
  "reasoning": "一句话说明判断依据"
}
```

**去重机制**：对events列表计算content_hash，若hash未变化则跳过LLM调用（避免重复检测）。

**存储**：结果写入`trip_completeness_checks`表（trip_id, result_json, input_hash, checked_at），触发生成PreparationItem（若有gaps）。

---

### 方案二：用户作息习惯自学习

**目标**：从历史事件时间分布推断实际用餐窗口和缓冲偏好，替代全局硬编码。

**数据来源**：`curated_events`中过去90天内有明确开始时间的事件，过滤掉`event_type in ("travel", "business_trip")`（跨时区事件会干扰）。

**推断逻辑**：

```python
# 在FamilyPreference新增字段
class FamilyPreference(Base):
    # ... 现有字段 ...
    inferred_meal_windows: dict = Column(JSONB)
    # 结构: {"lunch": [start_h, start_m, end_h, end_m], "dinner": [...]}
    # None = 使用全局默认值
    inferred_on: datetime = Column(DateTime(timezone=True))
    min_events_for_inference: int = 10  # 少于此数量时不推断
```

**推断算法**（无LLM，纯统计）：

```python
async def infer_meal_windows(family_id: UUID, db: AsyncSession) -> dict | None:
    # 查询近90天有时间的事件
    events = await db.execute(
        select(CuratedEvent.normalized_start, CuratedEvent.normalized_end)
        .where(CuratedEvent.family_id == family_id,
               CuratedEvent.normalized_start.isnot(None),
               CuratedEvent.normalized_start >= utc_now() - timedelta(days=90),
               CuratedEvent.event_type.notin_(["travel", "business_trip"]))
    )

    # 找中午时段(11:00-14:00)和晚上时段(17:00-21:00)的空闲段
    # 空闲段 = 相邻事件之间gap >= 45分钟的时间窗口
    # 取各时段空闲段的中位数
    ...
    # 若样本 < min_events_for_inference，返回None（使用默认值）
```

**更新触发**：每周日3:00 AM的Celery任务（和现有hygiene task合并），仅在events数量达到阈值后才更新。

**Orchestrator消费**：

```python
def _resolve_meal_windows(family_prefs: Optional[FamilyPreference]) -> list:
    if family_prefs and family_prefs.inferred_meal_windows:
        lunch = family_prefs.inferred_meal_windows.get("lunch")
        dinner = family_prefs.inferred_meal_windows.get("dinner")
        windows = []
        if lunch: windows.append(tuple(lunch))
        if dinner: windows.append(tuple(dinner))
        return windows
    return list(_MEAL_WINDOWS)  # 全局默认值作为冷启动fallback
```

---

### 方案三：Post-Session Reflection（对话结束即时深度整理）

**目标**：会话归档后，立即针对本次对话涉及的实体做深度整理，而非等待下一个T3周期。

**触发入口**（已有hook，只需扩展）：

```python
# session_service.py
async def archive_session(self, session_id, user_id, family_id):
    # 现有逻辑
    await self._extract_memories_background(session_id, user_id, family_id)
    # 新增：Post-Session Reflection（fire-and-forget）
    await self._trigger_post_session_reflection(session_id, user_id, family_id)
```

**Reflection范围**（精准，不全量扫描）：

第一步：从本次session的messages中提取实体（Haiku，低成本）：

```python
# 输入：session的所有messages的text拼接
# 输出：{"trips": ["trip_id_xxx"], "members": ["张总"], "dates": ["2026-03-15"]}
```

第二步：只对提取到的实体触发T2级别的focused curation：

```python
async def _focused_curation_for_entities(entities: dict, family_id: UUID):
    # trips: 触发行程完整性检测
    for trip_id in entities["trips"]:
        await check_trip_completeness(trip_id, family_id)

    # members: 触发关联发现（只针对涉及的人）
    if entities["members"]:
        await discover_associations_for_members(entities["members"], family_id)

    # dates: 触发日期临近检测
    for date_str in entities["dates"]:
        await check_date_approaching(date_str, family_id)
```

**与现有daily curation的冲突处理**：

Reflection只做增量（发现新关联/检测新gaps），不做dedup和全量reconciliation。daily curation保留作为T3兜底。使用已有的`CurationJob`的cooldown机制（检查同一实体的上次curation时间，若<30分钟则跳过）。

---

### 方案四：关联驱动PendingAction

**目标**：高置信度关联自动生成可执行的行动建议，从"信息提示"升级为"行动草案"。

**升级条件**（并非所有关联都升级）：

| 关联类型 | 升级条件 | 生成的Action类型 |
|---------|---------|---------------|
| location（顺便见面） | confidence > 0.7 AND 关系温度 cold/warm | `suggest_meeting` |
| stale_contact（久未联系） | 联系时间 > 60天 AND 即将出发 | `suggest_greeting` |
| date_proximity（重要日期临近） | 重要日期类型 = birthday/anniversary | `suggest_gift_or_message` |

**PendingAction数据模型扩展**：

```python
# conversation/pending_action.py
class ActionType(str, Enum):
    # 现有类型...
    SUGGEST_MEETING    = "suggest_meeting"     # 新增
    SUGGEST_GREETING   = "suggest_greeting"    # 新增
    SUGGEST_GIFT       = "suggest_gift"        # 新增

# PendingAction新增字段
class PendingAction(Base):
    # ... 现有字段 ...
    association_id: UUID = Column(ForeignKey("event_associations.id"))
    # 当action类型为suggest_*时，记录来源关联
    draft_content: str = Column(Text)
    # 预拟的行动内容（如草拟的邀约消息文本）
```

**草案生成**（Haiku，在关联发现后触发）：

```python
async def _generate_action_draft(association: EventAssociation, event: CuratedEvent, member: Member) -> str:
    # Haiku调用，生成具体草案文本
    # 例如：
    # action_type = suggest_meeting
    # 输出："张总，我下周三到周五在上海，您最近也在那边吗？
    #        如果方便的话，周四下午能不能找个地方叙一叙？"
```

**防止PendingAction泛滥**：

- 每用户同时未处理的`suggest_*`类型action上限：3条
- 同一(member, action_type)组合的cooldown：7天
- 用户dismiss后：对该member该类型suppress 30天

**Mobile端展示**：新增`association_card`卡片类型，展示关联场景 + 草案 + 确认/修改/拒绝三个操作。用户点"确认"后，`Tool Gateway`创建日历事件或发送消息。

---

### 方案五：关系驱动优先级（亲密关系无条件置顶）

**目标**：亲密关系相关事件（配偶/父母/子女的重要日期）无条件P0，不经过LLM校准。

**亲密关系定义**：`member.relationship_type in ("spouse", "partner", "parent", "child")`

**HybridPriorityEngine改造**：

```python
async def score(self, event_data: dict, family_id: UUID, ...) -> EnhancedPriorityScore:
    # 新增：亲密关系无条件置顶检查
    intimate_boost = await self._check_intimate_relationship_boost(event_data, family_id)
    if intimate_boost:
        # 直接返回P0，跳过所有LLM校准
        return EnhancedPriorityScore(
            base=PriorityScore(composite=0.95, ...),
            secretary_note=intimate_boost.note,
            fallback=False,
        )

    # 现有逻辑...
    base_score = compute_priority_score(event_data)

    # 关系温度驱动irrecoverability
    cold_boost = await self._check_cold_relationship_boost(event_data, family_id)
    if cold_boost and base_score.composite >= 0.3:
        # 对cold关系涉及的事件，irrecoverability自动提升
        # （错过维系机会 = 关系进一步疏远，不可逆）
        ...
```

**`_check_intimate_relationship_boost`逻辑**：

1. 从event_data提取关联的member_ids
2. 查询这些member的relationship_type
3. 若有spouse/partner/parent/child，且event_type in ("birthday", "anniversary", "family")
4. 返回boost（包含secretary_note："配偶生日，建议提前3天准备礼物和行程"）

---

### 方案六：DayTheme简报主题化

**目标**：让简报成为"注意力导航"而非"事件列表"。

**OrchestratedDay数据结构扩展**：

```python
@dataclass(frozen=True)
class DayTheme:
    """今日主题：由主线事件决定，组织其他事件围绕主线。"""
    title: str              # 主题标题，如"上海客户拜访日"
    primary_event_id: UUID  # 核心锚点事件
    focus: str              # 核心聚焦描述，如"下午3点与张总签约是关键节点"
    prep_note: str | None   # 准备提示，如"建议上午回顾合同要点"
    evening_forward: str | None  # 明日预警，如"明早6点航班，需提前值机"

@dataclass(frozen=True)
class OrchestratedDay:
    target_date: date
    slots: tuple[TimeSlot, ...]
    gaps: tuple[GapWarning, ...]
    annotations: tuple[SecretaryAnnotation, ...]
    density_score: float
    suggested_reorder: tuple[UUID, ...] | None
    day_theme: DayTheme | None  # 新增
```

**DayTheme生成算法**：

优先级：

1. 若当天有行程（trip_id事件）：主题 = 行程名称，primary = 行程中最重要的事件
2. 若有P0/P1事件：主题 = 该事件描述，primary = 最高优先级事件
3. 若density_score > 0.8（超忙）：主题 = "高密度工作日"，focus = 建议推迟低优先级事项
4. 否则：不生成主题（day_theme = None，简报正常列表展示）

DayTheme在`orchestrate_day()`末尾生成，使用Haiku（整合当天所有事件的优先级分数，cost极低）或纯规则生成（无LLM）。

**Mobile API响应变化**：

```json
{
  "day_theme": {
    "title": "上海客户签约日",
    "focus": "下午3点与张总的合同签署是今日核心，建议上午预留时间回顾合同条款",
    "prep_note": "对方已发来修订版合同，有2处条款需确认",
    "evening_forward": "明日9点飞回北京，今晚需完成值机"
  },
  "events": [...]
}
```

---

## 端到端场景验证

### 场景一：周四3点临时确认周五上海出差

**当前系统行为**：
- 周四3点：行程创建，mini_curate触发，关联发现（张总在上海）
- 周五凌晨3点：hygiene检测到"缺返程、缺住宿" → 推送提醒
- 周五早上：用户已在出租车上，提醒无用

**优化后行为**：
- 周四3点02分：T1触发行程完整性检测（LLM语义）→ 5秒内检测到缺返程
- 周四3点03分：生成PreparationItem，**立即推送** WebSocket消息："您的上海行程尚未安排返程，建议现在订票"
- 周四3点04分：关联发现"张总在上海" → confidence 0.82 → 生成PendingAction（suggest_meeting）→ 推送"秘书建议"卡片："张总也在上海，是否需要帮您约一下？[预拟消息] [确认] [稍后] [不了]"
- 用户点"确认" → 草稿消息推送给张总 → 自动创建"与张总会面"事件

### 场景二：用户说"去上海住老朋友家"

**当前系统行为**：
- LLM提取行程信息，不含"酒店/住宿"关键字
- hygiene检测：has_accommodation = False → 推送"建议预订住宿"
- 用户体验：**被质疑，信任受损**

**优化后行为**：
- LLM语义检测读取事件描述"住老朋友家" → 判断accommodation_type = "private"
- 不生成住宿gap提醒
- 秘书提示可选："住宿已确认为私人安排。如计划有变请告知。"

### 场景三：配偶生日与供应商会议同日

**当前系统行为**：
- 供应商会议 (meeting type) → 规则层较高分 → P1
- 配偶生日 (birthday type) → 规则层较低分（无商业影响）→ P2
- 简报：供应商会议排前

**优化后行为**：
- 配偶生日检测到relationship_type = "spouse" → 无条件P0，跳过LLM校准
- secretary_note自动生成："配偶生日，建议今天准备礼物，晚餐预留时间陪伴。供应商会议建议在下午早些时段结束。"
- 简报主题："今日提示：家庭日。工作安排建议18:00前完成，晚上留给家人。"

---

## 实现要点

### 新增数据表

```sql
-- 行程完整性检测结果缓存
CREATE TABLE trip_completeness_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trip_id UUID NOT NULL REFERENCES trips(trip_id),
    family_id UUID NOT NULL,
    input_hash VARCHAR(64) NOT NULL,  -- 防重复检测
    result JSONB NOT NULL,
    checked_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (trip_id, input_hash)
);
```

```sql
-- FamilyPreference扩展（已有表，新增列）
ALTER TABLE family_preferences
ADD COLUMN inferred_meal_windows JSONB,
ADD COLUMN meal_windows_inferred_at TIMESTAMP WITH TIME ZONE;
```

### 新增触发器注册

在`trigger_dispatcher.py`的`_TRIGGER_LEVEL_MAP`中补充：

```python
"session_archived": TriggerLevel.T2,         # Post-Session Reflection
"trip_completeness_check": TriggerLevel.T1,  # 行程完整性检测
```

### 性能影响评估

| 改造项 | 新增LLM调用 | 频率 | 模型 | 预估成本 |
|-------|-----------|------|------|---------|
| 行程完整性检测 | 1次/trip变更 | 低频（用户有出行时） | Haiku | 极低 |
| Post-Session Reflection实体提取 | 1次/session归档 | 中频（每次对话结束） | Haiku | 低 |
| Post-Session Reflection focused分析 | 0-3次/session | 中频 | Haiku | 低 |
| PendingAction草案生成 | 1次/高置信关联 | 低频 | Haiku | 极低 |
| DayTheme生成 | 0-1次/day（可选） | 每次生成简报 | 纯规则 | 零 |
| 作息自学习 | 0次 | 每周一次 | 纯统计 | 零 |

所有新增LLM调用均使用Haiku，单次token消耗 < 500，与现有Sonnet调用相比成本可忽略不计。

---

## 追加发现：上下文工程专家补充

### 补充问题A：记忆召回6层策略的精度问题（recall_service.py）

当前6层叠加无相关性过滤：层1-4（location/person/plan/keyword）是"找到即加入"，无阈值。语义搜索（向量相似度，最高精度信号）被置于第5层，且只能补充已被前4层加入的条目排除后的剩余名额，导致高精度的语义结果被低精度的关键词结果挤占。

**两阶段召回替代方案（Retrieve-then-Filter）**：

```
阶段一（宽召回，无LLM）：
  向量搜索 TOP-30（主力）
  + 关键词搜索 TOP-10（辅助）
  合并去重 → 候选集（约30-40条）

阶段二（精召回，Haiku）：
  若候选集 > limit：Haiku 重排序，选出最相关的 TOP-5
  若候选集 ≤ limit：直接返回，不调用 Haiku
```

Haiku重排序 prompt：给定用户消息和候选记忆列表，输出最相关的序号列表。单次约800 tokens，约$0.00008/次，远低于Sonnet。

### 补充问题B：上下文窗口L5注入策略（context_assembler.py）

当前`l5_fixed=800`（curated_events注入量）在所有任务类型中保持一致。"今天天气"类查询注入800 tokens的行程数据是噪声。

**分级注入策略**：

```python
L5_INJECTION_POLICY = {
    "weather": "skip",          # 完全无关，不注入
    "chat": "skip",
    "lookup": "today_only",     # 只注入今天事件（~150 tokens）
    "reminder": "today_only",
    "plan": "full_window",      # 7天完整数据（现有行为）
    "trip": "full_window",
    "analyze": "full_window",
}
```

只需扩展现有`TASK_OVERRIDES`，对L5 fetcher增加`scope`参数支持，最小改动。

### 补充问题C：硬编码的真实根因

`EventHygieneService`只持有`AsyncSession`，没有`llm`实例——这是**依赖设计导致的能力缺失**，被误认为"规则引擎更合适"。改造方案：在`detect_trip_gaps()`增加`llm_provider=None`可选参数，向后兼容，由调用方（Celery task）注入Haiku客户端。LLM失败时的降级策略：**保守策略**（假设行程完整），避免误报骚扰用户。

---

## 实施优先级（研发架构师建议）

```
Phase 1（1周）: 方案三 Post-Session Reflection
  → 核心价值最高，对话结束后分钟级响应，用户体验提升最明显
  → 接入点已有（session_service.py:archive_session），追加Celery task即可

Phase 2（1周）: 方案四 关联驱动PendingAction
  → 依赖Phase 1的Reflection输出；需扩展ActionType + ToolGateway新handler

Phase 3（3天）: 方案一 语义化行程完整性检测
  → 替换hygiene_service.py中约55行关键字代码，风险低，降级策略完备

Phase 4（3天）: 方案六 DayTheme简报主题化
  → 纯增量，OrchestratedDay新增Optional[DayTheme]字段，不影响现有接口

Phase 5（1周）: 方案二 作息自学习
  → 建议积累30天历史数据再启用；方案五关系优先级在Phase 2后随同实施
```

---

## 不在此方案范围内的事项

- **情绪分析语义化**（insight_service.py中的负面情绪关键字）：这些关键字实际来自`config`且可配置，问题严重程度低于上述P0/P1问题，可独立处理
- **`_batch_get_temperature_statuses`串行优化**：是性能问题，可独立处理，不影响核心逻辑
- **简报内容的全面重构**：DayTheme是增量添加，不需要重构现有列表结构
