# AI 秘书：可信参谋大脑架构方案 (V8.0)

> 综合秘书实务专家、移动端 UX 专家、AI 上下文工程专家三方评审 + 逻辑风险审查，在 V6.0/V7.0 基础上全面升级。
> V8.1 补丁：修复 4 个核心逻辑风险 + 3 个工程易错点（2026-02-18）。

---

## 一、系统定位升级：从"信息管理系统"到"会做事的秘书"

### 1.1 核心理念

V6/V7 是一个优秀的"信息整理→结构化存储→触发提醒"系统，但距离真正的秘书还有三个关键差距：

| 差距维度 | V6/V7 现状 | V8.0 目标 |
|----------|-----------|-----------|
| **主动性** | 数据变化驱动（脏位触发） | 时间节律 + 情境感知 + 承诺追踪三驱动 |
| **社交判断力** | 排除/冷却二元逻辑 | 社交意图识别 + 关系温度计 + 委婉策略 |
| **承诺闭合** | 无追踪机制 | 全生命周期承诺管理 + 模糊承诺跟进 |

### 1.2 秘书人格谱系（Progressive Persona）

系统不是从第一天就表现得像一个"全知管家"，而是随信任等级成长：

| 信任等级 | 条件 | 秘书行为模式 |
|---------|------|-------------|
| L0 新手 | 注册 < 7 天 | 谨慎的新秘书：多请示、少自作主张、推荐附带"我还在了解您" |
| L1 熟悉 | 7-30 天，确认率 > 80% | 上手的秘书：低风险可撤回操作自动执行，汇报即可 |
| L2 信任 | 30-90 天，低 dismiss 率 | 得力的秘书：中风险操作自动执行，仅敏感操作确认 |
| L3 默契 | > 90 天，L1 笔记本丰富 | 老秘书：大部分操作自动执行，仅支付/社交类确认 |

> **降级机制**：同一类别连续 3 次被纠正/dismiss，该类别自动降回上一等级。
>
> **反思日志 (Reflection Log)**：降级不仅是惩罚机制，更是学习机会。当触发降级时，系统生成一条反思记录写入 L1：

```python
class ReflectionLog:
    """信任降级时的自动反思机制。"""

    async def on_trust_downgrade(self, user_id: UUID, category: str,
                                  dismiss_history: List[DismissRecord]):
        # 分析被拒原因模式
        pattern = self._analyze_dismiss_pattern(dismiss_history)

        reflection = ReflectionEntry(
            user_id=user_id,
            category=category,
            pattern=pattern,  # e.g. "time_mismatch" / "preference_outdated" / "over_proactive"
            hypothesis=self._generate_hypothesis(pattern),
            # e.g. "用户近期偏好可能已变化，或该类别建议过于频繁"
            corrective_action=self._suggest_correction(pattern),
            # e.g. "降低该类别推送频率" / "标记相关 L1 事实为待验证"
        )

        # 写入 L1 作为系统学习记录
        await self.note_service.create_system_note(
            user_id=user_id,
            category="system_reflection",
            content=reflection.to_note_content(),
            life_type=NoteLifeType.TRANSIENT,  # 反思记录有时效性
            valid_until=utc_now() + timedelta(days=30),
        )
```

---

## 二、五层分级记忆模型 (L0-L4)

> V8.0 改进：在 V6.0 四层基础上新增 **L0 关系记忆层**，并强化各层的工程实现。

```
┌──────────────────────────────────────────────────────────────┐
│                        记忆架构全景                            │
│                                                              │
│  L0  关系图谱 (Relationship Graph)     ← 新增：以人为核心     │
│      PersonNode + RelationEdge + EmotionalMemory              │
│                                                              │
│  L1  笔记本 (Fact Store)               ← 强化：版本链+防幻觉  │
│      SecretaryNote + Provenance + FactVerificationGate        │
│                                                              │
│  L2  活跃窗口 (Active Window)          ← 改进：动态窗口       │
│      最近 10-25 轮对话 + SessionSummary 压缩兜底               │
│                                                              │
│  L3  摘要缓存 (Digest)                 ← 保持：加自信度字段   │
│      3-7 天对话摘要 + 摘要自信度评分                           │
│                                                              │
│  L4  深层档案 (Archive)                ← 强化：pgvector+HNSW  │
│      全量冷数据向量检索 + 轻量 GraphRAG 关联遍历               │
└──────────────────────────────────────────────────────────────┘
```

### 2.1 L0 关系记忆层（新增）

**设计动机**：真实秘书的记忆不是按时间分层的，而是以"人"为核心节点向外辐射。听到"张总"两个字时，秘书脑中瞬间激活的是一个关联网络：上次见面气氛、他秘书的联系方式、他老婆的喜好、他和王总的竞争关系、未闭合的承诺。

```
"张总"
  → 最近情绪标记：上次会面气氛不太好 (emotional_tone: tense)
  → 沟通通道：他秘书小李比较好说话 (contact_channel)
  → 送礼线索：老婆喜欢法国红酒 (gift_hint)
  → 禁忌规则：和王总有竞争关系，座位不能挨着 (constraint)
  → 未闭合承诺：上次答应给他介绍的设计师还没联系 (open_commitment)
  → 当前状态：最近在减肥 (current_state)
  → 关系温度：温 (60/100)，呈下降趋势 (relationship_temp)
```

**数据模型**：

```python
class PersonMemoryNode:
    """以人为核心的记忆节点 — 挂载在 person_profiles 上。"""
    person_id: UUID

    # 动态属性（非 L1 静态事实，而是推断性信号）
    emotional_history: List[EmotionalMark]       # 互动情绪记录
    communication_channels: List[ContactChannel]  # 最佳联络通道
    open_commitments: List[CommitmentItem]        # 未闭合承诺
    current_state_signals: List[StateSignal]      # 当前状态推断
    social_constraints: List[SocialConstraint]    # 社交禁忌

    # 关系温度计
    relationship_temperature: float  # 0-100
    temperature_trend: str           # rising / stable / declining
    last_interaction_quality: str    # positive / neutral / negative / tense
    next_interaction_suggestion: Optional[str]  # "建议 2 周内找理由联络"

class EmotionalMark:
    """互动情绪标记。"""
    event_date: datetime
    tone: str              # positive / neutral / negative / tense
    context_summary: str   # "商务晚宴，讨论合作方案时气氛紧张"
    confidence: float
```

