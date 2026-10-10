# 洞察系统统一简化 — 架构设计文档

> **状态**: DRAFT v7 (Round 14 研发团队全面评审)
> **日期**: 2026-03-10
> **主持**: Tech Lead (架构师)
> **参与**: 架构挑战者、后端工程师、产品工程师、领域专家 (人情/情感)

---

## 1. 问题陈述

当前洞察系统存在严重的架构复杂度问题：

| 维度 | 现状 | 问题 |
|------|------|------|
| 触发场景 | 7 个独立触发点 | 各自有不同的扫描逻辑、去重规则 |
| 数据表 | `memory_insights` + `user_insights` | 消费方查询不一致，kanban 查前者，briefing 查后者 |
| 中间产物 | EA → MI → UI 三层晋升 | 链路长、状态多、调试难 |
| 生成系统 | System A/B/C 各有子生成器 | 逻辑重叠，每个都独立调 LLM |
| LLM 调用 | 每个子生成器独立 prompt | 同一用户同一天可能被 6-8 次独立 LLM 调用 |

**核心矛盾**: 产品上是"秘书每天整理一次，统一产出建议"，但实现上是 7 条独立管道各自写入不同表。

---

## 2. 最终方案

### 2.1 数据模型

#### 新建 `insights` 统一表 + `insight_entities` 关联子表

```sql
CREATE TABLE insights (
    -- 主键
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 归属
    user_id                   UUID NOT NULL,
    family_id                 UUID NOT NULL,

    -- 内容: LLM 输出原子化洞察，每条只含一个可执行建议
    insight_type              VARCHAR(30) NOT NULL,  -- time, relationship, favor, health, memory, efficiency, finance
    title                     VARCHAR(200) NOT NULL,
    content                   TEXT NOT NULL,

    -- 评分
    importance                INT NOT NULL DEFAULT 50,  -- 0-100
    urgency                   INT NOT NULL DEFAULT 50,  -- 0-100

    -- 来源追踪
    source                    VARCHAR(30) NOT NULL DEFAULT 'scheduled',  -- scheduled, trip_event, reflection, manual
    source_context            JSONB DEFAULT '{}',  -- 非关键元数据，见 2.1.1

    -- 用户交互: 6 状态枚举 (含 acknowledged)
    status                    VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, active, acknowledged, acted, dismissed, expired
    -- feedback 只存用户反馈值: useful, not_useful, too_frequent, not_relevant, incorrect, defer, never, not_now
    feedback                  VARCHAR(20),
    feedback_at               TIMESTAMPTZ,
    -- feedback_source 区分反馈来源:
    -- 'user' = 用户主动反馈
    -- 'cascade_dismiss' / 'cascade_preserved' / 'cascade_reactivated' = 行程取消级联
    -- 'hygiene_event_past' / 'hygiene_entity_deleted' / 'hygiene_date_past' = 清理任务
    feedback_source           VARCHAR(30) DEFAULT 'user',

    -- 操作建议
    suggested_action          TEXT,
    action_options            JSONB,  -- List[ActionSpec]

    -- 去重: 编码义务身份而非实体元组
    -- favor → favor:{favor_record_id}
    -- relationship → relationship:{person_id}
    -- commitment → commitment:{commitment_id}
    -- time → time:{important_date_id}:{event_id}
    dedup_key                 VARCHAR(255),

    -- 展示追踪
    shown_at                  TIMESTAMPTZ,  -- 首次展示时间 (kanban/briefing/sidekick)

    -- 推送渠道追踪 (boolean 列替代 array)
    delivered_via_briefing    BOOLEAN NOT NULL DEFAULT false,
    delivered_via_sidekick    BOOLEAN NOT NULL DEFAULT false,
    delivered_via_kanban      BOOLEAN NOT NULL DEFAULT false,
    delivered_via_push        BOOLEAN NOT NULL DEFAULT false,

    -- 三级 dismiss 模型
    snoozed_until             TIMESTAMPTZ,   -- defer 时设置，该时间前不展示
    regen_suppressed_until    TIMESTAMPTZ,   -- dismiss 时设置，该时间前同 dedup_key 不可再生

    -- 生命周期
    expires_at                TIMESTAMPTZ,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    pushed_at                 TIMESTAMPTZ,
    read_at                   TIMESTAMPTZ
);

-- 关联实体子表: 一条洞察可关联多个人/事件/行程/日期/EA/领域来源
-- role 只表示语义关系 (不可变)，adopt 状态用 adopted_at 时间戳
-- entity_type='favor'/'commitment'/'important_date'/'memory' + role='source' 替代独立 FK 列
CREATE TABLE insight_entities (
    insight_id  UUID NOT NULL REFERENCES insights(id) ON DELETE CASCADE,
    entity_type VARCHAR(20) NOT NULL,   -- person, trip, event, important_date, event_association, favor, commitment, memory
    entity_id   UUID NOT NULL,
    role        VARCHAR(20) NOT NULL DEFAULT 'related',  -- primary, related, mentioned, source (IMMUTABLE)
    adopted_at  TIMESTAMPTZ,   -- NULL = 未 adopt, 非 NULL = 已 adopt (可回退为 NULL)
    done_at     TIMESTAMPTZ,   -- NULL = 未完成, 非 NULL = 该实体维度已完成
    PRIMARY KEY (insight_id, entity_type, entity_id),

    -- 约束: adopted_at 只允许在 primary/related 实体上设置
    CONSTRAINT chk_adopt_role CHECK (adopted_at IS NULL OR role IN ('primary', 'related')),
    -- 约束: done_at 只允许在已 adopted 的实体上设置
    CONSTRAINT chk_done_adopt CHECK (done_at IS NULL OR adopted_at IS NOT NULL)
);
```

**与旧方案的关键差异 (v7)**:
- **消除 4 个稀疏 FK 列**: `source_favor_id` 等提升为 `insight_entities` 中 `entity_type='favor' + role='source'` 行，统一机制
- **新增 `acknowledged` 状态**: 用户确认知悉义务存在，90 天内不再提醒 (见 2.1.2)
- **`dedup_key` 编码义务身份**: `favor:{favor_record_id}` 而非 `{type}:{entity_type}:{entity_ids}`
- **delivery_channels 改为 boolean 列**: 可索引、类型安全
- **CHECK 约束**: 防止 `adopted_at` 设置在 `mentioned` 实体上

索引策略：

```sql
-- ===== insights 表索引 =====

-- Kanban: 全局 active 列表
CREATE INDEX ix_insights_kanban
  ON insights (user_id, importance DESC, urgency DESC, created_at DESC)
  WHERE status IN ('pending', 'active');

-- Briefing: 高分 pending
CREATE INDEX ix_insights_briefing
  ON insights (user_id, importance DESC)
  WHERE status = 'pending' AND importance >= 60;

-- 去重 (同 user + 同 dedup_key 只允许一条活跃记录)
CREATE UNIQUE INDEX ix_insights_dedup
  ON insights (user_id, dedup_key)
  WHERE dedup_key IS NOT NULL AND status NOT IN ('dismissed', 'acted', 'expired');

-- Family 维度查询
CREATE INDEX ix_insights_family
  ON insights (family_id, status);

-- 过期清理 + Snooze + 再生抑制 (合并为一个通用生命周期索引)
CREATE INDEX ix_insights_lifecycle
  ON insights (expires_at, snoozed_until, regen_suppressed_until)
  WHERE status IN ('pending', 'active', 'dismissed');

-- ===== insight_entities 表索引 =====

-- 反向查: 某个实体关联了哪些洞察
CREATE INDEX ix_ie_entity
  ON insight_entities (entity_type, entity_id);

-- 来源反查: 某个领域实体 (favor/commitment) 对应的洞察
CREATE INDEX ix_ie_source
  ON insight_entities (entity_type, entity_id)
  WHERE role = 'source';
```

**查询模式示例：**

