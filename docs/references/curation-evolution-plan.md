# 策展系统演进方案：从被动呈现到主动干预

> 由产品研发团队（生活秘书、用户代言人、产品经理、AI上下文工程专家、研发架构师）联合讨论产出

---

## 核心设计原则

以下原则贯穿所有优化项，在实现细节冲突时以原则为准：

| # | 原则 | 解释 |
|---|------|------|
| P1 | **时机 > 内容** | 同一条建议在用户说"去北京"时给出值 10 分，第二天早报里给出值 2 分 |
| P2 | **判断题 > 选择题 > 开放题** | 系统做好决定给用户确认（判断题），而非列出选项让用户选（选择题） |
| P3 | **出错可逆 > 事前完美** | 每个自动化行为必须有可追溯/可撤销路径 |
| P4 | **不该做的比该做的更重要** | 秘书知道什么时候闭嘴、什么时候开口 |
| P5 | **帮你做好决定，而不是把决定推给你** | "这几件事我帮你安排好了，两处需要您拍板" |

---

## 优化项总览

| 编号 | 名称 | 优先级 | LLM 成本 | Schema 变更 |
|------|------|--------|----------|-------------|
| **E1** | 级联意图保留 | P0 | 无 (规则) + Haiku (20%兜底) | 无 |
| **E2** | 反馈信号细化与偏好提取 | P0 | Haiku (异步批量) | 新表 `preference_signals` + `user_preference_rules` |
| **E3** | 快路径关联融合 | P1 | 无 (L1注入) | 无 |
| **E4** | 级联通知汇总 | P1 | 无 | 无 |
| **E5** | 编排层主动减负 | P2 | 无 (纯规则) | `family_preferences.fatigue_state` 列 |
| **E6** | 多信号压力评分 | P2 | Haiku (仅建议文案) | 无 |
| **E7** | 节日备货周期扩展 | P2 | 无 | `important_dates.preparation_lead_days` 列 |
| **E8** | 占位事件（用户确认后） | P3 | 无 | `curated_events.status` 增加 `placeholder` 值 |

不做清单：
- 情感监控推送（"检测到你压力大"）— 侵入感过强
- 自动插入未确认的日历占位 — 污染日历信任
- 基于情绪数据的动态 buffer — 过度工程化，信号不可靠

---

## E1: 级联意图保留

### 问题场景

用户说"下月去上海看望外婆"。系统发现 3 条关联：
- A: 外婆生日在下月 15 号（temporal）
- B: 表姐在上海（location）
- C: 欠刘阿姨一个人情，刘阿姨在上海（memory + stale_contact）

行程取消后，当前系统在 `_handle_trip_lifecycle_end()` 中将 A、B、C **全部 dismiss**。但外婆生日不因行程取消而消失，欠刘阿姨的人情也不因行程取消而了结。

同样的问题存在于 `analyze_cascade()`：会议延迟 30 分钟，后面 5 个事件全标 `requires_user_decision=True`，产生 5 条通知轰炸。

### 解决方案

#### 1. Trip 取消时的分类处理

修改 `modules/curation/services/trigger_dispatcher.py` 的 `_handle_trip_lifecycle_end()` 方法。

**分类规则：**

| 关联特征 | 处理方式 | 理由 |
|----------|---------|------|
| `target_type = "date"` 且 ImportantDate（生日/纪念日） | **保留** → 转为独立 PendingAction | 时间节点不因行程取消而消失 |
| `association_type = "memory"` 且含 favor/commitment 标签 | **保留** → 转为独立 PendingAction | 承诺/人情有独立存在价值 |
| SocialIntent 来源（用户主动说过"想见某人"） | **保留** → 写入 secretary_notes | 用户意图不应被系统擅自丢弃 |
| `priority = "strongly_recommend"` 且 `confidence >= 0.85` | **保留供审** → 标记 `dismiss_reason = "source_cancelled:preserved"` | 高置信关联值得复审 |
| 纯位置依赖（`association_type = "location"` 且无上述特征） | **Dismiss** | 失去旅行载体后无独立意义 |
| 旅行准备类（行李、签证、门票等） | **Dismiss** | 行程取消后无意义 |

**实现要点：**

```python
# trigger_dispatcher.py _handle_trip_lifecycle_end() 内
# 替换当前的一刀切 dismiss 逻辑

async def _classify_association_on_cancel(
    self,
    assoc: EventAssociation,
    source_event: CuratedEvent,
) -> str:
    """返回: 'preserve_as_action' | 'preserve_as_note' | 'dismiss'"""

    # 规则 1: 日期关联（生日/纪念日）永远保留
    if assoc.target_type == "date":
        return "preserve_as_action"

    # 规则 2: 含 favor/commitment 语义的 memory 关联保留
    if (assoc.association_type == "memory"
        and assoc.target_type == "person"):
        return "preserve_as_action"

    # 规则 3: SocialIntent 来源保留为笔记
    if assoc.association_type == "social_intent":
        return "preserve_as_note"

    # 规则 4: 高置信度 strongly_recommend 保留供审
    if (assoc.priority == "strongly_recommend"
        and assoc.confidence >= 0.85):
        return "preserve_as_action"

    # 其余: dismiss
    return "dismiss"
```

**保留为 PendingAction 的转换逻辑：**

