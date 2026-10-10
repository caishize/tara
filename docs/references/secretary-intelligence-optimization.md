# Secretary Intelligence Optimization Plan

> 基于代码深度审计（6 模块 15,000+ 行）与四角色团队讨论的完整优化方案
>
> 团队构成：资深秘书顾问 · 移动产品用户代言人 · AI 上下文工程专家 · 研发架构师
>
> 核心目标：让 AI 秘书从"事件列表管理器"进化为"具备判断力、预见性和沟通艺术的智能管家"

---

## 一、问题验证与诊断

### 1.1 Gemini 分析验证结论

经过对 6 个核心模块（curation、briefing、insight、memory、views、ai_engine）的逐行审计，**Gemini 提出的所有问题均经验证为真实存在**，且实际问题范围远超其分析。

| Gemini 原始诊断 | 验证结果 | 实际严重程度 |
|---|---|---|
| 优先级判断硬编码 | **部分确认** — `priority_score.py` 4 维加权公式默认权重固定，但 `compute_priority_score()` 已接受 `weights` 参数可覆盖，`PriorityScore` 有 `w_*_override` 字段。**问题是所有调用方均未传入自定义权重**，基础设施已就绪但未接线。 | 缺少跨事件依赖分析、准备链传播、精力预算；需要增加的是 FamilyPreference → 权重传递的接线，而非重写评分引擎 |
| 缺乏动态编排层 | **确认** — curation pipeline 只做列表整理，无当日动态编排 | 比描述更严重：`ContextEnricher` 已构建丰富 `EventContext` 但 briefing 从未使用（死代码） |
| 需要实时影子再策展 | **部分确认** — `EventService` 在 create/update/delete/cancel 后通过 `_trigger_event_curation()` 触发异步全量再策展（Celery 任务），并有 `mini_curate` 方法做单事件同步策展。**但这是重量级全量管线重跑，非轻量级实时重排。** | 缺少的是：① 无外部日历持续监听，② 无轻量增量重排（当前是全量 collect→dedup→conflict→save），③ 无基于时间推进的自动提权（如事件临近时自动升高优先级） |
| 反馈闭环缺失 | **部分确认** — `InsightFeedbackLearner`（briefing 模块）**已接入** `InsightOrchestrator._apply_feedback_and_save()`，可读取 `suppressed_types` 和 `adjusted_weights`，基础反馈闭环工作正常。**但** `FeedbackService.should_suppress_insight()` 和 `FeedbackLearningService.analyze_user_preferences()` 是死代码（无调用方）。反馈仍未触达优先级评分、关联发现或上下文组装层。 |

### 1.2 审计发现的额外系统性问题

以下问题 Gemini 未识别到，由四角色团队讨论确认为关键缺陷：

**A. 三套建议系统并行但只用最弱的一套**（架构师 + 用户代言人共同发现）
- `SuggestionGenerator`（纯规则硬编码，被 daily briefing 使用）→ 用户看到的是 "今天的事项已告一段落，辛苦了" 这种无个性化的罐头文案
- `SmartSuggestionService`（11 策略引擎，**未被 daily briefing 调用**）→ 有 PersonStrategy、GiftStrategy、FavorStrategy 等丰富策略，全部闲置
- `BriefingGenerator`（LLM 驱动，**未被 daily briefing 调用**）→ 能产生个性化洞察，全部闲置
- 代码位置：`briefing/services/suggestion_generator.py` vs `suggestion_service.py` vs `briefing_generator.py`

**B. L4 上下文获取未使用语义搜索**（上下文工程师发现，P0 级别）
- `context_fetchers.py:~240` 有注释 `"upgrade to semantic_search when embedding infrastructure is available"`
- 但 pgvector HNSW 索引已在 memory 模块中部署运行，`MemoryRecallService._semantic_search()` 已实现
- 用户说 "工作压力好大" 无法召回 "办公室加班到凌晨" 的记忆，因为无词汇重叠
- **这是整个系统最大的质量缺口**

**C. 情绪检测仅 8 个关键词**（秘书顾问 + 上下文工程师共同发现）
- 硬编码：`["压力", "焦虑", "烦", "累", "困扰", "担心", "烦躁", "沮丧"]`
- 无法识别：`"心情不好"`, `"受不了了"`, `"开心不起来"`, `"七上八下"`, `"拿不准"` 等含蓄表达
- 代码位置：`insight_service.py:258`

**D. 压力检测计数所有情绪/工作记忆（含正面）**（上下文工程师发现）
- `_check_stress_pattern()` 查询 `memory_type IN (emotion, work)` 无情感极性过滤
- "今天升职了好开心" 也会被计为压力信号
- 代码位置：`proactive_insight_service.py:288-325`

**E. 记忆敏感度分类从未被调用**
- `classify_sensitivity()` 定义了 4 级分类（PUBLIC/FAMILY/PRIVATE/SENSITIVE）
- 但 `extraction_service.py` 的 `_store_single_memory()` **从不调用它**，所有记忆默认 PUBLIC
- 代码位置：`memory/models.py:156-182`（定义）vs `extraction_service.py:340-400`（未调用）

**F. Agent 主系统 Prompt 是全系统最弱的 Prompt**（上下文工程师发现）
- `agent_factory.py:91-111` 的 `SYSTEM_PROMPT_TEMPLATE` 只有 "你是一个智能家庭秘书助手" + 4 条泛泛指令
- 而策展 Prompt（`DEDUP_SYSTEM_PROMPT`, `ENHANCED_ASSOCIATION_PROMPT`）有详细人设、规则、反面案例
- 主 Agent Prompt 应该是全系统最精心设计的，但实际最粗糙
- 缺失：人设深度、理想回复示例、情绪感知指令、主动/被动平衡指导

**G. 中文关键词提取无分词**（上下文工程师发现）
- `recall_service.py:575-585` 的 `_extract_keywords()` 用正则 `re.findall(r'[\u4e00-\u9fff]{2,4}', text)` 提取关键词
- `re.findall` 做贪心非重叠匹配，会把不相关的字符合并为 2-4 字符块：如 "我下周去杭州出差见李明" 产出 `["我下周去", "杭州出差", "见李明"]`，其中 "我下周去" 不是有效词
- 核心问题：无中文分词，词边界完全错误，stop_words 过滤无法补偿
- 修复：引入 jieba（~200KB，0 延迟）进行中文分词