```sql
-- Kanban 全局列表 (无需 JOIN)
SELECT * FROM insights
WHERE user_id = ? AND status IN ('pending', 'active')
  AND (snoozed_until IS NULL OR snoozed_until <= now())
ORDER BY importance DESC, urgency DESC, created_at DESC
LIMIT 10;

-- 成员详情页: 某人相关的洞察 (通过子表 JOIN)
SELECT i.* FROM insights i
JOIN insight_entities ie ON i.id = ie.insight_id
WHERE ie.entity_type = 'person' AND ie.entity_id = ?
  AND i.status IN ('pending', 'active')
ORDER BY i.importance DESC;

-- 行程已 adopt 的洞察 (trip card 展示)
SELECT i.* FROM insights i
JOIN insight_entities ie ON i.id = ie.insight_id
WHERE ie.entity_type = 'trip' AND ie.entity_id = ?
  AND ie.adopted_at IS NOT NULL
ORDER BY i.created_at;

-- 来源反查: 某 favor 对应的活跃洞察
SELECT i.* FROM insights i
JOIN insight_entities ie ON i.id = ie.insight_id
WHERE ie.entity_type = 'favor' AND ie.entity_id = ? AND ie.role = 'source'
  AND i.status IN ('pending', 'active', 'acknowledged');
```

#### 2.1.1 `source_context` JSONB 标准结构

> 关键 FK (favor_id, commitment_id 等) 已通过 `insight_entities` (role='source') 统一管理。
> `source_context` 只存放非关键元数据。

```python
class SourceContext(BaseModel):
    """source_context JSONB 的运行时验证模型。只存非关键元数据。
    关键 FK 通过 insight_entities (entity_type + role='source') 管理。"""
    signal_ids: List[str] = Field(default_factory=list)
    ea_ids: List[str] = Field(default_factory=list)
    generation_batch_id: Optional[str] = None
    person_profile_ids: List[str] = Field(default_factory=list)
    confidence: Optional[float] = None
    health_subtype: Optional[str] = None    # overwork, sleep, exercise, meal, stress, general
    health_event: Optional[bool] = None     # 是否因健康/紧急事件产生
    reactivated_from: Optional[str] = None  # 上一条被重激活洞察的 ID
    reactivation_depth: int = 0             # DJ 重激活深度，防循环
    commitment_type: Optional[str] = None
    social_intent: Optional[bool] = None
    reason: Optional[str] = None  # e.g., 'trip_cancel_double_jeopardy'

    class Config:
        extra = 'allow'  # 允许额外字段 (向前兼容)
```

#### 2.1.2 统一状态枚举

```python
class InsightStatus(str, Enum):
    PENDING = "pending"            # 生成完毕，未曾展示
    ACTIVE = "active"              # 已展示给用户 (合并 pushed/read)
    ACKNOWLEDGED = "acknowledged"  # 用户确认知悉，90天内不主动提醒 (满足义务覆盖)
    ACTED = "acted"                # 用户执行了操作 (adopt/useful/action chip)
    DISMISSED = "dismissed"        # 用户 dismiss / 级联 dismiss / 自动过期前清理
    EXPIRED = "expired"            # TTL 到期，自动过期

# 状态机: acted/dismissed/expired 为终态，acknowledged 可回到 active
VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    'pending':      frozenset({'active', 'dismissed', 'expired'}),
    'active':       frozenset({'acknowledged', 'acted', 'dismissed', 'expired'}),
    'acknowledged': frozenset({'active', 'acted', 'dismissed', 'expired'}),  # 90天到期或上下文变化时回到 active
    'acted':        frozenset(),   # 终态
    'dismissed':    frozenset(),   # 终态 — 重新激活通过创建新洞察
    'expired':      frozenset(),   # 终态 — 重新生成通过 dedup_key 解锁
}
```

**`acknowledged` 状态语义**:
- 用户反馈 `feedback='acknowledged'`，status 转为 `acknowledged`
- 设 `snoozed_until = utc_now() + timedelta(days=90)`
- 义务覆盖审计视 `acknowledged` 为有效覆盖 (与 active 等同)
- 90 天后或底层义务上下文变化 (如 FavorRecord urgency 上升、关系温度从 warm 降为 cold) 时，自动回到 `active`
- 不计入 dismiss 累积次数
- **产品含义**: "我知道了，不用一直提醒我，我会处理的"

**与旧枚举的映射**: `pushed`→`active`, `read`→`active`, `actioned`→`acted`, `ignored`→`not_useful`, `never_again`→`never`

#### 保留的表 (不变)

| 表 | 角色 | 说明 |
|----|------|------|
| `event_associations` | 事件关联发现层 | 去掉 `promoted_at`, `promoted_insight_id`, `dismiss_cascaded_at` 字段 |
| `preference_signals` | 反馈信号收集 | 不变 |
| `user_preference_rules` | 偏好抑制规则 | 不变 |
| `family_preferences` | 家庭偏好 | 不变 |
| `curated_events` | 事件策展 | 不变 |

#### 废弃的表

| 表 | 替代 | 迁移后删除 |
|----|------|-----------|
| `memory_insights` | → `insights` | 迁移完成 + 7 天观察后 |
| `user_insights` | → `insights` | 迁移完成 + 7 天观察后 |
| `insight_feedbacks` | → `preference_signals` | 迁移完成后立即 |
| `InsightDeliveryLedger` | → `insights.delivered_via_*` | Phase 4 |

### 2.2 触发模型

```
+-----------------------------------------------------+
|                   Scheduled Path                     |
|                                                     |
|  Celery Beat 06:00 UTC                              |
|  +-------------------------+                        |
|  | InsightPipeline         |                        |
|  | .run_scheduled()        |                        |
|  |                         |                        |
|  | 1. collect_signals()    | <- CuratedEvent, EA,   |
|  |    + protected signals  |   ImportantDate, Temp,  |
|  |                         |   Commitment, Memory    |
|  | 2. generate_batch()     | <- 单次 Haiku 调用      |
|  |    全量上下文输入        |   max_tokens=1500      |
|  |                         |                        |
|  | 3. contextual_          | <- 从 Reactive 移至此处 |
|  |    reactivation()       |                        |
|  |                         |                        |
|  | 4. dedup()              | <- 管道侧计算 dedup_key |
|  | 5. apply_prefs()        |                        |
|  | 6. person_budget()      |                        |
|  | 7. persist()            | -> insights 表          |
|  | 8. sidekick_eval()      |                        |
|  +-------------------------+                        |
|                                                     |
|  原场景 ①②⑥ 合并                                    |
+-----------------------------------------------------+

+-----------------------------------------------------+
|                   Reactive Path                      |
|                                                     |
|  事件驱动 (T1 即时)                                  |
|  +-------------------------+                        |
|  | InsightPipeline         |                        |
|  | .run_reactive()         |                        |
|  |                         |                        |
|  | 1. build_context()      | <- 单个 CuratedEvent   |
|  |                         |   + 相关 EA + Memory    |
|  | 2. generate_single()    | <- 1 次 Haiku 调用     |
|  | 3. dedup()              |                        |
|  | 4. apply_prefs()        |                        |
|  | 5. persist()            | -> insights 表          |
|  +-------------------------+                        |
|                                                     |
|  紧急承诺即时触发                                     |
|  +-------------------------+                        |
|  | .run_reactive_          |                        |
|  |  commitment()           |                        |
|  | 对话提取到 firm          |                        |
|  | commitment 且            |                        |
|  | deadline <= 2 天         |                        |
|  | -> 立即产出洞察          |                        |
|  +-------------------------+                        |
|                                                     |
|  原场景 ④ (行程生命周期) + 紧急承诺                   |
+-----------------------------------------------------+

+-----------------------------------------------------+
|                   Maintenance Path                   |
|                                                     |
|  Celery Beat 04:00 UTC + 每 6h                      |
|  +-------------------------+                        |
|  | InsightHygiene          |                        |
|  | .run_cleanup()          |                        |
|  |                         |                        |
|  | 1. expire_stale()       | <- expires_at < now()  |
|  | 2. dismiss_invalid()    | <- source entity gone  |
|  | 3. dismiss_past_events()| <- related event past  |
|  | 4. handle_past_dates()  | <- 重要日期已过 (含可  |
|  |                         |    补偿判断)            |
|  | 5. obligation_coverage  | <- 义务覆盖审计         |
|  |    _audit()             |                        |
|  | 6. recheck_expired_     | <- PA 过期后义务再检查  |
|  |    cascade_actions()    |                        |
|  | 7. archive_old()        | <- 90天归档清理         |
|  | 8. check_acknowledged   | <- acknowledged 90天   |
|  |    _expiry()            |    到期回转 active      |
|  +-------------------------+                        |
|                                                     |
|  原场景 ③ (过期清理)                                  |
+-----------------------------------------------------+

+-----------------------------------------------------+
|           Non-Insight Paths (不变)                   |
|                                                     |
|  ⑤ 对话中记忆提取 -> CuratedEvent + EA (不产洞察)    |
|  ⑦ 对话后沉淀 -> CuratedEvent + EA (不产洞察)        |
|  这些产出被下次 Scheduled Path 的 collect_signals    |
|  读取作为信号源                                      |
+-----------------------------------------------------+
```

