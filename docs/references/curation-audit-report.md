# 秘书整理模块（Curation）深度审计报告

> 审查日期: 2026-02-19
> 审查范围: `backend/src/modules/curation/` 全目录 + 跨模块集成点
> 审查方法: 4 路并行 Agent 分析 (核心管线 / 关联引擎 / 卫生检查 / 触发集成) + 主线程交叉验证

---

## 一、架构概览

```
SecretaryCurationService (mixin 组合树)
├── CurationCollectorMixin       collector.py         — 三源数据采集
├── CurationDedupMixin           dedup_service.py     — LLM 主路 + 启发式降级
├── CurationAssociationMixin     association_service.py — 双引擎关联发现
├── CurationStorageMixin         storage_service.py   — diff/upsert 存储
├── CurationConflictMixin        conflict_resolver.py — 冲突检测与解决
└── CurationQueryMixin           query_service.py     — 时光轴/图谱查询

辅助组件:
├── RuleBasedAssociationEngine   rule_engine.py       — 确定性规则匹配
├── MemoryEngine                 memory_engine.py     — 记忆→意图提取
├── ContextEnricher              context_enricher.py  — 事件上下文富化 (死代码)
├── ImpactArbitrator             impact_arbitrator.py — 触发分级
├── TriggerDispatcher            trigger_dispatcher.py — 增量触发路由
├── DirtyBitManager              dirty_bit_manager.py — Redis 脏位队列
├── ShouldRunService             should_run_service.py — 执行门控
├── ProactiveTriggerer           proactive_triggerer.py — 主动洞察扫描
└── CurationWriteDelegate        write_delegate.py    — 外部写入网关
```

两条主要管线:
- **mini_curate** (实时): 对话提取 → 标题+时间精确匹配 → 单事件 upsert → 异步关联发现
- **curate_family_events** (批量): 三源采集 → LLM 去重归一化 → 行程折叠 → diff 存储 → 冲突检测 → 双引擎关联 → LLM 整合

---

## 二、P0 — 严重问题

### 2.1 采集层静默失败导致事件级联取消

**位置:** `collector.py:78-156`

三个数据源（TripPlan / ImportantDate / ConversationMemory）各自独立 `try/except`，失败后仅 `logger.error()`，不中断管线。后续 diff/upsert 逻辑会将"本次未采集到但上次存在"的事件标记为 stale 并 cancel。

```python
try:
    travels = ...
except Exception as e:
    logger.error(f"Error collecting travel plans: {e}")
    # raw_events 中无 travel 数据 → diff 视为"已删除" → 全部 cancel
```

**后果:** 一次短暂的 DB 连接抖动即可导致用户所有即将到来的行程事件被静默取消，直到下次 curation 重新采集。

---

### 2.2 LLM 关联的 target_id 未做 DB 校验

**位置:** `association_service.py:235-245`, `models.py:183`

LLM 返回的 `target_id`（指向 Member / Memory 的 UUID 字符串）直接写入 `EventAssociation` 表，无 FK 约束，无存在性检查。

**后果:** LLM 幻觉出的 UUID 会创建孤儿关联，前端展示时查不到对应实体。`EventAssociation.target_id` 定义为 `String(100)`，甚至不强制 UUID 格式。

---

### 2.3 ContextEnricher 已构建但从未在关联管线中调用

**位置:** 构造: `curation_service.py:69`，未调用: `association_service.py` 全文件

`ContextEnricher` 提供 6 维度事件上下文（历史访问、关联人物、优先级原因、可调整度等），但在关联发现管线和 LLM prompt 构建中完全未调用。仅在查询路径 `query_service.py:88` 中使用。

**后果:**
- LLM 做关联发现时缺少历史访问频率、关联人物互动记录等关键上下文
- `EventContext` 中设计的 `adjustability`、`priority_reason` 等字段在关联发现路径从未生成
- 设计与实现脱节，6 维度上下文是死代码

---

### 2.4 should_push 标志计算后被完全忽略