```python
async def _convert_to_standalone_action(
    self,
    assoc: EventAssociation,
    source_event: CuratedEvent,
    family_id: UUID,
) -> None:
    """将有价值的关联转换为独立 PendingAction"""
    # 幂等检查：同一 association_id 不重复创建
    existing = await self._session.execute(
        select(PendingAction).where(
            PendingAction.association_id == assoc.id,
            PendingAction.status == ActionStatus.PENDING.value,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return

    action_type_map = {
        "date": ActionType.SUGGEST_GREETING.value,
        "person": ActionType.SUGGEST_MEETING.value,
    }

    pending = PendingAction(
        user_id=source_event.user_id,
        family_id=family_id,
        action_type=action_type_map.get(
            assoc.target_type, ActionType.SUGGEST_MEETING.value
        ),
        association_id=assoc.id,
        payload={
            "original_event_title": source_event.title,
            "target_id": assoc.target_id,
            "target_type": assoc.target_type,
            "reason": assoc.reason,
            "source_cancelled": True,
        },
        display_data={
            "title": assoc.title,
            "subtitle": f"虽然「{source_event.title}」已取消，但这件事仍值得关注",
        },
        draft_content=assoc.reason,
        expires_at=utc_now() + timedelta(days=14),
    )
    self._session.add(pending)
```

**并发安全：** 对 association 查询增加 `with_for_update(skip_locked=True)`，避免与定时策展 (T3) 竞争同一组记录。

#### 2. Cascade 分析的优先级分流

修改 `modules/curation/services/orchestrator.py` 的 `analyze_cascade()`。

**原则：P0/P1 事件需要用户决策，P2/P3 事件系统自动处理（延后或取消）。**

```python
# orchestrator.py analyze_cascade() 内
# 替换当前对所有受影响事件统一设 requires_user_decision=True 的逻辑

for ev in affected_events:
    event_priority = ev.priority or "normal"

    # P0/P1：外部会议、已预约事项、接送孩子等 → 需用户决策
    requires_decision = event_priority in ("critical", "high")

    # P2/P3：内部会议、个人事务、采购等 → 系统建议自动处理
    auto_action = None
    if not requires_decision:
        if change_type == "delayed":
            auto_action = "auto_defer"
        elif change_type == "cancelled":
            auto_action = "auto_cancel"

    impacts.append(CascadeImpact(
        event_id=ev.id,
        event_title=ev.title,
        impact_type="needs_reschedule" if requires_decision else auto_action,
        requires_user_decision=requires_decision,
    ))
```

#### 3. 对 20% 模糊案例的 Haiku 兜底

当规则无法确定分类（如"和李经理讨论 Q2 预算"是纯位置关联还是有独立价值？）时，收集所有模糊案例批量调用 Haiku：

```
<cancelled_trip>北京出差 3月15-18日</cancelled_trip>
<ambiguous_associations>
1. 和李经理讨论Q2预算 (关联原因: 李经理在北京)
2. 给妈妈买北京糕点 (关联原因: 妈妈喜欢北京糕点)
</ambiguous_associations>

对于每个关联，判断取消旅行后应该：
- CANCEL: 失去意义
- PRESERVE: 有独立价值
- TRANSFORM: 需要改变形式但保留意图（如"买糕点"→"网购"）

输出 JSON array，每项含 index, action, reason。
```

Token 估算：输入 ~200，输出 ~100。频率：每用户每月 ~2 次行程取消。成本可忽略。

---

## E2: 反馈信号细化与偏好提取

### 问题场景

用户 dismiss 了"去北京出差时见张叔叔"这个关联。当前系统执行 `memory.feedback_weight *= 0.5`，**全局降低张叔叔相关记忆的权重**。后果：用户问"张叔叔生日快到了送什么好"时，关于张叔叔的记忆召回能力打了五折。

同时，`FeedbackType` 枚举只有 `useful/not_useful/too_frequent/not_relevant/incorrect` 五种，不区分"现在不是时候"和"永远不要"。所有非 `useful` 的反馈被扁平化成同一个 negative signal。

### 解决方案：三层偏好架构

#### 第一层：即时信号收集（无 LLM）

**新增 `preference_signals` 表（Migration 109）：**

```python
class PreferenceSignal(Base):
    __tablename__ = "preference_signals"

    id = Column(UUID, primary_key=True, default=uuid4)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    family_id = Column(UUID, ForeignKey("families.id"), nullable=False)

    signal_type = Column(String(32), nullable=False)  # dismiss, confirm, defer, never

    # 原始上下文快照（不修改源数据）
    source_type = Column(String(32), nullable=False)   # association, insight, memory_recall
    source_id = Column(UUID, nullable=False)
    source_context = Column(JSON, nullable=False)
    # source_context 结构示例:
    # {
    #   "event_type": "business_trip",
    #   "suggestion_type": "social_meeting",
    #   "person_id": "uuid",
    #   "person_name": "张叔叔",
    #   "location": "北京",
    #   "association_type": "location"
    # }

    user_reason = Column(Text, nullable=True)  # 用户文字反馈（如有）

    # 聚合触发键（同类信号计数用）
    category_key = Column(String(128), nullable=False, index=True)
    # 格式: "{event_type}:{suggestion_type}" 如 "business_trip:social_meeting"

    processed = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
```