**召回策略**：实体 ID 精确匹配 + 1-2 hop 关系遍历。当 ContextAssembler 扫描到"张总"时：
1. 直接加载张总的 PersonMemoryNode
2. 遍历张总关联的人物（如他的秘书、他的竞争对手）
3. 不按时间老化，而是按关系活跃度动态更新

### 2.2 L1 笔记本强化：版本链 + 防幻觉

**问题**：V6.0 的语义 UPSERT 存在两个缺陷：(1) LLM 可能从模糊上下文"推断"错误事实写入 L1；(2) 事实冲突时直接覆盖，丢失历史。

**改进 A：Fact Provenance Chain（事实溯源链）**

```python
class NoteLifeType(Enum):
    """事实时效类型 — 区分永久偏好与阶段性状态。"""
    PERMANENT = "permanent"    # 长期偏好：过敏、基础规则、口味
    TRANSIENT = "transient"    # 短期状态：最近在减肥、本周出差中、项目忙不约饭

class SecretaryNote:
    # 新增字段
    provenance: List[dict]        # [{source: "conversation", memory_id: "...", confidence: 0.8}]
    version: int                  # 版本号
    superseded_by: Optional[UUID] # 被哪条新事实取代
    contradiction_flags: List[dict]  # 被标记的矛盾记录
    life_type: NoteLifeType       # 事实时效类型（默认 PERMANENT）
    valid_until: Optional[datetime]  # TRANSIENT 类型的过期时间
```

**TRANSIENT 事实的生命周期管理**：

```python
class TransientFactManager:
    """管理阶段性事实的过期与降级。"""

    async def process_expiring_facts(self, user_id: UUID):
        """定时任务：检查并处理过期的 TRANSIENT 事实。"""
        expired = await self.note_repo.get_expired_transient_notes(user_id)
        for note in expired:
            # 不直接删除，而是降级到 L4 归档
            await self.archive_service.archive_transient_note(note)
            note.status = "archived"
            note.archived_at = utc_now()
            # 恢复被 TRANSIENT 覆盖的 PERMANENT 事实（如有）
            await self._restore_superseded_permanent(note)

    async def _restore_superseded_permanent(self, transient_note):
        """当 TRANSIENT 过期时，检查是否有被其覆盖的 PERMANENT 事实需要恢复。"""
        superseded = await self.note_repo.find_superseded_by(transient_note.id)
        for note in superseded:
            if note.life_type == NoteLifeType.PERMANENT:
                note.status = "active"
                note.superseded_by = None
```

> **设计要点**：当用户说"最近在减肥"时，系统创建 TRANSIENT 事实（默认 valid_until = 30 天后），而不是覆盖"喜欢日料"这一 PERMANENT 偏好。TRANSIENT 过期后，PERMANENT 偏好自动恢复。

当新事实与旧事实冲突时（如"喜欢香格里拉" vs "上次住香格里拉体验不好"）：
1. 比较两条事实的 provenance（来源数量、用户确认次数）
2. 高 provenance 的事实成为主版本
3. 低 provenance 的标记为 superseded，但保留（用户可在"秘书笔记"中回溯）

**改进 B：FactVerificationGate（事实验证门）**

```python
class FactVerificationGate:
    """在 LEARN_FACT 写入 L1 前做后验检查。"""

    async def verify(self, fact: dict, source_memories: list) -> FactDecision:
        # 规则1: 至少 2 条独立来源支撑
        if len(source_memories) < 2:
            return FactDecision(action="QUEUE_FOR_CONFIRMATION")

        # 规则2: 不能与已确认事实矛盾（矛盾时需要用户裁决）
        conflicts = await self._check_conflicts(fact)
        if conflicts:
            return FactDecision(action="USER_ARBITRATION", conflicts=conflicts)

        # 规则3: 高风险类别（健康/过敏/支付）需要用户确认
        if fact["category"] in ("health", "allergy", "payment"):
            return FactDecision(action="REQUIRE_CONFIRMATION")

        return FactDecision(action="AUTO_WRITE")
```

### 2.3 L2 活跃窗口：动态大小

```python
def compute_window_size(intent_classification, active_tool_count):
    """根据对话复杂度动态调整窗口。"""
    base = 10
    if intent_classification.action in (ActionType.PLAN, ActionType.ANALYZE):
        base = 20  # 复杂任务保留更多上下文
    if active_tool_count > 3:
        base = min(base + 5, 25)
    return base
```

### 2.4 L4 深层档案：pgvector + 轻量 GraphRAG

**迁移到 pgvector 原生类型 + HNSW 索引**：

```sql
ALTER TABLE conversation_memories
    ADD COLUMN embedding_vec vector(1536);

CREATE INDEX ix_conv_memories_embedding_hnsw
    ON conversation_memories
    USING hnsw (embedding_vec vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);
```

**轻量 GraphRAG**：利用现有 `MemoryAssociation` 做 N-hop 关系遍历，不引入新图数据库。

```python
class LightweightGraphRAG:
    """基于现有关联表的图检索。"""

    async def traverse_context(self, seed_entity_ids: List[UUID], depth: int = 2):
        visited = set()
        frontier = set(seed_entity_ids)
        context_nodes = []
        for _ in range(depth):
            associations = await self._get_associations(frontier)
            next_frontier = set()
            for assoc in associations:
                neighbor = assoc.memory_id_b if assoc.memory_id_a in frontier else assoc.memory_id_a
                if neighbor not in visited:
                    next_frontier.add(neighbor)
                    context_nodes.append(assoc)
            visited.update(frontier)
            frontier = next_frontier
        return context_nodes
```

