# 对话流全链路深度审计报告

## 调用链路概览

```
POST /chat → _classify_intent() → _dispatch_ws_chat_job()
  ├── FAST:   asyncio.create_task(publish_fast_path()) → FastWorker.handle() → PubSub → WS
  ├── SLOW:   save_user_msg → enqueue(Redis Stream) → worker_runner → AgentWorker.process() → PubSub → WS
  └── HYBRID: asyncio.create_task(publish_hybrid_path())
                ├── Leg1: FastWorker (same as FAST)
                └── Leg2: enqueue(hybrid_background) → AgentWorker.process() → PubSub → WS
```

---

## P0: 严重问题

### 1. Streaming-Input 模式无超时保护

**位置**: `worker_runner.py:108-113`, `worker_runner.py:128-129`

当 `sdk_streaming_input_enabled=True` 时，`_should_disable_worker_timeout()` 返回 True，`asyncio.wait_for` 的 timeout 被跳过。如果 SDK 子进程死锁、网络分区或 tool 执行无限阻塞，该任务将永远不会结束。

`_SessionStreamingActor` 有队列空闲超时（用于 actor 退出），但没有单任务执行超时。heartbeat 任务虽然在运行，但它只检查 cancel 信号，不做执行时间守卫。

**影响**: 一个卡死的 streaming-input 任务会占用 semaphore 槽位（默认 3 个并发），逐渐拖垮整个 Worker 的任务处理能力。用户端永远卡在"思考中"。

**修复方向**: 即使 streaming-input 模式也应有最大执行时间上限（如 10 分钟），超时后强制断开 SDK 连接并通知用户。

### 2. PubSub 订阅者断连期间消息丢失

**位置**: `core/pubsub/redis_pubsub.py:128-137`

Redis PUB/SUB 是 fire-and-forget 协议。当 WebSocket 断连但 WS manager 尚未完成清理（取消 PubSub 订阅）时，Redis 仍报告 `receivers > 0`，publish 返回成功。实际上消息已丢失 — 不会被推入 offline queue（因为 receivers 不为 0），也不会到达已断开的客户端。

**影响**: 在网络抖动、移动端切后台等常见场景下，关键消息（如 COMPLETE、CONFIRM_CARD）可能永久丢失。客户端重连后无法通过 resume 协议恢复这些消息。

**修复方向**: 采用双写策略 — 每条关键消息同时写入 offline queue（或专用 per-job message log），不依赖 `receivers` 计数。客户端重连时通过 resume 协议按 `job_id + last_seq` 补齐。

### 3. Hybrid 模式 Fast→Slow 上下文断裂

**位置**: `ws_publishers.py:582-601` vs `agent_worker.py:247-257`

Hybrid Leg1 (Fast) 的 `db.commit()` (ws_publishers.py:591) 在 Leg2 入队 (ws_publishers.py:636) 之前。代码上 Leg2 是在 Leg1 commit 之后入队的，但 AgentWorker 组装上下文的时机取决于 Worker 从 Redis Stream dequeue 的延迟。

`context_snapshot` 中的 `fast_result_summary` (ws_publishers.py:611) 只截取前 500 字符，仅作为 system prompt hint，不注入正式对话历史。AgentWorker 的 `_rehydrate_context` (agent_worker.py:649) 设置 `max_conversation_turns=0`，完全依赖 ContextAssembler 从 DB 读取 L2 消息。

在 PostgreSQL READ COMMITTED 下，如果 Worker 极快拾取任务（<1ms），新事务可能看不到刚 commit 的 Fast 回复。实际概率低但非零，尤其在 DB 负载高时。

**修复方向**: `context_snapshot` 应携带完整的 Fast 回复内容，AgentWorker 启动时强制合并到上下文中，不完全依赖 DB 读取。

### 4. Fast/Hybrid Path 异常时前端无兜底通知

**位置**: `chat.py:309,382`, `ws_publishers.py:399-408,656-665`

Fast/Hybrid 路径通过 `asyncio.create_task()` 后台运行，HTTP 已返回 200。`publish_fast_path` / `publish_hybrid_path` 的顶层 try/except 会尝试发送 ERROR 到 PubSub (ws_publishers.py:400-408)。但如果 PubSub 本身不可用（Redis 宕机），错误发布的 except 是 bare `pass` (ws_publishers.py:407-408)。

**影响**: 用户拿到 `{job_id, route_type: "fast"}` 后，WebSocket 上永远收不到任何消息。

**修复方向**:
1. `asyncio.create_task()` 添加 `done_callback`，检测异常后写入 DB 标记（如 `job_status:{job_id} = error`）
2. 前端 poll fallback 端点 (`GET /poll/{job_id}`) 应定时检查，发现超时无消息时主动查询 DB