### 2.3 生成管道

#### Scheduled Batch Generation

```python
class InsightPipeline:
    SIGNAL_TOKEN_BUDGET = 8000

    async def run_scheduled(self, user_id, family_id, target_date):
        prefs = await self._load_preferences(user_id)
        budget = self._build_budget(prefs)
        await self._refresh_stale_insights(user_id)

        # 1. 收集所有信号源 (含 protected 社交义务信号)
        signals = await self._collect_signals(user_id, family_id, target_date)

        # 2. 信号压缩 (承诺跟进 + 重要日期不可截断)
        compressed = self._compress_signals(signals, self.SIGNAL_TOKEN_BUDGET)

        # 3. 单次 LLM 调用 — 全量上下文输入
        candidates = await self._generate_batch(compressed, budget)

        # 4. 上下文再激活
        reactivated = await self._contextual_reactivation(user_id, compressed)
        candidates.extend(reactivated)

        # 5. 管道侧计算 dedup_key (不依赖 LLM 输出)
        for c in candidates:
            c.dedup_key = self._compute_dedup_key(c)

        # 6. 去重 (含累积 dismiss 升级检查)
        deduped = await self._dedup(candidates, user_id)

        # 7. 偏好过滤 (含不可抑制白名单)
        filtered = self._apply_preferences(deduped, prefs)

        # 8. 人物预算 (每人最多 2 条)
        budgeted = self._person_budget_filter(filtered)

        # 9. 持久化 (返回实际插入的 ID 列表)
        saved = await self._persist(budgeted)

        # 10. Sidekick 评估
        await self._trigger_sidekick(user_id, saved)
        return saved

    def _compute_dedup_key(self, candidate: InsightCandidate) -> str:
        """管道侧计算 dedup_key，基于义务身份而非实体元组。"""
        source_entities = [e for e in candidate.entities if e.role == 'source']
        if candidate.insight_type == 'favor' and source_entities:
            return f"favor:{source_entities[0].entity_id}"
        if candidate.insight_type == 'relationship':
            primary = next((e for e in candidate.entities if e.entity_type == 'person' and e.role == 'primary'), None)
            return f"relationship:{primary.entity_id}" if primary else f"relationship:{candidate.insight_type}:{hash(candidate.title)}"
        if source_entities:
            return f"{source_entities[0].entity_type}:{source_entities[0].entity_id}"
        # Fallback: type + sorted entity IDs
        entity_ids = sorted(str(e.entity_id) for e in candidate.entities if e.role in ('primary', 'related'))
        return f"{candidate.insight_type}:{':'.join(entity_ids)}"
```

#### 信号压缩算法

```python
def _compress_signals(self, signals: AllSignals, budget: int) -> AllSignals:
    """优先级: protected > upcoming_events > relationships > memories > associations。
    整条丢弃 (LLM 处理不完整信号效果差)。Token 估算: len(text) / 3.5 + 20% buffer。"""
    PRIORITY_ORDER = [
        ('protected', signals.protected),       # 人情/承诺 — 不可截断
        ('upcoming_events', signals.events),     # 按时间近远排序
        ('relationships', signals.relationships), # 按温度低高排序
        ('memories', signals.memories),           # 按 recency 排序
        ('associations', signals.associations),
    ]
    result = AllSignals()
    used = 0
    for category, items in PRIORITY_ORDER:
        for item in items:
            tokens = int(len(item.to_prompt_text()) / 3.5 * 1.2)
            if category == 'protected' or used + tokens <= budget:
                result.add(category, item)
                used += tokens
    return result
```

#### 单次 LLM 调用设计

| 指标 | 值 |
|------|-----|
| 输入 token（典型） | 3000-5000 |
| 输入 token（极端） | 5000-8000（压缩后） |
| max_tokens | 2000（留 buffer 防 JSON 截断） |
| temperature | 0.3 |
| model | Haiku 4.5 |
| 单次调用延迟 | 800-1200ms |
| 故障处理 | 失败后重试 1 次，仍失败则跳过本次（不影响 protected 义务 — 审计兜底） |

Prompt 结构：

```
[system] SECRETARY_PERSONA + 洞察生成指令

[user] 以下是用户 {user_name} 的当前状态全景。请综合所有信号，生成 0-{budget} 条最有价值的洞察建议。

       <signals>
         <upcoming_events>...</upcoming_events>
         <relationships>...</relationships>
         <commitments>...</commitments>
         <memories>...</memories>
         <associations>...</associations>
       </signals>

       [PROTECTED - 不可忽略的社交义务]
       - 人情: ... (已提醒N次)
       - 关系: ... (已M天未联系)

       每条洞察格式 (JSON array):
       [{"type":"...", "title":"<=10字", "content":"<=50字具体可执行的建议",
         "importance":0-100, "urgency":0-100,
         "suggested_action": "具体操作建议",
         "entities": [{"type":"person", "id":"rel_1", "role":"primary"}],
         "source_signal_ids": ["evt_1", "rel_1", "ea_1"]}]

       注意: dedup_key 由系统自动计算，不需要在输出中包含。
```

#### Reactive Generation

```python
async def run_reactive(self, event: CuratedEvent, family_id):
    context = await self._build_event_context(event, family_id)
    candidates = await self._generate_single(context)
    for c in candidates:
        c.dedup_key = self._compute_dedup_key(c)
    # dedup + prefs + persist ...
```

### 2.4 消费模型

```python
class InsightQueryService:
    """统一洞察查询入口。所有消费方通过此服务查询 insights 表。"""

    async def get_for_kanban(self, user_id: UUID, limit: int = 10) -> List[InsightCard]:
        """Kanban AI 建议卡片列表 — 无需 JOIN，主表直查。
        返回结果包含 delivered_via_* 信息，前端可据此标注"已在简报中提醒"。"""
        stmt = (
            select(Insight)
            .where(
                Insight.user_id == user_id,
                Insight.status.in_(['pending', 'active']),
                or_(Insight.expires_at.is_(None), Insight.expires_at > utc_now()),
                or_(Insight.snoozed_until.is_(None), Insight.snoozed_until <= utc_now()),
            )
            .order_by(Insight.importance.desc(), Insight.urgency.desc(), Insight.created_at.desc())
            .limit(limit)
        )
        ...

    async def get_for_member(self, user_id: UUID, person_id: UUID, limit: int = 20) -> List[InsightCard]:
        """成员详情页 — 通过 insight_entities 反查。"""
        ...  # JOIN insight_entities WHERE entity_type='person' AND entity_id=person_id

    async def get_for_trip(self, user_id: UUID, trip_id: UUID, limit: int = 10) -> List[InsightCard]:
        """行程详情页/Timeline — 通过 insight_entities 反查。"""
        ...

    async def get_for_briefing(self, user_id: UUID, family_id: UUID, limit: int = 5) -> List[InsightCard]:
        """每日简报 — 高分洞察，无需 JOIN。"""
        ...  # WHERE status='pending' AND importance >= 60

    async def get_for_sidekick(self, user_id: UUID, limit: int = 3) -> List[InsightCard]:
        """Sidekick 注入候选 — 近 6h 高分。"""
        ...  # WHERE importance >= 70 AND created_at >= now() - 6h
```

### 2.5 操作模型