---

## 三、ContextAssembler 2.0（上下文组装引擎）

> V8.0 改进：统一组装入口 + Token 预算管理 + 缓存比对。

### 3.1 组装流水线（7 步）

```
用户消息
    ↓
Step 1: 全息扫描 + 实体链接 (Holographic Scan + Entity Linking)
    提取 {人, 地, 意图, 时间} 并集
    + 指代消解 (Co-reference Resolution): "他"→张总, "那个人"→王明
    + 别名归一 (Alias Normalization): "张总"/"老张"/"张明" → person_id:xxx
    输出: 经过 Entity Linking 后的 Target_ID 列表（非原始字符串）
    ↓
Step 2: 信息分级 (Information Triage)  ← 新增
    判断此次交互的紧急度和信息推送等级
    ↓
Step 3: L0 关系图遍历 (Graph Traverse)  ← 新增
    以扫描出的人物为种子，1-2 hop 遍历关系记忆
    ↓
Step 4: 隐私权限核对 (Privacy Check)
    分级隐私过滤（公开/限定/私密/儿童）
    ↓
Step 5: L4 闪回 (Flashback)
    当前意图向量化，检索历史偏好 + GraphRAG 关联
    ↓
Step 6: L1 事实剪枝 (Category Pruning)
    只加载与当前任务相关分类的事实，节省 Token
    ↓
Step 7: 仲裁拦截与复活 (Arbitration)
    ExclusionLedger 查询 + L2 显式点名覆盖
```

### 3.2 L3 摘要防重叠：时间戳守卫 (Timestamp Guard)

**问题**：L3 的周期性摘要（Daily/Weekly Summary）按会话压缩，可能包含 L2 活跃窗口已覆盖的时间段。如果 L2 有 10:00-14:00 的对话原文，而 L3 有一条"今天全天"的摘要，10:00-14:00 的信息会在 Prompt 中以"原文 + 摘要"形式重复出现，浪费 Token 且可能导致 LLM 困惑。

**解决方案**：

```python
class TimestampGuard:
    """L3 摘要加载时的时间防重叠过滤。"""

    async def filter_l3_digests(self, digests: List[MemorySummary],
                                 l2_window: ActiveWindow) -> List[AnnotatedDigest]:
        l2_min_time = l2_window.earliest_timestamp
        l2_max_time = l2_window.latest_timestamp
        result = []

        for digest in digests:
            if digest.time_range_end <= l2_min_time:
                # 完全在 L2 之前 → 安全加载
                result.append(AnnotatedDigest(digest=digest, annotation=None))
            elif digest.time_range_start >= l2_max_time:
                # 完全在 L2 之后 → 安全加载（理论上不常见）
                result.append(AnnotatedDigest(digest=digest, annotation=None))
            else:
                # 与 L2 有时间重叠 → 加载但附带守卫指令
                result.append(AnnotatedDigest(
                    digest=digest,
                    annotation=f"[注意: 以下摘要覆盖 {digest.time_range_start}~{digest.time_range_end}，"
                               f"其中 {l2_min_time}~{l2_max_time} 已有原文在 L2 中，以 L2 原文为准]"
                ))

        return result
```

**组装 Prompt 时的守卫指令**：当 L3 摘要与 L2 有时间重叠时，在 Prompt 中显式标注："以下 L3 摘要包含部分 L2 已涵盖的内容，若有出入，以 L2 对话原文为准。"

### 3.3 Token 预算管理器

```python
class TokenBudget:
    """实时 Token 计数和分配管理。"""

    TOTAL = 5000
    ALLOCATION = {
        "system_identity": 200,     # 固定开销
        "relationship_graph": 500,  # L0 关系图
        "family_context": 300,      # 家庭成员
        "active_window": 1200,      # L2 对话历史
        "facts": 800,               # L1 事实
        "digests": 500,             # L3 摘要
        "flashback": 800,           # L4 向量召回
        "data_summary": 200,        # 数据概况
        "buffer": 500,              # 安全缓冲
    }

    # 任务优先级权重：根据意图动态调整分配
    TASK_OVERRIDES = {
        ActionType.ANALYZE: {  # 深度分析 → 压缩 L2，扩展 L4
            "active_window": 800,
            "flashback": 1500,
            "digests": 800,
        },
        ActionType.PLAN: {  # 规划任务 → 压缩 L3，扩展 L2+L4
            "active_window": 1500,
            "digests": 300,
            "flashback": 1200,
        },
        ActionType.LOOKUP: {  # 简单查询 → 最小上下文
            "active_window": 800,
            "flashback": 400,
            "digests": 300,
        },
    }

    def adjust_for_task(self, action_type: ActionType):
        """根据任务类型动态调整 Token 分配，避免预算死锁。"""
        overrides = self.TASK_OVERRIDES.get(action_type, {})
        for layer, budget in overrides.items():
            self.allocation[layer] = budget

    def try_add(self, layer: str, text: str) -> Optional[str]:
        tokens = self._count_tokens(text)
        remaining = self.allocation[layer] - self.used[layer]
        if tokens <= remaining:
            self.used[layer] += tokens
            return text
        return self._truncate_to_budget(text, remaining)
```

> **设计要点**：当用户请求"查一下 3 年前张总的合同细节"（ANALYZE 类型）时，系统自动压缩 L2（对话历史对此类任务价值低），将省出的 Token 分给 L4（档案检索），避免"预算死锁"。

### 3.3 Context_Hash 缓存