---

## P1: 高优先级问题

### 5. cancel_generation 未校验 session 归属

**位置**: `chat.py:724-744`, `agent_worker.py:160-175`

`cancel_generation()` 只校验 JWT 身份，不验证 `session_id` 是否属于当前用户。任何已认证用户只要知道他人的 `session_id`，即可写入 `cancel:{session_id}` Redis key 中断其对话。

Worker 端 `_check_cancel()` (agent_worker.py:160-175) 只检查 key 是否存在，不校验 value 中的 user_id。

**修复方向**: cancel 前应查 DB 验证 session_id 属于当前 user_id。

### 6. SDK Pool 跨进程 Redis Marker 与实际状态不一致

**位置**: `chat.py:192-208`, `sdk_client_pool.py:237-253,479-494`

`_classify_intent` 通过 `has_active_client()` 检查 Redis key `sdk_pool:active:{session_id}` (TTL=1800s)。SDK client 可能已因 idle timeout 被清理（池的清理周期 60s），但 Redis marker 的 TTL 远大于 idle timeout 检查频率。

反向：SDK client 刚创建但 `_set_active_marker` 的 Redis SET 尚未完成，本应走 SLOW 的被路由到 FAST。

Session affinity 机制 (task_queue.py:613-789) 部分弥补了这个问题 — 即使路由错误，任务最终会被 redirect 到正确的 worker。但冷启动 (~68s) 的延迟仍存在。

**修复方向**: marker TTL 应与池的 idle timeout + cleanup interval 对齐，或 marker 在池清理时主动删除（当前已做，sdk_client_pool.py:319）。需确认 `_cleanup_idle` 中调用 `_close_client` 是否可靠触发 `_clear_active_marker`。

### 7. Worker SIGKILL 后的恢复延迟窗口

**位置**: `worker_runner.py:139-203`, `task_queue.py:350-449`

Worker 被 SIGKILL 后的恢复链路：

1. heartbeat key TTL 过期 (30s)
2. 另一个 Worker dequeue 轮询 (每 1s)
3. `_claim_stale_messages` 检查 idle_time > claim_timeout_ms (90s)
4. **总延迟 ≈ 30s + 90s = ~2 分钟**

期间用户卡在"思考中"。DLQ 写入 (`move_to_dlq`, task_queue.py:540-577) 不触发 PubSub 通知，失败任务静默消失。

**修复方向**: 缩短 claim_timeout_ms 到与 heartbeat_TTL 相同级别（30s）；DLQ 写入时同步发送 PubSub ERROR 通知。

### 8. WebSocket 连接建立与 PubSub 订阅之间的消息间隙

**位置**: `core/websocket/manager.py:448,484-501`

WebSocket 连接建立后，`start_listening()` 创建 asyncio task (manager.py:448)，但实际 Redis SUBSCRIBE 完成前有时间窗口。offline queue drain (manager.py:484-501) 在订阅之后执行，但订阅完成前发布的消息既不在 offline queue（当时有 subscriber），也不被新订阅接收。

**修复方向**: 先 drain offline queue，然后 subscribe，再二次 drain（覆盖间隙期间到达的消息）。

### 9. Worker 与 API 共进程，无隔离

**位置**: `worker_runner.py:212`

`run_agent_worker_loop()` 作为 asyncio background task 在 FastAPI 进程内运行。Worker 的 CPU/内存飙升直接影响 API 延迟。一个失控的 LLM tool call 可能卡死整个服务。

Semaphore 限制并发任务数为 3 (worker_runner.py:249)，但无法限制单任务的资源占用。

**修复方向**: 分离 Worker 到独立进程/容器。当前架构可通过 `sdk_streaming_input_enabled` + session affinity 平滑迁移。

---

## P2: 中优先级问题

### 10. AgentWorker 内部双重上下文加载

**位置**: `agent_worker.py:247-257`

AgentWorker.process() 中先调用 `_try_assemble_context()` (ContextAssembler 四层 pipeline)，紧接着调用 `_rehydrate_context()` (ContextService 读取对话历史 + 人物档案)。两者都从 DB 加载对话历史 (L2)，且 ContextAssembler 的 L2 fetcher 和 ContextService.build_compressed_history 查询的是同一张表。

ContextAssembler 有 Redis 缓存 (TTL=300s, context_assembler.py:493-538)，但 `_rehydrate_context` 没有缓存。

注意：IntentRouter 本身是轻量的 — 不加载深度上下文，仅做 Haiku 分类。之前关于 "IntentRouter 与 ContextAssembler 双重加载" 的判断不完全准确。