**H. Token 估算在英文/混合文本场景浪费上下文空间**（上下文工程师发现）
- `context_assembler.py:40-54` 的 `estimate_tokens()` 使用字符级启发式：中文字符 ×1.5，其他字符 ×0.3
- 中文场景（本项目主要场景）：1.5 token/字符 基本准确（Claude tokenizer 对 CJK 通常 1.0-2.0 token/字符）
- 英文/混合场景：0.3 token/字符 高估约 20-50%（实际英文约 0.2-0.25 token/字符），可能浪费 15-30% 预算
- 当前无 tiktoken 等真实 tokenizer 依赖（全项目 grep 确认）
- **对纯中文对话影响较小，但当上下文含大量英文（如代码片段、外文地名）时浪费明显**

**I. 农历日期循环计算——两条路径不一致**
- **已修复路径**：`DateService._compute_next_occurrence()` 委托 `ImportantDate.get_next_occurrence()` 模型方法（`date_models.py:88-134`），使用 `lunarcalendar.Converter.Lunar2Solar()` 正确转换农历→阳历，每年计算当年对应的阳历日期
- **仍有 Bug 的路径**：`ImportantDateRepository._get_next_occurrence()`（`date_repository.py:119-123`）注释写 `# For now, use the stored solar_date`，直接取 `lunar_month/lunar_day` 当作阳历月/日使用，导致农历八月十五永远变成 9 月 15 日
- **风险**：`DateRepository.get_upcoming_dates()` 调用的是 repository 内的错误路径；`DateService.get_upcoming()` 调用的是正确路径。两个 API 返回不同结果
- 此外，模型方法的 `except Exception: pass` 静默回退意味着当 `lunarcalendar` 库不可用时会无声降级为错误行为

**J. Insight 去重是精确标题匹配，语义重复不识别**（用户代言人发现）
- `InsightOrchestrator._dedup_insights()` 用 `(title, insight_type)` 匹配
- "记得联系李叔叔" 和 "你已经很久没和李叔叔说话了" 不被去重，因为标题不同
- 而系统已有 3072 维 embedding 基础设施可复用

**K. 上下文组装无跨层交互**（上下文工程师发现）
- L4 结果不影响 L3 选择：L4 召回 "王伟在北京" 的记忆，但 L3 不会优先加载王伟的人物画像
- 无查询理解层：原始用户消息直接传入 L4，未提取意图和话题

---

## 二、优化架构全景

### 2.1 架构层次图

```
用户请求 / 日程变更
    ↓
┌──────────────────────────────────────────────────────────┐
│              统一智能管线（6 阶段）                          │
│                                                           │
│  Stage 1: 数据收集 → LLM 去重 → 存储 (现有, 保持不变)       │
│       ↓                                                   │
│  Stage 2: 混合优先级引擎 (规则80% + LLM校准20%)    ← NEW   │
│    ├─ 常规事件: 现有 compute_priority_score + 家庭权重覆盖   │
│    ├─ 模糊事件(分数0.35-0.65): Haiku 校准(批量5个,~80ms)   │
│    └─ 校准内容: 准备链、精力预算、跨事件依赖、秘书批注       │
│       ↓                                                   │
│  Stage 3: 秘书编排层                               ← NEW   │
│    ├─ 时间块编排: 缓冲、通勤、休息                          │
│    ├─ 秘书批注: 接入已有死代码 ContextEnricher              │
│    ├─ 负荷评估: density_score 0-1                          │
│    └─ 级联分析: 事件变更影响传播                             │
│       ↓                                                   │
│  Stage 4: 统一推荐引擎 (合并3系统)                  ← NEW   │
│    ├─ 13 策略并行 (asyncio.gather)                         │
│    ├─ LLM 语义去重 (复用 3072-dim embedding)               │
│    ├─ 反馈学习过滤 (真正应用 FeedbackLearning 结果)         │
│    └─ 情绪感知调整                                         │
│       ↓                                                   │
│  Stage 5: 信息密度适配                              ← NEW   │
│    ├─ 规则驱动(无LLM): 日程密度 × 时段 × 情绪状态          │
│    ├─ 忙碌日(density>0.8): max 3 推荐, 折叠低优先级        │
│    └─ 空闲日(density<0.4): max 7 推荐, 含探索性内容        │
│       ↓                                                   │
│  Stage 6: 反馈闭环                                  ← NEW   │
│    ├─ FeedbackBus: 12 种信号, 4 个消费者                   │
│    ├─ FamilyPreference: 从行为自动学习的规则库              │
│    └─ PreferenceLearner: 每日批量归纳 (Celery task)        │
└──────────────────────────────────────────────────────────┘
    ↓
  Briefing / Chat Context / Push / Timeline
```

### 2.2 新增核心组件

| 组件 | 文件 | 职责 | 替代/增强对象 |
|---|---|---|---|
| `HybridPriorityEngine` | `curation/services/priority_engine.py` | 规则(80%) + LLM 校准(20%)的混合优先级 | 增强 `priority_score.py` |
| `SecretaryOrchestrator` | `curation/services/orchestrator.py` | 日程编排、缓冲计算、级联分析、秘书批注 | 全新；接入已有死代码 `ContextEnricher` |
| `RecommendationEngine` | `briefing/services/recommendation_engine.py` | 合并 3 套建议/洞察系统为统一推荐引擎 | 替代 `SuggestionGenerator` + `SmartSuggestionService` + `InsightOrchestrator` |
| `DensityController` | `briefing/services/density_controller.py` | 自适应信息密度控制 | 全新 |
| `FeedbackBus` | `core/feedback/feedback_bus.py` | 反馈信号分发总线 | 扩展现有 `InsightFeedbackLearner` 的反馈到优先级/关联/上下文层，替代死代码 `FeedbackLearningService` |
| `FamilyPreference` | `curation/models/family_preference.py` | 个性化规则库（学习型） | 全新 |
| `EmotionUnderstandingService` | `memory/services/emotion_understanding.py` | LLM 驱动的情绪理解 | 替代 8 关键词硬编码 |

---

## 三、优化方案详细设计

### 3.1 混合优先级引擎

#### 3.1.1 核心理念

**不用 LLM 替换所有规则，而是用 LLM 校准模糊区间。** 80% 的事件（明确高/低优先级）继续走现有规则引擎（零延迟、零成本），只有 20% 的模糊事件（composite 0.35-0.65）和高复杂度事件（3+ associations）才触发 Haiku 校准。

#### 3.1.2 问题场景