> **Service 拆分** (避免 God Service):
> - `InsightFeedbackService` — 反馈记录 + 状态转换
> - `InsightAdoptService` — adopt + trip task done
> - `InsightCascadeService` — 行程取消级联 + EA 级联
> - `InsightDomainBridge` — 领域回写 (事件驱动)

```python
class InsightFeedbackService:
    """反馈记录 + 状态转换。"""

    async def record_feedback(self, insight_id: UUID, user_id: UUID, feedback: str, reason: Optional[str] = None):
        insight = await self._get(insight_id, user_id)
        insight.feedback = feedback
        insight.feedback_at = utc_now()
        insight.feedback_source = 'user'

        if feedback == 'never':
            # Level 3: 永久抑制
            self._transition_status(insight, 'dismissed')
            await self._create_permanent_suppression(insight)

        elif feedback in ('not_useful', 'not_relevant', 'incorrect'):
            # Level 2: 内容否定 — 设置再生抑制窗口
            # 累积 dismiss 升级: 同 dedup_key 达到类型阈值 → 自动升 Level 3
            dismiss_count = await self._get_dismiss_count(insight.user_id, insight.dedup_key)
            threshold = SUPPRESSION_THRESHOLDS.get(insight.insight_type, 3)
            if dismiss_count >= threshold - 1:  # 达到阈值
                await self._create_permanent_suppression(insight)
                insight.feedback = 'never'
            else:
                insight.regen_suppressed_until = utc_now() + self._get_suppression_window(insight)
            self._transition_status(insight, 'dismissed')

        elif feedback == 'defer':
            # Level 1: 时机不对 — snooze (根据类型自动调整时长)
            snooze_days = 7 if insight.insight_type in ('favor', 'relationship') else 3
            insight.snoozed_until = utc_now() + timedelta(days=snooze_days)
            if insight.expires_at and insight.expires_at < insight.snoozed_until:
                insight.expires_at = insight.snoozed_until + timedelta(days=1)

        elif feedback == 'acknowledged':
            # 用户确认知悉: "我知道了，会处理的"
            self._transition_status(insight, 'acknowledged')
            insight.snoozed_until = utc_now() + timedelta(days=90)
            if insight.expires_at and insight.expires_at < insight.snoozed_until:
                insight.expires_at = insight.snoozed_until + timedelta(days=1)

        elif feedback == 'useful':
            self._transition_status(insight, 'acted')

        # 写入 preference signal
        signal = PreferenceSignal(...)
        self.db.add(signal)

        # 发布领域事件 (替代直接 service 调用)
        if feedback in ('not_useful', 'never', 'not_relevant'):
            await self.event_bus.publish(InsightDismissedEvent(
                insight_id=insight.id, insight_type=insight.insight_type,
                entities=insight.entities, feedback=feedback,
            ))

    async def batch_feedback(self, insight_ids: List[UUID], user_id: UUID, feedback: str):
        """批量反馈 (全部忽略)。"""
        for iid in insight_ids:
            await self.record_feedback(iid, user_id, feedback)

    def _transition_status(self, insight: Insight, new_status: str):
        allowed = VALID_TRANSITIONS.get(insight.status, frozenset())
        if new_status not in allowed:
            raise InvalidTransitionError(f"Insight {insight.id}: {insight.status} -> {new_status} not allowed")
        insight.status = new_status


class InsightAdoptService:
    """Adopt + trip task done。"""

    async def adopt_to_trip(self, insight_id: UUID, user_id: UUID, trip_id: UUID):
        """将洞察 adopt 到行程。多实体洞察自动拆分为独立行程任务。"""
        # 乐观锁: 状态守卫
        result = await self.db.execute(
            update(Insight)
            .where(Insight.id == insight_id, Insight.user_id == user_id,
                   Insight.status.in_(['pending', 'active', 'acknowledged']))
            .values(status='acted', feedback='useful', feedback_at=utc_now(), feedback_source='user')
            .returning(Insight.id)
        )
        if result.rowcount == 0:
            raise InsightNotActionableError(...)

        # 设置 adopted_at 时间戳
        existing = await self.db.execute(
            select(InsightEntity).where(
                InsightEntity.insight_id == insight_id,
                InsightEntity.entity_type == 'trip',
                InsightEntity.entity_id == trip_id,
            )
        )
        row = existing.scalar_one_or_none()
        if row:
            row.adopted_at = utc_now()
        else:
            self.db.add(InsightEntity(
                insight_id=insight_id, entity_type='trip', entity_id=trip_id,
                role='related', adopted_at=utc_now(),
            ))

        # 发布领域事件
        await self.event_bus.publish(InsightAdoptedEvent(
            insight_id=insight_id, trip_id=trip_id,
            entities=await self._get_entities(insight_id),
        ))

    async def mark_trip_task_done(self, insight_id: UUID, user_id: UUID, trip_id: UUID,
                                  completed_entity_ids: Optional[List[UUID]] = None):
        """行程中 adopted 洞察标记完成。
        completed_entity_ids: 指定哪些实体维度已完成。
        单实体洞察可以不传 (视为全部完成)。"""
        insight = await self._get(insight_id, user_id)
        entities = [e for e in insight.entities if e.role in ('primary', 'related')]

        # 单实体兼容: 不传参视为全部完成
        if len(entities) > 1 and not completed_entity_ids:
            raise ValueError("Multi-entity insight requires explicit completed_entity_ids")
        target_ids = completed_entity_ids or [e.entity_id for e in entities]

        # 标记 per-entity done_at
        for eid in target_ids:
            await self.db.execute(
                update(InsightEntity)
                .where(InsightEntity.insight_id == insight_id, InsightEntity.entity_id == eid)
                .values(done_at=utc_now())
            )

        # 检查是否所有实体都已完成 — 若是则整条洞察完成
        undone = await self.db.execute(
            select(func.count()).where(
                InsightEntity.insight_id == insight_id,
                InsightEntity.done_at.is_(None),
                InsightEntity.role.in_(['primary', 'related']),
            )
        )
        if undone.scalar() == 0:
            self._transition_status(insight, 'acted')

        # 发布领域事件
        await self.event_bus.publish(InsightTaskCompletedEvent(
            insight_id=insight_id, trip_id=trip_id,
            completed_entity_ids=target_ids,
        ))
```

### 2.6 领域回写 (事件驱动)

> **设计决议**: 领域回写通过事件总线解耦，而非 InsightActionService 直接调用 domain service。
> 复用现有 outbox relay (5s cycle)，保证最终一致性。

```python
class InsightDomainBridge:
    """监听洞察事件，执行领域回写。best-effort + 事件重试。"""

    async def handle_insight_adopted(self, event: InsightAdoptedEvent):
        """Adopt 时设置意图状态，不标记完成。"""
        for e in event.entities:
            if e.entity_type == 'favor' and e.role == 'source':
                await self.favor_service.mark_in_progress(e.entity_id, action_type='adopt_to_trip')
            elif e.entity_type == 'person':
                await self.temperature_service.record_interaction_intent(e.entity_id, interaction_type='insight_adopted')

    async def handle_task_completed(self, event: InsightTaskCompletedEvent):
        """行程任务完成，触发领域回写。按 completed_entity_ids 限定范围。"""
        completed_set = set(event.completed_entity_ids)
        insight = await self.db.get(Insight, event.insight_id)
        for e in insight.entities:
            if e.role == 'source' and e.entity_id in completed_set:
                if e.entity_type == 'favor':
                    await self.favor_service.mark_reciprocated(e.entity_id, action_type='task_completed')
                elif e.entity_type == 'commitment':
                    await self.commitment_service.mark_followed_up(e.entity_id)
            elif e.entity_type == 'person' and e.entity_id in completed_set:
                await self.temperature_service.record_interaction(e.entity_id, interaction_type='insight_acted')

    async def handle_insight_dismissed(self, event: InsightDismissedEvent):
        """级联 dismiss EA (best-effort)。"""
        for e in event.entities:
            if e.entity_type == 'event_association':
                await self.ea_service.dismiss(e.entity_id)
```

### 2.7 迁移策略

#### Phase 0: 准备 (1 天)