**修复方向**: `_rehydrate_context` 应在 ContextAssembler 已提供 L2 数据时跳过重复的对话历史查询。

### 11. ContextAssembler 四个独立 DB Session

**位置**: `ai_engine/context_fetchers.py:40,98,152,221`

L1-L4 四个 fetcher 各自 `async with get_db_session() as session` 打开独立 DB 连接。虽然通过 `asyncio.gather` 并行执行，但每次 slow path 请求消耗 4 个连接池槽位。

**影响**: 高并发 + 每请求 4 连接 → 连接池压力倍增。

### 12. cancel 机制依赖轮询，最坏延迟 10s

**位置**: `agent_worker.py:495-508`

Cancel 信号通过 Redis key `cancel:{session_id}` 传递。heartbeat 每 10s 检查一次。如果 SDK 正在执行长 tool call，即使检测到 cancel，SDK 无 interrupt API，需等当前操作完成。

### 13. upgrade_to_slow 后 Fast 阶段结果不入库

**位置**: `ws_publishers.py:278-334`

FastWorker 返回 `upgrade_to_slow` 时直接 `return`，跳过 assistant message 持久化 (ws_publishers.py:343-363)。已发送给用户的文本不会存入 conversation history。

### 14. FastWorker agentic loop 中的长事务

**位置**: `fast_worker.py:245-549`

`_handle_agentic` 在整个 agentic loop 期间持有 `tool_db` session。多轮 LLM + tool 执行可能持续数十秒，长期占用连接池资源。

### 15. DLQ 无监控告警

**位置**: `task_queue.py:540-577`

DLQ 只写不读。失败任务写入 `agent:tasks:dlq` stream 后无任何告警、通知或重处理机制。随时间累积成静默黑洞。

### 16. edit_message 的 is_superseded 与并发写入竞争

**位置**: `chat.py:590-599`

mark superseded → commit 之间，另一个路径可能正在写入新消息到同一 session。

### 17. feedback 端点 JSONB 变更可能不被 SQLAlchemy 检测

**位置**: `chat.py:962-970`

赋值新 dict 到 ORM JSONB 字段。如果 column 未配置 `MutableDict`，SQLAlchemy 可能不检测变更。应使用 `flag_modified(message, "message_metadata")` 确保触发 UPDATE。

---

## P3: 低优先级/观察项

### 18. Session Lock 引用计数潜在泄漏

**位置**: `ws_publishers.py:38-57`, `worker_runner.py:37-71`

如果异常发生在 `lock.acquire()` (ws_publishers.py:46) 之后、`try:` 之前（理论上不可能在 asyncio 中但属于防御性问题），ref count 递增但永不递减，导致该 session 的 lock 永不释放。两份几乎一样的 copy-paste 代码扩大了维护风险。

### 19. ContextAssembler 缓存 5 分钟时间桶可能返回过时上下文

**位置**: `context_assembler.py:589-600`

缓存 key 含 5 分钟时间桶。桶内相同消息会命中缓存，但如果期间有新消息/记忆写入，上下文可能过时。

### 20. Worker consumer_name 随机 UUID 导致僵尸 consumer 累积

**位置**: `worker_runner.py:247`

每次重启生成新 consumer_name。旧 consumer 在 PEL 中的记录需 heartbeat TTL 过期后才被清理。频繁重启导致 Redis Stream consumer group 累积僵尸条目。

### 21. 三套 Session 序列化机制并存

**位置**: `worker_runner.py:80-113`

SessionMailboxActor、`_acquire_session_lock`、`_SessionStreamingActor` 三套机制由两个 feature flag 切换。逻辑分散在三个函数中，测试覆盖和状态机推理成本高。

### 22. poll fallback 端点的 JSONB 查询无索引

**位置**: `chat.py:990-1003`

`message_metadata["job_id"].astext == job_id` 查询 JSONB 字段，无 GIN 索引时全表扫描。

### 23. WebSocket 开发模式认证绕过

**位置**: `core/websocket/websocket.py:36-46`

development 模式下 JWT 验证失败时 fallback 到硬编码默认 user/family ID。如果 `strict_auth_enabled` 配置错误，生产环境也可能触发。

### 24. AsyncOpenAI client 每次语音请求重建

**位置**: `chat.py:450-476`

`_transcribe_voice_upload` 每次创建 + 关闭 `AsyncOpenAI` client。应复用全局实例。

### 25. SDK stream handler 非关键事件丢失无恢复

**位置**: `sdk_stream_handler.py:370-376`

thinking/tool_call 等非关键 PubSub 发布失败时静默吞掉。`_content_publish_failed` flag 只覆盖 content 事件，不覆盖 tool_call。前端可能看到不完整的工具执行 UI。