**位置:** `impact_arbitrator.py:149`, `trigger_dispatcher.py` 全文件

`ImpactArbitrator.assess()` 对 HIGH 级触发设置 `should_push=True`，但 `TriggerDispatcher.dispatch()` 和所有 Celery task **从未读取** 该标志来触发推送。

**后果:** 高影响力事件（如新行程创建、3 天内的重要日期）被整理后，用户不会收到任何通知。唯一的用户推送路径是冲突检测的 `publish_confirm_card()`。

---

### 2.5 主动洞察扫描发现触发但不通知用户

**位置:** `proactive_triggerer.py:112-340`, `tasks.py:858-867`

4 类主动扫描（临近日期 / 冷关系 / 过期承诺 / 用户节奏偏离）发现异常后，仅触发 `trigger_curation_async()` 再走一次 curation 管线，**不发送任何 FCM / WebSocket / 推送通知**。

```
proactive_scan 发现: "王阿姨的生日后天" → trigger_curation_async()
→ curate_family_task → ImpactArbitrator: date_approaching ≤3d → HIGH
→ should_push=True → [无人消费此标志] → 事件存入 DB → 用户不知道
```

**后果:** "秘书事后整理发现重要关联"这一核心场景完全断路。

---

## 三、P1 — 高优先级问题

### 3.1 Memory 反馈权重更新后从未被读取

**位置:** 更新: `curation_service.py:408`，查询: `collector.py:265-316`

用户 dismiss 关联后 `memory.feedback_weight *= 0.5`（最低 0.1）。但 `_get_relevant_memories()` 查询时 **不使用** `feedback_weight` 做排序或过滤，仅按插入顺序返回前 20 条。

**后果:** 用户反复 dismiss 的低质量记忆依然被注入 LLM prompt，产出相同的低质量关联。

---

### 3.2 关联循环中 N 次重复加载相同上下文数据

**位置:** `association_service.py:138-143`

对每个 curated event，独立查询 `_get_members_with_locations()`、`_get_relevant_memories()`、`_get_important_dates_in_range()`。这些数据在同一 family 内不变。

**后果:** N 个事件 → 3N 次 DB 查询。典型 10 事件家庭每次 curation 产生 30+ 次冗余查询 + 12 次 LLM 调用。

---

### 3.3 记忆上下文无相关性排序，平坦截断前 20 条

**位置:** `collector.py:303`, `prompts.py:7`

`MEMORY_QUERY_LIMIT = 20`，取最近 20 条记忆（按插入顺序），不按与当前事件的语义相关性排序。

**后果:** 与当前事件高度相关的老记忆被裁掉，不相关的新记忆占满配额。LLM 看到的上下文噪声 > 信号。

---

### 3.4 批次间事件无法合并

**位置:** `dedup_service.py:228-264`

事件 > 50 条时分批处理，每批独立 LLM 去重。跨批事件（如 batch 1 的"北京出差 Jan 28"和 batch 2 的"北京会议 Jan 28"）永远不会被合并。

---

### 3.5 LLM 时间解析无事后校验

**位置:** `dedup_service.py:307`, `prompts.py:37-39`

LLM 将"下周一上午"解析为具体 datetime，但系统不检查结果是否与原始 raw event 的时间范围一致。

**后果:** LLM 数错日期，curated event 的 start_time 静默偏移数天。

---

### 3.6 heuristic fallback 不调用 cluster_events() — 死代码

**位置:** `dedup_service.py:645`, `dedup_utils.py:cluster_events()`

LLM 去重失败时 `_fallback_heuristic_dedup()` 仅将每个 raw event 原样传递（confidence=0.5），不调用 `dedup_utils.py` 中实现的 union-find 聚类算法。

**后果:** `cluster_events()` 是死代码。LLM 降级时零去重。

---

### 3.7 EventCurated 领域事件的 briefing handler 是 TODO 桩

**位置:** `stream_consumers.py:67-68`

```python
async def _handle_briefing_event(event_type: str, payload: dict) -> None:
    logger.info("briefing-workers received %s", event_type)
    # TODO: delegate to briefing module service
```