1. 新建 `insights` + `insight_entities` 表 (Alembic migration)
2. 新建 `InsightPipeline`, `InsightQueryService`, service 骨架代码
3. 新建 `Insight`, `InsightEntity` ORM models
4. 新建 feature flag: `USE_UNIFIED_INSIGHTS = false` (支持 user_id 级别细粒度)

#### Phase 1: 数据迁移 + Shadow Read (2-3 天)

> 统一为 shadow read 策略 (非双写)。
> 新管道在测试用户上启用，旧管道保持不变写旧表。
> 消费方 shadow read 对比两表结果。

1. 一次性数据迁移脚本：
   - `user_insights` WHERE status NOT IN ('dismissed', 'actioned') AND (expires_at IS NULL OR expires_at > now()) → `insights` + `insight_entities`
   - `memory_insights` WHERE status = 'pending' AND is_promoted = false → `insights` + `insight_entities`
   - `related_event_ids` (UUID ARRAY) → 展开为 `insight_entities` 多行 (过滤已删除实体)
   - `priority (1-10)` → `importance (0-100)`: `priority * 10`，NULL → 50
2. Feature flag 按 user_id 逐步开启，新 `InsightPipeline` 写入新表
3. 各消费方开启 shadow read：同时查新表和旧表，返回旧表结果，log 差异
4. 监控差异率：目标 < 5%

#### Phase 2: 切换 (1 天)

1. `USE_UNIFIED_INSIGHTS = true`
2. 消费方返回新表结果
3. 停止旧管道 (InsightOrchestrator) 写入
4. 保留旧表 7 天只读

#### Phase 3: 清理 (1 天)

1. 删除旧表: `memory_insights`, `user_insights`, `insight_feedbacks`
2. 删除 EA 上的晋升字段
3. 删除旧路径代码
4. 清理 feature flag

#### 风险控制

| 风险 | 缓解 |
|------|------|
| 数据迁移遗漏 | 迁移脚本运行 2 次（第 2 次应为 no-op），并 COUNT 对比 |
| 新管道 LLM 质量下降 | Shadow read 对比洞察内容相似度 |
| 消费方切换遗漏 | Grep `memory_insights` / `MemoryInsight` / `user_insights` / `UserInsight` |
| 性能回退 | 新表索引设计覆盖所有热路径查询；Phase 2 监控 p95 延迟 |
| 两管道并行重叠 | Feature flag 细化到 user_id 级别，非全量并行 |

---

## 3. 社交义务安全网

### 3.1 行程取消级联

行程取消时对关联洞察做三路分类，保留重要社交意图：

```python
class InsightCascadeService:
    async def cascade_from_trip_cancel(self, trip_id: UUID) -> dict:
        """两阶段处理。"""

        preserved_obligation_ids = set()  # 阶段 1 已保留的义务 ID

        # === 阶段 1: pending/active/acknowledged 洞察 — 三路分类 ===
        pending_insights = await self._get_insights_by_trip(
            trip_id, statuses=['pending', 'active', 'acknowledged'],
            for_update_skip_locked=True,  # 跳过正在被用户操作的行
        )
        for insight in pending_insights:
            classification = self._classify_on_cancel(insight)
            if classification == 'preserve_as_action':
                await self._convert_to_pending_action(insight, trip_id)
                insight.status = 'acted'
                insight.feedback_source = 'cascade_preserved'
                preserved_obligation_ids.update(self._get_obligation_ids(insight))
            elif classification == 'preserve_as_note':
                await self._convert_to_secretary_note(insight)
                insight.status = 'acted'
                insight.feedback_source = 'cascade_preserved'
            else:
                insight.status = 'dismissed'
                insight.feedback_source = 'cascade_dismiss'

        # 记录被 SKIP LOCKED 跳过的 IDs，调度复查
        skipped_ids = self._get_skipped_ids()
        if skipped_ids:
            await self._schedule_cascade_recheck(skipped_ids, trip_id, delay=timedelta(minutes=5))

        # === 阶段 2: acted+adopted 洞察 — Double Jeopardy 保护 ===
        adopted_insights = await self._get_adopted_insights_by_trip(trip_id)
        for insight in adopted_insights:
            # 循环检测: reactivation_depth >= 2 直接转 PA，不再创建新洞察
            depth = (insight.source_context or {}).get('reactivation_depth', 0)
            if depth >= 2:
                await self._convert_to_pending_action(insight, trip_id)
                continue

            # 跳过阶段 1 已保留的义务
            obligation_ids = self._get_obligation_ids(insight)
            if obligation_ids & preserved_obligation_ids:
                continue

            if await self._has_pending_obligation(insight):
                reactivated = InsightCandidate(
                    insight_type=insight.insight_type,
                    title=insight.title,
                    content=f"[行程取消后重新提醒] {insight.content}",
                    importance=insight.importance,
                    urgency=min(insight.urgency + 10, 100),
                    source='reactive',
                    entities=self._copy_source_entities(insight),
                    source_context={**(insight.source_context or {}),
                                    'reactivated_from': str(insight.id),
                                    'reactivation_depth': depth + 1,
                                    'reason': 'trip_cancel_double_jeopardy'},
                )
                # 绕过 dedup: 使用独立 dedup_key
                reactivated.dedup_key = f"{insight.dedup_key}:dj:{utc_now().isoformat()}"
                await self.pipeline._persist([reactivated])

        # 清理 adopted entity links + 级联 dismiss EA
        await self._cleanup_trip_entity_links(trip_id)
        await self._dismiss_ea_by_trip(trip_id)

    def _classify_on_cancel(self, insight: Insight) -> str:
        """三路分类规则。"""
        entities = insight.entities
        has_person = any(e.entity_type == 'person' for e in entities)
        has_date = any(e.entity_type == 'important_date' for e in entities)
        if has_date:
            return 'preserve_as_action'
        if has_person and insight.insight_type in ('relationship', 'favor', 'memory'):
            return 'preserve_as_action'
        if insight.importance >= 80:
            return 'preserve_as_action'
        if (insight.source_context or {}).get('social_intent'):
            return 'preserve_as_note'
        return 'dismiss'

    async def _has_pending_obligation(self, insight: Insight) -> bool:
        """检查底层领域义务是否仍未解决。通过 insight_entities (role='source') 查找。"""
        source_entities = [e for e in insight.entities if e.role == 'source']

        # 健康事件: 无论关系温度如何都视为有义务
        if (insight.source_context or {}).get('health_event'):
            return True

        for se in source_entities:
            if se.entity_type == 'favor':
                favor = await self.db.get(FavorRecord, se.entity_id)
                if favor and favor.status in ('pending', 'in_progress'):
                    return True
            elif se.entity_type == 'commitment':
                c = await self.db.get(CommitmentItemRecord, se.entity_id)
                if c and c.status != 'fulfilled':
                    return True

        if insight.insight_type == 'relationship':
            for pe in [e for e in insight.entities if e.entity_type == 'person']:
                temp = await self.temperature_service.get_temperature(pe.entity_id)
                if temp and temp.status == 'cold':
                    return True

        for de in [e for e in insight.entities if e.entity_type == 'important_date']:
            d = await self.db.get(ImportantDate, de.entity_id)
            if d and d.next_occurrence and d.next_occurrence >= utc_now().date():
                return True
        return False
```

### 3.2 三级 dismiss 模型 + acknowledged

| 级别 | 用户操作 | feedback | status 变化 | 抑制机制 |
|------|---------|----------|------------|---------|
| Ack | acknowledged | acknowledged | → acknowledged | `snoozed_until` = +90 天，满足义务覆盖 |
| L1 | defer | defer | 不变 (保持 pending/active) | `snoozed_until` = +3/7 天 (按类型) |
| L2 | not_useful/not_relevant/incorrect | 对应值 | → dismissed | `regen_suppressed_until` = +N 天（按类型） |
| L3 | never | never | → dismissed | `user_preference_rules` 永久抑制 |
| L2→L3 升级 | 同 dedup_key 达到类型阈值 | → never | → dismissed | 自动升级为永久抑制 |