**修改 `curation_service.py` 的 `dismiss_association()`：**

```python
# 替换 _downweight_memory()
# 不再修改 memory.feedback_weight
# 改为写入 preference_signals

async def dismiss_association(self, association_id, user_id, reason=None):
    assoc = await self._load_association(association_id)
    assoc.is_dismissed = True
    assoc.dismiss_reason = reason

    # 写入偏好信号（替代 _downweight_memory）
    signal = PreferenceSignal(
        user_id=user_id,
        family_id=assoc.family_id,
        signal_type="dismiss",
        source_type="association",
        source_id=assoc.id,
        source_context={
            "event_type": source_event.event_type,
            "suggestion_type": assoc.association_type,
            "person_id": assoc.target_id if assoc.target_type == "person" else None,
            "location": source_event.location,
        },
        category_key=f"{source_event.event_type}:{assoc.association_type}",
    )
    self._session.add(signal)
    await self._session.flush()
```

**FeedbackType 扩展（`core/feedback/types.py`）：**

增加两个值：
- `DEFER = "defer"` — "暂时不要"（scope: this_event，不影响全局）
- `NEVER = "never"` — "永远不要"（scope: 需二次确认后生效）

#### 第二层：偏好提取（Haiku，异步批量）

**新增 Celery 定时任务 `secretary.extract_preference_rules`（每日 05:00）：**

触发条件：某个 `category_key` 下累积 >= 3 条未处理的 `PreferenceSignal`。

```python
# modules/curation/services/preference_extraction_service.py (新文件)

class PreferenceExtractionService:
    async def extract_rules(self, user_id: UUID) -> list[UserPreferenceRule]:
        # 1. 按 category_key 分组查询未处理信号
        groups = await self._group_unprocessed_signals(user_id)

        new_rules = []
        for category_key, signals in groups.items():
            if len(signals) < 3:
                continue

            # 2. 批量调用 Haiku 提取结构化偏好
            rule = await self._extract_via_llm(signals)

            # 3. 低置信度标记为 draft
            if rule and rule.confidence >= 0.6:
                rule.is_active = True
            elif rule:
                rule.is_active = False  # draft，等更多信号

            if rule:
                new_rules.append(rule)

            # 4. 标记信号为已处理
            for s in signals:
                s.processed = True

        return new_rules
```

**Haiku Prompt 设计：**

```
<dismissal_signals>
1. 2026-02-20: 忽略"去北京出差时见张叔叔" (出差, 北京, 社交)
2. 2026-02-15: 忽略"去上海出差时见老同学" (出差, 上海, 社交)
3. 2026-02-10: 忽略"去深圳出差时约陈总吃饭" (出差, 深圳, 社交)
</dismissal_signals>

分析这些反馈的共同模式，提取一条用户偏好规则。

输出 JSON:
{
  "condition": {
    "event_type": "business_trip",
    "suggestion_type": "social_meeting"
  },
  "action": "suppress",
  "confidence": 0.85,
  "explanation": "用户不希望在出差期间安排社交活动",
  "scope": "event_type",
  "ttl_days": 90
}
```

Token 估算：输入 ~250，输出 ~150。频率：每用户每周 0-1 次。

**新增 `user_preference_rules` 表（Migration 109）：**

```python
class UserPreferenceRule(Base):
    __tablename__ = "user_preference_rules"

    id = Column(UUID, primary_key=True, default=uuid4)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    family_id = Column(UUID, ForeignKey("families.id"), nullable=False)

    # 条件匹配
    condition_event_type = Column(String(64), nullable=True)
    condition_suggestion_type = Column(String(64), nullable=True)
    condition_person_id = Column(UUID, nullable=True)
    condition_location = Column(String(128), nullable=True)

    # 动作
    action = Column(String(32), nullable=False)  # suppress, deprioritize
    confidence = Column(Float, nullable=False)
    explanation = Column(Text, nullable=False)
    scope = Column(String(32), nullable=False)  # event_type, person, global

    # 生命周期
    source_signal_count = Column(Integer, default=3)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True, index=True)

    created_at = Column(DateTime(timezone=True), default=utc_now)
```

#### 第三层：偏好应用（规则匹配，实时）

在 `association_service.py` 的 `_filter_low_quality_associations()` 中增加偏好规则匹配：

```python
async def _apply_preference_rules(
    self,
    associations: list[EventAssociation],
    user_id: UUID,
    event: CuratedEvent,
) -> list[EventAssociation]:
    """根据已学习的偏好规则调整关联置信度"""
    rules = await self._load_active_rules(user_id)

    result = []
    for assoc in associations:
        adjustment = 1.0
        for rule in rules:
            if not rule.is_active or rule.expires_at < utc_now():
                continue

            match = True
            if rule.condition_event_type and event.event_type != rule.condition_event_type:
                match = False
            if rule.condition_suggestion_type and assoc.association_type != rule.condition_suggestion_type:
                match = False
            if rule.condition_person_id and assoc.target_id != str(rule.condition_person_id):
                match = False

            if match:
                if rule.action == "suppress":
                    adjustment *= (1.0 - rule.confidence)
                elif rule.action == "deprioritize":
                    adjustment *= (1.0 - rule.confidence * 0.5)

        # 条件性降权（非全局）
        assoc_copy = EventAssociation(
            **{c.key: getattr(assoc, c.key) for c in assoc.__table__.columns}
        )
        assoc_copy.confidence = max(0.05, assoc.confidence * adjustment)
        result.append(assoc_copy)

    return result
```