```python
class ContextHashCache:
    """基于上下文指纹的缓存，避免重复 LLM 编排。"""

    async def compute_hash(self, request: AssemblyRequest) -> str:
        components = [
            str(request.family_id),
            str(sorted(request.scan.persons)),
            str(sorted(request.scan.locations)),
            str(request.scan.intent),
            str(await self._get_facts_version(request.user_id)),
            str(await self._get_exclusion_version(request.family_id)),
        ]
        return hashlib.sha256("|".join(components).encode()).hexdigest()

    async def get_or_assemble(self, request, assembler) -> AssembledContext:
        ctx_hash = await self.compute_hash(request)
        cached = await redis_client.get(f"ctx_cache:{ctx_hash}")
        if cached:
            return AssembledContext.from_cache(cached)
        result = await assembler.assemble(request)
        await redis_client.set(f"ctx_cache:{ctx_hash}", result.to_cache(), ttl=300)
        return result
```

---

## 四、四级触发策略 (T0-T3)

> V8.0 改进：新增 T0 情境触发 + ImpactArbitrator 规则引擎 + DirtyBitManager 累积队列。

### 4.1 触发等级定义

| 等级 | 名称 | 触发条件 | 资源消耗 | 处理逻辑 |
|------|------|---------|---------|---------|
| **T0** | 情境主动触发 | 时间节律 / 位置变化 / 情绪推断 / 承诺到期 | 极低 | 不调 LLM，基于规则和 L1 事实主动推送 |
| **T1** | 即时补全 | 用户说话/同步数据 | 极低 | Heuristic 字段填充，不调 LLM |
| **T2** | 增量更新 | 脏位涉及 48 小时内 | 中 | Fast Model 局部编排 |
| **T3** | 全局统筹 | 脏位累积阈值 / 每日定时 / 用户主动请求 | 高 | Pro Model 全息拼图 |

### 4.2 T0 情境主动触发（新增）

真实秘书的主动服务不由"数据变化"驱动，而由**时间节律**和**情境感知**驱动。

```python
class ProactiveTriggerer:
    """T0：基于时间和情境的主动触发。"""

    async def check_triggers(self, user_id: UUID):
        triggers = []

        # 1. 时间衰减触发：重要日期提前量
        approaching = await self._check_approaching_dates(user_id)
        # 距生日 30 天 → 该准备礼物了
        # 距出差 3 天 → 该检查行程了
        triggers.extend(approaching)

        # 2. 关系冷却触发：长期未联络预警
        cold_contacts = await self._check_cold_relationships(user_id)
        # 距上次联系张总已 60 天 → "要不要找个理由联络？"
        triggers.extend(cold_contacts)

        # 3. 模糊承诺跟进
        vague_commitments = await self._check_vague_commitments(user_id)
        # 老板 3 天前说"改天约老李" → 该跟进了
        triggers.extend(vague_commitments)

        # 4. 用户节律匹配
        rhythm_actions = await self._check_rhythm_alignment(user_id)
        # 老板周一下午情绪低 → 安排轻松事务
        triggers.extend(rhythm_actions)

        return triggers
```

### 4.3 ImpactArbitrator（影响力仲裁器）

**纯规则引擎，零 LLM 消耗**。不是所有数据变动都值得重跑 LLM。

```python
class ImpactLevel(Enum):
    SILENT = "silent"       # 静默更新，不触发 LLM
    LOW = "low"             # T1: heuristic 填充
    MEDIUM = "medium"       # T2: 增量 LLM
    HIGH = "high"           # T3: 全量编排

class ImpactArbitrator:
    """基于规则的影响力判定。"""

    def evaluate(self, trigger_type: str, payload: dict, diff: dict) -> ImpactLevel:
        changed_fields = set(diff.keys())

        # 只改了备注/描述 → 静默
        if not changed_fields - {"notes", "description", "priority"}:
            return ImpactLevel.SILENT

        # 时间微调 < 2 小时且无冲突 → 低影响
        if "start_time" in changed_fields:
            shift = abs(diff["start_time"]["delta_hours"])
            if shift < 2 and not payload.get("has_conflict"):
                return ImpactLevel.LOW

        # 新增人物实体 → 高影响
        if "new_person_entities" in payload:
            return ImpactLevel.HIGH

        # 地点或日期变更 → 中影响
        if changed_fields & {"location", "destination", "date"}:
            return ImpactLevel.MEDIUM

        # 多字段同时变更 → 高影响
        if len(changed_fields) >= 3:
            return ImpactLevel.HIGH

        return ImpactLevel.LOW
```

### 4.4 DirtyBitManager（脏位累积队列）

```python
class DirtyBitManager:
    """Redis-based 脏位管理器，支持累积和批量处理。"""

    BATCH_THRESHOLD = 5       # 累积 5 个低/中影响变动后批量处理
    BATCH_TIMEOUT = 300       # 或 5 分钟超时强制刷新

    async def mark_dirty(self, family_id: str, trigger: DirtyTrigger):
        impact = self.arbitrator.evaluate(trigger.type, trigger.payload, trigger.diff)

        if impact == ImpactLevel.SILENT:
            await self._apply_silent_update(trigger)
            return

        if impact == ImpactLevel.HIGH:
            await self._dispatch_immediate(family_id, trigger)  # 立即 T3
            return

        # 低/中影响: 入队累积
        await redis_client.rpush(f"dirty:{family_id}", trigger.serialize())
        queue_len = await redis_client.llen(f"dirty:{family_id}")

        if queue_len >= self.BATCH_THRESHOLD:
            await self._dispatch_batch(family_id)  # 批量 T2
        else:
            # 防饥饿：确保超时强制刷新
            await self._ensure_timeout_flush(family_id)

    async def _ensure_timeout_flush(self, family_id: str):
        """防止脏位产生频率低于阈值导致的饥饿状态。

        设置 Redis 定时键，当 BATCH_TIMEOUT 到期时通过 Celery Beat
        轮询或 Redis keyspace notification 触发强制刷新。
        """
        timer_key = f"dirty_timer:{family_id}"
        # 仅在没有活跃定时器时设置（NX: 不覆盖已有计时器）
        await redis_client.set(timer_key, "1", ex=self.BATCH_TIMEOUT, nx=True)
```