**场景 1：准备链传播**
> 周三有商务晚宴，需要周一买礼物、周二确认餐厅、周三上午准备谈话要点。现有系统独立评分，"买礼物" 被评为 P3（不紧急），但它是整条链的瓶颈。

**场景 2：精力预算**
> 周一有 3 个高强度事件。现有系统分别评 P1/P1/P2，不知道第三个事件时用户已精力耗尽。

**场景 3：人情动态权重**
> 领导的会议邀请比同事聚餐重要 10 倍，但现有系统只看 event_type（都是 meeting = 0.7）。

#### 3.1.3 接口设计

```python
# 文件: src/modules/curation/services/priority_engine.py

class HybridPriorityEngine:
    """
    双层优先级评分:
    - 快速层: 现有 compute_priority_score() + FamilyPreference 权重覆盖
    - 校准层: Haiku 对模糊事件进行上下文感知校准
    """

    async def score(
        self,
        event_data: dict,
        member_context: dict | None,
        family_id: UUID,
        family_prefs: FamilyPreference | None = None,
    ) -> EnhancedPriorityScore:
        # Step 1: 规则评分（现有逻辑，快速）
        weights = family_prefs.priority_weights if family_prefs else None
        base_score = compute_priority_score(event_data, member_context, weights=weights)

        # Step 2: 判断是否需要 LLM 校准
        if self._needs_calibration(base_score, event_data):
            calibration = await self._get_calibration(event_data, member_context, family_prefs)
            if calibration and calibration.confidence >= 0.6:
                return self._apply_calibration(base_score, calibration)

        return EnhancedPriorityScore(base=base_score, calibration=None)

    def _needs_calibration(self, score, event_data) -> bool:
        """仅校准模糊区间和高复杂度事件。"""
        composite = score.composite
        if 0.35 <= composite <= 0.65:
            return True
        if event_data.get("association_count", 0) >= 3:
            return True
        return False
```

**LLM 校准 Prompt（Haiku，批量 5 个事件，~80ms）**

```
你是一位私人秘书，需要精确评估以下事件的优先维度。

## 评估维度（每项 0-1）
- severity: 对雇主事业/家庭/健康的实际影响
- stakeholder: 涉及的人对雇主有多重要（参考人物画像）
- irrecoverability: 错过/推迟的后果严重程度
- preparation_hours: 需要多少准备时间
- secretary_note: 一句话秘书提醒（可选）

## 雇主偏好
{family_preference_rules}

## 人物关系
{person_profiles_summary}

## 事件列表
{events_json}

输出 JSON 数组，每个元素包含 event_id, severity, stakeholder,
irrecoverability, preparation_hours, secretary_note, confidence
```

**缓存策略**
- Per-curation-run 内存缓存：同一次策展运行内事件不变
- Redis 缓存：`cal:type:{event_type}:family:{id}` → 24h TTL，同类型同家庭免重复校准
- 批量处理：每次 Haiku 调用最多 5 个事件，降低延迟

**降级**：LLM 失败时回退到现有 `compute_priority_score()`，结果标记 `fallback=True` 不写缓存

---

### 3.2 秘书编排层

#### 3.2.1 问题场景

**场景 1：缓冲时间**
> 10:00 朝阳区会议结束，14:00 海淀区客户拜访。现有系统只检测时间重叠。秘书会说："会议和拜访间有 4 小时，跨区通勤约 1 小时，建议 12:30 出发，途中可在 XX 附近午餐。"

**场景 2：负荷感知**
> 周二有 5 个事件。现有系统显示 "今天有 5 项日程"。秘书会说："今天日程非常满，建议将朋友聚餐改约周末，家长会可让配偶代参加。"

**场景 3：级联变更**
> 上午航班延误 2 小时。现有系统无法计算对下午会议和晚宴的级联影响。

#### 3.2.2 接口设计

```python
# 文件: src/modules/curation/services/orchestrator.py

@dataclass(frozen=True)
class TimeSlot:
    start: time
    end: time
    event_id: UUID | None      # None for buffer/free slots
    slot_type: str              # event | buffer | travel | free | preparation
    note: str | None            # 秘书批注

@dataclass(frozen=True)
class OrchestratedDay:
    date: date
    slots: list[TimeSlot]
    gaps: list[GapWarning]      # 问题间隙（无缓冲、通勤不可能等）
    annotations: list[SecretaryAnnotation]
    density_score: float        # 0-1，日程拥挤度
    suggested_reorder: list[UUID] | None  # 优化建议


class SecretaryOrchestrator:
    """
    将平铺事件列表转化为有结构的一天安排。

    关键设计：纯读路径组件，不修改策展数据，在 briefing 时运行。
    接入已有但未使用的 ContextEnricher 获取历史上下文和人物关系。
    """

    def __init__(self, db: AsyncSession, priority_engine: HybridPriorityEngine):
        self.db = db
        self.priority_engine = priority_engine
        # 接入已有死代码
        self._enricher = ContextEnricher(db, MemoryEngine(db))

    async def orchestrate_day(
        self,
        family_id: UUID,
        user_id: UUID,
        target_date: date,
        events: list[CuratedEvent],
        family_prefs: FamilyPreference | None = None,
    ) -> OrchestratedDay:
        """
        编排流程:
        1. 按优先级加权开始时间排序
        2. 插入缓冲时间块（location 变化 → 通勤，高强度事件后 → 休息）
        3. 检测间隙问题（无缓冲、通勤不可能、背靠背、超载）
        4. 通过 ContextEnricher 生成秘书批注（人物关系、历史上下文）
        5. 计算 density_score
        6. density > 0.8 时生成调整建议
        """

    async def analyze_cascade(
        self,
        changed_event: CuratedEvent,
        change_type: str,  # delayed | cancelled | location_changed | time_changed
        change_detail: dict,
        affected_events: list[CuratedEvent],
    ) -> CascadeAnalysis:
        """分析事件变更的级联影响，输出调整方案和需用户决策的项。"""

    async def build_preparation_timeline(
        self,
        anchor_event: CuratedEvent,
        preparation_items: list[PreparationItem],
    ) -> PreparationTimeline:
        """倒推准备时间线，每步有 deadline、建议执行时间、耗时估计、秘书提醒。"""
```

**缓冲时间规则**
- 默认：15 分钟（可通过 `FamilyPreference.buffer_minutes` 覆盖）
- 地点变化：30-60 分钟（根据城市距离估算）
- 高强度事件后：15-30 分钟休息
- 餐饮时间（12:00-13:30, 18:00-19:30）尽量保留