**偏好规则的自动演化：**

- 反向信号：用户主动触发被抑制的内容（如主动问起张叔叔）→ 匹配规则的 confidence 衰减 20%
- TTL 到期（默认 90 天）：规则自动失活，等待新信号重新提取
- 冲突检测：新规则与旧规则矛盾时，保留 confidence 更高的

**迁移策略（处理遗留 feedback_weight）：**

1. 上线后停止写入 `feedback_weight`
2. 已有 `feedback_weight < 1.0` 的记忆，生成 PreferenceSignal 记录上下文
3. 通过新管道逐步提取偏好规则
4. 6 个月后废弃 `feedback_weight` 字段

---

## E3: 快路径关联融合

### 问题场景

用户说"下周去北京出差"，Fast Path 秒回"好的，已记录"。背景异步发现张叔叔在北京且 87 天没联系。但这个发现要到次日早报才呈现，错过了对话中的最佳情绪窗口。

### 解决方案：L1 上下文注入预计算关联

**核心思路：不新增 LLM 调用，不动 IntentRouter 核心流程。** 通过改进数据管道让现有 Haiku 调用自然融合关联信息。

#### 数据管道

```
mini_curate() 完成 → rule_engine 同步探测 strongly_recommend 关联
  → 结果写入 Redis (key: assoc:hints:{family_id}:{location_hash}, TTL 1h)

ContextAssembler.collect_l1() 读取 Redis → 注入 L1 层
  → Haiku system prompt 自然包含关联信息
  → Haiku 回复时自然融合（"已记录北京出差。对了，张叔叔也在北京，87天没联系了"）
```

#### 实现细节

**mini_curate 增加缓存写入（`curation_service.py`）：**

```python
# mini_curate() 末尾，sync_hints 返回前
if sync_hints:
    await self._cache_association_hints(
        family_id=family_id,
        location=location,
        hints=[
            {
                "title": h.title,
                "reason": h.reason,
                "priority": h.priority,
                "target_name": h.target_name,
            }
            for h in sync_hints[:3]  # 最多缓存 3 条
        ],
    )
```

**ContextAssembler L1 扩展（`context_assembler.py`）：**

```python
# collect_l1() 新增关联 hints 读取
async def _collect_association_hints(self, family_id, mentioned_locations):
    hints = []
    for loc in mentioned_locations:
        cache_key = f"assoc:hints:{family_id}:{_hash(loc)}"
        cached = await self._redis.get(cache_key)
        if cached:
            hints.extend(json.loads(cached))

    if hints:
        # 取 Top-1 最高优先级，避免信息过载
        top = sorted(hints, key=lambda h: _priority_rank(h["priority"]))[0]
        return ContextItem(
            layer="l1",
            source="association_hint",
            content=f"[关联提示] {top['title']}：{top['reason']}",
            tokens=self._estimate_tokens(top),
            importance=0.9,
        )
    return None
```

**Token 预算：** L1 从 500 → 600 tokens，增加 100 tokens。总预算 6800 → 6900。

**延迟影响：** Redis GET < 1ms，零感知。

**关键约束：** Fast Path 回复最多附带 **1 条** 关联提示，避免信息过载。如果有多条 strongly_recommend 关联，取置信度最高的一条内联，其余进入早报。

#### 追加推送模式（可选增强）

对于 mini_curate 完成**晚于** Fast Path 回复的情况（异步关联发现），通过 WebSocket 追加消息：

```python
# 异步关联发现完成后
if strongly_recommend_associations and session_still_active:
    top_assoc = strongly_recommend_associations[0]
    await pubsub.publish(
        channel=f"ws:{user_id}",
        message={
            "type": "ASSOCIATION_HINT",
            "data": {
                "text": f"对了，{top_assoc.title}",
                "actions": [
                    {"label": "安排一下", "action": "confirm", "id": str(top_assoc.id)},
                    {"label": "先记着", "action": "defer"},
                    {"label": "不用提醒", "action": "dismiss"},
                ],
            },
        },
    )
```

移动端展示为聊天气泡下方的轻量级卡片（非弹窗）。

用户 3 秒内无新输入才展示（防止打断输入节奏）。

---

## E4: 级联通知汇总

### 问题场景

上午客户会议延迟 30 分钟 → 后面 5 个事件受影响 → 当前 `analyze_cascade()` 对每个生成 `requires_user_decision=True` → 5 条通知轰炸。

### 解决方案

`analyze_cascade()` 的输出不变（保留每个 CascadeImpact 的详细信息），但消费方（`trigger_dispatcher.py` 或 WebSocket 推送逻辑）在推送时**合并为一条汇总消息**：