> **防饥饿保障**：如果脏位产生频率正好略低于 `BATCH_THRESHOLD`（如每 6 分钟产生 4 个），必须依赖 `BATCH_TIMEOUT`（5 分钟）强制刷新。工程实现中，Celery Beat 每分钟扫描 `dirty_timer:*` 过期事件，或使用 Redis keyspace notification（`__keyevent@0__:expired`）监听定时键到期后触发 `flush_dirty()`。

---

## 五、承诺追踪系统（新增核心模块）

> 秘书最核心的能力之一：盯紧每一个承诺的闭合。

### 5.1 承诺提取与分类

```python
class CommitmentType(Enum):
    FIRM = "firm"              # 明确承诺："周三给你报价"
    VAGUE = "vague"            # 模糊承诺："改天一起吃饭"
    CONDITIONAL = "conditional" # 条件承诺："如果方案通过就启动"
    DELEGATED = "delegated"    # 代办承诺："帮我催一下老张"

class CommitmentItem:
    id: UUID
    commitment_type: CommitmentType
    who_promised: str              # 谁承诺的
    what_promised: str             # 承诺内容
    to_whom: str                   # 对谁承诺
    deadline: Optional[datetime]   # 明确 deadline（firm 类型有）
    suggested_follow_up: Optional[datetime]  # 系统建议的跟进时间
    status: str                    # pending / followed_up / fulfilled / expired
    follow_up_count: int           # 已跟进次数
    source_conversation_id: UUID   # 来源对话
```

### 5.2 承诺预过滤门（Pre-filter Gate）

**问题**：CommitmentTracker 和 SocialIntentParser 是独立模块。如果不建立衔接，"改天约老李"既会被 CommitmentTracker 跟踪为承诺，又可能被 SocialIntentParser 识别为客套。若系统把客套当承诺来追踪并推送提醒，会显得极度低情商。

**解决方案**：承诺提取必须经过社交意图预过滤：

```python
class CommitmentPreFilter:
    """承诺提取前的社交意图门控 — 只有真实意图才进入跟踪队列。"""

    TRACKING_THRESHOLD = 0.6  # 社交意图评分 >= 0.6 才允许跟踪

    async def filter_commitments(self, raw_commitments: List[CommitmentItem],
                                  conversation_context: dict) -> List[CommitmentItem]:
        filtered = []
        for commitment in raw_commitments:
            # 调用 SocialIntentParser 评估意图真实性
            intent = await self.social_parser.classify(
                statement=commitment.what_promised,
                context=conversation_context,
            )

            if intent.type == SocialIntentType.GENUINE:
                # 真实意图 → 正常跟踪
                filtered.append(commitment)

            elif intent.type == SocialIntentType.OBLIGATION:
                # 面子义务 → 降优先级跟踪，延长跟进周期
                commitment.suggested_follow_up = (
                    utc_now() + timedelta(days=7)  # 比正常多等几天
                )
                commitment.priority = "low"
                filtered.append(commitment)

            elif intent.type == SocialIntentType.SOCIAL_COURTESY:
                # 社交客套 → 仅记录在 L0 关系层作为背景，不创建跟踪项
                await self.relationship_service.record_social_signal(
                    person_id=commitment.to_whom,
                    signal_type="courtesy_commitment",
                    content=commitment.what_promised,
                )
                # 不加入 filtered → 不进入跟踪队列

        return filtered
```

> **核心规则**：`SocialIntentScore < 0.6` 的意图禁止进入承诺跟进队列，仅作为 L0 关系背景记录。

### 5.3 模糊承诺跟进逻辑

```python
class VagueCommitmentTracker:
    """处理"改天约"、"下次记得"等模糊承诺。"""

    DEFAULT_FOLLOW_UP_DAYS = {
        CommitmentType.VAGUE: 3,        # "改天约" → 3 天后提醒跟进
        CommitmentType.CONDITIONAL: 7,   # "如果通过就…" → 7 天后检查条件
        CommitmentType.DELEGATED: 2,     # "帮我催" → 2 天后检查进度
    }

    async def check_and_follow_up(self, user_id: UUID):
        pending = await self.repo.get_pending_commitments(user_id)
        for commitment in pending:
            if self._should_follow_up(commitment):
                await self._generate_follow_up_suggestion(commitment)

    def _should_follow_up(self, commitment: CommitmentItem) -> bool:
        days_since = (utc_now() - commitment.created_at).days
        threshold = self.DEFAULT_FOLLOW_UP_DAYS.get(commitment.commitment_type, 5)
        return days_since >= threshold and commitment.follow_up_count < 3
```

---

## 六、社交智慧引擎（新增核心模块）

### 6.1 社交意图识别

```python
class SocialIntentType(Enum):
    GENUINE = "genuine"            # 真的想做（语气坚定、主动提起、给了具体细节）
    SOCIAL_COURTESY = "courtesy"   # 社交客套（被动回应、没给时间、模糊表述）
    OBLIGATION = "obligation"      # 碍于面子（语气犹豫、但有社交压力）

class SocialIntentParser:
    """从对话语境区分真意图 vs 客套。"""

    EXECUTION_STRATEGY = {
        SocialIntentType.GENUINE: "immediate",      # 立即执行
        SocialIntentType.SOCIAL_COURTESY: "record",  # 记录但不跟进
        SocialIntentType.OBLIGATION: "low_priority",  # 执行但降低优先级
    }
```

**判断依据**（供 LLM prompt 使用）：
- `genuine`：用户主动提起、给了具体时间/地点、语气坚定、历史上确实有互动
- `courtesy`：被问到才说、没给时间、"有空""下次"等模糊词、历史上约了多次都推掉
- `obligation`：语气犹豫但有社交压力（如对方是上级/长辈）、"也得约一下"

### 6.2 关系温度计