**后果:** curation 完成后 briefing 模块不感知，用户可能在数小时内看到过时的 briefing。

---

## 四、P2 — 中优先级问题

### 4.1 冲突检测仅时间维度，无空间感知

**位置:** `conflict_detection.py:36-38, :105`

`CONFLICT_EVENT_TYPES = {"business_trip", "travel", "meeting", "appointment"}`，仅检测时间区间重叠。

| 检查项 | 状态 |
|--------|------|
| 时间重叠 | 有 |
| 空间冲突（北京开会 + 上海出差同日） | **无** |
| 交通衔接（18:00 散会 → 18:30 登机） | **无** |
| 生日 vs 出差同日不告警（birthday 排除在 CONFLICT_EVENT_TYPES 外） | **过度排除** |
| 成员维度冲突（家庭成员各自日程） | **无** |
| 100 事件硬上限 `_MAX_NEARBY_EVENTS` | 超限静默截断 |

---

### 4.2 冲突自动解决无审计追踪

**位置:** `conflict_detection.py:438-461`

`resolve_conflict_auto()` 直接修改 `normalized_start/end`，不记录"此事件被自动从 X 移到 Y"。

---

### 4.3 两套冲突解决器互不调用

**位置:** `conflict_detection.py` vs `conflict_resolver_service.py`

- `conflict_detection.py`: 管线内实际执行自动解决 / 创建 PendingAction
- `conflict_resolver_service.py`: 提供多选项评分，用于 UI 展示

两者不共享逻辑、不共享评分标准。

---

### 4.4 优先级评分不接入用户偏好和关系健康度

**位置:** `priority_score.py:1-77, :91`

四维模型（紧迫度 / 严重度 / 利益相关者 / 不可挽回性），但：
- **无用户偏好**: 无法指定"家庭 > 工作"。`_HIGH_STAKEHOLDER_RELATIONS = {"spouse", "parent", "child", "partner"}` 全局硬编码。
- **无关系健康度**: `relationship` 模块的温度计数据未被引用。
- **无频率感知**: 每日提醒与年度航班获得同等紧迫度权重。

---

### 4.5 规则引擎仅匹配 primary_location

**位置:** `rule_engine.py:94-96`

地理关联仅检查 `Member.primary_location`（字符串子串匹配），忽略 `Member.locations` JSONB 数组中的工作地、第二住所。

---

### 4.6 规则引擎日期匹配不支持农历

**位置:** `rule_engine.py:152-153`

±7 天窗口仅基于 `ImportantDate.solar_date`，不读取 `lunar_date`。农历生日/节日不参与日期关联。

---

### 4.7 多日事件分解硬编码 9:00-18:00

**位置:** `dedup_service.py:491-492`

非行程类多日事件（住院、跨天演出）被分解为每日 9:00-18:00 子事件。

---

### 4.8 T2 触发在 Redis 不可用时静默丢弃

**位置:** `trigger_dispatcher.py:183`, `dirty_bit_manager.py:187-197`

`mark_dirty()` 的 `on_immediate` 回调在 `TriggerDispatcher` 中传入 `None`。Redis 不可用时 LOW/MEDIUM T2 触发直接丢弃。

---

### 4.9 TripPlan 双重 TripCreated 事件发布

**位置:** `trip_plan.py:332` + `trip_plan.py:374`

创建行程时 `publish_with_outbox`（事务内）和 `event_bus.publish`（commit 后）各发一次 `TripCreated`，导致 stream consumer 收到两次，触发两次 curation。Redis 锁防止并发执行，但浪费 Celery 资源。

---

### 4.10 单事务覆盖全管线，无中间检查点

**位置:** `curation_service.py:137-192`

采集 → LLM 去重（10-30s）→ 存储 → 关联 → 提交，全在一个 DB session 中，仅最后 `commit()`。末尾失败全部回滚，无部分进度保存。10-30+ 秒 LLM 调用期间 session 持有所有 ORM 对象在内存中。