```python
# trigger_dispatcher.py 消费 CascadeAnalysis 时

async def _push_cascade_summary(
    self,
    analysis: CascadeAnalysis,
    user_id: UUID,
):
    """将多个级联影响合并为一条汇总消息"""
    need_decision = [i for i in analysis.impacts if i.requires_user_decision]
    auto_handled = [i for i in analysis.impacts if not i.requires_user_decision]

    summary_parts = []

    if auto_handled:
        titles = "、".join(f"「{i.event_title}」" for i in auto_handled[:3])
        suffix = f"等{len(auto_handled)}项" if len(auto_handled) > 3 else ""
        summary_parts.append(f"{titles}{suffix}已自动调整")

    if need_decision:
        titles = "、".join(f"「{i.event_title}」" for i in need_decision)
        summary_parts.append(f"{titles}需要您确认")

    text = f"{analysis.summary}。{'；'.join(summary_parts)}。"

    # 发送单条汇总消息 + 内嵌确认卡片
    await pubsub.publish(
        channel=f"ws:{user_id}",
        message={
            "type": "CASCADE_SUMMARY",
            "data": {
                "text": text,
                "decisions": [
                    {
                        "event_id": str(i.event_id),
                        "event_title": i.event_title,
                        "options": ["保留", "推迟", "取消"],
                    }
                    for i in need_decision
                ],
                "auto_handled": [str(i.event_id) for i in auto_handled],
            },
        },
    )
```

**效果：** 5 条通知 → 1 条汇总。"客户会推迟30分钟，「内部例会」「买菜」已自动调整；「面试候选人」需要您确认。"

---

## E5: 编排层主动减负

### 问题场景

日程密度 > 0.8 时，`orchestrator.py` 只添加一行 GapWarning 文字（"今天日程非常满，建议将低优先级事项推迟"），不采取实际行动。用户看到"很忙"并没有获得帮助。

### 解决方案

#### 1. Orchestrator 产出减负建议（维持只读原则）

Orchestrator 不直接创建 PendingAction（违反只读约束），而是在 `OrchestratedDay` 中增加 `deferral_suggestions` 字段：

```python
# models.py
@dataclass(frozen=True)
class DeferralSuggestion:
    event_id: UUID
    event_title: str
    reason: str
    suggested_new_date: Optional[date]  # 建议推迟到的日期
    priority_level: str
```

```python
# orchestrator.py orchestrate_day() Step 6 增强

if density > 0.7 and p2p3_events:
    deferral_candidates = [
        (e, s) for e, s in scored
        if s.priority_level in ("P2", "P3")
        and e.event_type not in _UNDEFERRABLE_TYPES
    ]

    suggestions = []
    for event, score in deferral_candidates[:2]:  # 最多建议 2 件
        suggested_date = self._find_next_light_day(
            target_date, family_id, exclude_event_ids=[event.id]
        )
        suggestions.append(DeferralSuggestion(
            event_id=event.id,
            event_title=event.title,
            reason=f"今日日程较满(密度{density:.0%})，建议推迟",
            suggested_new_date=suggested_date,
            priority_level=score.priority_level,
        ))
```

**不可推迟事件类型：**

```python
_UNDEFERRABLE_TYPES = frozenset({
    "pickup_child",      # 接孩子
    "medical_appointment",  # 已预约的看病
    "flight",            # 航班
    "exam",              # 考试
    "interview",         # 面试（对方在等）
})
```

#### 2. DailyBriefingService 消费建议生成 PendingAction

```python
# briefing/services/daily_briefing_service.py generate_briefing() 内

if orchestrated_day.deferral_suggestions:
    for suggestion in orchestrated_day.deferral_suggestions:
        pending = PendingAction(
            action_type="suggest_defer",
            payload={
                "event_id": str(suggestion.event_id),
                "suggested_new_date": suggestion.suggested_new_date.isoformat(),
                "reason": suggestion.reason,
            },
            display_data={
                "title": f"建议推迟「{suggestion.event_title}」",
                "subtitle": f"→ {suggestion.suggested_new_date.strftime('%m月%d日')}",
            },
            expires_at=utc_now() + timedelta(hours=12),
        )
```

#### 3. 疲劳感知 Buffer 膨胀（纯规则）

```python
# orchestrator.py _compute_gap() 内

def _compute_fatigue_multiplier(self, family_prefs) -> float:
    """基于 fatigue_state 计算 buffer 膨胀系数，纯规则"""
    fatigue = family_prefs.fatigue_state or {}
    base = 1.0

    # 连续高密度天数
    consecutive_days = fatigue.get("consecutive_high_density_days", 0)
    if consecutive_days >= 3:
        base += 0.25

    # 近 7 天健康类记忆数
    health_neg = fatigue.get("health_negative_7d", 0)
    if health_neg >= 2:
        base += 0.2

    return min(base, 1.5)  # 上限 50% 增幅
```

**fatigue_state 写入来源：** `ProactiveInsightService` 在每日 06:00 扫描时，将计算结果写入 `FamilyPreference.fatigue_state` JSONB 列。Orchestrator 只读该列，不直接调用 insight 服务（避免循环依赖）。

**Schema 变更（Migration 109）：**

```sql
ALTER TABLE family_preferences
ADD COLUMN fatigue_state JSONB DEFAULT '{}';
```

#### 4. 连续高强度自动加大 Buffer

不需要情绪数据，纯看事件序列：

```python
# _compute_gap() 内增加

# 连续高强度事件后的额外缓冲
consecutive_high_intensity = 0
for i in range(slot_index - 1, -1, -1):
    if slots[i].slot_type == "event" and _is_high_intensity(slots[i]):
        consecutive_high_intensity += 1
    else:
        break

if consecutive_high_intensity >= 2:
    required_buffer = int(required_buffer * 1.3)  # 加 30%
if consecutive_high_intensity >= 3:
    required_buffer = int(required_buffer * 1.5)  # 加 50%
```