**集成方式**：在 `DailyBriefingService` 中替换平铺事件加载
```python
# 旧: today_events = await event_aggregator.get_today_events(...)
# 新:
raw_events = await event_aggregator.get_today_events(...)
orchestrated = await orchestrator.orchestrate_day(
    family_id, user_id, target_date, raw_events, family_prefs
)
```

---

### 3.3 统一推荐引擎

#### 3.3.1 设计理念

合并三套系统，采用 `SmartSuggestionService` 已有的策略模式架构（最成熟），加上 `InsightOrchestrator` 的 DB 持久化能力，加上 `BriefingGenerator` 的 LLM 生成能力。

#### 3.3.2 接口设计

```python
# 文件: src/modules/briefing/services/recommendation_engine.py

class RecommendationStrategy(Protocol):
    """可插拔的推荐策略协议。"""
    async def generate(
        self, user_id: UUID, family_id: UUID, context: RecommendationContext
    ) -> list[Recommendation]: ...

    @property
    def strategy_name(self) -> str: ...


class RecommendationEngine:
    """
    统一推荐引擎，替代 SuggestionGenerator + SmartSuggestionService + InsightOrchestrator。

    13 个策略并行执行（asyncio.gather），通过适配器模式逐步迁移，
    Phase 1-2 无任何破坏性变更。
    """

    def __init__(self, db: AsyncSession):
        self._strategies: list[RecommendationStrategy] = [
            # 从 InsightOrchestrator 迁移（System A/B/C）
            MemoryInsightStrategy(db),       # trip_correlation, emotion_pattern
            ProactiveInsightStrategy(db),    # relationship_maintenance, favor_reminder
            TimePreparationStrategy(db),     # 事件准备提醒
            # 从 SmartSuggestionService 迁移（11 策略）
            CurationStrategy(db),
            PreparationStrategy(db),
            LocationStrategy(db),
            PersonStrategy(db),
            AnniversaryStrategy(db),
            FavorStrategy(db),
            GiftStrategy(db),
            RelationshipStrategy(db),
            # 编排层新增
            ScheduleOptimizationStrategy(db),  # 从 OrchestratedDay.gaps 派生
            PeriodAwareStrategy(db),           # 早/午/晚时段调整
        ]

    async def generate(
        self,
        user_id: UUID,
        family_id: UUID,
        target_date: date | None = None,
        period: str | None = None,
        orchestrated_day: OrchestratedDay | None = None,
        limit: int = 10,
    ) -> list[Recommendation]:
        """
        生成统一推荐。流程:
        1. 构建共享上下文（情绪、抑制列表、类型权重）
        2. asyncio.gather 并行执行所有策略
        3. LLM 语义去重（复用 3072-dim embedding，相似度 >= 0.75 合并）
        4. 应用反馈权重（真正使用 FeedbackLearning 结果）
        5. 按 priority × type_weight 排序
        6. 时段过滤 + 密度过滤
        """
```

**语义去重**（修复标题精确匹配的缺陷）

```python
async def _semantic_dedup(self, recommendations: list[Recommendation]) -> list[Recommendation]:
    """
    用 embedding 相似度替代 (title, type) 精确匹配。
    复用 memory 模块已有的 text-embedding-3-large 基础设施。
    阈值 0.75：同一意图的不同表达会被合并。

    额外机制：
    - shown_count 计数器：同一主题出现 3 次未被操作 → 自动抑制 30 天
    - last_shown_at 冷却：dismissed → 7 天冷却，shown-but-ignored → 3 天冷却
    """
```

**反馈学习应用**（扩展现有闭环到推荐层）

```python
async def _apply_feedback_learning(self, recs: list[Recommendation], user_id: UUID):
    """
    扩展反馈闭环到推荐引擎（现有 InsightFeedbackLearner 只覆盖 Insight 层）。

    1. 从 FamilyPreference.recommendation_weights 加载类型权重（新增）
    2. 从 FamilyPreference.suppressed_types 加载抑制列表（新增）
    3. 复用 InsightFeedbackLearner 的 suppressed_types 和 adjusted_weights
    4. 过滤 + 权重调整 + 重新排序
    注：FeedbackService.should_suppress_insight() 为死代码，不再使用
    """
```

**迁移路径（4 阶段，适配器模式）**
1. Phase 1：创建 `RecommendationEngine` 包装现有策略（适配器，不改逻辑）
2. Phase 2：将 `DailyBriefingService` 接入 `RecommendationEngine`
3. Phase 3：废弃 `SmartSuggestionService` API，重定向
4. Phase 4：删除 `SuggestionGenerator` 死代码

---

### 3.4 闭环反馈系统

#### 3.4.1 断裂点诊断

**已工作的反馈路径**：`InsightFeedbackLearner`（briefing 模块）已接入 `InsightOrchestrator._apply_feedback_and_save()`，提供 `get_suppressed_types()` 和 `get_adjusted_weights()`。这条路径是工作的。

**仍断裂的反馈点**：

| 断裂点 | 代码位置 | 问题 |
|---|---|---|
| `FeedbackLearningService.analyze_user_preferences()` | `feedback_service.py:216-265` | 生成推荐但无消费者（死代码） |
| `should_suppress_insight()` | `feedback_service.py:182-205` | 存在但从未被调用（死代码，`InsightFeedbackLearner` 有独立实现） |
| 反馈未触达优先级评分 | — | Insight 反馈不影响 `compute_priority_score()` 权重 |
| 反馈未触达关联发现 | — | 不影响 `RuleBasedAssociationEngine` 策略选择 |
| 反馈未触达上下文组装 | — | 不影响 L3/L4 内容选取 |

#### 3.4.2 FeedbackBus 设计

```python
# 文件: src/core/feedback/feedback_bus.py

class FeedbackSignal(str, Enum):
    """12 种反馈信号。"""
    INSIGHT_USEFUL = "insight_useful"
    INSIGHT_IGNORED = "insight_ignored"        # 24h 未操作
    INSIGHT_NEVER_AGAIN = "insight_never_again"
    SUGGESTION_ACTED = "suggestion_acted"
    SUGGESTION_DISMISSED = "suggestion_dismissed"
    EVENT_RESCHEDULED = "event_rescheduled"
    EVENT_CANCELLED = "event_cancelled"
    BUFFER_ADJUSTED = "buffer_adjusted"
    PRIORITY_OVERRIDE = "priority_override"
    ANNOTATION_HELPFUL = "annotation_helpful"
    CONTACT_INITIATED = "contact_initiated"
    CONTACT_SKIPPED = "contact_skipped"


class FeedbackConsumer(Protocol):
    async def on_feedback(self, event: FeedbackEvent) -> None: ...

    @property
    def consumes_signals(self) -> list[FeedbackSignal]: ...


class FeedbackBus:
    """
    进程内反馈分发总线。挂接到现有 domain event 基础设施。
    不引入 Redis Streams 等新基础设施。
    """
```