---

### 4.11 query_service 读路径触发 DB commit

**位置:** `query_service.py:97-100, :332-340`

时光轴和图谱的 GET 请求在 `enrich_event()` 后调用 `await self.session.commit()` 持久化富化结果。GET 请求不应有 DB 副作用。

---

### 4.12 图谱查询 10 次串行 DB 查询 + O(N) 地点全扫描

**位置:** `query_service.py:141-494`

单次图谱加载执行 10 次串行查询，无并行化。地点扩展先取出所有有地点的事件再在 Python 中字符串匹配。

---

### 4.13 脏位 payload 覆写丢失中间变更

**位置:** `dirty_bit_manager.py:199-200`

Redis HASH key 为 `{trigger_type}:{entity_id}`，同一实体后续更新覆盖前一次 payload。行程先改目的地再改日期，第一次 diff 丢失。

---

### 4.14 ImpactArbitrator 不参考事件自身优先级

**位置:** `impact_arbitrator.py:118-135`

仅看 `trigger_type` + `payload` + `diff`，不看被影响事件的 priority。P0 医疗预约移动 1.5h → LOW（规则 6），P3 可选提醒改 3 字段 → HIGH（规则 8）。

---

### 4.15 增量路径不发布 EventCurated 领域事件

**位置:** `trigger_dispatcher.py` 全文件 vs `curation_service.py:200`

`EventCurated` 仅在完整管线路径（`curate_family_events`）发布，增量路径（`TriggerDispatcher`）无发布。增量整理的结果对下游消费者不可见。

---

## 五、P3 — 低优先级问题

### 5.1 collector 时间表达式仅支持 4 种

**位置:** `collector.py:180-208`

`_parse_time_hint()` 仅处理"明天/后天/下周X/下个月"。"下下周"、"三天后"、"这周五"、"3月15日"返回 None，事件静默丢弃无 warning 日志。

---

### 5.2 recurring date 去重按标题精确匹配会误碰撞

**位置:** `collector.py:109-119`

两条标题相同但 `date_type` 不同的 recurring date 误碰撞。`raw_events.remove()` 为 O(n) 操作。

---

### 5.3 far-future 365 天硬截断

**位置:** `storage_service.py:233-267`

超过 1 年的事件被自动停用。13 个月后的合法预订被误杀。

---

### 5.4 EventAssociation 可同时 is_confirmed + is_dismissed

**位置:** `models.py:183`

无 DB CHECK 约束防止两个互斥状态共存。

---

### 5.5 LLM confidence 无 [0,1] 范围校验

**位置:** `schemas.py:237`

`LLMCuratedEvent.confidence` 默认 0.8，无 `ge=0, le=1` 验证。

---

### 5.6 ShouldRunService 双重评估

**位置:** `tasks.py:317` + `tasks.py:551`

定时路径中先入队前评估一次，再 Celery task 内评估一次。

---

### 5.7 daily_curation_task 定义但未注册到调度器

**位置:** `tasks.py:388`, `celery_app.py`

遗留代码。实际周期性执行通过 `curate_family_task`。

---

### 5.8 trip_grouping 目的地归一化仅 strip().lower()

**位置:** `trip_grouping.py:27-32`

"Shanghai" 和 "上海" 不会合并。中英文、缩写、别名无语义归一化。

---

### 5.9 增量路径关联发现不检查已有关联

**位置:** `trigger_dispatcher.py:922-939`

`_discover_associations_for_event()` 不检查同一事件是否已有关联，可能创建重复关联。

---

### 5.10 stale SocialIntent 无清理机制

**位置:** `hygiene_service.py` 全文件

`social_intents` 表中 `status=active` 的过期意图（如 90 天前表达的"想见某人"）永不被清理或过期。

---

## 六、缺失能力清单

### 6.1 调度编排 (Schedule Orchestration) — 完全缺失

