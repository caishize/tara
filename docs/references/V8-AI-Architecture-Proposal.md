# 生活秘书 AI 子系统 V8.0 架构提案

> **版本** 8.1 | **日期** 2026-02-18
> **基于**: V6.0 四层记忆 + V7.0 脏位触发 + 三方专家评审 + 逻辑风险审查

---

## 目录

1. [提案概述与动机](#一提案概述与动机)
2. [四层记忆体系 (L1-L4)](#二四层记忆体系-l1-l4)
3. [统一上下文装配器 (ContextAssembler)](#三统一上下文装配器-contextassembler)
4. [智能触发与脏位管理](#四智能触发与脏位管理)
5. [双脑路由增强](#五双脑路由增强)
6. [可靠性与一致性](#六可靠性与一致性)
7. [可扩展性](#七可扩展性)
8. [安全与隐私](#八安全与隐私)
9. [实施路线图](#九实施路线图)
10. [KPI 与验收标准](#十kpi-与验收标准)

---

## 一、提案概述与动机

### 1.1 问题陈述

当前系统（V4.0 架构实现）在记忆管理、上下文装配、触发机制三个核心 AI 子系统中存在以下已确认差距：

| 维度 | 现状问题 | 风险等级 |
|------|---------|---------|
| **记忆分层** | 实际为"三层半"——L1(SecretaryNote) 和 L4(ConversationMemory+embedding) 之间缺乏显式分级 | P0 |
| **Token 预算** | `get_comprehensive_context()` 无大小限制，大量记忆直接拼接 | P0 |
| **向量存储** | `embedding` 用 `ARRAY(Float)`，语义搜索为 O(n) 全扫描 | P1 |
| **路由效率** | IntentRouter 两次串行 LLM 调用（分类 + 补全），无 Fast→Slow 升级 | P1 |
| **触发分级** | `ShouldRunService` 仅二元(run/skip)，缺乏影响评估 | P2 |
| **隐私控制** | 上下文装配无隐私过滤，所有记忆均可进入 LLM prompt | P1 |
| **合并失真** | `consolidation_service` 未使用 `superseded_by` 字段，合并后原始记忆仍参与召回 | P2 |

### 1.2 设计原则

本提案遵循以下原则：

| # | 原则 | 说明 |
|---|------|------|
| 1 | **渐进增强** | 在现有 V4.0 代码基础上增量改造，不做全盘重写 |
| 2 | **Token 感知** | 上下文装配的每个环节都有 Token 预算约束 |
| 3 | **瞬时 Agent** | 保持无状态 Agent 架构，上下文完全从 DB 重建 |
| 4 | **可观测** | 每个子系统暴露结构化指标，支持 A/B 测试 |
| 5 | **隐私默认** | 敏感数据默认不进入 LLM 上下文 |
| 6 | **幂等优先** | 触发与写入遵循 V7.0 的 DiffApply 幂等规范 |

---

## 二、四层记忆体系 (L1-L4)

### 2.1 层级定义

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  L1: 事实基座 (Fact Base)                                              │  │
│  │  表: secretary_notes                                                   │  │
│  │  特征: 用户确认的偏好、禁忌、例行安排                                     │  │
│  │  写入: LLM 提取 + FactVerificationGate + 用户确认                       │  │
│  │  生命周期: 永久 (用户主动删除)                                           │  │
│  │  Token 预算: 始终注入, ~500 tokens                                     │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  L2: 活跃窗口 (Active Window)                                          │  │
│  │  表: conversation_messages + session_summaries                         │  │
│  │  特征: 当前会话对话 + 近期会话压缩摘要                                    │  │
│  │  写入: 对话流自动写入                                                    │  │
│  │  生命周期: 会话级 (消息) / 7天 (摘要)                                    │  │
│  │  Token 预算: ~2000 tokens (近 10 条消息 + 压缩摘要)                     │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  L3: 摘要层 (Digest Layer)                                             │  │
│  │  表: memory_summaries + person_profiles                                │  │
│  │  特征: 整合后的周期性摘要、人物档案                                       │  │
│  │  写入: 定期 consolidation (周日 3:00 AM)                                │  │
│  │  生命周期: 永久 (周期性刷新)                                             │  │
│  │  Token 预算: 按需注入, ~1000 tokens                                    │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  L4: 归档层 (Archive)                                                  │  │
│  │  表: conversation_memories + memory_associations                       │  │
│  │  特征: 高细粒度原始记忆 + 向量嵌入 + 关联图谱                             │  │
│  │  写入: 对话后异步提取                                                    │  │
│  │  生命周期: 永久 (可降级/软删)                                            │  │
│  │  Token 预算: 语义召回后注入, ~1500 tokens                               │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 与现有代码的映射

| 层级 | 现有实现 | 需要改造 |
|------|---------|---------|
| L1 | `secretary_notes` 表 + `SecretaryNoteService` | 增加 `FactVerificationGate` (见 2.3) + `NoteLifeType` + `valid_until` (见 2.6) |
| L2 | `conversation_messages` + `SessionSummary` + `context_service.py` | 增加 Token 预算约束 |
| L3 | `memory_summaries` + `PersonProfile` + `consolidation_service.py` | 修复 `superseded_by` 逻辑 |
| L4 | `conversation_memories` + `MemoryAssociation` + `recall_service.py` | pgvector 迁移 + Token 限制 |

### 2.3 L1 事实验证门 (FactVerificationGate)

**问题**: 当前 `secretary_note_service.py` 中 LLM 提取的事实直接入库，无后验证。

**方案**: 在 L1 写入前增加验证管道：

```python
# 文件: backend/src/modules/memory/fact_verification.py

class FactVerificationGate:
    """
    验证 LLM 提取的事实是否可信，防止幻觉污染 L1。

    验证维度:
    1. 证据追溯 - 事实必须可追溯到原始对话
    2. 矛盾检测 - 与现有 L1 事实是否矛盾
    3. 置信度阈值 - 低置信度事实进入 pending 状态
    """

    CONFIDENCE_AUTO_ACCEPT = 0.85   # 自动接受阈值
    CONFIDENCE_PENDING = 0.6        # 待确认阈值
    # < 0.6 则丢弃

    async def verify(self, candidate: NoteCandidate,
                     existing_notes: List[SecretaryNote],
                     source_messages: List[str]) -> VerificationResult:
        # 1. 证据追溯: 检查 candidate.content 是否有 source_messages 支撑
        # 2. 矛盾检测: 与 existing_notes 做语义比较
        # 3. 返回 ACCEPT / PENDING / REJECT
        ...
```

**落点**: `backend/src/modules/memory/secretary_note_service.py` 中的 `_extract_notes_from_memories()` 调用此 Gate。

### 2.4 L3 合并修复

**问题**: `consolidation_service.py` 中 `mark_memories_consolidated()` 只设 `is_consolidated=True`，从不设 `superseded_by`。已合并的 L4 记忆仍被 recall 返回。

**修复方案**:

```python
# 文件: backend/src/modules/memory/consolidation_service.py
# 改造 _create_topic_summary() 末尾

async def _create_topic_summary(self, memories, ...):
    summary = await self._generate_summary(memories)
    saved_summary = await self._save_summary(summary)

    # 新增: 标记原始记忆为已合并，指向摘要
    memory_ids = [m.id for m in memories]
    await self.memory_repo.mark_superseded(
        memory_ids=memory_ids,
        superseded_by=saved_summary.id,
        new_status=MemoryStatus.SUPERSEDED,
    )
```

**recall_service 配合改造**: 在召回时过滤 `SUPERSEDED` 状态的记忆：

```python
# recall_service.py - 所有查询增加过滤
.filter(ConversationMemory.status != MemoryStatus.SUPERSEDED)
```

### 2.5 L1 事实时效管理 (NoteLifeType)

**问题**: L1 采用语义 UPSERT，阶段性事实（如"这周在减肥"、"最近项目忙不约饭"）会永久覆盖长期偏好（如"喜欢日料"），导致短期状态过期后秘书"失忆"。

**方案**: 在 `secretary_notes` 表增加时效字段：

```python
# 文件: backend/src/modules/memory/secretary_note_service.py

class NoteLifeType(str, Enum):
    PERMANENT = "permanent"    # 长期偏好：过敏、口味、出行规则
    TRANSIENT = "transient"    # 短期状态：减肥中、出差中、项目忙

# secretary_notes 表新增字段 (Alembic migration)
# life_type VARCHAR(20) DEFAULT 'permanent'
# valid_until TIMESTAMP WITH TIME ZONE NULL
```

**落点**: `secretary_note_service.py` 中的 `_extract_notes_from_memories()` 需要判断事实时效性：

```python
async def _classify_life_type(self, fact_content: str) -> Tuple[NoteLifeType, Optional[datetime]]:
    """判断事实是永久偏好还是阶段性状态。"""
    TRANSIENT_SIGNALS = ["最近", "这周", "这几天", "目前", "暂时", "临时"]
    if any(signal in fact_content for signal in TRANSIENT_SIGNALS):
        return NoteLifeType.TRANSIENT, utc_now() + timedelta(days=30)
    return NoteLifeType.PERMANENT, None
```

**TRANSIENT 过期处理**: Celery Beat 定时任务检查过期 TRANSIENT 事实，归档到 L4 并恢复被其覆盖的 PERMANENT 事实。

### 2.6 L4 向量存储迁移

**问题**: `embedding` 字段为 `ARRAY(Float)`，语义搜索为 Python 内存计算 O(n)。

**方案**: 分两阶段迁移到 pgvector native。

**阶段 1 (已有基础)**:
- Migration 048 已添加 `embedding_v` 列 (vector(1536)) + HNSW 索引
- 需要在 `recall_service.py` 的 `_semantic_search()` 中优先使用 `embedding_v`

**阶段 2**:
- 回填脚本: 将 `embedding` ARRAY 数据复制到 `embedding_v`
- 新写入统一走 `embedding_v`
- 保留 `embedding` 列作为兼容层，最终通过迁移删除

```python
# recall_service.py - _semantic_search() 改造
async def _semantic_search(self, query_embedding, user_id, family_id, limit):
    if self.memory_repo.has_pgvector:
        # O(log n) HNSW 搜索
        results = await self.memory_repo.vector_search(
            query_embedding, user_id, family_id, limit,
            threshold=self.config.semantic_similarity_threshold
        )
    else:
        # 降级: ARRAY(Float) 内存计算
        results = await self._fallback_semantic_search(...)
    return results
```

---

## 三、统一上下文装配器 (ContextAssembler)

### 3.1 问题分析

当前上下文装配分散在三处，无统一的 Token 预算管理：

| 现有组件 | 位置 | 问题 |
|---------|------|------|
| `ContextRehydrationService` | `conversation/context_service.py` | 8 路并行 fetch，无大小限制 |
| `ContextAwareRecallService` | `memory/recall_service.py` | 6 层召回 + 增强，无 Token 控制 |
| `AgentContext.system_prompt_context()` | `ai_engine/agent_context.py` | 仅轻量数据，业务数据依赖工具 |

### 3.2 ContextAssembler 五步管道

```
用户消息 (User Input)
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ContextAssembler 管道                         │
│                                                                 │
│  Step 0: Entity Linking (实体链接 - 前置)                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 指代消解: "他"→张总, "那个人"→王明                        │   │
│  │ 别名归一: "张总"/"老张"/"张明" → person_id:xxx            │   │
│  │ 输出: resolved_entity_ids: Set[UUID]                     │   │
│  └──────────────────────────────────────────────────────────┘   │
│       │                                                         │
│  Step 1: Collect (并行收集)                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐       │
│  │ L1 Notes │ │ L2 Msgs  │ │ L3 Profs │ │ L4 Recall    │       │
│  │ (全量)   │ │ (近10条)  │ │ (相关人)  │ │ (语义+关键词) │       │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘       │
│       │            │            │               │               │
│  Step 2: Budget (Token 预算分配)                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ TokenBudgetAllocator                                     │   │
│  │                                                          │   │
│  │ 总预算: system_prompt_budget (默认 6000 tokens)           │   │
│  │                                                          │   │
│  │ L1 固定: 500 tokens  (事实基座始终注入)                    │   │
│  │ L2 固定: 2000 tokens (活跃窗口)                           │   │
│  │ L3 弹性: 500-1500 tokens (按相关性裁剪)                   │   │
│  │ L4 弹性: 500-2000 tokens (按相关性裁剪)                   │   │
│  │                                                          │   │
│  │ 弹性分配规则:                                              │   │
│  │ - L3/L4 剩余空间按 recall 相关性分数分配                   │   │
│  │ - 超出预算时按 importance × recency 裁剪                  │   │
│  └──────────────────────────────────────────────────────────┘   │
│       │                                                         │
│  Step 3: Filter (隐私 + 排除过滤)                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ PrivacyFilter                                            │   │
│  │ - 过滤 sensitivity_level >= HIGH 的记忆                   │   │
│  │ - 按用户 privacy_settings 排除特定类别                     │   │
│  │                                                          │   │
│  │ ExclusionFilter (V6.0 ExclusionLedger 简化版)            │   │
│  │ - 最近 N 次 dismiss 的洞察/记忆不再注入                   │   │
│  │ - 冷却期内的重复建议不注入                                 │   │
│  └──────────────────────────────────────────────────────────┘   │
│       │                                                         │
│  Step 4: Rank (优先级排序)                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 排序公式:                                                │   │
│  │ score = importance × feedback_weight × recency_decay     │   │
│  │                                                          │   │
│  │ recency_decay = max(0.3, 1.0 - days_ago / 90)          │   │
│  │ feedback_weight: 0.1 (多次 dismiss) ~ 2.0 (confirm)     │   │
│  └──────────────────────────────────────────────────────────┘   │
│       │                                                         │
│  Step 5: Serialize (序列化为 prompt text)                        │
│       │                                                         │
│       ▼                                                         │
│  输出: formatted_context: str + metadata: ContextMetadata       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 代码落点

新建 `backend/src/ai_engine/context_assembler.py`:

```python
@dataclass
class TokenBudget:
    """Token budget configuration for context assembly.

    支持任务类型动态调整，避免固定分配导致的预算死锁。
    例如 ANALYZE 类型任务需要更多 L4 空间来检索历史档案，
    此时应压缩 L2（对话历史对分析任务价值低）。
    """
    total: int = 6000
    l1_fixed: int = 500
    l2_fixed: int = 2000
    l3_min: int = 500
    l3_max: int = 1500
    l4_min: int = 500
    l4_max: int = 2000

    # 任务类型覆盖规则
    TASK_OVERRIDES = {
        "analyze": {"l2_fixed": 800, "l4_min": 1000, "l4_max": 2500},  # 压缩 L2，扩展 L4
        "plan":    {"l2_fixed": 1500, "l3_max": 800, "l4_max": 2200},  # 平衡型
        "lookup":  {"l2_fixed": 800, "l3_max": 500, "l4_max": 800},    # 最小上下文
    }

    def for_action(self, action_type: str) -> 'TokenBudget':
        """根据任务类型返回调整后的预算配置。"""
        overrides = self.TASK_OVERRIDES.get(action_type, {})
        if not overrides:
            return self
        import dataclasses
        return dataclasses.replace(self, **overrides)


@dataclass(frozen=True)
class ContextMetadata:
    """Metadata about the assembled context for observability."""
    total_tokens_used: int
    l1_tokens: int
    l2_tokens: int
    l3_tokens: int
    l4_tokens: int
    memories_included: int
    memories_filtered: int
    assembly_time_ms: float


class ContextAssembler:
    """
    Unified context assembly engine with token budget management.

    Replaces the scattered context assembly in:
    - conversation/context_service.py (rehydration)
    - memory/recall_service.py (ContextAwareRecallService)
    - ai_engine/agent_context.py (system prompt)
    """

    def __init__(self, db: AsyncSession, budget: Optional[TokenBudget] = None):
        self.db = db
        self.budget = budget or TokenBudget()

    async def assemble(self, user_id: UUID, family_id: UUID,
                       session_id: str, user_message: str,
                       route_type: RouteType,
                       action_type: ActionType = None) -> Tuple[str, ContextMetadata]:
        """Six-step context assembly pipeline."""
        # Step 0: Entity Linking (指代消解 + 别名归一)
        resolved_entities = await self._resolve_entities(
            user_message, user_id, family_id)

        # Step 1: Collect (parallel)
        l1, l2, l3, l4 = await self._collect(
            user_id, family_id, session_id, user_message,
            resolved_entities=resolved_entities)

        # Step 1.5: L3 Timestamp Guard (防止 L2/L3 语义重叠)
        l3 = self._apply_timestamp_guard(l3, l2)

        # Step 2: Budget allocation (支持任务类型动态调整)
        allocated = self._allocate_budget(l1, l2, l3, l4, route_type,
                                          action_type=action_type)

        # Step 3: Privacy + exclusion filter (使用 resolved_entity_ids)
        filtered = await self._apply_filters(
            allocated, user_id, resolved_entity_ids=resolved_entities)

        # Step 4: Rank by score
        ranked = self._rank(filtered)

        # Step 5: Serialize
        return self._serialize(ranked)

    async def _resolve_entities(self, user_message: str,
                                 user_id: UUID, family_id: UUID) -> Set[UUID]:
        """Step 0: 实体链接 — 指代消解 + 别名归一。

        将用户消息中的人名、代词、别名统一解析为 person_id。
        ExclusionFilter 使用 ID 匹配而非字符串匹配，避免代词/别名导致误拦截。
        """
        # 从 L2 活跃窗口提取对话上下文中的人物引用
        # 使用 member_context 做别名映射
        ...

    def _apply_timestamp_guard(self, l3_digests: List, l2_window) -> List:
        """Step 1.5: L3 时间戳守卫 — 防止 L2/L3 语义重叠。

        当 L3 摘要的时间范围与 L2 活跃窗口重叠时，附带守卫指令：
        "以下摘要包含 L2 已覆盖的时间段，若有出入以 L2 原文为准。"
        """
        ...
```

**集成方式**: `fast_worker.py` 和 `agent_worker.py` 中用 `ContextAssembler.assemble()` 替代现有的 `context_service.build_context()` + `recall_service.get_comprehensive_context()` 调用链。

### 3.4 Token 估算策略

使用轻量估算而非精确 tokenizer 调用（避免 tiktoken 依赖开销）：

```python
def estimate_tokens(text: str) -> int:
    """
    快速 Token 估算。
    中文约 1.5 token/字符，英文约 0.25 token/word。
    误差 < 10%，满足预算管理精度需求。
    """
    cn_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - cn_chars
    return int(cn_chars * 1.5 + other_chars * 0.3)
```

---

## 四、智能触发与脏位管理

### 4.1 三级触发分类 (T1/T2/T3)

基于 V7.0 设计，将现有 `trigger_dispatcher.py` 的触发器正式分级：

```
┌─────────────────────────────────────────────────────────────────┐
│                    三级触发分类                                   │
│                                                                 │
│  T1: 即时触发 (Immediate)                                        │
│  ├── 触发源: 事件 CRUD, 行程创建/变更, 用户主动请求              │
│  ├── 延迟: < 1s                                                 │
│  ├── 执行: 同步 mini_curate() 或防抖聚合后 incremental          │
│  └── 现有实现: trigger_dispatcher._handle_trip_created() 等     │
│                                                                 │
│  T2: 延迟触发 (Deferred)                                         │
│  ├── 触发源: 记忆提取完成, 日期临近, 天气变化                     │
│  ├── 延迟: 5min-1h (防抖聚合窗口)                               │
│  ├── 执行: DirtyBitManager 累积后批量处理                        │
│  └── 现有实现: trigger_dispatcher._handle_memory_extracted()    │
│                                                                 │
│  T3: 定期校验 (Scheduled)                                        │
│  ├── 触发源: 调度器定时触发                                      │
│  ├── 频率: 24h 兜底 + 7天 full review                           │
│  ├── 执行: ShouldRunService 判定后 incremental 或 full          │
│  └── 现有实现: should_run_service + curation_service.curate()   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 ImpactArbitrator (影响评估器)

**问题**: 现有 `ShouldRunService` 仅返回 `should_run: bool`，无法区分触发的影响级别。

**方案**: 在 `ShouldRunService` 之上增加影响评估层：

```python
# 文件: backend/src/modules/curation/services/impact_arbitrator.py

class ImpactLevel(str, Enum):
    SILENT = "silent"      # 无可见变化，纯后台更新
    LOW = "low"            # 小调整，不推送
    MEDIUM = "medium"      # 值得在简报中提及
    HIGH = "high"          # 需要即时推送

class ImpactArbitrator:
    """
    评估触发事件的影响级别，决定处理策略。

    规则示例:
    - trip_created → HIGH (新行程直接影响用户日程)
    - memory_extracted + 无冲突 → SILENT (背景知识更新)
    - date_approaching + 7天内 → MEDIUM (需要提醒)
    - date_approaching + 3天内 → HIGH (紧急提醒)
    """

    async def assess(self, trigger: TriggerEvent,
                     context: FamilyContext) -> ImpactAssessment:
        level = self._classify_impact(trigger, context)
        return ImpactAssessment(
            level=level,
            should_push=level >= ImpactLevel.HIGH,
            should_brief=level >= ImpactLevel.MEDIUM,
            execution_mode=self._decide_mode(level),
        )
```

**落点**: 在 `trigger_dispatcher.py` 的 `dispatch()` 入口处调用，替代直接的 handler routing。

### 4.3 DirtyBitManager (脏位管理器)

**问题**: T2 触发目前逐个处理，缺少累积-批处理机制。

**方案**: 基于 Redis 的脏位累积队列：

```python
# 文件: backend/src/modules/curation/services/dirty_bit_manager.py

class DirtyBitManager:
    """
    Redis-based dirty bit accumulation for T2 deferred triggers.

    工作流:
    1. 触发事件到来 → mark_dirty(family_id, trigger_type, entity_id)
    2. Redis HASH: curation:dirty:{family_id} → {entity_type:entity_id: timestamp}
    3. 防抖窗口结束 → flush_dirty(family_id) → 批量提交 incremental curation
    4. 处理完成 → clear_dirty(family_id, processed_entities)
    """

    DEBOUNCE_WINDOW_SECONDS = 300  # 5 分钟防抖窗口
    BATCH_THRESHOLD = 5            # 累积 5 个变动后立即批量处理

    async def mark_dirty(self, family_id: UUID,
                         trigger_type: str, entity_id: str):
        key = f"curation:dirty:{family_id}"
        field = f"{trigger_type}:{entity_id}"
        await redis_client.hset(key, field, utc_now().isoformat())
        # 设置/刷新 TTL
        await redis_client.expire(key, self.DEBOUNCE_WINDOW_SECONDS * 2)

        # 检查是否达到批量阈值
        queue_len = await redis_client.hlen(key)
        if queue_len >= self.BATCH_THRESHOLD:
            await self._dispatch_flush(family_id)
        else:
            # 防饥饿：确保超时强制刷新
            await self._ensure_timeout_flush(family_id)

    async def _ensure_timeout_flush(self, family_id: UUID):
        """防饥饿机制：设置 Redis 定时键，超时后触发强制刷新。

        避免脏位产生频率低于 BATCH_THRESHOLD 导致整理任务延迟数小时。
        实现方式二选一：
        1. Celery Beat 每分钟扫描 dirty_timer:* 键是否存在
        2. Redis keyspace notification (__keyevent@0__:expired) 监听定时键到期
        """
        timer_key = f"dirty_timer:{family_id}"
        await redis_client.set(timer_key, "1",
                               ex=self.DEBOUNCE_WINDOW_SECONDS, nx=True)

    async def flush_dirty(self, family_id: UUID) -> List[DirtyEntry]:
        """获取并清空所有脏位，返回待处理列表。"""
        key = f"curation:dirty:{family_id}"
        timer_key = f"dirty_timer:{family_id}"
        entries = await redis_client.hgetall(key)
        if entries:
            await redis_client.delete(key)
            await redis_client.delete(timer_key)  # 清除定时器
        return [DirtyEntry.parse(k, v) for k, v in entries.items()]
```

**调度集成**: Celery Beat 每分钟扫描 `dirty_timer:*` 键，对存在超过 `DEBOUNCE_WINDOW_SECONDS` 的家庭调用 `flush_dirty()` 后提交批量 curation。这确保即使脏位产生频率低于 `BATCH_THRESHOLD`，整理任务也不会无限延迟。

### 4.4 Context Hash 缓存

当同一家庭短时间内多次请求时，避免重复的上下文装配：

```python
# 在 ContextAssembler 中
async def assemble(self, ...):
    # 计算输入 hash
    context_hash = self._compute_hash(user_id, family_id, user_message)

    # 检查 Redis 缓存 (TTL 60s)
    cached = await redis_client.get(f"ctx:{context_hash}")
    if cached:
        return self._deserialize_cached(cached)

    # ... 正常装配 ...

    # 缓存结果
    await redis_client.setex(
        f"ctx:{context_hash}", 60,
        self._serialize_for_cache(result))
```

---

## 五、双脑路由增强

### 5.1 当前路由架构评估

| 组件 | 现状 | 评价 |
|------|------|------|
| IntentRouter | Haiku 两轴分类 + 补全 | 两次串行 LLM 调用增加延迟 |
| FastWorker | Haiku 处理 ~80% 流量 | 支持 agentic 模式，但 max_turns 耗尽后无升级路径 |
| HybridWorker | 快答 + 后台增强 | 30s 冷却期合理，但粒度可更细 |
| AgentWorker | Sonnet + SDK | SDK 池化已解决冷启动问题 |

### 5.2 路由优化：合并分类+补全

将 IntentRouter 的两次串行 LLM 调用合并为一次：

```python
# intent_router.py 改造

UNIFIED_CLASSIFICATION_PROMPT = """你是家庭助手的请求分类器。

## 任务
分析用户输入，输出以下信息：

1. difficulty: immediate | thinking | unsure
2. action: lookup | create | greet | chat | weather | time | plan | analyze | transact
3. enhance: true | false (是否需要深度建议)
4. confidence: 0.0-1.0
5. lookup_target: task | reminder | schedule | trip | member | today | unknown
6. lookup_filter: 关键实体或过滤条件 (从当前消息和对话上下文推断)
7. reasoning: 一句话解释

{context_block}

## 重要
- lookup_filter 必须从当前消息和对话上下文中推断，不要留空
- 如果无法确定某个字段，设为默认值而非 null

## 输出（严格JSON）：
{{"difficulty":"...","action":"...","enhance":...,"confidence":...,"lookup_target":"...","lookup_filter":null,"reasoning":"..."}}
"""
```

**效果**: 路由延迟从 ~400ms (2次 Haiku) 降至 ~200ms (1次 Haiku)。

### 5.3 Fast→Slow 升级机制

**问题**: `fast_worker.py` 的 agentic 循环耗尽 `max_turns` 后返回 fallback text，不会升级到 Slow Path。

**方案**: 增加升级信号检测：

```python
# fast_worker.py 改造

async def _fast_agentic(self, ...):
    for turn in range(self._fast_agentic_max_turns):
        response = await self._call_llm(...)

        if response.stop_reason == "end_turn":
            return response  # 正常完成

        # 处理工具调用...

    # max_turns 耗尽: 检测是否应升级
    if self._should_upgrade_to_slow(messages, user_message):
        # 发出升级信号
        return FastWorkerResult(
            status="upgrade_to_slow",
            partial_context=messages,  # 传递已有上下文
            reason="tool_limit_exceeded",
        )

    # 真正无需升级的场景: 返回 fallback
    return FastWorkerResult(status="complete", text=fallback_text)


def _should_upgrade_to_slow(self, messages, user_message) -> bool:
    """检测当前任务是否超出 Fast Path 能力。"""
    # 检测信号: 多步规划、复杂分析、跨域查询
    tool_calls = [m for m in messages if m.get("role") == "assistant"
                  and m.get("tool_use")]
    unique_tools = {tc["name"] for msg in tool_calls for tc in msg.get("tool_use", [])}
    return len(unique_tools) >= 3  # 使用了 3+ 种不同工具
```

**路由层集成**: 在 `chat_handler.py` 中处理 `upgrade_to_slow` 信号，将已有上下文传递给 AgentWorker。

### 5.4 路由决策流程图 (V8.0)

```
用户消息
    │
    ▼
[Redis 热会话检测]
    │
    ├── 有热会话? → 直走 Slow Path (保持对话连续性)
    │
    └── 无热会话? → [Haiku 统一分类 (1次调用)]
                        │
                        ├── FAST (difficulty=immediate, confidence > 0.8)
                        │     │
                        │     ├── 正常完成 → SSE 返回
                        │     │
                        │     └── max_turns 耗尽 → [升级检测]
                        │           ├── 需升级 → 异步提交 Slow Path (带已有上下文)
                        │           └── 不升级 → fallback 返回
                        │
                        ├── HYBRID (difficulty=immediate, enhance=true)
                        │     └── 快答 SSE + 后台 Sonnet 增强
                        │
                        └── SLOW (difficulty=thinking / unsure)
                              └── Celery → Sonnet SDK Agent
```

---

## 六、可靠性与一致性

### 6.1 幂等写入 (继承 V7.0 curation-accuracy 设计)

现有 `curation-accuracy-idempotency-design.md` 中的 DiffApply 方案已为策展模块设计了完整的幂等架构。V8.0 将此模式扩展到记忆模块：

| 模块 | 幂等键 | 指纹字段 | 状态 |
|------|--------|---------|------|
| curated_events | `stable_key` | `source_fingerprint` + `semantic_fingerprint` | 已设计，待实现 |
| event_associations | `association_key` | `version` | 已设计，待实现 |
| conversation_memories | `content_hash` (新增) | `embedding` similarity | 需新增 |
| secretary_notes | `title_hash` (现有 pg_trgm 去重) | `content` similarity | 已有基础 |

### 6.2 Anti-Hallucination 策略

针对 LLM 生成内容的可靠性：

| 场景 | 策略 | 实现 |
|------|------|------|
| L1 事实写入 | FactVerificationGate (见 2.3) | 新建 |
| 策展去重 | LLM 失败不 fallback 到 heuristic | V7.0 已设计 |
| 记忆提取 | 置信度阈值 + 源追溯 | 改造 extraction |
| 对话回复 | Agent SDK 已有 `max_turns` 保护 | 现有 |

### 6.3 反馈闭环

跨轮次的用户反馈（dismiss/confirm/snooze）必须持久化并影响后续行为：

**现有机制**:
- `memory_config.feedback_max_dismiss_count = 5` (记忆)
- `insight_feedbacks` 表 (洞察)

**V8.0 增强**:
- 继承 V7.0 的 `association_feedback_memory` 表 (策展)
- ContextAssembler 的 Step 3 (Filter) 统一消费所有反馈源
- 反馈跨模块聚合：同一实体在不同模块的反馈共享

```python
# ExclusionFilter 逻辑
class ExclusionFilter:
    async def should_exclude(self, item: ContextItem, user_id: UUID,
                              resolved_entity_ids: Set[UUID] = None) -> bool:
        """排除过滤 — 基于 Entity ID 匹配，而非原始字符串。

        重要: resolved_entity_ids 来自 ContextAssembler Step 0 的实体链接结果，
        已完成指代消解（"他"→张总）和别名归一（"张总"/"老张"→同一 person_id）。
        排除规则匹配使用 target_id (UUID)，避免代词/别名导致误拦截。
        """
        # 1. 检查排除规则 (基于 target_id 而非 name_string)
        exclusion = await self._check_exclusion_rule(
            item.family_id, item.target_type, item.target_id)
        if exclusion:
            # L2 显式点名覆盖 (Override): 用户在对话中提到了被排除的实体
            if resolved_entity_ids and item.target_id in resolved_entity_ids:
                await self._record_override(exclusion)
                return False  # 不排除
            return True  # 排除

        # 2. 检查 insight_feedbacks: 该实体最近是否被 dismiss
        # 3. 检查 association_feedback_memory: 该关联是否被 dismiss
        # 4. 检查 memory.feedback_weight < 0.3: 该记忆是否被多次负反馈
        # 5. 检查冷却期: 该建议类型是否在冷却期内
        ...
```

---

## 七、可扩展性

### 7.1 嵌入缓存优化

**问题**: `embedding_service.py` 使用进程内 dict 缓存 (max 1000)，多 worker 不共享。

**方案**: 迁移到 Redis 共享缓存：

```python
# embedding_service.py 改造

class EmbeddingService:
    CACHE_TTL = 86400  # 24h

    async def get_embedding(self, text: str) -> List[float]:
        cache_key = f"emb:{hashlib.md5(text.encode()).hexdigest()}"

        # Redis 缓存查找
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        # API 调用
        embedding = await self._generate_embedding(text)

        # 写入 Redis (异步，不阻塞)
        await redis_client.setex(cache_key, self.CACHE_TTL,
                                  json.dumps(embedding))
        return embedding
```

### 7.2 记忆量级规划

| 阶段 | 单家庭记忆量 | 召回延迟目标 | 方案 |
|------|------------|------------|------|
| 当前 | < 1K | < 500ms | ARRAY(Float) + 内存过滤 |
| V8.0 Phase 1 | 1K-10K | < 200ms | pgvector HNSW + Token 预算裁剪 |
| V8.0 Phase 2 | 10K-100K | < 100ms | pgvector IVFFlat + 分区表 |
| 远期 | 100K+ | < 50ms | 独立向量库 (Qdrant/Weaviate) |

### 7.3 轻量 GraphRAG

**问题**: 现有 `memory_associations` + `relationship_edges` 是简单的关联表，无法支持复杂的图检索。

**V8.0 方案**: 在现有表结构上增加最短路径查询和关联聚合能力，不引入外部图数据库：

```python
# 利用 PostgreSQL 递归 CTE 实现 BFS
async def find_related_context(self, entity_name: str,
                                max_hops: int = 2) -> List[GraphNode]:
    """
    从给定实体出发，BFS 遍历 memory_associations 和 relationship_edges，
    返回 max_hops 跳内的关联上下文。
    """
    query = text("""
    WITH RECURSIVE graph AS (
        SELECT source_id, target_id, relationship_type, 1 as depth
        FROM memory_associations
        WHERE family_id = :family_id AND source_id = :entity_id

        UNION ALL

        SELECT ma.source_id, ma.target_id, ma.relationship_type, g.depth + 1
        FROM memory_associations ma
        JOIN graph g ON ma.source_id = g.target_id
        WHERE g.depth < :max_hops
    )
    SELECT DISTINCT target_id, relationship_type, depth
    FROM graph ORDER BY depth
    """)
```

---

## 八、安全与隐私

### 8.1 记忆隐私分级

**新增字段**: `conversation_memories.sensitivity_level`

```python
class SensitivityLevel(str, Enum):
    PUBLIC = "public"        # 可自由进入 LLM context
    FAMILY = "family"        # 仅同家庭可见
    PRIVATE = "private"      # 仅创建者可见
    SENSITIVE = "sensitive"  # 不进入 LLM context，仅 UI 展示
```

**默认分类规则**:
- `FAVOR` 类型记忆 → `FAMILY`
- `HEALTH` 类型记忆 → `PRIVATE`
- `EMOTION` 类型记忆 → `PRIVATE`
- 含金融/医疗实体 → `SENSITIVE`
- 其他 → `PUBLIC`

**ContextAssembler 集成**: Step 3 (Filter) 中根据 `sensitivity_level` 过滤。

### 8.2 隐私推断防护 (Privacy Inference Protection)

**问题**: 即使隐藏了家庭成员的具体信息（如位置），LLM 推理可通过间接信息反推隐私数据。例如建议"在两地中间约饭"，用户可从中间点反推另一方位置。

**方案**: 涉及未授权共享信息的协同编排，采用"黑箱计算"模式：

```python
# 文件: backend/src/ai_engine/context_assembler.py - _apply_filters() 中

class PrivacyInferenceGuard:
    """防止 LLM 通过推理泄露成员隐私。

    对于未授权共享具体信息的成员：
    - 不将可推断数据传入 LLM prompt
    - 推荐结果由系统后端直接计算
    - 展示为确认框，不暴露推算过程
    """

    async def sanitize_for_llm(self, context_items: List[ContextItem],
                                privacy_settings: dict) -> List[ContextItem]:
        for item in context_items:
            if item.source_member_id:
                member_privacy = privacy_settings.get(item.source_member_id)
                if member_privacy and not member_privacy.get("share_location"):
                    item.remove_fields(["location", "coordinates", "address"])
                if member_privacy and not member_privacy.get("share_schedule"):
                    item.remove_fields(["schedule_gaps", "free_slots"])
        return context_items
```

**落点**: `context_assembler.py` 的 Step 3 (Filter) 中集成。

### 8.3 审计日志

所有 L1 写入和敏感操作记录审计日志：

```python
# 审计事件类型
AUDIT_EVENTS = [
    "l1_note_created",      # 新事实写入
    "l1_note_modified",     # 事实修改
    "l1_note_deleted",      # 事实删除
    "memory_shared",        # 记忆跨家庭共享
    "context_assembled",    # 上下文装配 (含注入的记忆 ID 列表)
    "privacy_downgrade",    # 隐私级别降低
]
```

---

## 九、实施路线图

### Phase 1: 基座 (2 周)

| 任务 | 优先级 | 工作量 | 落点文件 |
|------|--------|--------|---------|
| TokenBudget + 估算函数 + 任务类型动态分配 | P0 | 2d | `ai_engine/context_assembler.py` (新建) |
| ContextAssembler 框架 (含 Entity Linking + L3 时间戳守卫) | P0 | 4d | `ai_engine/context_assembler.py` |
| L1 NoteLifeType + valid_until 字段 | P0 | 1d | `memory/secretary_note_service.py` + migration |
| IntentRouter 合并两次调用 | P1 | 1d | `ai_engine/router/intent_router.py` |
| L3 superseded_by 修复 | P1 | 1d | `memory/consolidation_service.py` |
| SUPERSEDED 状态过滤 | P1 | 0.5d | `memory/recall_service.py` |

### Phase 2: 增强 (2 周)

| 任务 | 优先级 | 工作量 | 落点文件 |
|------|--------|--------|---------|
| FactVerificationGate | P0 | 2d | `memory/fact_verification.py` (新建) |
| ImpactArbitrator | P1 | 2d | `curation/services/impact_arbitrator.py` (新建) |
| DirtyBitManager | P1 | 2d | `curation/services/dirty_bit_manager.py` (新建) |
| Fast→Slow 升级机制 | P1 | 2d | `ai_engine/workers/fast_worker.py` |
| pgvector 优先使用 | P2 | 1d | `memory/recall_service.py` |

### Phase 3: 安全与可观测 (1 周)

| 任务 | 优先级 | 工作量 | 落点文件 |
|------|--------|--------|---------|
| sensitivity_level 字段迁移 | P1 | 1d | Alembic migration |
| PrivacyFilter + ExclusionFilter (基于 Entity ID) | P1 | 2d | `ai_engine/context_assembler.py` |
| PrivacyInferenceGuard (隐私推断防护) | P1 | 1d | `ai_engine/context_assembler.py` |
| CommitmentPreFilter (承诺预过滤门) | P1 | 1d | `modules/memory/commitment_service.py` (新建) |
| 信任降级 ReflectionLog | P2 | 1d | `modules/member/trust_service.py` |
| 嵌入 Redis 缓存迁移 | P2 | 1d | `memory/embedding_service.py` |
| 观测指标 (Prometheus) | P2 | 1d | `core/observability/metrics.py` |

### Phase 4: 优化 (1 周)

| 任务 | 优先级 | 工作量 | 落点文件 |
|------|--------|--------|---------|
| Context Hash 缓存 | P2 | 1d | `ai_engine/context_assembler.py` |
| pgvector 回填脚本 | P2 | 1d | Alembic migration |
| 轻量 GraphRAG 递归 CTE | P3 | 2d | `memory/recall_service.py` |
| HybridWorker 细粒度冷却 | P3 | 1d | `ai_engine/router/intent_router.py` |

---

## 十、KPI 与验收标准

### 10.1 性能指标

| 指标 | 当前 | V8.0 目标 | 测量方式 |
|------|------|----------|---------|
| 路由延迟 (P95) | ~400ms | < 250ms | IntentRouter timing |
| 上下文装配延迟 (P95) | 无测量 | < 500ms | ContextAssembler timing |
| 语义搜索延迟 (P95) | O(n) 无基线 | < 50ms (pgvector) | recall_service timing |
| Fast Path 覆盖率 | ~70% | > 80% | 路由统计 |
| Slow Path 冷启动 | ~68s (已池化) | < 5s (池化稳态) | AgentWorker timing |

### 10.2 质量指标

| 指标 | 当前 | V8.0 目标 | 测量方式 |
|------|------|----------|---------|
| L1 事实准确率 | 无测量 | > 95% | 用户 confirm/reject 比 |
| 记忆召回相关性 | 无测量 | > 85% (用户感知) | 对话反馈 + 抽样 |
| dismiss 复发率 | 无测量 | < 1% | ExclusionFilter 统计 |
| 策展幂等性 (noop ratio) | 无基线 | > 95% (无变化时) | DiffApply 统计 |
| Token 预算超限率 | 100% (无预算) | < 5% | ContextAssembler 统计 |

### 10.3 观测仪表板

```
┌─────────────────────────────────────────────────────────┐
│ V8.0 AI 子系统监控仪表板                                  │
│                                                         │
│ [路由分布] FAST: 82% | HYBRID: 8% | SLOW: 10%          │
│ [升级率]   Fast→Slow: 2.3%                              │
│                                                         │
│ [上下文装配]                                              │
│ 平均 Token 使用: 4200/6000 (70%)                         │
│ L1: 480 | L2: 1800 | L3: 720 | L4: 1200                │
│ 缓存命中率: 35%                                          │
│                                                         │
│ [触发器]                                                 │
│ T1 即时: 12/h | T2 延迟: 45/h | T3 定期: 2/day          │
│ 脏位队列深度: 3 families                                  │
│ ShouldRun skip rate: 67%                                │
│                                                         │
│ [记忆健康]                                                │
│ L4 总量: 2,847 | 活跃: 2,103 | 合并: 621 | 淘汰: 123    │
│ L1 事实: 89 | 已确认: 76 (85%) | 待确认: 13             │
│ 语义搜索 P95: 42ms                                       │
│                                                         │
│ [反馈闭环]                                                │
│ dismiss 复发率: 0.3%                                     │
│ 用户满意度: 4.2/5                                        │
└─────────────────────────────────────────────────────────┘
```

---

## 附录 A: 文件变更清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| **新建** | `src/ai_engine/context_assembler.py` | 统一上下文装配器 (含 Entity Linking, L3 时间戳守卫, 隐私推断防护) |
| **新建** | `src/modules/memory/fact_verification.py` | L1 事实验证门 |
| **新建** | `src/modules/memory/commitment_service.py` | 承诺预过滤门 (CommitmentPreFilter + SocialIntentParser 联动) |
| **新建** | `src/modules/curation/services/impact_arbitrator.py` | 影响评估器 |
| **新建** | `src/modules/curation/services/dirty_bit_manager.py` | 脏位管理器 (含防饥饿机制) |
| **改造** | `src/ai_engine/router/intent_router.py` | 合并两次 LLM 调用 |
| **改造** | `src/ai_engine/workers/fast_worker.py` | Fast→Slow 升级 |
| **改造** | `src/modules/memory/consolidation_service.py` | superseded_by 修复 |
| **改造** | `src/modules/memory/recall_service.py` | SUPERSEDED 过滤 + pgvector 优先 |
| **改造** | `src/modules/memory/embedding_service.py` | Redis 共享缓存 |
| **改造** | `src/modules/memory/secretary_note_service.py` | NoteLifeType + valid_until + TransientFactManager |
| **改造** | `src/modules/curation/services/trigger_dispatcher.py` | T1/T2/T3 分级 |
| **改造** | `src/modules/curation/services/should_run_service.py` | 集成 ImpactArbitrator |
| **改造** | `src/modules/member/trust_service.py` | 信任降级 ReflectionLog |
| **迁移** | `src/db/migrations/` | sensitivity_level, content_hash, life_type, valid_until 字段 |

## 附录 B: 与 V6.0/V7.0 的对照

| V6.0/V7.0 提案 | V8.0 采纳情况 | 理由 |
|----------------|-------------|------|
| 四层记忆 (L1-L4) | **采纳，重新定义层边界** | 映射到现有表结构而非新建 |
| ContextAssembler 五步管道 | **采纳** | 统一分散的上下文装配 |
| TokenBudget | **采纳，简化估算** | 用中文字符估算替代 tiktoken |
| ExclusionEngine / ExclusionLedger | **简化为 ExclusionFilter** | 在 ContextAssembler 内实现，不独立服务 |
| FactVerificationGate | **采纳** | L1 写入必须验证 |
| DirtyBitManager | **采纳** | Redis HASH 实现 |
| T1/T2/T3 触发分级 | **采纳，映射到现有 trigger_dispatcher** | 正式定义现有的隐式分级 |
| ImpactArbitrator | **采纳，规则化** | 基于规则而非 LLM 评估 |
| Context_Hash 缓存 | **采纳，Phase 4** | 低优先级优化 |
| 独立 GraphRAG 服务 | **降级为 PostgreSQL 递归 CTE** | 当前数据量不需要外部图数据库 |
| Action Protocol (指令分离) | **已有 PendingAction 机制** | 不需额外改造 |
| 周级 KPI 看板 | **采纳** | Prometheus + Grafana |

### V8.1 补充改进 (逻辑风险修复)

| 改进项 | 来源 | 采纳情况 | 说明 |
|--------|------|---------|------|
| Entity Linking (指代消解+别名归一) | 逻辑审查 | **采纳，Phase 1** | ExclusionFilter 必须基于 Entity ID 而非字符串匹配 |
| L3 时间戳守卫 (Timestamp Guard) | 逻辑审查 | **采纳，Phase 1** | 防止 L2/L3 语义重叠浪费 Token |
| L1 NoteLifeType (PERMANENT/TRANSIENT) | 逻辑审查 | **采纳，Phase 1** | 阶段性事实不覆盖长期偏好 |
| CommitmentPreFilter (承诺预过滤门) | 逻辑审查 | **采纳，Phase 3** | CommitmentTracker 必须依赖 SocialIntentParser 评分 |
| Token 预算任务类型动态调整 | 逻辑审查 | **采纳，Phase 1** | 避免固定分配导致的预算死锁 |
| DirtyBit 防饥饿机制 | 逻辑审查 | **采纳，Phase 2** | Redis 定时键 + Celery Beat 巡检确保超时刷新 |
| 隐私推断防护 (PrivacyInferenceGuard) | 逻辑审查 | **采纳，Phase 3** | 黑箱计算防止间接推断泄露位置等隐私 |
| 信任降级 ReflectionLog | 逻辑审查 | **采纳，Phase 3** | 降级时生成反思记录，驱动系统自我修正 |

---

> **文档状态**: 提案 (Draft)
> **下一步**: 团队评审 → 确认优先级 → Phase 1 启动