**4 个消费者**

| 消费者 | 消费信号 | 学习内容 | 写入目标 |
|---|---|---|---|
| `PriorityFeedbackConsumer` | EVENT_RESCHEDULED, PRIORITY_OVERRIDE, EVENT_CANCELLED | 事件类型权重偏好 | `FamilyPreference.event_type_severity` |
| `AssociationFeedbackConsumer` | CONTACT_INITIATED, CONTACT_SKIPPED, ANNOTATION_HELPFUL, ANNOTATION_DISMISSED | 关联类型有效性 | `FamilyPreference.association_weights` |
| `RecommendationFeedbackConsumer` | INSIGHT_*, SUGGESTION_* | 推荐类型偏好与抑制 | `FamilyPreference.recommendation_weights`, `suppressed_types` |
| `BufferTimeFeedbackConsumer` | BUFFER_ADJUSTED | 缓冲时间偏好 | `FamilyPreference.buffer_minutes` |

**反馈信号流向全景**

```
用户操作                  信号类型              影响范围
─────────────────────────────────────────────────────────
点击"有用"               INSIGHT_USEFUL       → 记忆权重 +0.15
                                              → 同类推荐权重 ×1.1
                                              → 关联置信度 +0.1

忽略 24h 未操作          INSIGHT_IGNORED      → 同类推荐权重 ×0.98
                                              → shown_count +1
                                              → 3 次后自动抑制 30 天

点击"没用"               SUGGESTION_DISMISSED → 记忆权重 -0.1
                                              → 同类推荐权重 ×0.8
                                              → 连续 3 次 → 类型抑制 7 天

点击"不再提醒此类"        INSIGHT_NEVER_AGAIN  → 该类型永久抑制
                                              → 记入 FamilyPreference

确认 association          CONTACT_INITIATED    → association 置信度 → 1.0
                                              → 关联类型权重 +0.2

用户调整缓冲时间          BUFFER_ADJUSTED      → 更新对应事件类型的缓冲偏好
```

---

### 3.5 个性化规则库（FamilyPreference）

#### 3.5.1 数据模型

```python
# 文件: src/modules/curation/models/family_preference.py

class FamilyPreference(Base):
    """
    家庭个性化偏好规则 — 从用户行为中自动学习。
    单一新表，JSONB 列存储各维度偏好。
    所有优化组件在每次策展运行时加载一次此记录并传递。
    """
    __tablename__ = "family_preferences"

    id = Column(UUID, primary_key=True)
    family_id = Column(UUID, ForeignKey("families.id"), nullable=False, unique=True, index=True)

    # 优先级维度权重（从 PRIORITY_OVERRIDE 反馈学习）
    # 默认: {"urgency": 0.30, "severity": 0.25, "stakeholder": 0.25, "irrecoverability": 0.20}
    priority_weights = Column(JSONB, default=dict)

    # 事件类型严重度覆盖（学习型）
    # {"meeting": 0.5, "medical": 0.95, "travel": 0.6}
    event_type_severity = Column(JSONB, default=dict)

    # 缓冲时间偏好（从 BUFFER_ADJUSTED 学习）
    # {"default": 15, "location_change": 45, "meeting": 10}
    buffer_minutes = Column(JSONB, default=dict)

    # 推荐类型权重（从 insight/suggestion 反馈学习）
    # {"relationship_maintenance": 1.3, "gift_reminder": 0.7}
    recommendation_weights = Column(JSONB, default=dict)

    # 被抑制的推荐类型（从 NEVER_AGAIN 反馈）
    suppressed_types = Column(JSONB, default=list)

    # 关联类型有效性（从 CONTACT_INITIATED/SKIPPED 学习）
    association_weights = Column(JSONB, default=dict)

    # 信息密度偏好
    density_preferences = Column(JSONB, default=dict)

    # 秘书批注偏好
    annotation_preferences = Column(JSONB, default=dict)

    # 学习元数据
    last_learned_at = Column(DateTime(timezone=True))
    learning_events_count = Column(Integer, default=0)
```

**规则推断逻辑**

```python
# 文件: src/modules/curation/services/preference_learner.py

class PreferenceLearner:
    """
    从反馈信号中归纳偏好规则。Celery 每日任务。

    归纳逻辑:
    - 指数衰减: 近期反馈权重高于旧反馈（半衰期 30 天）
    - 信号数 >= 3 且正/负比例 >= 70% → 创建/更新规则
    - 置信度 < 0.2 → 规则失活（自动恢复测试）
    """

    async def consolidate(self, family_id: UUID) -> FamilyPreference:
        """从过去 90 天的反馈中重新计算偏好。"""
```

**集成方式**：每次策展运行开始时加载一次，传递到所有阶段

```python
# 在 curation_service.py:
async def curate_family_events(self, family_id, ...):
    prefs = await FamilyPreferenceRepo(self.session).get_or_default(family_id)
    # 传递到: HybridPriorityEngine, SecretaryOrchestrator, RecommendationEngine, DensityController
```

---

### 3.6 情绪理解服务

#### 3.6.1 三层递进设计

**Tier 1（零成本快速修复 — 修改提取 Prompt）**

在 `MEMORY_EXTRACTION_PROMPT` 的输出 schema 中添加两个字段：

```json
{
  "type": "emotion",
  "summary": "...",
  "entities": {
    "emotion": "焦虑",
    "sentiment": "negative",         // ← 新增: positive | negative | mixed | neutral
    "emotion_intensity": 3           // ← 新增: 1-5
  }
}
```

提取 LLM 已经理解情感极性，只是未持久化。此修改零额外 LLM 调用。

修复 `_check_stress_pattern()`：

```python
# 旧: memory_type IN (emotion, work) → 计数
# 新: memory_type IN (emotion, work) AND entities->>'sentiment' = 'negative' → 计数
```

**Tier 2（情绪趋势聚合）**