系统不具备：
- 自动在主事件前创建准备事件（如生日前 3 天的"买礼物"提醒）
- 检查行程配套完整性（长途旅行无酒店 → 提醒）
- 依赖排序（准备事件必须在主事件之前）
- 行程闭环检查（有去无回 → 提醒）

`EventAssociation.association_type=task` 和 `PreparationItem` 表已存在，但无代码驱动。

---

### 6.2 信息分层 (Visibility Tiers) — 完全缺失

所有 curated events 在时光轴上平权展示。无：
- Focus / Standard / Detail 三层分级
- "今天最重要的 3 件事"概要视图
- 琐碎事件折叠/收纳

`ContextEnricher` 中的 `adjustability`、`priority_reason` 等字段本可支撑分层，但未被调用（见 2.3）。

---

### 6.3 交通时间感知 — 完全缺失

`CuratedEvent.city` 字段存在但未用于距离/交通估算。无法检测不可行安排（如"17:00 A 楼散会 → 18:30 B 机场登机"）。

---

### 6.4 跨模块关联断路

| 断路 | 说明 |
|------|------|
| curation × gift | 生日关联不触发礼物模块推荐 |
| curation × relationship | 关系温度计不参与优先级评分和关联发现 |
| curation × weather | 行程关联不注入目的地天气 |
| proactive_scan × notification | 主动扫描发现 → curation → 无通知 |
| EventCurated × briefing | 领域事件发布但 handler 是 TODO 桩 |
| curation → conversation context | 关联发现不注入对话上下文，下次聊天不提及 |

---

## 七、LLM 调用成本分析

单次 `curate_family_events` 的 LLM 调用量：

| 步骤 | 调用次数 | 说明 |
|------|----------|------|
| 去重归一化 | ceil(N_raw / 50) | 每 50 个 raw events 一批 |
| 关联发现 | N_curated | 每个 curated event 一次 |
| 关联整合 | 1 | 全量关联去重 |
| **总计** | **ceil(N/50) + N + 1** | 10 事件 ≈ 12 次 LLM 调用 |

加上每个事件独立的 3 次 DB 查询（成员 / 记忆 / 日期），**10 事件家庭单次 curation = 12 次 LLM + 30+ 次冗余 DB 查询**。

---

## 八、代码定位索引

| 问题编号 | 文件 | 行号 |
|----------|------|------|
| 2.1 | collector.py | 78-156 |
| 2.2 | association_service.py | 235-245 |
| 2.3 | curation_service.py / association_service.py | 69 / 全文件 |
| 2.4 | impact_arbitrator.py | 149 |
| 2.5 | proactive_triggerer.py / tasks.py | 112-340 / 858-867 |
| 3.1 | curation_service.py / collector.py | 408 / 265-316 |
| 3.2 | association_service.py | 138-143 |
| 3.3 | collector.py / prompts.py | 303 / 7 |
| 3.4 | dedup_service.py | 228-264 |
| 3.5 | dedup_service.py / prompts.py | 307 / 37-39 |
| 3.6 | dedup_service.py / dedup_utils.py | 645 / cluster_events() |
| 3.7 | stream_consumers.py | 67-68 |
| 4.1 | conflict_detection.py | 36-38, 105 |
| 4.2 | conflict_detection.py | 438-461 |
| 4.3 | conflict_detection.py / conflict_resolver_service.py | — / 58-101 |
| 4.4 | priority_score.py | 91 |
| 4.5 | rule_engine.py | 94-96 |
| 4.6 | rule_engine.py | 152-153 |
| 4.7 | dedup_service.py | 491-492 |
| 4.8 | trigger_dispatcher.py / dirty_bit_manager.py | 183 / 187-197 |
| 4.9 | trip_plan.py | 332, 374 |
| 4.10 | curation_service.py | 137-192 |
| 4.11 | query_service.py | 97-100 |
| 4.12 | query_service.py | 141-494 |
| 4.13 | dirty_bit_manager.py | 199-200 |
| 4.14 | impact_arbitrator.py | 118-135 |
| 4.15 | trigger_dispatcher.py / curation_service.py | — / 200 |