```python
class RelationshipThermometer:
    """动态关系温度计算。"""

    async def compute_temperature(self, person_id: UUID, user_id: UUID) -> float:
        # 基于 4 个维度加权计算
        interaction_freq = await self._get_interaction_frequency(person_id, user_id)
        interaction_quality = await self._get_recent_quality(person_id, user_id)
        commitment_fulfillment = await self._get_commitment_rate(person_id, user_id)
        recency = await self._get_days_since_last_contact(person_id, user_id)

        temp = (
            0.3 * interaction_freq +
            0.3 * interaction_quality +
            0.2 * commitment_fulfillment +
            0.2 * self._recency_score(recency)
        )
        return min(100, max(0, temp * 100))

    async def check_alerts(self, user_id: UUID) -> List[str]:
        """检查需要关系维护预警的联系人。"""
        persons = await self._get_important_persons(user_id)
        alerts = []
        for p in persons:
            temp = await self.compute_temperature(p.id, user_id)
            if temp < 30:
                alerts.append(f"与{p.name}的关系温度偏低({temp:.0f})，已 {p.days_since_contact} 天未联系")
        return alerts
```

### 6.3 ExclusionLedger（行为约束账本）

```python
class ExclusionRule(Base):
    """行为约束规则 — 替代 V6.0 的简单黑名单。"""
    __tablename__ = "exclusion_rules"

    id = Column(PGUUID, primary_key=True)
    family_id = Column(PGUUID, nullable=False)
    target_type = Column(String(30))    # person / topic / location / category
    target_id = Column(String(200))
    status = Column(String(20))         # active / cooling_down / expired / overridden
    reason = Column(Text)
    created_from = Column(String(30))   # dismiss / explicit_block / auto_detect
    cooldown_until = Column(DateTime(timezone=True))
    override_count = Column(Integer, default=0)  # 被 L2 覆盖的次数
```

**Override 逻辑（基于 Entity ID，非原始字符串）**：

> **关键设计**：`active_window_mentions` 必须是经过 Step 1 实体链接后的 `Target_ID` 集合，而非原始字符串。否则当用户使用代词（"他"）、别名（"张总"/"老张"）时，排除引擎会因字符串不匹配而误拦截用户想要的实体。

```python
async def check_with_override(self, family_id, target_type, target_id,
                               resolved_entity_ids: Set[UUID]):
    """
    检查排除规则，支持 L2 显式点名覆盖。

    Args:
        resolved_entity_ids: 经过 Entity Linking 后的实体 ID 集合，
                            已完成指代消解和别名归一。
                            例如 "他"/"张总"/"老张" 均已解析为同一 person_id。
    """
    rule = await self._get_active_rule(family_id, target_type, target_id)
    if rule is None:
        return False, None  # 不排除

    # L2 显式点名 → 覆盖排除（基于 Entity ID 而非字符串匹配）
    if target_id in resolved_entity_ids:
        rule.status = "overridden"
        rule.override_count += 1
        return False, "[OVERRIDE: 用户显式要求]"

    # 冷却期到期 → 自动过期
    if rule.cooldown_until and utc_now() > rule.cooldown_until:
        rule.status = "expired"
        return False, None

    return True, None  # 排除
```

---

## 七、信息分级路由器（新增）

> 真实秘书最核心的能力之一：判断什么信息该立即打扰老板、什么该攒着汇报、什么该自己处理掉。

### 7.1 多维优先级评分

```python
class PriorityScore:
    """替代脏位系统的二元"高/低影响"判断。"""

    @staticmethod
    def compute(event) -> float:
        return (
            0.30 * urgency(event.deadline) +          # 时间紧迫性
            0.25 * severity(event.consequence_type) +  # 后果严重性
            0.25 * stakeholder_weight(event.persons) + # 利益相关方权重
            0.20 * irrecoverability(event.type)        # 挽回难度
        )
```

### 7.2 推送策略与每日预算

```
每日推送预算：最多 5 条主动推送（P0 紧急不受限）

推送等级:
  P0 紧急  → Push 通知 + 对话流顶置      → "明天的航班取消了"
  P1 重要  → 晨报卡片内聚合              → "今天 3 件事需要关注"
  P2 有用  → 对话流中自然穿插             → "下周三是张明生日"
  P3 锦花  → 仅在用户空闲时推送           → "您最近与家人互动减少了"
```

### 7.3 中断权重矩阵

```python
class InterruptionController:
    """根据用户当前状态调整推送策略。"""

    async def should_push_now(self, user_id: UUID, priority: str) -> bool:
        state = await self._infer_user_state(user_id)

        if state == "in_meeting":
            return priority == "P0"  # 只有紧急才打扰
        elif state == "commuting":
            return priority in ("P0", "P1")  # 信息类可以推
        elif state == "idle":
            return True  # 闲下来了，按优先级排好序一起推
        return priority == "P0"
```

---

## 八、双脑路由优化

### 8.1 路由合并与提速

**改进**：将两次串行 Haiku 调用（classify + recover_lookup）合并为一次，降低 P50 延迟约 400ms。

### 8.2 Fast → Slow 动态升级

```python
# 在 FastWorker._handle_agentic 中：
if tool_call_count >= self._fast_agentic_max_tool_calls:
    # 不是返回兜底文本，而是升级到 Slow Path
    yield {
        "type": "route_upgrade",
        "from": "fast", "to": "slow",
        "reason": "tool_complexity_exceeded",
        "context": messages,
    }
    return
```

### 8.3 误分类检测与自纠正

```python
class ClassificationVerifier:
    """后验分类验证。"""

    async def verify(self, classification, execution_result):
        # Fast 执行失败 → 可能误分类为 immediate
        if classification.route_type == RouteType.FAST:
            if execution_result.get("fallback_text_used"):
                await self._record_misclassification(classification, "fast_fallback")

        # Slow 完成得太快 → 可能浪费了 Sonnet
        if classification.route_type == RouteType.SLOW:
            if execution_result["duration_ms"] < 2000 and execution_result["tool_calls_count"] == 0:
                await self._record_misclassification(classification, "slow_too_simple")
```