```python
async def compute_emotional_trend(user_id: UUID, window_days: int = 7) -> str:
    """
    从已提取的 sentiment 值计算情绪趋势。
    无额外 LLM 调用，纯 DB 聚合。

    返回: "declining" | "improving" | "stable"
    规则: negative >= 3 且 negative > positive × 2 → declining
    """
```

**Tier 3（对话语气适配）**

将情绪趋势注入 Agent 系统 Prompt：

```
## 用户近期情绪状态
最近7天情绪趋势: {trend}
负面情绪记忆: {count} 条
正面情绪记忆: {count} 条
建议回复语气: {empathetic|encouraging|neutral}
```

---

### 3.7 上下文组装增强

#### 3.7.1 L4 语义搜索启用（P0 修复）

```python
# 文件: src/ai_engine/context_fetchers.py
# 修改 fetch_l4_memories()

async def fetch_l4_memories(self, session, family_id, user_id, query_text, token_budget):
    """
    L4 记忆获取 — 启用语义搜索（修复已有但未使用的 pgvector 基础设施）。

    混合策略:
    1. query_text >= 10 字符 → 生成 embedding → pgvector HNSW 语义搜索
    2. 同时执行全文搜索作为补充
    3. 合并、去重、按 (语义相似度 × 0.6 + 重要性 × 0.3 + 时效性 × 0.1) 排序
    4. 按 token_budget 截断
    """
```

#### 3.7.2 跨层交互（L4 → L3 反馈）

```python
# 两阶段组装:
# Phase A: 执行 L4 记忆检索
l4_results = await fetch_l4_memories(...)
# Phase B: 提取 L4 中提到的人物，用于增强 L3 人物画像选择
mentioned_person_ids = extract_person_ids(l4_results)
l3_results = await fetch_l3_profiles(..., boost_person_ids=mentioned_person_ids)
```

#### 3.7.3 查询理解层（L4 前处理）

```python
# 在传入 L4 之前，分解用户消息为多个查询维度:
# "下次去北京出差怎么安排" → ["北京", "出差", "行程安排"]
# 对每个维度分别检索，合并结果

async def decompose_query(self, user_message: str, entity_resolver) -> list[str]:
    """
    利用已有的 entity_resolver + 关键词提取，
    将用户消息分解为多个语义查询。
    """
```

#### 3.7.4 新增 L5 编排上下文层

```python
LAYER_BUDGETS = {
    "l1_notes": 500,
    "l2_conversation": 2000,
    "l3_profiles": 1500,
    "l4_memories": 2000,
    "l5_orchestration": 800,   # ← 新增
}

async def _fetch_l5_orchestration(self, session, family_id, target_date) -> str:
    """
    L5: 编排上下文 — 注入当日编排结果和秘书批注。

    使 Agent 在对话中自然表达对日程的理解（"我看到你下午有个客户拜访"），
    而不是每次从零推理。
    """
```

#### 3.7.5 Token 估算修复

```python
def estimate_tokens(self, text: str) -> int:
    """使用 tiktoken 精确估算，回退到改进启发式。"""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        # 改进启发式: 中文每字 ~0.7 token，英文每 4 字符 ~1 token
        cn_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - cn_chars
        return int(cn_chars * 0.7 + other_chars / 4)
```

#### 3.7.6 关键词提取修复

```python
# 旧: re.findall(r'[\u4e00-\u9fff]{2,4}', text) → 噪声 bigrams
# 新: 引入 jieba 进行中文分词
import jieba

def extract_keywords(text: str) -> list[str]:
    words = jieba.cut(text, cut_all=False)
    return [w for w in words if len(w) >= 2 and w not in STOP_WORDS]
```

---

### 3.8 信息密度自适应

#### 3.8.1 设计理念

日程越满，信息越精简。用户代言人提出的"整洁桌面"原则。

#### 3.8.2 接口设计

```python
# 文件: src/modules/briefing/services/density_controller.py

@dataclass(frozen=True)
class DensityProfile:
    day_density: float          # 0-1, from orchestrated_day.density_score
    period_multiplier: float    # morning=1.0, afternoon=0.7, evening=0.5
    emotional_state: str        # stressed | normal | relaxed
    max_recommendations: int
    max_annotations: int
    show_household: bool
    show_upcoming_trips: bool


class DensityController:
    """
    规则驱动的信息密度控制（无 LLM，确定性，易调试）。

    密度级别:
    - FOCUSED (density > 0.8): max 3 推荐, 仅 P0/P1 事件, 低优先级折叠
    - STANDARD (0.4-0.8): max 5 推荐, 全量事件
    - RELAXED (density < 0.4): max 7 推荐, 含探索性内容
    - REFLECTIVE (晚间空闲): 回顾型内容（记忆回放、关系盘点）

    额外因子:
    - 周末自动降低一级（更放松）
    - 用户情绪负面时降低一级（减少压力）
    - FamilyPreference.density_preferences 覆盖
    """

    def compute_profile(
        self,
        orchestrated_day: OrchestratedDay,
        period: str,
        family_prefs: FamilyPreference | None,
        emotional_trend: str,
    ) -> DensityProfile: ...
```

**"整洁桌面"算法**（用户代言人提出）

```
daily_noise_budget = 10          # 用户不滚动即可看到的最大项数
urgency_items = alerts + conflicts + overdue_prep   # 始终显示
remaining_budget = daily_noise_budget - len(urgency_items)
scored_items = sort(events + insights + suggestions, by=relevance_score)
visible = urgency_items + scored_items[:remaining_budget]
deferred = scored_items[remaining_budget:]    # "查看更多" 可展开
```

---

### 3.9 Agent 系统 Prompt 重构

#### 3.9.1 问题

现有 `SYSTEM_PROMPT_TEMPLATE`（`agent_factory.py:91-111`）是全系统最弱的 Prompt，而它应该是最强的。与策展 Prompt（有详细人设、规则、反面案例）形成鲜明对比。

#### 3.9.2 改进方向

```
你是{user_name}家的私人秘书，服务这个家庭已有一段时间。

## 你的性格
- 温暖但专业，像一位值得信赖的管家
- 主动但不打扰，在合适的时机提供合适的信息
- 记忆力出色，能自然地引用过去的对话和经历
- 对家庭成员的关系和喜好有深入了解

## 你的工作原则
- 永远先理解用户的情绪状态，再决定回复的语气和内容
- 用户忙碌时简洁回复，用户悠闲时可以多聊几句
- 提到准备事项时，说明为什么现在该做（而非简单列出）
- 提到联系人时，引用具体记忆让建议有温度

## 当前状态
{l5_orchestration_context}

## 情绪感知
{emotional_trend_and_suggestion}

## 回复示例
- 用户问"明天有什么安排" → 不只列事件，而是说"明天上午有两个会，间隔有点紧，建议提前准备好XX。下午比较轻松，可以处理一下周三出差的准备。"
- 用户说"好累啊" → 不急着推待办，先共情，再视情况建议

## 家庭信息
{context}

## 你对这个家庭的了解
{memories}

## 家庭成员画像
{person_profiles}
```