#### 5. 吃饭时间保护

当前 `_MEAL_WINDOWS` 只是生成注解文字。增加保护逻辑：

```python
# _compute_gap() 内

# 如果事件跨越午餐时间，生成强警告
meal_windows = self._resolve_meal_windows(family_prefs)
for meal_name, (h_start, m_start, h_end, m_end) in meal_windows.items():
    meal_start = prev_end.replace(hour=h_start, minute=m_start)
    meal_end = prev_end.replace(hour=h_end, minute=m_end)

    if (event.normalized_start <= meal_start
        and event.normalized_end >= meal_end):
        warnings.append(GapWarning(
            gap_type="meal_conflict",
            affected_event_ids=[event.id],
            suggestion=f"此事件占用了{meal_name}时间，建议调整",
        ))
```

---

## E6: 多信号压力评分

### 问题场景

当前 `_check_stress_pattern()` 用 `COUNT(*) >= 3 negative memories in 7 days` 判断压力。信号维度单一，既有假阳性（用户说了 3 次"累"但心态轻松）也有假阴性（日程极满但情绪记忆未捕获）。

### 解决方案：多信号规则引擎

**替换 `_check_stress_pattern()` 为多维度评分（`proactive_insight_service.py`）：**

```python
async def _compute_stress_score(self, user_id: UUID) -> float:
    """0.0-1.0 压力分数，纯规则，零 LLM"""
    score = 0.0

    # 信号 1: 负面记忆密度（保留原有，权重 0.25）
    neg_count = await self._count_negative_memories(user_id, window_days=7)
    score += min(neg_count / 5.0, 1.0) * 0.25

    # 信号 2: 近 3 天日程密度均值（新增，权重 0.25）
    avg_density = await self._avg_recent_density(user_id, days=3)
    score += min(avg_density / 0.8, 1.0) * 0.25

    # 信号 3: 健康类负面记忆（新增，权重 0.20）
    health_neg = await self._count_health_memories(user_id, window_days=14)
    score += min(health_neg / 3.0, 1.0) * 0.20

    # 信号 4: 事件取消/推迟频率（新增，权重 0.15）
    cancel_rate = await self._cancelled_events_ratio(user_id, window_days=7)
    score += min(cancel_rate / 0.3, 1.0) * 0.15

    # 信号 5: 连续高密度天数（新增，权重 0.15）
    consecutive = await self._consecutive_high_density_days(user_id)
    score += min(consecutive / 5.0, 1.0) * 0.15

    return score
```

**LLM 仅用于高压力场景的建议文案生成：**

```python
async def _generate_stress_insight(self, user_id, score, signals):
    if score < 0.6:
        return None

    # score >= 0.6 时调用 Haiku 生成具体建议
    # 重点：不说"你压力大"，而是提供具体行动建议
    prompt = f"""
<user_signals>
{self._format_signals(signals)}
</user_signals>
<upcoming_3days>
{await self._get_upcoming_schedule_text(user_id, days=3)}
</upcoming_3days>

基于以上信息，生成一条简洁的生活建议。
规则：
- 不要说"检测到压力"或"你最近辛苦了"
- 提供 1-2 个具体可行的行动建议
- 结合日程现实（如果有空档就建议休息，如果没有就建议推迟低优先级事项）
- 语气像贴心助理而非心理咨询师

输出一个 JSON: {{"title": "...", "content": "...", "action_options": [...]}}
"""
```

**重要：** 洞察呈现方式不能是"检测到你压力大"，而是通过具体建议**隐含**关怀：

- 正确："这周安排比较密，周六上午我帮你留空了。要不要约老王吃个饭？"
- 错误："检测到你最近压力较大，建议注意休息"

---

## E7: 节日备货周期扩展

### 问题场景

`_find_date_based_associations()` 使用固定 `±7天窗口`。但中国场景中：
- 中秋月饼：提前 2-3 周订
- 春节年货：提前 1 个月
- 老人 70 大寿：提前 2 个月筹备

### 解决方案

**`important_dates` 表增加列（Migration 109）：**

```sql
ALTER TABLE important_dates
ADD COLUMN preparation_lead_days INTEGER DEFAULT 7;
```

**`_find_date_based_associations()` 改用 per-date 窗口：**

```python
# rule_engine.py _find_date_based_associations() 内

# 替换固定 7 天窗口
# 当前: timedelta(days=7)
# 改为: 每个 ImportantDate 自带 preparation_lead_days

for important_date in important_dates:
    lead_days = important_date.preparation_lead_days or 7
    if 0 <= days_diff <= lead_days:
        # 生成关联
```

**默认 preparation_lead_days 规则（`date_manager/services/date_service.py`）：**

在创建 ImportantDate 时根据类型自动设置：