---

## 九、用户体验层设计

### 9.1 冷启动策略

| 阶段 | 时间 | 策略 |
|------|------|------|
| 首次对话 | 0-5 分钟 | 秘书自我介绍 + 自然闲聊收集核心信息 |
| 首日 | 0-24 小时 | 从对话中被动提取，不主动打扰 |
| 首周 | 1-7 天 | 每天通过 1-2 个小问题丰富画像 |

**首次欢迎卡片**（替代空白对话页）：
```
┌─────────────────────────────────┐
│ 你好！我是你的生活秘书             │
│                                  │
│ 越了解你，我越能帮到你。            │
│ 先从一件小事开始？                  │
│                                  │
│ [告诉我家人的生日]                  │
│ [帮我规划一次出差]                  │
│ [记住一个重要的事]                  │
│ [随便聊聊]                        │
└─────────────────────────────────┘
```

### 9.2 透明度设计

**秘书笔记（L1 用户化）**：将 L1 笔记本包装为用户可见可编辑的"秘书笔记"页面。

```
┌──────────────────────────────────┐
│ 秘书笔记                           │
│                                   │
│ [出行偏好]                          │
│ · 高铁：一等座、靠窗          [编辑] │
│ · 酒店：四星以上、近地铁      [编辑] │
│ · 航空：东航里程会员          [编辑] │
│                                   │
│ [家人信息]                          │
│ · 妈妈：花粉过敏、喜欢紫色   [编辑] │
│ · 小宝：花生过敏              [编辑] │
│                                   │
│ [屏蔽偏好]                          │
│ · 如家快捷酒店 (2.15 屏蔽)    [解除] │
└──────────────────────────────────┘
```

**推荐解释性**：每条推荐附带触发原因。
- "推荐这家酒店：因为您上次住过且评价不错"
- "建议联系张明：他也在北京，且你们 3 个月没见了"

### 9.3 信任修复仪式

当 AI 犯错被纠正后：
```
纠正 → 秘书回复"已更正！"
     → 下次同类场景主动提及"按照您上次纠正的，这次选的是一等座"
     → toast 提示"已记住，30 天内不再推荐类似内容"
```

### 9.4 渐进式功能解锁

| 阶段 | 可用功能 | 解锁条件 |
|------|---------|---------|
| 基础 | 对话 + 提醒 + 天气 | 注册即可 |
| 进阶 | + 看板 + 简报 + 记忆 | 7 天 + 2 个家庭成员 |
| 高级 | + 旅行规划 + 礼物 + 人情 | 30 天或手动开启 |
| 专家 | + 图谱 + 全局统筹 | 手动开启 |

### 9.5 多角色家庭隐私分级

| 隐私级别 | 说明 | 默认可见者 |
|---------|------|-----------|
| 公开 | 家庭共享日程 | 所有家庭成员 |
| 限定 | 个人工作日程 | 仅显示"忙碌"时间段 |
| 私密 | 个人隐私事项 | 仅本人 |
| 儿童 | 孩子相关 | 父母双方 |

### 9.6 隐私推断防护 (Privacy Inference Protection)

**问题**：即使隐藏了成员的具体信息，LLM 的推理能力可能通过间接信息反推隐私数据。典型场景：如果系统建议"在两地中间约饭"，即便隐藏了太太的地点，用户也能根据"中间点"反推出太太的位置。

**解决方案**：对涉及未授权共享信息的协同编排，采用"黑箱计算"模式：

```python
class PrivacyInferenceGuard:
    """防止 LLM 通过推理泄露隐私信息。"""

    INFERENCE_RISK_PATTERNS = [
        "midpoint_location",     # 中间点推算泄露位置
        "schedule_gap_analysis", # 空闲时段推算行程
        "preference_contrast",   # 对比偏好推断关系状态
    ]

    async def sanitize_collaborative_context(self, context: CollaborativeContext,
                                              privacy_settings: dict) -> CollaborativeContext:
        """在协同编排中，确保不向 LLM 暴露可推断的隐私数据。"""
        for member in context.participants:
            if not member.has_shared("location"):
                # 不将位置传入 LLM，由系统后端直接计算推荐地点
                context.remove_inference_source(member.id, "location")
                # 推荐结果由系统直接展示为确认框，不附带推算逻辑
                context.add_system_computed_suggestion(
                    type="meeting_location",
                    display="为您推荐了一个方便双方的地点",
                    computed_by="system",  # 明确标注为系统计算，非 LLM 推理
                )
        return context
```

> **核心原则**：对于未授权共享具体信息的成员，编排建议只能由"系统后端直接计算并展示确认框"，禁止在 Prompt 中暴露任何可推算逻辑给 LLM。LLM 只看到最终推荐结果，看不到推算过程。

---

## 十、遗漏场景补充

基于秘书专家评审，以下 12 个高频场景需纳入规划：

| # | 场景 | 频率 | 建议归属模块 | 优先级 |
|---|------|------|-------------|-------|
| 1 | 承诺跟催/追踪 | 每日 | 新增 CommitmentTracker | P0 |
| 2 | 代理回复/沟通 | 每日 | 扩展 conversation | P1 |
| 3 | 文件/资料准备 | 每周 | 扩展 briefing | P2 |
| 4 | 费用/报销管理 | 每月 | 扩展 trip | P2 |
| 5 | 多方时间协调 | 每周 | 扩展 curation | P1 |
| 6 | 应急/突发处理 | 不定 | 扩展 curation (conflict_resolver) | P1 |
| 7 | 礼仪/规范顾问 | 不定 | 扩展 gift + relationship | P2 |
| 8 | 定期例行事务 | 每月 | 扩展 date_manager (RecurringTask) | P1 |
| 9 | 家庭成员代管 | 不定 | 扩展 member | P2 |
| 10 | 信息摘要/舆情 | 每日 | 扩展 briefing | P3 |
| 11 | 情绪感知/安抚 | 不定 | AI Engine 层面 | P3 |
| 12 | 多角色切换 | 每日 | 扩展 member (Role Context) | P2 |