---

### 3.10 基础修复清单

以下修复无依赖、可立即执行：

| 修复项 | 文件 | 修改量 | 说明 |
|---|---|---|---|
| 敏感度分类 | `extraction_service.py:~370` | 1 行 | 添加 `classify_sensitivity()` 调用 |
| 农历循环 | `date_repository.py:119-123` | ~10 行 | Repository 路径仍用 lunar_month/day 当阳历，需改为调用 `lunarcalendar.Converter`（DateService 路径已修复） |
| Insight 并行化 | `insight_orchestrator.py:74-86` | ~5 行 | 改为 `asyncio.gather` |
| System C 中文 | `insight_service.py:119-120, 157-168` | ~10 行 | 英文替换为中文 |
| L4 语义搜索 | `context_fetchers.py:~240` | ~20 行 | 调用已有 `semantic_search()` |
| Token 估算 | `context_assembler.py` | ~10 行 | 引入 tiktoken（中文场景改善有限，主要优化英文/混合文本） |
| 关键词提取 | `recall_service.py` via `utils.py:583` | ~10 行 | 引入 jieba |
| 情绪提取 | `MEMORY_EXTRACTION_PROMPT` | Prompt 修改 | 添加 sentiment + intensity 字段 |
| 压力检测 | `proactive_insight_service.py:288-325` | ~3 行 | 添加 sentiment=negative 过滤 |

---

## 四、场景验证

### 场景 1：出差前的准备链

**当前行为**：
> 周三出差上海。Timeline 显示 3 个独立事件：周一"买伴手礼"(P3)、周二"确认酒店"(P2)、周三"出差"(P0)。"买伴手礼"因不紧急排在最后。

**优化后**：
> `HybridPriorityEngine` 识别准备链依赖，"买伴手礼"升为 P1，secretary_note: "这是周三上海出差的前置准备。"
> `SecretaryOrchestrator` 倒推：周一下午买伴手礼 → 周二上午确认酒店/整理文件 → 周二晚收拾行李。
> Briefing secretary_summary: "本周核心是周三上海出差。今天需要完成伴手礼采购。"

### 场景 2：忙碌日的信息收敛

**当前行为**：
> 周二 6 个事件，Briefing 全量展示 + 3 建议 + 4 insight，信息过载。

**优化后**：
> `DensityController` 检测 density=0.85 → FOCUSED 模式。
> 4 个 P0/P1 事件展示，2 个低优折叠为"另有 2 项可推迟"。
> max 2 推荐。secretary_summary: "今天日程较满。上午专注两个会议，下午客户拜访前预留 30 分钟。晚上聚会可考虑改周末。"

### 场景 3：反馈学习闭环

**当前行为**：
> 用户连续 5 天忽略节气提醒，系统继续每天生成。

**优化后**：
> 每次忽略 → `INSIGHT_IGNORED` → `RecommendationFeedbackConsumer` → 权重 ×0.98。
> shown_count 到 3 → 自动抑制 30 天。
> 写入 `FamilyPreference.suppressed_types: ["solar_term_reminder"]`。
> 30 天后置信度衰减 → 自动恢复测试。

### 场景 4：情绪感知建议调整

**当前行为**：
> 用户说"好累"、"压力好大"，系统照常推送任务型建议。
> 更糟：`_check_stress_pattern()` 把"升职好开心"也当压力信号。

**优化后**：
> Tier 1: 提取时 sentiment=negative, intensity=3。
> Tier 2: `compute_emotional_trend()` → "declining"。
> 推荐引擎：任务型建议延后（除非 P0），增加关怀型内容。
> Agent Prompt 注入：建议回复语气 = empathetic。
> secretary_summary 风格变化：从"今天有 3 件事"到"今天日程不算太满，上午会议结束后可以稍作休息。"

### 场景 5：级联变更

**当前行为**：
> 航班延误 2 小时，用户告诉系统，系统说"好的，我记下了"。

**优化后**：
> Agent 通过 L5 编排上下文了解全天安排。检测级联影响。
> 主动回复："航班延误了，帮你调整下午安排：1. 午餐会改到 15:00；2. 客户拜访推迟到 16:00。需要我帮你通知 XX 改时间吗？"
> 生成 PendingAction 让用户确认。

### 场景 6："Wow" 时刻（用户代言人提出）

**人情精准匹配**：
> 用户出差到杭州。系统知道：(1) 张阿姨住杭州，(2) 上个月张阿姨帮忙带了一周孩子，(3) 记忆中张阿姨喜欢龙井茶。
> 推荐："你到杭州了。上个月张阿姨帮忙带孩子辛苦了，她住在离你酒店 20 分钟的地方。要不要带盒龙井茶过去？"
> 三个系统协作 = 魔法般的体验。

**记忆串联**：
> Timeline 上显示"下周二：妈妈生日"。不是干巴巴的倒计时，而是附带："去年你在湖南菜馆庆祝，妈妈说下次想试粤菜。"

---

## 五、实现优先级与依赖图

### 5.1 四阶段依赖图

```
Phase 0 (基础修复，无依赖，立即可做):
├── 敏感度分类修复 (1 行)
├── 农历日期 Repository 路径修复 (DateService 路径已正确)
├── L4 语义搜索启用
├── Token 估算优化 (tiktoken，对纯中文场景改善有限，主要改善混合文本)
├── 关键词提取修复 (jieba)
├── Insight 并行化 (asyncio.gather)
├── System C 中英文统一
├── 情绪提取字段添加 (Prompt 修改)
└── 压力检测过滤修复

Phase 1 (基础设施，Phase 0 后):
├── [1A] FamilyPreference 模型 + 迁移 + Repository
├── [1B] FeedbackBus 基础设施 (core/feedback/)
└── [1C] HybridPriorityEngine (包装现有 compute_priority_score)

Phase 2 (编排层，Phase 1 后):
├── [2A] SecretaryOrchestrator (读路径，不改策展管线)
│         依赖: [1A], [1C]
├── [2B] DensityController
│         依赖: [2A]
└── [2C] Agent 系统 Prompt 重构 + L5 编排上下文层

Phase 3 (统一引擎 + 闭环，Phase 2 后):
├── [3A] RecommendationEngine (适配器包装现有策略)
│         依赖: [1A], [2A]
├── [3B] 接入 briefing (破坏性变更: briefing schema 改变)
│         依赖: [2A], [2B], [3A]
├── [3C] 注册 FeedbackBus 消费者
│         依赖: [1A], [1B]
├── [3D] PreferenceLearner Celery 任务
│         依赖: [1A], [3C]
└── [3E] 废弃旧系统、删除死代码
          依赖: [3B]
```

