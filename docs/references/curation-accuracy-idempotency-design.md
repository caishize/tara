# Curation 准确优先与幂等重构设计

## 1. 目标

本方案目标：

1. 准确优先：避免 LLM 失败后落库低质量结果。
2. 幂等优先：相同输入重复执行时不产生重复写入。
3. 节流优先：存在“无变化”场景时直接跳过，减少无意义计算。
4. 反馈闭环：用户 dismiss/confirm 能跨轮次生效，不被重算复活。

非目标：

1. 不追求一次性重写全部模块。
2. 不在本阶段优化 UI 展示样式。

## 2. 当前问题摘要

1. Full pipeline 存在“清理后重写”路径，导致稳定 ID 和反馈记忆丢失风险。
2. 触发路径不统一，部分场景会错误回落到 full pipeline。
3. “应跳过”场景未前置判定，导致无信号也执行计算。
4. dismiss/confirm 抑制主要依赖当前关联记录，跨轮次不稳定。

## 3. 新增架构：ShouldRun + DiffApply

## 3.1 总流程

统一整理流程：

1. `CollectSignals`：采集轻量变更信号（watermark / 计数 / 外部告警摘要）。
2. `ShouldRun`：判定 `skip | incremental | full`。
3. `ComputeCandidates`：仅在需要时生成事件/关联候选。
4. `Canonicalize`：规范化并生成稳定 key 与 fingerprint。
5. `DiffPlan`：生成 create/update/deactivate/noop 计划。
6. `ApplyPatch`：仅应用差异，不做 delete+insert 替换。
7. `Publish`：仅对 create/update/deactivate 发事件。

## 3.2 ShouldRun 决策层

新增决策结果：

1. `skip_no_signal`
2. `run_incremental`
3. `run_full`

判定输入：

1. 上次成功整理时间。
2. Trip/Memory/ImportantDate 的 `max(updated_at)` watermark。
3. 未来窗口内 active 事件计数。
4. 待处理冲突/待确认关联/待执行反馈计数。
5. 外部重大信号（天气 severe alert、手动触发）。

跳过条件（全部满足才 skip）：

1. watermark 无变化。
2. 未来窗口无 active 事件。
3. 无 pending conflict/association action。
4. 无 severe weather signal。
5. 非手动触发。
6. 未到强制兜底周期（例如 24h）。

升级为 full 条件（任一满足）：

1. 手动触发。
2. schema/version 变更。
3. 连续 N 次 incremental 后达到校验阈值。
4. 到达周级深度校验周期（例如每周一次）。

其他默认 incremental。

## 4. 数据模型变更

## 4.1 curated_events 扩展字段

新增字段：

1. `stable_key`：稳定身份键（同一语义事件跨轮次不变）。
2. `source_fingerprint`：源数据指纹（原始输入变化检测）。
3. `semantic_fingerprint`：语义指纹（标题/时间/地点规范化后哈希）。
4. `version`：事件版本号（仅变化时递增）。

索引与约束：

1. unique(`family_id`, `stable_key`)
2. index(`family_id`, `source_fingerprint`)

## 4.2 curated_event_sources 新表

用途：维护 source 到 curated_event 的稳定映射，支持 merged 场景稳定 ID。

字段建议：

1. `id`
2. `family_id`
3. `source_type`
4. `source_id`
5. `curated_event_id`
6. `created_at`
7. `updated_at`

约束：

1. unique(`family_id`, `source_type`, `source_id`)

## 4.3 event_associations 扩展字段

新增：

1. `association_key`：稳定关联键（source_stable_key + target + type）
2. `version`

约束：

1. unique(`family_id`, `association_key`)

## 4.4 association_feedback_memory 新表

用途：把 dismiss/confirm/snooze 转成跨轮次硬约束。

字段建议：

1. `id`
2. `family_id`
3. `association_key`
4. `feedback_type` (`dismiss|confirm|snooze`)
5. `reason`
6. `strength`
7. `expires_at` (可空)
8. `created_at`
9. `updated_at`