---

## 十一、评估指标体系

> V6/V7 仅 3 个 KPI，V8.0 扩展到 12 个。

| 类别 | 指标 | 目标 |
|------|------|------|
| **Token 效率** | 平均 context token 使用率 | 80-95% of budget |
| | Token 节约率 vs 无缓存基线 | >60% |
| | Context_Hash 命中率 | >40% |
| **质量** | L1 事实准确率（用户确认率） | >90% |
| | 关联推荐确认率 | >30% |
| | 关联推荐 dismiss 率（误报） | <20% |
| | 记忆召回 relevance（用户反馈） | >4.0/5.0 |
| **延迟** | 意图分类 P95 | <800ms |
| | 上下文组装 P95 | <200ms |
| | Fast Path E2E P95 | <3s |
| | Slow Path E2E P95 | <15s |
| **可靠性** | 路由误分类率 | <5% |

---

## 十二、实施优先级

### P0（立即实施）

| 改进项 | 预期收益 | 实现复杂度 |
|--------|---------|-----------|
| TokenBudget + 统一 ContextAssembler | 防 token 超限，提升质量 | 中 |
| pgvector 迁移 + HNSW 索引 | 语义检索 >10s → <100ms | 低 |
| 承诺追踪系统 (CommitmentTracker) | 秘书最核心价值 | 中 |
| 信息分级路由 + 推送预算 | 避免通知轰炸 | 中 |
| FactVerificationGate | 防幻觉污染 L1 | 低 |

### P1（第二批）

| 改进项 | 预期收益 | 实现复杂度 |
|--------|---------|-----------|
| ImpactArbitrator + DirtyBitManager | Token 节约 60%+ | 中 |
| L0 关系记忆图谱 (PersonMemoryNode) | 大幅提升上下文相关性 | 中 |
| 渐进授权信任模型 (Progressive Trust) | 改善用户体验 | 中 |
| ExclusionLedger + Override 机制 | 完整行为约束 | 中 |
| 事实冲突检测 + supersede 链 | 解决矛盾上下文 | 低 |
| 冷启动引导式对话 | 提升新用户留存 | 低 |

### P2（第三批）

| 改进项 | 预期收益 | 实现复杂度 |
|--------|---------|-----------|
| Context_Hash 缓存 | 无变动场景延迟 <100ms | 低 |
| 社交意图识别 (SocialIntentParser) | 区分客套/真意 | 高 |
| 关系温度计 + T0 情境触发 | 主动性提升 | 中 |
| 秘书笔记 UI (L1 用户可见) | 透明度提升 | 中 |
| 渐进式功能解锁 | 降低新用户认知负担 | 中 |
| 分类器合并 + 误分类检测 | 路由延迟降 400ms | 中 |

### P3（远期）

| 改进项 | 预期收益 | 实现复杂度 |
|--------|---------|-----------|
| 轻量 GraphRAG | 提升关系推理质量 | 高 |
| 角色化界面（老人模式等） | 差异化体验 | 高 |
| 家庭协同决策 | 新功能场景 | 高 |
| 数据生命周期管理 | 控制存储增长 | 低 |
| 完整评估指标体系 | 量化优化效果 | 中 |

---

## 十三、名词解释

| 术语 | 定义 |
|------|------|
| **关系记忆图谱 (L0)** | 以人为核心节点、向外辐射的记忆组织方式，包含情绪标记、承诺记录、社交禁忌 |
| **事实溯源链 (Provenance)** | 每条 L1 事实附带的来源证据链，用于冲突裁决和防幻觉 |
| **承诺追踪 (Commitment Tracking)** | 从对话中提取承诺项并全生命周期跟踪直至闭合 |
| **社交意图识别** | 区分用户的真实意图(genuine)、社交客套(courtesy)、面子义务(obligation) |
| **关系温度计** | 基于互动频率、质量、承诺履行率、时效性计算的关系健康度指标 |
| **影响力仲裁器** | 纯规则引擎，零 LLM 消耗，判断数据变动是否值得触发 LLM 编排 |
| **信息分级路由** | 4 级推送策略(P0-P3) + 每日预算 + 中断权重矩阵 |
| **渐进授权** | 用户信任等级(L0-L3)随使用时间和确认率动态调整，驱动确认频率 |
| **FactVerificationGate** | L1 写入前的后验检查门，防止 LLM 幻觉污染事实库 |
| **Context_Hash** | 上下文素材的特征指纹，用于缓存比对避免重复 LLM 调用 |
| **实体链接 (Entity Linking)** | 将对话中的代词（"他"）、别名（"张总"/"老张"）统一解析为唯一 person_id，确保排除引擎等基于 ID 匹配 |
| **时间戳守卫 (Timestamp Guard)** | L3 摘要加载时检查与 L2 活跃窗口的时间重叠，附带去重指令防止语义重复 |
| **事实时效类型 (NoteLifeType)** | 区分 L1 事实的 PERMANENT（长期偏好）和 TRANSIENT（阶段性状态），TRANSIENT 过期后自动降级 |
| **承诺预过滤门 (CommitmentPreFilter)** | CommitmentTracker 前置门控，依赖 SocialIntentParser 评分过滤社交客套，score < 0.6 不进入跟踪队列 |
| **反思日志 (ReflectionLog)** | 信任降级时自动生成的内省记录，分析被拒原因模式并提出纠正建议 |
| **隐私推断防护 (PrivacyInferenceGuard)** | 防止 LLM 通过间接推理泄露未授权信息（如从中间点反推位置），采用黑箱计算模式 |

---

> V8.0 方案的核心升级：从"信息管理系统"进化为"会做事的秘书"——具备主动承诺追踪、社交判断力、情境感知和渐进式信任建设，同时通过 Token 预算管理和影响力仲裁保持工业级运行效率。