> **UI 建议**: 前端不直接暴露 4 种反馈。默认"忽略"= defer，长按/左滑弹出 bottom sheet 展示:
> "我知道了"(acknowledged), "不感兴趣"(not_useful), "不再提醒此类"(never)。
> 第 (threshold-1) 次 dismiss 时弹出提示: "你已多次忽略此建议，是否不再提醒？"

**再生抑制窗口（按类型差异化）**:

```python
SUPPRESSION_WINDOWS = {
    'favor': timedelta(days=30),        # 社交义务: 短抑制
    'relationship': timedelta(days=30),
    'memory': timedelta(days=14),
    'time': timedelta(days=14),
    'efficiency': timedelta(days=60),   # 信息类: 长抑制
    'finance': timedelta(days=60),
    'health': timedelta(days=14),
}
```

**抑制阈值差异化** (累积 dismiss 升级):

```python
SUPPRESSION_THRESHOLDS = {
    'favor': 5, 'relationship': 5,  # 社交: 需要更多 dismiss 才触发
    'health': 4,
    'efficiency': 3, 'finance': 3, 'time': 3, 'memory': 3,
}
```

### 3.3 义务覆盖审计

**核心不变量**: 一个领域层未完成义务必须始终满足以下之一：
- (a) 存在活跃/acknowledged 洞察
- (b) 存在待办 PA
- (c) 存在永久抑制规则
- (d) 存在尚在抑制窗口内的 dismissed 洞察 (`regen_suppressed_until > now()`)
- (e) 累积 dismiss 达到类型阈值

若均不成立，则为"孤儿义务"。每次审计总上限 20 条。

```python
class InsightHygiene:
    async def obligation_coverage_audit(self):
        """确保无未完成义务缺少洞察覆盖。每次上限 20 条。"""
        uncovered: list[ObligationSignal] = []
        uncovered += await self._find_uncovered_favors()
        uncovered += await self._find_uncovered_cold_relationships()
        uncovered += await self._find_uncovered_commitments()
        for obligation in uncovered[:20]:
            await self._inject_priority_signal(obligation)

    async def _find_uncovered_favors(self) -> list[ObligationSignal]:
        """查找 FavorRecord.status='pending' 但无覆盖的人情。
        通过 insight_entities (role='source') JOIN，非 JSONB 查询。"""
        stmt = text("""
            SELECT fr.id, fr.person_id, fr.favor_type, fr.description
            FROM favor_records fr
            WHERE fr.status = 'pending'
              AND fr.family_id = :family_id
              -- (a) 无活跃/acknowledged 洞察覆盖 (通过 insight_entities source 反查)
              AND NOT EXISTS (
                  SELECT 1 FROM insight_entities ie
                  JOIN insights i ON ie.insight_id = i.id
                  WHERE ie.entity_type = 'favor' AND ie.entity_id = fr.id AND ie.role = 'source'
                    AND i.status IN ('pending', 'active', 'acknowledged')
              )
              -- (b) 无待办 PA 覆盖 (通过 source_entity_id 列查询)
              AND NOT EXISTS (
                  SELECT 1 FROM pending_actions pa
                  WHERE pa.source_entity_id = fr.id
                    AND pa.status = 'pending'
              )
              -- (c) 无永久抑制规则覆盖
              AND NOT EXISTS (
                  SELECT 1 FROM user_preference_rules upr
                  WHERE upr.entity_type = 'favor'
                    AND upr.entity_id = fr.id
                    AND upr.rule_type = 'suppress_forever'
              )
              -- (d) 无尚在抑制窗口内的 dismissed 洞察
              AND NOT EXISTS (
                  SELECT 1 FROM insight_entities ie2
                  JOIN insights i2 ON ie2.insight_id = i2.id
                  WHERE ie2.entity_type = 'favor' AND ie2.entity_id = fr.id AND ie2.role = 'source'
                    AND i2.status = 'dismissed'
                    AND i2.regen_suppressed_until IS NOT NULL
                    AND i2.regen_suppressed_until > NOW()
              )
              -- (e) 排除累积 dismiss 达到类型阈值 (favor = 5)
              AND NOT EXISTS (
                  SELECT 1 FROM insight_entities ie3
                  JOIN insights i3 ON ie3.insight_id = i3.id
                  WHERE ie3.entity_type = 'favor' AND ie3.entity_id = fr.id AND ie3.role = 'source'
                    AND i3.feedback_source = 'user'
                    AND i3.status = 'dismissed'
                  GROUP BY ie3.entity_id
                  HAVING COUNT(*) >= 5
              )
            LIMIT 20
        """)
        ...

    async def _find_uncovered_commitments(self) -> list[ObligationSignal]:
        """与 _find_uncovered_favors 同等五条件覆盖检查。"""
        # 同构查询，entity_type='commitment'，阈值=3
        ...
```

> **性能注意**: `pending_actions` 表需新增 `source_entity_id UUID` 列（可索引），替代 `payload->>'original_favor_id'` JSONB 提取。

### 3.4 重要日期过期处理

```python
class InsightHygiene:
    async def handle_past_dates(self):
        """处理重要日期已过的洞察。区分可补偿 vs 不可补偿。"""
        past_date_insights = await self._get_insights_with_past_dates()
        for insight in past_date_insights:
            date_entity = self._get_primary_date_entity(insight)
            if not date_entity:
                continue
            imp_date = await self.db.get(ImportantDate, date_entity.entity_id)
            if not imp_date or not imp_date.next_occurrence:
                continue
            days_past = (utc_now().date() - imp_date.next_occurrence).days
            if days_past <= 0:
                continue  # 未过期

            has_social_obligation = insight.insight_type in ('favor', 'relationship', 'memory')

            if days_past <= 7 and has_social_obligation:
                # 7天内的社交义务: 降级但保留，修改标题提醒已过期
                insight.title = f"[已过期] {insight.title}"
                insight.urgency = max(insight.urgency - 20, 30)
                insight.content = f"原定日期已过{days_past}天，但仍可补上。{insight.content}"
            else:
                # 超过 7 天或非社交义务: dismiss
                insight.status = 'dismissed'
                insight.feedback_source = 'hygiene_date_past'

    async def dismiss_past_event_insights(self):
        """Dismiss insights whose related curated events have passed.
        排除已 adopted 到未来行程的洞察。"""
        adopted_ids_subq = select(InsightEntity.insight_id).where(InsightEntity.adopted_at.isnot(None))
        await self.db.execute(
            update(Insight).where(
                Insight.id.in_(
                    select(InsightEntity.insight_id).join(CuratedEvent, and_(
                        InsightEntity.entity_type == 'event',
                        InsightEntity.entity_id == CuratedEvent.id,
                    )).where(CuratedEvent.normalized_start < utc_now())
                ),
                Insight.status.in_(['pending', 'active']),
                ~Insight.id.in_(adopted_ids_subq),
            ).values(status='dismissed', feedback_source='hygiene_event_past')
        )

    async def check_acknowledged_expiry(self):
        """检查 acknowledged 洞察是否满 90 天，或底层义务上下文变化。"""
        acknowledged = await self.db.execute(
            select(Insight).where(
                Insight.status == 'acknowledged',
                or_(
                    Insight.snoozed_until <= utc_now(),  # 90 天到期
                )
            )
        )
        for insight in acknowledged.scalars():
            # 回到 active，让用户重新注意
            insight.status = 'active'
            insight.snoozed_until = None

    async def check_trip_completed_adopted(self):
        """行程正常结束后检查未完成的 adopted 洞察。
        Phase 1 简化版: 解除 adopted 状态，让义务覆盖审计接管。"""
        # 找到 completed 行程的已 adopted 但未 done 的洞察实体
        stmt = (
            select(InsightEntity)
            .join(TripPlan, and_(
                InsightEntity.entity_type == 'trip',
                InsightEntity.entity_id == TripPlan.id,
            ))
            .where(
                TripPlan.status == 'completed',
                InsightEntity.adopted_at.isnot(None),
                InsightEntity.done_at.is_(None),
            )
        )
        for ie in (await self.db.execute(stmt)).scalars():
            ie.adopted_at = None  # 解除 adopted，义务覆盖审计会接管

    ENTITY_TABLE_MAP = {'person': FamilyMember, 'trip': TripPlan, 'event': CuratedEvent, 'important_date': ImportantDate}

    async def dismiss_orphaned_entities(self):
        """Dismiss insights whose primary entities no longer exist. 使用 NOT EXISTS 替代 NOT IN。"""
        for entity_type, table in self.ENTITY_TABLE_MAP.items():
            await self.db.execute(
                update(Insight).where(
                    Insight.id.in_(
                        select(InsightEntity.insight_id).where(
                            InsightEntity.entity_type == entity_type,
                            InsightEntity.role == 'primary',
                            ~exists(select(table.id).where(table.id == InsightEntity.entity_id)),
                        )
                    ),
                    Insight.status.in_(['pending', 'active']),
                ).values(status='dismissed', feedback_source='hygiene_entity_deleted')
            )

    async def archive_old(self):
        """90 天归档: dismissed/expired 行清理，累积 dismiss 计数已缓存到 preference_signals。"""
        cutoff = utc_now() - timedelta(days=90)
        await self.db.execute(
            delete(Insight).where(
                Insight.status.in_(['dismissed', 'expired']),
                Insight.created_at < cutoff,
            )
        )
```