约束：

1. unique(`family_id`, `association_key`, `feedback_type`)

## 4.5 curation_state 新表

用途：ShouldRun 的轻量状态缓存。

字段建议：

1. `family_id` (PK)
2. `last_success_at`
3. `trip_watermark`
4. `memory_watermark`
5. `date_watermark`
6. `last_input_fingerprint`
7. `idle_backoff_level`
8. `last_mode` (`skip|incremental|full`)
9. `updated_at`

## 5. 幂等算法规范

## 5.1 Event 层

对每个候选事件：

1. 计算 `stable_key`。
2. 查现存事件（按 `family_id + stable_key`）。
3. 不存在：`create`。
4. 存在且 fingerprints 相同：`noop`。
5. 存在且 fingerprints 不同：`update changed fields + version+1`。

对现存事件：

1. 本轮未出现但仍在窗口内：`deactivate`（不硬删）。

禁止行为：

1. 在重算写路径中执行替换式 `delete+insert`。

## 5.2 Association 层

对每条候选关联：

1. 生成 `association_key`。
2. 先应用 `association_feedback_memory` 过滤（dismiss/snooze hard block）。
3. 与现存关联按 key 做 diff。

规则：

1. key 未变但文案优化：`update`。
2. key 与指纹均未变：`noop`。
3. key 不再出现：`deactivate` 或 `dismissed_by_system`。

## 6. LLM 策略（准确优先）

1. Dedup/association consolidation 失败不落 heuristic 结果，转 retry。
2. 降低温度并固定输入排序，减少输出抖动。
3. 输出先 canonicalize 再计算 fingerprint。
4. Prompt 强制注入近期 feedback 约束摘要。

## 7. 触发与执行策略

1. 实时触发走“防抖聚合”：同一 family/entity 在短窗口合并。
2. 实时优先 incremental，避免编辑风暴。
3. scheduled 作为漂移校验与漏算兜底，不做默认主路径。
4. cooldown 仅约束周期任务，不阻塞高优先级变更任务。

## 8. 观测与验收指标

新增指标：

1. `curation_should_run_skip_ratio`
2. `curation_noop_ratio`
3. `curation_patch_write_count`
4. `curation_full_run_ratio`
5. `association_dismiss_reappearance_rate`
6. `llm_retry_count`

验收阈值建议：

1. 无输入变化场景 `noop_ratio >= 0.95`
2. dismiss 复发率 `< 1%`
3. scheduled full 比例明显下降

## 9. 实施顺序

Phase 1（基座）：

1. 加表与字段迁移（state/source_map/feedback/fingerprint）。
2. 写 ShouldRun 服务（只读轻查询 + 决策）。

Phase 2（写路径替换）：

1. Event 写入改为 DiffApply。
2. Association 写入改为 key-upsert + feedback filter。

Phase 3（触发收敛）：

1. 统一 trigger taxonomy。
2. 引入防抖聚合与运行模式路由。

Phase 4（准确性强化）：

1. 关闭 heuristic 落库 fallback。
2. LLM 重试与不确定结果隔离。

## 10. 对现有代码的落点

1. `backend/src/modules/curation/tasks.py`
2. `backend/src/modules/curation/services/curation_service.py`
3. `backend/src/modules/curation/services/storage_service.py`
4. `backend/src/modules/curation/services/trigger_dispatcher.py`
5. `backend/src/modules/curation/services/association_service.py`
6. `backend/src/core/events/handlers/stream_consumers.py`
7. `backend/src/core/scheduler/dispatcher.py`

## 11. 兼容策略

1. 新旧路径并行开关：`CURATION_ACCURACY_MODE=legacy|diff_apply`
2. 家庭级灰度：按 family_id 白名单启用。
3. 全链路回滚：保留 legacy 写路径直到指标稳定。