```python
_DEFAULT_LEAD_DAYS = {
    "birthday": 14,           # 生日提前 2 周
    "anniversary": 14,        # 纪念日提前 2 周
    "spring_festival": 30,    # 春节提前 1 个月
    "mid_autumn": 21,         # 中秋提前 3 周
    "milestone_birthday": 60, # 整数大寿提前 2 个月
    "wedding": 90,            # 婚礼提前 3 个月
    "default": 7,
}

def _compute_lead_days(date_type: str, metadata: dict) -> int:
    if date_type == "birthday" and metadata.get("is_milestone"):
        return _DEFAULT_LEAD_DAYS["milestone_birthday"]
    return _DEFAULT_LEAD_DAYS.get(date_type, 7)
```

---

## E8: 占位事件（用户确认后）

### 问题场景

高置信度关联（"出差前准备行李"、"周五给张叔叔买礼物"）停留在文字注解层面，不占据时间轴。但如果系统自动插入日历占位，会污染日历信任。

### 解决方案：仅在用户确认关联后生成占位

**触发条件：**
- 用户通过 `confirm_association()` 确认了一个关联（非系统自动）
- 关联的 `priority = "strongly_recommend"`
- 关联的目标有时间属性（如 ImportantDate 有日期）

**实现（`curation_service.py` confirm_association 增强）：**

```python
async def confirm_association(self, association_id, user_id, create_event=True):
    assoc = await self._load_association(association_id)
    assoc.is_confirmed = True

    if create_event and assoc.priority == "strongly_recommend":
        # 查找主事件时间范围内的空闲时段
        source_event = await self._load_curated_event(assoc.source_event_id)
        gap = await self._find_suitable_gap(
            family_id=source_event.family_id,
            date_range=(source_event.normalized_start, source_event.normalized_end),
            duration_minutes=60,  # 默认 1 小时
        )

        if gap:
            placeholder = CuratedEvent(
                family_id=source_event.family_id,
                user_id=user_id,
                title=assoc.title,
                normalized_start=gap.start,
                normalized_end=gap.end,
                status="placeholder",  # 新状态
                event_type="preparation",
                priority="normal",
                source_types=["association_confirmed"],
                original_event_ids=[str(source_event.id)],
                confidence=assoc.confidence,
            )
            self._session.add(placeholder)
```

**Placeholder 的视觉区分（移动端）：**
- 虚线边框 + 浅灰背景（区别于实线的正式事件）
- 标签："暂定"
- 支持拖拽调整时间
- 长按可直接删除

**生命周期管理：**
- 主事件取消 → E1 的分类逻辑决定是否保留
- 主事件结束后 24 小时 → 未确认的 placeholder 自动过期

---

## 补充修复项

### F1: InterventionClassifier 注入 Agent 状态摘要

当前 InterventionClassifier 只看用户新消息来分类干预类型，缺乏"Agent 正在做什么"的上下文。

```python
# intervention/classifier.py classify() prompt 增强

# 新增 ~80 tokens 的当前 agent 状态
<current_agent_state>
状态: {generation_state}
当前任务: {task_summary}
已生成内容摘要: {partial_text_last_100_chars}
正在执行的工具: {active_tool or "无"}
</current_agent_state>
```

Haiku 额外 80 tokens 延迟增加 ~20ms，仍在 150ms 预算内。

### F2: Sidekick Gate 3 改为实体 ID 匹配

当前文本包含 `entity.lower() in task_summary.lower()` 有假阳性/假阴性。

```python
# sidekick_worker.py _is_contextually_relevant() 替换

def _is_contextually_relevant(self, insight, session_context) -> bool:
    # Level 1: 实体 ID 精确匹配
    insight_ids = set(insight.related_person_ids or [])
    context_ids = set(session_context.get("mentioned_person_ids", []))
    if insight_ids & context_ids:
        return True

    # Level 2: 事件类型亲和度
    affinity_map = {
        ("trip_correlation", "trip"): True,
        ("favor_reciprocation", "gift"): True,
        ("relationship_maintenance", "social"): True,
    }
    key = (insight.insight_type, session_context.get("action_category", ""))
    if affinity_map.get(key):
        return True

    # Level 3: 地点重叠
    if (insight.location
        and insight.location in session_context.get("mentioned_locations", [])):
        return True

    return False
```

### F3: HybridPriorityEngine 模糊区间缩小

当前规则打分后 score 0.35-0.65 触发 LLM 校准，约 30-40% 事件命中。增加 2 个打分维度缩小到 ~15%：

```python
# priority_engine.py compute_priority_score() 增强

# 新增维度 1: 用户历史交互频率
interaction_bonus = min(event.interaction_count / 10.0, 1.0) * 0.15

# 新增维度 2: 与关联数量的关系
assoc_bonus = min(association_count / 3.0, 1.0) * 0.10

# 加入合成分后，模糊区间从 0.35-0.65 缩小到约 0.42-0.58
# Haiku 校准调用减少约 50%
```

---

## 数据库迁移计划 (Migration 109)