### 3.5 PendingAction 适配

社交义务类 PA 永不过期。`pending_actions` 表需新增 `source_entity_id` 列:

```python
async def _convert_to_pending_action(self, insight: Insight, trip_id: UUID):
    SOCIAL_OBLIGATION_TYPES = {'favor', 'relationship'}
    expires_at = (
        None if insight.insight_type in SOCIAL_OBLIGATION_TYPES
        else utc_now() + timedelta(days=14)
    )
    source_entity = next((e for e in insight.entities if e.role == 'source'), None)
    pa = PendingAction(
        user_id=insight.user_id, family_id=insight.family_id,
        action_type=self._map_action_type(insight),
        source_entity_id=source_entity.entity_id if source_entity else None,
        payload={'original_insight_id': str(insight.id), 'original_trip_id': str(trip_id)},
        expires_at=expires_at,
    )
```

兜底: `InsightHygiene.recheck_expired_cascade_actions()` 检查 PA 过期后底层义务是否仍在，若在则清除 `regen_suppressed_until`。

### 3.6 健康/情感洞察保护

- **子类型细化**: `health:overwork`, `health:sleep`, `health:exercise`, `health:meal`, `health:stress`, `health:general`
- **白名单扩展**: 高 urgency (>=70) 健康洞察不可抑制
- **差异化阈值**: 社交义务需 5 次 dismiss 才触发抑制，健康需 4 次，信息类 3 次
- **生命事件穿透**: 穿透条件使用 OR 逻辑，更安全:

```python
def _should_pierce_suppression(self, candidate: InsightCandidate) -> bool:
    """即使该人物/类型被永久抑制，以下情况仍可生成洞察。"""
    return (
        candidate.urgency >= 80
        or candidate.insight_type == 'health'
        or (candidate.source_context or {}).get('health_event')
    )
```

### 3.7 类型化 TTL

```python
TYPE_TTL_OVERRIDES = {
    'favor': None,            # 永不自动过期 — 只通过 dismiss/act/writeback 退出
    'relationship': timedelta(days=60),
    'memory': timedelta(days=30),
    'time': None,             # 由事件日期驱动
    'efficiency': timedelta(days=7),
    'finance': timedelta(days=14),
    'health': timedelta(days=3),
}
```

### 3.8 并发安全

- **用户操作**: 乐观锁 `WHERE status IN ('pending', 'active')` + `.returning(Insight.id)` 检查 rowcount
- **级联操作**: `FOR UPDATE SKIP LOCKED` 跳过正在被用户操作的行
  - 记录 skipped IDs，调度 5 分钟延迟 Celery 任务 `cascade_recheck_skipped` 复查
- **delivery 标记**: `UPDATE SET delivered_via_kanban = true WHERE id = ? AND NOT delivered_via_kanban` 幂等
- **dedup 持久化**: `INSERT ON CONFLICT DO NOTHING` 防止 TOCTOU 竞态
  - `_persist()` 返回实际插入的 ID 列表，而非传入的候选列表
- **snooze vs 过期**: defer 时如 `expires_at < snoozed_until`，延长 `expires_at`

### 3.9 上下文再激活

```python
class InsightPipeline:
    async def _contextual_reactivation(self, user_id: UUID, current_signals: AllSignals) -> List[InsightCandidate]:
        """在 Scheduled 批量路径中检查被 dismiss 的未了结义务。
        纯规则匹配，不调用 LLM。"""
        dismissed_obligations = await self.db.execute(
            select(Insight).where(
                Insight.user_id == user_id,
                Insight.status == 'dismissed',
                Insight.insight_type.in_(['favor', 'relationship', 'memory']),
                or_(Insight.regen_suppressed_until.is_(None),
                    Insight.regen_suppressed_until <= utc_now()),
                Insight.created_at >= utc_now() - timedelta(days=30),
            ).limit(20)
        )
        dismissed_list = dismissed_obligations.scalars().all()

        # 批量预加载: 一次查询所有相关领域实体
        source_entities_map = await self._batch_load_source_entities(dismissed_list)
        person_temps = await self._batch_load_temperatures(dismissed_list)

        candidates = []
        for old in dismissed_list:
            if not self._is_obligation_still_pending(old, source_entities_map, person_temps):
                continue
            # 纯规则匹配: 共享实体 ID 数量 / 总实体数量 > 0.6
            relevance = self._check_context_relevance_rule_based(old, current_signals)
            if relevance > 0.6:
                candidates.append(InsightCandidate(
                    insight_type=old.insight_type,
                    title=old.title,
                    content=old.content,
                    importance=old.importance,
                    urgency=min(old.urgency + 10, 100),
                    source='scheduled',
                    entities=self._copy_source_entities(old),
                    source_context={**(old.source_context or {}),
                                    'reactivated_from': str(old.id)},
                ))
        return candidates

    def _check_context_relevance_rule_based(self, old: Insight, signals: AllSignals) -> float:
        """纯规则匹配: 共享实体 ID 集合的 Jaccard 系数。"""
        old_entity_ids = {e.entity_id for e in old.entities if e.role in ('primary', 'related')}
        signal_entity_ids = signals.get_all_entity_ids()
        if not old_entity_ids:
            return 0.0
        intersection = old_entity_ids & signal_entity_ids
        union = old_entity_ids | signal_entity_ids
        return len(intersection) / len(union) if union else 0.0
```

---

## 4. 受影响的代码路径

### 4.1 需要修改的文件

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `backend/src/modules/insight/models.py` | 新增 | Insight + InsightEntity ORM models |
| `backend/src/modules/insight/insight_pipeline.py` | 新增 | 统一生成管道 + 信号压缩 + 偏好过滤 + 白名单 + 再激活 + dedup_key 计算 |
| `backend/src/modules/insight/insight_query_service.py` | 新增 | 统一查询服务 |
| `backend/src/modules/insight/insight_feedback_service.py` | 新增 | 反馈 + 状态转换 + 累积升级 |
| `backend/src/modules/insight/insight_adopt_service.py` | 新增 | adopt + trip task done |
| `backend/src/modules/insight/insight_cascade_service.py` | 新增 | 行程取消级联 + DJ 循环检测 |
| `backend/src/modules/insight/insight_domain_bridge.py` | 新增 | 领域回写 (事件驱动) |
| `backend/src/modules/insight/insight_hygiene.py` | 新增 | 过期/过时/孤儿/日期过期/归档/acknowledged 到期 |
| `backend/src/modules/views/services/kanban_service.py` | 重写查询 | MemoryInsight → Insight |
| `backend/src/modules/views/services/timeline_service.py` | 重写查询 | UserInsight → Insight |
| `backend/src/modules/briefing/services/insight_service.py` | 重写查询 | UserInsight → Insight |
| `backend/src/modules/briefing/services/insight_orchestrator.py` | 重写 | 调用 InsightPipeline |
| `backend/src/ai_engine/workers/sidekick_worker.py` | 改查询 | UserInsight → Insight |
| `backend/src/modules/curation/services/trigger_dispatcher.py` | 修改 | 调用 InsightPipeline.run_reactive() |
| `backend/src/modules/curation/models.py` | 删字段 | EA 去掉 promoted_at 等 |
| `backend/src/modules/relationship/favor_service.py` | 修改 | 新增 mark_reciprocated() + mark_in_progress() |
| `backend/src/modules/relationship/thermometer.py` | 修改 | 新增 record_interaction() + record_interaction_intent() |
| `backend/src/modules/memory/commitment_service.py` | 修改 | 新增 mark_followed_up() |
| `backend/src/modules/conversation/pending_action.py` | 修改 | 新增 source_entity_id 列 |
| `preference_extraction_service.py` | 修改 | 只计算 `feedback_source='user'` 的信号 |