### 5.2 最小可行交付

如果只能做一件事：**Phase 0 + Phase 1A + 1C + 2A**

这提供：
- 所有基础 bug 修复（语义搜索、token、分词、农历 Repository 路径、敏感度）
- 更智能的优先级（LLM 校准模糊事件）
- 秘书式日程编排（缓冲时间、通勤检测、负荷评估）
- 学习基础（FamilyPreference 表）

**零破坏性变更**。1 个新 DB 表，0 个现有 API 改变。

### 5.3 各 Phase 投入产出

| Phase | 新文件 | 修改文件 | 新 DB 表 | 核心价值 |
|---|---|---|---|---|
| Phase 0 | 0 | ~10 处小修改 | 0 | 修复已知 bug，释放已有能力 |
| Phase 1 | 3 | ~5 | 1 (family_preferences) | 系统开始学习 + 优先级智能化 |
| Phase 2 | 3 | ~6 | 0 | 从"事件列表"到"日程编排" |
| Phase 3 | 2 + 4 个消费者 | ~8 | 0 | 统一推荐 + 反馈闭环 + 密度适配 |

---

## 六、设计约束

### 6.1 禁止事项

| 禁止 | 原因 | 正确做法 |
|---|---|---|
| 硬编码优先级权重 | 无法个性化 | LLM 校准 + FamilyPreference |
| 正则匹配情绪关键词 | 覆盖率低，误报高 | LLM 情绪分析 / sentiment 字段 |
| 硬编码时间阈值 | 用户习惯不同 | FamilyPreference 学习 |
| 固定信息密度 | 忙闲差异大 | DensityController 动态调整 |
| 精确标题匹配去重 | 语义重复不识别 | Embedding 相似度去重 |
| 忽略反馈信号 | 系统永远不进化 | FeedbackBus 闭环 |

### 6.2 降级策略

每个 LLM 调用点必须有降级方案：

| LLM 调用点 | 降级方案 |
|---|---|
| `HybridPriorityEngine` 校准 | 现有 `compute_priority_score()` |
| `SecretaryOrchestrator` 批注生成 | 返回无批注的时间排序 |
| `EmotionUnderstandingService` | 返回 `valence="neutral"` |
| 推荐引擎 LLM 去重 | `(title, type)` 精确去重 |
| L4 语义搜索 embedding | 全文搜索回退 |

### 6.3 性能预算

| 组件 | 目标延迟 | LLM 模型 | 调用频率 |
|---|---|---|---|
| 优先级校准（5 事件批量） | < 80ms | Haiku 4 | 每次策展，20% 事件触发 |
| 日程编排 | < 200ms（纯规则） | 无 LLM | 每日 + 事件变更 |
| 秘书批注生成 | < 3s | Haiku 4 | 每日 briefing |
| 情绪分析（Tier 1） | 0ms（已在提取时完成） | 无额外调用 | — |
| 语义去重 | < 500ms（embedding 计算） | embedding API | 每次推荐生成 |
| Token 估算 | < 1ms | 无 LLM | 每次上下文组装 |
| 中文分词 | < 1ms | 无 LLM（jieba） | 每次记忆召回 |

---

## 七、现有代码修改索引

### Phase 0 精确修改点

| 修改项 | 文件路径 | 行号/位置 | 修改方式 |
|---|---|---|---|
| 敏感度分类 | `src/modules/memory/extraction_service.py` | `_store_single_memory()` ~370 | 添加 `classify_sensitivity()` 调用 |
| 农历循环 | `src/modules/date_manager/date_repository.py` | 119-123 | Repository 路径仍有 bug，改为调用 `lunarcalendar.Converter`（DateService 路径已修复，无需改） |
| L4 语义搜索 | `src/ai_engine/context_fetchers.py` | ~240 | 调用 `memory_repo.semantic_search()` |
| Token 估算 | `src/ai_engine/context_assembler.py` | token 估算函数 | 引入 tiktoken（中文场景改善有限，主要优化英文/混合文本） |
| 关键词提取 | `src/modules/memory/recall_service.py` → `utils.py` | 575-585 | 引入 jieba |
| Insight 并行 | `src/modules/briefing/services/insight_orchestrator.py` | 74-86 | `asyncio.gather` |
| System C 中文 | `src/modules/insight/insight_service.py` | 119-120, 157-168 | 英文 → 中文 |
| 情绪提取 | `src/modules/memory/extraction_service.py` | MEMORY_EXTRACTION_PROMPT | 添加 sentiment/intensity |
| 压力检测 | `src/modules/insight/proactive_insight_service.py` | 288-325 | 添加 sentiment=negative 过滤 |

### Phase 1 新建文件

| 文件 | 类型 |
|---|---|
| `src/modules/curation/models/family_preference.py` | 新模型 |
| `src/core/feedback/feedback_bus.py` | 新基础设施 |
| `src/modules/curation/services/priority_engine.py` | 新服务 |
| Alembic migration | 新建 `family_preferences` 表 |

### Phase 2 新建文件

| 文件 | 类型 |
|---|---|
| `src/modules/curation/services/orchestrator.py` | 新服务 |
| `src/modules/briefing/services/density_controller.py` | 新服务 |
| `src/ai_engine/context_assembler.py` | 修改：添加 L5 |
| `src/ai_engine/sdk/agent_factory.py` | 修改：Prompt 重构 |

### Phase 3 新建文件

| 文件 | 类型 |
|---|---|
| `src/modules/briefing/services/recommendation_engine.py` | 新服务（合并 3 系统） |
| `src/core/feedback/consumers/` | 4 个消费者文件 |
| `src/modules/curation/services/preference_learner.py` | 新 Celery 任务 |
| `src/modules/briefing/services/briefing_service.py` | 修改：接入新引擎 |