```sql
-- 1. preference_signals 表
CREATE TABLE preference_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    family_id UUID NOT NULL REFERENCES families(id),
    signal_type VARCHAR(32) NOT NULL,
    source_type VARCHAR(32) NOT NULL,
    source_id UUID NOT NULL,
    source_context JSONB NOT NULL DEFAULT '{}',
    user_reason TEXT,
    category_key VARCHAR(128) NOT NULL,
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_preference_signals_user_category
    ON preference_signals(user_id, category_key, processed);

-- 2. user_preference_rules 表
CREATE TABLE user_preference_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    family_id UUID NOT NULL REFERENCES families(id),
    condition_event_type VARCHAR(64),
    condition_suggestion_type VARCHAR(64),
    condition_person_id UUID,
    condition_location VARCHAR(128),
    action VARCHAR(32) NOT NULL,
    confidence FLOAT NOT NULL,
    explanation TEXT NOT NULL,
    scope VARCHAR(32) NOT NULL,
    source_signal_count INTEGER NOT NULL DEFAULT 3,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_preference_rules_user_active
    ON user_preference_rules(user_id, is_active);

-- 3. family_preferences 增加 fatigue_state 列
ALTER TABLE family_preferences
ADD COLUMN IF NOT EXISTS fatigue_state JSONB DEFAULT '{}';

-- 4. important_dates 增加 preparation_lead_days 列
ALTER TABLE important_dates
ADD COLUMN IF NOT EXISTS preparation_lead_days INTEGER DEFAULT 7;
```

---

## Celery 任务变更

| 任务名 | 队列 | 调度 | 说明 |
|--------|------|------|------|
| `secretary.extract_preference_rules` | secretary | 每日 05:00 | 批量提取偏好规则 (E2) |
| `secretary.refresh_fatigue_state` | secretary | 每日 05:30 | 更新 fatigue_state (E5) |

---

## 场景验证

### 场景 A: "北京出差取消"

```
Day 0: 用户说"下月去北京出差"
  → mini_curate 创建 CuratedEvent
  → rule_engine 发现:
    - 张叔叔在北京(location, confidence=0.85, cold 87天)
    - 后天是张叔叔65岁生日(temporal, confidence=0.92)
    - 欠刘阿姨人情，刘阿姨在北京(memory+stale, confidence=0.78)
  → [E3] L1 注入最高置信关联
  → Fast Path 回复: "好的，已记录下月北京出差。
     对了，后天是张叔叔65岁生日，要不要提前准备个礼物？"
  → [E3] 用户点击"安排一下" → PendingAction(SUGGEST_GIFT)

Day 5: 用户取消北京出差
  → [E1] _classify_association_on_cancel():
    - 张叔叔location关联 → dismiss (纯位置依赖)
    - 张叔叔生日temporal关联 → preserve_as_action (日期不因行程取消消失)
    - 刘阿姨memory关联 → preserve_as_action (人情不因行程取消消失)
  → 推送汇总: "北京出差已取消。提醒您：张叔叔生日礼物还需安排，
     刘阿姨的人情也要另想办法。[处理一下] [先放着]"
```

### 场景 B: "周三日程爆满"

```
早报编排:
  → orchestrate_day() 计算 density = 0.85
  → [E5] fatigue_state.consecutive_high_density_days = 3
  → fatigue_multiplier = 1.25 (buffer 膨胀 25%)
  → P2/P3 事件: "回复李阿姨微信"(P3) + "查看礼物推荐"(P2)
  → DeferralSuggestion: 推迟到周六

早报展示:
  ┌─ 今日核心 ─────────────────────────┐
  │ 09:00 客户会议                      │
  │ 12:00 妈妈生日午餐                  │
  │ 15:00 项目评审                      │
  └─────────────────────────────────────┘
  ┌─ 建议推迟 ─────────────────────────┐
  │ ☐ 回复李阿姨微信 → 周六             │
  │ ☐ 查看礼物推荐 → 本周内             │
  │ [同意推迟]  [全部保留]               │
  └─────────────────────────────────────┘
```

### 场景 C: "出差时不想见朋友" 偏好学习

```
Signal 1 (02/10): dismiss "去深圳出差时约陈总" → PreferenceSignal
Signal 2 (02/15): dismiss "去上海出差时见老同学" → PreferenceSignal
Signal 3 (02/20): dismiss "去北京出差时见张叔叔" → PreferenceSignal

每日 05:00: extract_preference_rules 任务
  → category_key "business_trip:social_meeting" 有 3 条信号
  → Haiku 提取: {
      condition: {event_type: "business_trip", suggestion_type: "social_meeting"},
      action: "suppress",
      confidence: 0.85,
      explanation: "用户不希望在出差期间安排社交活动",
      ttl_days: 90
    }
  → 写入 user_preference_rules

下次出差:
  → association_service._apply_preference_rules()
  → "见某人"类关联 confidence 降至 0.15 (= original * (1 - 0.85))
  → 不再出现在推荐中

但用户主动问 "张叔叔生日送什么好":
  → 不受影响 (偏好规则只影响 association，不影响 memory recall)
  → 张叔叔记忆的 feedback_weight 未被修改，正常召回
```

### 场景 D: "会议延迟级联"

```
10:00 客户会延迟 30 分钟
  → analyze_cascade() 检测影响:
    - 11:30 内部例会 (P2) → auto_defer
    - 13:30 面试候选人 (P1) → requires_user_decision
    - 15:00 项目评审 (P1) → requires_user_decision
    - 17:00 接孩子 (P0) → requires_user_decision
    - 18:00 买菜回家 (P3) → auto_defer

  → [E4] 汇总推送 (1 条，非 5 条):
    "客户会推迟30分钟。「内部例会」「买菜」已自动调整；
     「面试」「项目评审」「接孩子」需要您确认。[查看详情]"
```