### 4.2 可以删除的文件/代码

| 文件/代码 | 原因 |
|---------|------|
| `insight_service.py` (旧) | 合入 InsightPipeline |
| `proactive_insight_service.py` | 合入 InsightPipeline |
| `consolidation_service.py` | 合入 InsightPipeline._dedup() |
| `feedback_service.py` | 合入 InsightFeedbackService |
| `dismiss_cascade_service.py` | 合入 InsightCascadeService |
| `briefing/models.py InsightFeedback` 枚举 | 统一为 FeedbackType |
| `InsightDeliveryLedger` 表 | 替代为 delivered_via_* 列 |
| `InsightOrchestrator._consolidate_user_insights()` | 单次 LLM 不产出重复 |
| `KanbanService._deduplicate_memory_insights()` | 生成时已去重 |
| `InsightOrchestrator._sweep_orphan_memory_insights()` | 统一表无需晋升 |
| EA 上的 `promoted_at`, `promoted_insight_id`, `dismiss_cascaded_at` | insight_entities 替代 |

### 4.3 API 端点变更

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/insights/{id}/adopt` | POST | 洞察 adopt 到行程 |
| `/api/v1/insights/{id}/trip-task-done` | POST | 行程任务完成 |
| `/api/v1/insights/{id}/feedback` | POST | 统一反馈 (支持 acknowledged/defer/not_useful/never) |
| `/api/v1/insights/{id}/action` | POST | 执行 action chip |
| `/api/v1/insights/{id}/entities/{entity_id}/done` | POST | 多实体洞察 per-entity 完成标记 |
| `/api/v1/insights/batch-feedback` | POST | 批量反馈 (全部忽略) |

> **过渡期**: 保留旧端点 `/kanban/future-view/accept-suggestion` 作为 302 转发，避免强制升级移动端。

---

## 5. Open Questions

1. **义务覆盖审计的性能**: `_find_uncovered_favors()` 使用 `insight_entities` JOIN 替代 JSONB 查询已优化，但大家庭场景下 (20+ favor records + 5 个 NOT EXISTS) 仍需针对性索引。需在 staging 环境做 EXPLAIN ANALYZE。

2. **手动任务的 dedup**: 用户手动创建 "带护照" 后 trip_completeness 也生成 "记得带护照"。建议 trip_completeness 产出时检查已有 `source='manual'` 的同行程洞察做文本相似度匹配。

3. **评分动态衰减 (Phase 2)**: `score_expires_at` 列延后到 Phase 2 实际实现时再加入 DDL。遵循 YAGNI。

4. **情绪/健康升级路径 (Phase 2)**: severity 对比 + 绕过 dismiss。需要独立信号基础设施。

5. **高风险行动跟进确认 (Phase 2)**: 3 天延迟 Celery 任务确认是否完成。Phase 1 通过 `check_trip_completed_adopted` 简化版兜底。

6. **级联审计日志 (Phase 2)**: 复用 preference_signals 记录级联事件。

---

## 6. Round 14 评审记录

> **日期**: 2026-03-10
> **团队**: 架构挑战者、后端工程师、产品工程师、领域专家

### 6.1 已整合的修订 (全部已在上文 SSOT 中直接生效)

| ID | 严重度 | 修订内容 |
|----|--------|---------|
| R14-C1 | CRITICAL | 消除 4 个稀疏 FK 列 (`source_favor_id` 等)，统一到 `insight_entities` (role='source') |
| R14-C2 | HIGH | 新增 `acknowledged` 状态 — 满足义务覆盖但不再提醒 90 天 |
| R14-C3 | HIGH | 义务覆盖审计增加 `regen_suppressed_until` 条件，防 premature reactivation |
| R14-C4 | HIGH | Double Jeopardy 循环检测: `reactivation_depth >= 2` 直接转 PA |
| R14-C5 | HIGH | 新增 `handle_past_dates()` 处理重要日期过期，区分可补偿/不可补偿 |
| R14-C6 | HIGH | 领域回写改为事件驱动 (InsightDomainBridge)，消除隐式分布式事务 |
| R14-C7 | HIGH | InsightActionService 拆分为 4 个 service (Feedback/Adopt/Cascade/DomainBridge) |
| R14-C8 | HIGH | `dedup_key` 编码义务身份 (`favor:{id}`)，管道侧计算而非 LLM 生成 |
| R14-C9 | HIGH | `delivery_channels` array 改为 4 个 boolean 列 |
| R14-C10 | HIGH | `pending_actions` 新增 `source_entity_id` 列，替代 JSONB 文本提取 |
| R14-M1 | MEDIUM | `_check_context_relevance()` 明确为纯规则匹配 (Jaccard 系数) |
| R14-M2 | MEDIUM | 90 天归档策略 (archive_old) |
| R14-M3 | MEDIUM | Phase 2 预适配列 (`score_expires_at`) 延后，遵循 YAGNI |
| R14-M4 | MEDIUM | 索引从 9 个合并为 6 个 |
| R14-M5 | MEDIUM | `_has_pending_obligation()` 增加 health_event 检查 |
| R14-M6 | MEDIUM | 生命事件穿透条件改为 OR 逻辑 |
| R14-M7 | MEDIUM | 审计 dismiss 阈值使用 `SUPPRESSION_THRESHOLDS` 常量，不硬编码 |
| R14-M8 | MEDIUM | `cascade_from_trip_cancel` 阶段 1/2 去重 (preserved_obligation_ids) |
| R14-M9 | MEDIUM | 新增 `check_trip_completed_adopted()` Phase 1 简化版半完成检测 |
| R14-M10 | MEDIUM | Feature flag 细化到 user_id 级别 |
| R14-M11 | MEDIUM | `insight_entities` 增加 CHECK 约束 |
| R14-M12 | MEDIUM | `_persist()` 返回实际插入 ID 列表 |
| R14-M13 | MEDIUM | `dismiss_orphaned_entities()` 改用 NOT EXISTS 替代 NOT IN |

### 6.2 产品建议 (实现时参考)

| 建议 | 说明 |
|------|------|
| 反馈渐进式披露 | 默认"忽略"=defer，长按弹出 bottom sheet 展示更多选项 |
| 合并 not_now/defer | 后端根据洞察类型自动选择 snooze 时长 |
| 累积升级提示 | 第 (threshold-1) 次 dismiss 时弹出确认 |
| 多实体 adopt 自动拆分 | adopt 时自动创建独立行程任务，前端无需理解"实体" |
| 多渠道标注 | kanban 中标注"已在简报中提醒" |
| 批量反馈端点 | `POST /insights/batch-feedback` |
| API 过渡期 | 保留旧端点 302 转发 |

### 6.3 架构挑战者未采纳的建议 (及理由)

| 建议 | 未采纳理由 |
|------|-----------|
| 表垂直拆分 (insights + insight_interactions) | Kanban 热路径已无 JOIN，拆分增加所有写操作的复杂度，收益 < 成本 |
| 状态枚举扩展 (dismissed_by_user 等) | acknowledged 已解决核心需求，更细粒度通过 feedback_source 区分足够 |
| 两阶段 LLM (per-domain → synthesis) | 增加系统复杂度和延迟，Haiku 4.5 对当前信号量足够，后续可作为 Phase 2 优化 |
| 义务覆盖审计分离为独立系统 | 审计逻辑与洞察生命周期紧耦合 (regen_suppressed_until, dismissed count)，分离反增复杂度 |
