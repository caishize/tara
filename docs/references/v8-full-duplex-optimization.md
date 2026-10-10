# V8 Full-Duplex Conversation Optimization Plan

> 基于 Claude Agent SDK 0.1.39 验证行为的智能秘书全双工对话系统设计

---

## 1. 架构总览

### 1.1 核心升级点

当前系统基于 `SessionStreamingExecutor` 已实现 SDK 持久连接、跨 turn `receive_messages()` 迭代和并发 `query()` 注入的基础能力。本方案在此基础上引入三项核心能力：

1. **介入分类层 (Intervention Layer)** — 用户在 Agent 活跃期间发送的消息，经 Haiku 分类后按类型选择不同的 SDK 操作
2. **Sidekick 洞察注入** — 系统侧 Insight 在合适时机通过 `query()` 注入活跃会话
3. **断点保护与缝合** — 中断生成时保存部分内容，新 turn 通过 stitching_context 实现无感衔接

### 1.2 组件关系

```
用户消息 → API Handler
               ↓
         [是否存在活跃生成？]
          ↙ 否              ↘ 是
  IntentRouter          InterventionClassifier (Haiku <150ms)
  (现有双脑路由)              ↓
       ↓              InterventionSignal
  TaskQueue            → Redis PubSub session:signal:{session_id}
       ↓                     ↓
  ReactiveSessionActor ← 信号监听 (三路 asyncio.wait)
       ↓
  ClaudeSDKClient (持久连接, receive_messages())
       ↓
  SDKStreamHandler → Redis PubSub ws:{user_id} → WebSocket → Mobile
```

### 1.3 SDK 行为基础 (已验证, SDK 0.1.39)

| 场景 | SDK 行为 | 本方案利用方式 |
|------|---------|-------------|
| Turn 间 `query()` | ResultMessage 后 query → 新独立 turn | IDLE 状态下的正常请求处理 |
| Tool 执行中 `query()` | 消息合并到当前 turn 回答中，不产生独立 ResultMessage | ADDITIVE / SIDEKICK 注入 |
| `interrupt()` + `query()` | <10ms 中断 → error ResultMessage → 新 query 独立 turn | CORRECTION / DIGRESSION 处理 |
| `receive_messages()` | 跨 turn 持续迭代器，不在 ResultMessage 处停止 | ReactiveSessionActor 持久监听 |

---

## 2. 介入分类系统

### 2.1 五类介入信号

| 类型 | 语义 | 典型场景 | SDK 操作 |
|------|------|---------|---------|
| **CORRECTION** | 用户纠正当前任务方向 | "不对，我要查北京的不是上海的" | `interrupt()` + `query()` |
| **ADDITIVE** | 用户补充当前任务信息 | "顺便也查一下明天的天气" | `query()` (合并到当前 turn) |
| **CANCEL** | 用户取消当前操作 | "算了不用查了" | `interrupt()` + 发布完成 |
| **CONFIRM** | 用户确认待执行操作 | "确认执行"（针对 PendingAction） | `query()` (作为确认指令注入) |
| **DIGRESSION** | 用户转移话题 | "对了明天北京天气怎么样"（与当前任务无关） | 排入 FIFO 队列等待下一 turn |

### 2.2 分类器设计

分类器运行在 API 层，仅当 `session:status:{session_id}` 显示活跃生成时触发。

**分类提示词：**

```
你是一个消息意图分类器。判断用户的新消息与当前正在执行的任务之间的关系。

当前任务摘要: {current_task_summary}
用户上条消息: {last_user_message}
用户新消息: {new_user_message}

分类规则:
- CORRECTION: 用户在纠正或修改当前任务的方向，需要中断当前执行重新开始
- ADDITIVE: 用户在补充当前任务的额外信息或条件，可以注入当前上下文
- CANCEL: 用户想取消或终止当前操作
- CONFIRM: 用户在确认一个待执行的操作（如购买、预订、发送）
- DIGRESSION: 用户转移了话题，与当前正在执行的任务无关

输出JSON: {"type":"CORRECTION|ADDITIVE|CANCEL|CONFIRM|DIGRESSION","confidence":0.0-1.0}
```

**性能要求：**
- 模型：Claude Haiku 4
- max_tokens: 64
- 目标延迟: <150ms
- 无 system prompt，全部内容放入 user message（减少处理 token 数）

**置信度策略：**

| 置信度 | 处理方式 |
|--------|---------|
| >= 0.85 | 立即执行对应 SDK 操作 |
| 0.60 ~ 0.85 | 执行但写入审计日志供复盘 |
| < 0.60 | 降级为 ADDITIVE（最安全：不中断、不丢失信息） |

降级为 ADDITIVE 的理由：ADDITIVE 是所有误分类中代价最小的——它不会触发 `interrupt()` 破坏当前生成，同时用户的信息仍然进入了 Agent 的上下文。如果分类错误，用户下一条消息自然会形成 CORRECTION。

### 2.3 `current_task_summary` 的构建

分类器需要知道 Agent 当前在做什么。此信息来源于 `session:status:{session_id}` 中存储的结构化状态：

```python
@dataclass(frozen=True)
class SessionStatus:
    state: str              # GENERATING | TOOL_EXECUTING | WAITING_USER
    job_id: str
    worker_id: str
    sdk_session_id: str
    last_heartbeat: str
    task_summary: str       # 从 TaskPayload.user_input 截取前100字符
    active_tool: Optional[str]  # 当前正在执行的工具名称
```

API handler 从 Redis GET 获取此状态，用 `task_summary` 和 `active_tool` 构建分类提示词的 `current_task_summary`。

---

## 3. ReactiveSessionActor

### 3.1 设计定位

`ReactiveSessionActor` 替换现有 `_SessionStreamingActor`（session_streaming_executor.py），保留其全部现有能力（持久 `receive_messages()` 迭代器、FIFO 请求队列、请求路由），新增介入信号监听和 SDK 操作协调。

### 3.2 状态机

```
IDLE ──[query()]──> GENERATING ──[ToolUseBlock]──> TOOL_EXECUTING
  ^                     |                              |
  |                     v                              v
  +──[ResultMessage]── IDLE <──[tool_result]── GENERATING
  |
  +──[AskUserQuestion]──> WAITING_USER ──[answer]──> GENERATING
```

### 3.3 状态 x 介入类型 操作矩阵

> 注：SIDEKICK 紧急度门控规则详见 §7.2。medium/low 仅在 IDLE 状态注入，high 可在 TOOL_EXECUTING 期间注入。

| 当前状态 | CORRECTION | ADDITIVE | CANCEL | CONFIRM | DIGRESSION | SIDEKICK |
|---------|-----------|----------|--------|---------|-----------|----------|
| **GENERATING** | interrupt() + query() | 缓冲到 turn 结束后注入为补充信息（[SUPPLEMENTARY_INFO] 包装） | interrupt() + 发布完成 | 缓冲 | 排入请求队列，当前 turn 正常完成后处理 | low/medium 拒绝，high 缓冲到 turn 结束 |
| **TOOL_EXECUTING** | 检查工具可中断性，可中断则 interrupt()，否则缓冲 | query() (合并到当前 turn) | 检查工具可中断性 | query() (注入确认) | 排入请求队列，工具完成后处理 | high: query() (合并)，medium/low: 拒绝 |
| **IDLE** | query() 直接处理 | query() 直接处理 | 无操作（已无活跃生成） | query() 直接处理 | query() 直接处理 | query() 直接处理 |
| **WAITING_USER** | 替换待定回答 | 缓冲到下一个 IDLE（WAITING_USER 状态下直接 query() 语义不明确，缓冲更安全） | interrupt() + 发布完成 | 需先 interrupt() 打破 ask_user_question 阻塞，再 query() 注入确认并恢复生成 | interrupt() + emit_partial_content(interrupted_by="digression") + emit_bridging("digression") + 排入请求队列 | 高优先级: 缓冲到下一个 IDLE；低/中优先级: 拒绝（与 GENERATING 一致） |

### 3.4 核心循环（三路 asyncio.wait）

```python
class ReactiveSessionActor:
    """Per-session actor with intervention signal handling.

    Replaces _SessionStreamingActor. Retains:
    - Owned pooled ClaudeSDKClient
    - Persistent receive_messages() iterator
    - FIFO request queue

    Adds:
    - Redis PubSub signal listener on session:signal:{session_id}
    - Generation state machine
    - Intervention dispatch
    - Stitching context management
    """

    async def _run(self):
        # 初始化异步数据源
        queue_task = asyncio.ensure_future(self._request_queue.get())
        message_task: Optional[asyncio.Task] = None  # Phase 2 才创建
        signal_task = asyncio.ensure_future(self._next_intervention_signal())

        while self._running:
            # 两阶段优化:
            # Phase 1 (无活跃 SDK 工作): 只等待 queue_task + signal_task（二路 wait）
            #   此时没有活跃的 SDK client，不可能有 SDK 消息，无需 message_task
            # Phase 2 (有活跃 SDK 工作): 完整三路 wait（queue_task + message_task + signal_task）
            #   SDK client 正在处理请求，需要监听 SDK 消息流
            # 功能等价于始终三路 wait，但 Phase 1 避免了无意义的 message_task 空转
            waitables = {queue_task, signal_task}
            if self._has_pending_sdk_work():
                if message_task is None:
                    message_task = asyncio.ensure_future(self._next_sdk_message())
                waitables.add(message_task)

            done, _ = await asyncio.wait(
                waitables,
                return_when=asyncio.FIRST_COMPLETED,
            )

            # 优先级: 介入信号 > SDK 消息 > 新任务请求
            if signal_task in done:
                signal = signal_task.result()
                if signal is not None:
                    await self._handle_intervention(signal)
                signal_task = asyncio.ensure_future(self._next_intervention_signal())

            if message_task is not None and message_task in done:
                message = message_task.result()
                if message is not None:
                    await self._handle_message(message)
                message_task = asyncio.ensure_future(self._next_sdk_message())

            if queue_task in done:
                request = queue_task.result()
                if request is not None:
                    await self._accept_request(request)
                queue_task = asyncio.ensure_future(self._request_queue.get())
```

### 3.5 工具可中断性判定

某些工具执行的外部操作不可回滚（如发送消息、创建预订），在这些工具执行期间收到 CORRECTION/CANCEL 时，不能直接 `interrupt()`，必须等工具完成后再处理。

```python
# 在 ToolGateway 或 tool 定义层面标记
NON_INTERRUPTIBLE_TOOLS = frozenset({
    "create_trip", "book_ticket", "send_message",
    "checkout", "create_task", "confirm_action",
})

async def _handle_correction_during_tool(self, signal: InterventionSignal):
    if self._active_tool_name in NON_INTERRUPTIBLE_TOOLS:
        # 缓冲 correction，等工具完成后再 interrupt + query
        self._deferred_intervention = signal
        return
    # 可中断工具：立即 interrupt
    await self._do_correction(signal)
```

工具完成后，在 `_handle_message()` 处理 tool_result 时检查是否有 deferred_intervention：

```python
async def _handle_message(self, message):
    # ... 现有消息分发逻辑 ...

    if is_tool_result(message) and self._deferred_intervention:
        deferred = self._deferred_intervention
        self._deferred_intervention = None
        await self._handle_intervention(deferred)
```

### 3.6 与现有栈的集成点

| 现有组件 | 集成方式 | 变更程度 |
|---------|---------|---------|
| `SessionStreamingExecutorManager` | `ReactiveSessionActor` 替换 `_SessionStreamingActor`，Manager 的 `_get_or_create_actor()` 指向新类 | 小改 |
| `agent_pool_executor.execute_with_pool_or_fallback()` | 不变，仍通过 Manager.submit() 提交请求 | 无改 |
| `SDKClientPool` | 不变，ReactiveSessionActor 通过 `pooled.client` 访问 SDK 客户端 | 无改 |
| `SDKStreamHandler` | 不变，仍负责 SDK 消息解析和事件发射，新增几个事件类型 | 小改 |
| `PooledToolContext` | 不变，`ctx.update()` 在每个新请求时交换内部状态 | 无改 |
| `TaskQueue` | 不变，仍通过 Redis Streams 分发任务 | 无改 |

---

## 4. 介入信号协议

### 4.1 Redis 通道约定

```
session:signal:{session_id}    # PubSub: 用户介入信号 + Sidekick 洞察
session:status:{session_id}    # STRING: 生成状态 (SET/GET, 非 PubSub)
session:stitch:{session_id}    # STRING: 中断时的缝合上下文
```

使用独立于 `ws:{user_id}` 的通道，防止介入信号泄漏到 WebSocket 客户端。

### 4.2 信号消息格式

```json
{
  "signal_id": "uuid-v4",
  "type": "correction|additive|cancel|confirm|digression|sidekick_insight",
  "session_id": "session-uuid",
  "job_id": "current-job-uuid",
  "user_id": "user-uuid",
  "timestamp": "2026-02-21T12:00:00Z",
  "payload": {},
  "priority": 1
}
```

**优先级定义：**
- 1 = 立即处理（CANCEL, CORRECTION）
- 2 = 下一间隙处理（ADDITIVE, CONFIRM）
- 3 = 尽力而为（SIDEKICK, DIGRESSION）

**通用 `text` 字段：**

所有 payload 类型均包含 `text` 字段作为通用回退键，包含用户原始消息文本。Actor 端优先使用类型特定键（如 `corrected_input`、`additional_input`），`text` 仅在特定键缺失时使用。

**类型特定 payload：**

CORRECTION:
```json
{"text": "...", "corrected_input": "...", "original_input": "...", "intent_class": "correction"}
```

ADDITIVE:
```json
{"text": "...", "additional_input": "...", "intent_class": "additive"}
```

CANCEL:
```json
{"reason": "user_initiated"}
```

CONFIRM:
```json
{"text": "...", "pending_action_id": "uuid", "confirmation": "approve|reject", "intent_class": "confirm"}
```

DIGRESSION:
```json
{"text": "...", "new_input": "...", "intent_class": "digression"}
```

SIDEKICK_INSIGHT:
```json
{
  "insight_type": "trip_correlation|favor_reciprocation|weather_alert",
  "insight_text": "...",
  "urgency": "high|medium|low",
  "source_system": "A|B|C",
  "context_entities": ["张伟", "北京"],
  "expires_at": "2026-02-22T00:00:00Z"
}
```

### 4.3 发布流程（API 层）

```
用户发送消息 (POST /assistant/agent/chat)
    ↓
API handler: GET session:status:{session_id}
    ↓
[无活跃生成] → 正常 IntentRouter 双脑路由 → TaskQueue
[有活跃生成] → InterventionClassifier (Haiku, <150ms)
    ↓
PUBLISH session:signal:{session_id} {signal_json}
    ↓
返回 {"status": "signal_accepted", "signal_id": "...", "signal_type": "..."}
```

API 层不等待 Agent 处理结果，立即返回 202 Accepted。Agent 的后续输出通过现有 WebSocket 推送通道送达。

### 4.4 消费流程（Actor 侧）

```python
async def _signal_listener(self):
    """Subscribe to session:signal:{session_id}."""
    async for raw_msg in self._redis_pubsub.listen():
        signal = InterventionSignal.from_dict(json.loads(raw_msg["data"]))

        # 过期信号防护：job_id 不匹配则丢弃
        if signal.job_id != self._current_job_id:
            logger.warning("Stale signal rejected: signal_job=%s current=%s",
                          signal.job_id, self._current_job_id)
            continue

        # 信号去重：UUID 去重集合（最近 100 个）
        if signal.signal_id in self._processed_signals:
            continue
        self._processed_signals.add(signal.signal_id)

        await self._pending_interventions.put(signal)
```

### 4.5 并发安全保证

1. **Job ID 匹配**：每个信号携带目标 `job_id`，Actor 拒绝与 `_current_job_id` 不匹配的信号，防止上一次生成的过期信号影响新生成
2. **状态门控**：Actor 依据 `_generation_state` 决定 SDK 操作，不满足条件时缓冲信号
3. **信号去重**：`signal_id` (UUID) 在有界集合中追踪，防止 Redis PubSub at-least-once 语义导致重复
4. **单任务事件循环**：`_generation_state` 仅在 Actor 的单线程事件循环内变更，无需 asyncio Lock
5. **缓冲排序**：多信号缓冲时按优先级排序：CANCEL > CORRECTION > DIGRESSION > ADDITIVE > SIDEKICK

---

## 5. SDK 操作实现

### 5.1 CORRECTION 操作

```python
async def _do_correction(self, signal: InterventionSignal):
    # 1. 中断 SDK (<10ms) — 立即停止生成，最高优先级
    await self._pooled.client.interrupt()
    # receive_messages() 将产出 error ResultMessage

    # 2. 捕获中断前的部分内容
    partial_text = self._current_handler.final_text
    partial_thinking = self._current_handler.final_thinking

    # 3. 构建缝合上下文（内存中，无 Redis 往返）
    stitching = StitchingContext(
        partial_text=partial_text,
        partial_thinking=partial_thinking,
        interrupted_at=utc_now(),
        reason="correction",
        original_input=signal.payload.get("original_input", ""),
        completed_tools=self._current_handler.completed_tool_names,
        partial_tool=self._current_handler.active_tool_info,
    )

    # 4. 异步保存缝合上下文到 Redis（后台任务，不阻塞主流程）
    asyncio.create_task(self._save_stitching_context(stitching))

    # 5. 向客户端推送 partial 标记
    await self._emit("partial_content", {
        "is_partial": True,
        "partial_text": partial_text,
        "interrupted_by": "correction",
        "generation_id": self._current_generation_id,
    })

    # 6. 构建纠正提示词
    corrected_prompt = self._build_correction_prompt(signal, stitching)

    # 7. 捕获旧 generation_id（在覆盖前保存，用于 continues_from）
    old_generation_id = self._current_generation_id

    # 8. 生成新 generation_id
    self._current_generation_id = str(uuid4())

    # 9. 向客户端推送 bridging 标记（携带 continues_from 关联旧生成）
    await self._emit("bridging", {
        "signal_type": "correction",
        "new_generation_id": self._current_generation_id,
        "continues_from": old_generation_id,
    })

    # 10. 发送新 query
    await self._pooled.client.query(corrected_prompt)
    self._generation_state = GenerationState.GENERATING
```

### 5.2 ADDITIVE 操作

根据 SDK 验证行为，tool 执行期间的 `query()` 会合并到当前 turn 的回答中。利用此特性实现无缝补充：

```python
async def _do_additive(self, signal: InterventionSignal):
    if self._generation_state == GenerationState.TOOL_EXECUTING:
        # 安全注入：合并到当前 turn
        wrapped = (
            "[SUPPLEMENTARY_INFO]\n"
            f"用户补充了以下信息（请纳入当前任务的考虑，无需单独回复此条）:\n"
            f"{signal.payload['additional_input']}\n"
            "[/SUPPLEMENTARY_INFO]"
        )
        await self._pooled.client.query(wrapped)

    elif self._generation_state == GenerationState.GENERATING:
        # 生成中不安全注入（合并行为不可控），缓冲到 turn 结束
        self._buffered_additives.append(signal)

    elif self._generation_state == GenerationState.IDLE:
        # 直接作为新 turn 处理
        await self._pooled.client.query(signal.payload["additional_input"])
        self._generation_state = GenerationState.GENERATING
```

缓冲的 ADDITIVE 在当前 turn 的 ResultMessage 到达后自动发送。注意：flush 时使用 `[SUPPLEMENTARY_INFO]` 标签包装（与即时注入一致），而非发送原始文本，确保 Agent 将其视为补充信息而非新任务：

```python
async def _on_result_message(self, result):
    # ... 现有完成逻辑 ...
    self._generation_state = GenerationState.IDLE

    # 发送缓冲的 additive 信息（使用 [SUPPLEMENTARY_INFO] 包装）
    if self._buffered_additives:
        combined = "\n".join(
            s.payload["additional_input"] for s in self._buffered_additives
        )
        self._buffered_additives.clear()
        wrapped = (
            "[SUPPLEMENTARY_INFO]\n"
            f"用户在上一轮生成期间补充了以下信息:\n"
            f"{combined}\n"
            "[/SUPPLEMENTARY_INFO]"
        )
        await self._pooled.client.query(wrapped)
        self._generation_state = GenerationState.GENERATING
```

### 5.3 CANCEL 操作

```python
async def _do_cancel(self, signal: InterventionSignal):
    partial_text = self._current_handler.final_text

    if self._active_tool_name in NON_INTERRUPTIBLE_TOOLS:
        # 不可中断工具执行中：标记待取消，等工具完成后处理
        self._cancel_after_tool = True
        return

    await self._pooled.client.interrupt()

    # 保存部分内容作为 is_partial 消息
    if partial_text:
        await self._emit("partial_content", {
            "is_partial": True,
            "partial_text": partial_text,
            "interrupted_by": "cancel",
            "generation_id": self._current_generation_id,
        })

    await self._emit("done", {"reason": "user_cancelled"})
    self._generation_state = GenerationState.IDLE
```

### 5.4 CONFIRM 操作

```python
async def _do_confirm(self, signal: InterventionSignal):
    confirmation_prompt = (
        "[USER_CONFIRMATION]\n"
        f"用户已确认执行操作 (pending_action_id: {signal.payload['pending_action_id']})\n"
        f"确认结果: {signal.payload['confirmation']}\n"
        "请继续执行已确认的操作。\n"
        "[/USER_CONFIRMATION]"
    )

    if self._generation_state == GenerationState.WAITING_USER:
        # WAITING_USER 状态下 SDK 阻塞在 ask_user_question 工具上，
        # 必须先 interrupt() 打破阻塞，才能发送新 query
        await self._pooled.client.interrupt()
        old_generation_id = self._current_generation_id
        self._current_generation_id = str(uuid4())
        await self._emit("bridging", {
            "signal_type": "confirm",
            "new_generation_id": self._current_generation_id,
            "continues_from": old_generation_id,
        })
        await self._pooled.client.query(confirmation_prompt)
        self._generation_state = GenerationState.GENERATING

    elif self._generation_state == GenerationState.GENERATING:
        # 确认请求在生成期间到达，缓冲到 turn 结束
        self._buffered_confirms.append(signal)

    else:
        await self._pooled.client.query(confirmation_prompt)
```

### 5.5 DIGRESSION 操作

话题跳跃不应中断当前生成，而是排入队列等待当前 turn 完成后作为独立任务处理：

```python
async def _do_digression(self, signal: InterventionSignal):
    if self._generation_state == GenerationState.IDLE:
        # 无活跃生成，直接作为新 turn
        await self._pooled.client.query(signal.payload["new_input"])
        self._generation_state = GenerationState.GENERATING
    else:
        # 有活跃生成：排入请求队列，保留 FIFO 语义
        # 创建新的请求对象，当前 turn 完成后自动处理
        queued_request = StreamingRequest(
            task=TaskPayload(
                user_input=signal.payload["new_input"],
                session_id=self.session_id,
                # ... 从 signal 构建
            ),
            publish_fn=self._publish_fn,
        )
        await self._request_queue.put(queued_request)
```

---

## 6. 缝合上下文与断点保护

### 6.1 缝合上下文结构

```python
@dataclass(frozen=True)
class StitchingContext:
    partial_text: str               # 中断前已生成的文本
    partial_thinking: str           # 中断前的思考内容
    interrupted_at: datetime        # 中断时间
    reason: str                     # correction | digression | cancel
    original_input: str             # 用户原始输入
    completed_tools: list[str]      # 中断前已完成的工具名称列表
    partial_tool: Optional[dict]    # 中断时正在执行的工具信息
```

存储位置：`session:stitch:{session_id}`，TTL 300 秒，被新 turn 消费后自动清除。

### 6.2 纠正场景的缝合提示词

```python
def _build_correction_prompt(self, signal: InterventionSignal,
                              stitching: StitchingContext) -> str:
    parts = []

    # 事实性嵌入（不提"中断"，让 Agent 不知道被打断过）
    if stitching.completed_tools:
        tool_results = self._format_completed_tool_results(stitching.completed_tools)
        parts.append(f"你已经完成了以下操作的结果：{tool_results}")

    if stitching.partial_tool:
        parts.append(
            f"你之前尝试调用了 {stitching.partial_tool['name']}，"
            f"但操作未完成，请在需要时重新调用。"
        )

    parts.append(f"用户的最新指示：{signal.payload['corrected_input']}")

    return "\n".join(parts)
```

**关键设计：事实性嵌入而非恢复框架**

```
好的做法（Agent 不知道被中断）：
  "你已经查询了上海的天气（晴，25°C），用户现在想查北京的天气。"

避免的做法（Agent 变得过度谨慎）：
  "你之前在查上海天气但被中断了，现在用户改成要查北京的。"
```

这种差异很重要：第一种写法让 Agent 把已有信息当作正常上下文处理；第二种写法会让 Agent 产生"需要小心恢复"的倾向，导致不必要的确认和冗余操作。

### 6.3 话题跳跃的缝合

DIGRESSION 走队列而非 interrupt，所以不需要缝合上下文。当前 turn 正常完成，下一 turn 是全新话题。

但如果用户的跳跃实际上与原话题有关联（秘书行为模式中的"暗线不断"），Agent 通过 SDK 内部的对话历史自然具备这种上下文连续性，无需额外干预。

### 6.4 客户端侧 is_partial 消息处理

| 介入类型 | 客户端对 partial 消息的处理 |
|---------|------------------------|
| CORRECTION | 将 partial 消息标记为 `is_partial=true`，以降低视觉权重展示（如 50% 透明度），新生成内容替换该气泡 |
| CANCEL | 将 partial 消息保留，标记为 `is_partial=true`，作为对话记录的一部分 |
| DIGRESSION | 不产生 partial（当前 turn 正常完成） |

---

## 7. Sidekick 洞察注入

### 7.1 注入架构

```
CurationPipeline ──[curated_events]──┐
InsightOrchestrator ──[user_insights]──┤──> SidekickWorker
BriefingModule ──[daily_briefing]────┘        ↓
                                   评估与活跃会话的相关性
                                        ↓
                                   PUBLISH session:signal:{session_id}
                                   (type=sidekick_insight)
                                        ↓
                                   ReactiveSessionActor._handle_sidekick_insight()
```

### 7.2 注入时机决策

| 当前状态 | 注入行为 | 理由 |
|---------|---------|------|
| TOOL_EXECUTING | `query()` 注入 | SDK 合并到当前 turn 回答，自然融入 |
| IDLE | `query()` 直接注入 | 作为独立 turn 处理 |
| GENERATING | 缓冲到下一个 IDLE 或 TOOL_EXECUTING | 生成期间合并不可控 |
| WAITING_USER | 高优先级: 缓冲到下一个 IDLE；低/中优先级: 拒绝 | 与 GENERATING 一致的安全优先策略，WAITING_USER 下 query() 语义不明确 |

### 7.3 注入提示词格式

```python
injection_prompt = (
    "[SYSTEM_INSIGHT]\n"
    f"以下信息可能与当前对话相关（仅供参考，请在回复中自然融入，"
    f"如果与当前话题无关则忽略）:\n"
    f"{insight.insight_text}\n"
    "[/SYSTEM_INSIGHT]"
)
```

### 7.4 注入防护

**相关性检查：**

注入前检查洞察的关键实体是否与当前对话上下文有交集。不执行实体提取（避免额外延迟），而是利用 Insight 自带的 `context_entities` 与当前请求的 `user_input` 和最近 3 个工具调用结果做文本包含检查：

```python
async def _is_contextually_relevant(self, insight: SidekickInsight) -> bool:
    context_text = self._current_task.user_input if self._current_task else ""
    for tc in self._recent_tool_results[-3:]:
        context_text += " " + str(tc.get("result", ""))

    return any(entity in context_text for entity in insight.context_entities)
```

**注入频率限制：**

| 限制项 | 值 | 说明 |
|--------|-----|------|
| 每会话最大注入数 | 3 | 防止信息过载 |
| 每 turn 最大注入数 | 1 | 防止单 turn 内多次注入导致 Agent 混乱 |
| 注入最小间隔 | 60 秒 | 冷却期 |
| 高优先级可绕过 | 是 | urgency=high 的洞察忽略频率限制 |

**紧急度门控：**

- `high`：可在 TOOL_EXECUTING 期间注入
- `medium` / `low`：只在 IDLE 时注入

### 7.5 防脱轨设计

1. **提示词框架**：`[SYSTEM_INSIGHT]` 标签 + "如果无关则忽略"的明确指令，给 Agent 自主判断的空间
2. **实体交集检查**：只注入与当前话题相关的洞察
3. **频率限制**：防止信息过载
4. **过期检查**：`expires_at` 超时的洞察直接丢弃

---

## 8. 上下文窗口管理

### 8.1 介入导致的 Token 膨胀问题

每次 `query()` 调用都向 SDK 内部的对话历史追加内容。经过 N 次介入后：

```
Turn 1: 原始 query + Agent 回复 + 工具调用
Turn 2: ADDITIVE 注入 + 合并后的回复
Turn 3: CORRECTION → interrupt error + 新 query + 回复
Turn 4: SIDEKICK 注入 + 合并后的回复
```

SDK 自身有上下文压缩机制，但我们无法控制其行为。

### 8.2 介入预算

```python
@dataclass(frozen=True)
class InterventionBudget:
    max_interventions_per_session: int = 5
    max_additive_per_turn: int = 2
    max_correction_per_session: int = 3
    context_compression_threshold: int = 3
```

- 单 turn 内最多 2 次 ADDITIVE（超出则缓冲到下一 turn）
- 单会话最多 3 次 CORRECTION（超出则触发会话重置）
- 累计 3 次介入后，主动触发 `ContextService.compress_if_needed()`

### 8.3 会话重置阈值

当介入次数超过预算时，强制重置 SDK 会话：

```python
async def _check_intervention_budget(self):
    if (self._intervention_count >= self._budget.max_interventions_per_session or
        self._correction_count >= self._budget.max_correction_per_session):

        # 压缩整个会话历史为摘要
        summary = await self._context_service.build_compressed_history(
            self.session_id, self._user_id
        )

        # 关闭当前 SDK 客户端
        await self._pool.mark_disconnected(self.session_id)

        # 以摘要作为新会话的上下文起点
        new_task = TaskPayload(
            user_input=self._last_user_input,
            context_snapshot={"session_summary": summary, "reset_reason": "intervention_limit"},
            # ...
        )
        await self._request_queue.put(StreamingRequest(task=new_task, ...))

        # 重置计数器
        self._intervention_count = 0
        self._correction_count = 0
```

### 8.4 缝合上下文的 Token 控制

缝合上下文硬限 500 token。策略：
- 工具结果只保留关键发现（不保留完整 JSON）
- `partial_text` 截取最后 200 字符（Agent 只需要断点附近的内容）
- `partial_thinking` 截取最后 100 字符

### 8.5 介入后的缓存失效

`ContextAssembler` 的内容哈希缓存在介入后必须失效：

```python
async def _after_intervention(self):
    await ContextAssembler.invalidate_context_cache(self._user_id)
```

---

## 9. 流式推送增强

### 9.1 新增事件类型

在现有 `MessageType` 枚举基础上新增：

```python
class MessageType(str, Enum):
    # ... 现有类型 ...
    GENERATION_STATE = "generation_state"     # 生成状态变更通知
    PARTIAL_CONTENT = "partial_content"       # 中断生成的部分内容
    BRIDGING = "bridging"                     # 生成间的过渡标记
    SIDEKICK_INSIGHT = "sidekick_insight"     # 主动洞察推送（通知客户端展示）
```

### 9.2 内容元数据增强

每个 content 事件携带可选元数据：

```json
{
  "type": "content",
  "text": "北京明天的天气...",
  "job_id": "job-uuid",
  "meta": {
    "is_partial": false,
    "generation_id": "gen-uuid",
    "turn_index": 2,
    "signal_source": null,
    "continues_from": null
  }
}
```

- `generation_id`：每次 interrupt + resume 后更换，客户端用于关联 partial 和续接内容
- `signal_source`：标记此内容是由哪种介入触发的（correction / additive / null）
- `continues_from`：引用被中断的 `generation_id`，用于客户端 UI 衔接

### 9.3 CORRECTION 场景的推送序列

```
1. [partial_content] {is_partial: true, partial_text: "已查询...", interrupted_by: "correction", generation_id: "gen-1"}
2. [bridging] {signal_type: "correction", new_generation_id: "gen-2", continues_from: "gen-1"}
3. [content] {text: "好的，北京...", meta: {generation_id: "gen-2", continues_from: "gen-1", signal_source: "correction"}}
4. [content] {text: "明天晴天...", meta: {generation_id: "gen-2"}}
5. [done] {generation_id: "gen-2"}
```

### 9.4 背压处理

现有 `JobMessageLog` 的双写模式（PubSub + Stream）确保消息不丢失。对于介入场景的额外考虑：

1. **客户端慢消费**：Redis PubSub 是 fire-and-forget，`JobMessageLog` 保底。客户端可通过现有 `/api/v1/messages/replay` 端点做间隙恢复
2. **介入信号洪峰**：`_pending_interventions` 队列设置最大容量 10，超出时丢弃低优先级信号（SIDEKICK），CANCEL 始终绕过队列限制
3. **快速连续纠正**：1.5 秒去抖窗口，窗口内只保留最后一次 CORRECTION

### 9.5 去抖设计

```python
class InterventionDebouncer:
    """合并快速连续的同类介入信号。"""

    DEBOUNCE_WINDOW_SECONDS = 1.5

    def __init__(self):
        self._pending: Optional[InterventionSignal] = None
        self._timer: Optional[asyncio.TimerHandle] = None

    async def submit(self, signal: InterventionSignal) -> Optional[InterventionSignal]:
        # CANCEL 不参与去抖，立即执行
        if signal.type == "cancel":
            self._clear()
            return signal

        # 替换当前 pending（后到的信号覆盖先到的）
        self._pending = signal

        # 等待去抖窗口
        await asyncio.sleep(self.DEBOUNCE_WINDOW_SECONDS)

        # 如果这期间没有被更新的信号替换，执行当前信号
        if self._pending is signal:
            self._pending = None
            return signal

        return None  # 已被更新的信号取代
```

---

## 10. Session 状态管理

### 10.1 Redis 状态结构

```json
// SET session:status:{session_id} {json} EX 600
{
  "state": "GENERATING",
  "job_id": "current-job-uuid",
  "worker_id": "worker-hostname-pid",
  "sdk_session_id": "sdk-session-abc",
  "last_heartbeat": "2026-02-21T12:00:30Z",
  "task_summary": "查询北京明天的天气",
  "active_tool": "get_weather"
}
```

TTL 600 秒，Actor 每 10 秒心跳刷新。

### 10.2 心跳与故障检测

```python
async def _heartbeat_loop(self):
    while self._running:
        await self._update_session_status()
        await asyncio.sleep(10)

async def _update_session_status(self):
    status = SessionStatus(
        state=self._generation_state.value,
        job_id=self._current_job_id,
        worker_id=self._worker_id,
        sdk_session_id=self._sdk_session_id,
        last_heartbeat=utc_now().isoformat(),
        task_summary=self._current_task_summary,
        active_tool=self._active_tool_name,
    )
    await self._redis.set(
        f"session:status:{self.session_id}",
        json.dumps(asdict(status)),
        ex=600,
    )
```

### 10.3 Worker 崩溃恢复

1. Worker 进程死亡 → 心跳 TTL（30 秒）过期
2. `session:status` 变为 stale（`last_heartbeat` > 30 秒前）
3. 下一次 API 请求检测到 stale 状态
4. 新 Worker 接管：
   - 从 `AssistantChatSession.context["sdk_session_id"]` 加载 SDK 会话 ID
   - 尝试 SDK 会话恢复：`ClaudeAgentOptions(resume=sdk_session_id)`
   - 恢复失败则重新开始，用 stitching_context 作为前置上下文
5. 推送 `error` 事件到客户端，客户端显示"重新连接中..."

**恢复决策：**

| 条件 | 动作 |
|------|------|
| `sdk_session_id` 存在 且 会话年龄 < 30 分钟 | 尝试 SDK resume |
| Resume 失败 | 新会话 + stitching_context 作为前置 |
| 无 `sdk_session_id` | 新会话 |
| 会话年龄 > 30 分钟 | 新会话（SDK 会话已过期） |

---

## 11. 数据模型变更

### 11.1 `assistant_chat_messages` 表新增列

```sql
ALTER TABLE assistant_chat_messages ADD COLUMN generation_id UUID;
ALTER TABLE assistant_chat_messages ADD COLUMN is_partial BOOLEAN DEFAULT false;
ALTER TABLE assistant_chat_messages ADD COLUMN signal_type VARCHAR(30);
ALTER TABLE assistant_chat_messages ADD COLUMN continues_from UUID;

CREATE INDEX ix_chat_messages_generation ON assistant_chat_messages(generation_id);
```

- `generation_id`：标识同一次生成的内容块，interrupt + resume 后更换
- `is_partial`：标记被中断生成的消息
- `signal_type`：标记触发此消息的介入类型（correction / additive / digression / null）
- `continues_from`：引用此消息所续接的 `generation_id`

### 11.2 `assistant_chat_sessions` 表新增列

```sql
ALTER TABLE assistant_chat_sessions ADD COLUMN sdk_session_id VARCHAR(200);
ALTER TABLE assistant_chat_sessions ADD COLUMN generation_count INTEGER DEFAULT 0;
```

- `sdk_session_id`：当前关联的 SDK 会话 ID（已在 context JSONB 中存储，专列用于索引查询）
- `generation_count`：本会话累计生成次数（含 interrupt + resume），用于分析

### 11.3 介入审计日志表（新建）

```sql
CREATE TABLE intervention_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES assistant_chat_sessions(id),
    signal_id UUID NOT NULL,
    signal_type VARCHAR(30) NOT NULL,
    job_id VARCHAR(100) NOT NULL,
    user_id UUID NOT NULL,
    generation_state VARCHAR(20) NOT NULL,
    action_taken VARCHAR(30) NOT NULL,
    payload JSONB,
    classification_confidence FLOAT,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_intervention_audit_session ON intervention_audit_log(session_id, created_at);
CREATE INDEX ix_intervention_audit_type ON intervention_audit_log(signal_type);
```

- `generation_state`：收到信号时的 Actor 状态
- `action_taken`：实际执行的操作（interrupt_and_query / buffer / reject / inject / queue）
- `classification_confidence`：Haiku 分类器的置信度
- `latency_ms`：从信号发布到 SDK 操作的延迟

### 11.4 Redis-only 状态（无新 DB 表）

| Key | 类型 | TTL | 用途 |
|-----|------|-----|------|
| `session:status:{session_id}` | STRING (JSON) | 600s, 心跳刷新 | 跨进程状态可见性 |
| `session:stitch:{session_id}` | STRING (JSON) | 300s, 消费后删除 | 中断时的缝合上下文 |
| `session:signal:{session_id}` | PubSub channel | N/A | 介入信号传输 |

---

## 12. 移动端适配

### 12.1 BLoC 状态扩展

在现有 `AssistantLoaded` 状态基础上新增字段：

```dart
class AssistantLoaded extends AssistantState {
  // ... 现有字段 ...
  final String? currentGenerationId;      // 当前生成 ID
  final bool hasPartialMessage;            // 是否有 partial 消息
  final String? interruptionType;          // 当前中断类型
}
```

### 12.2 新增 StreamEventType

```dart
enum StreamEventType {
  // ... 现有类型 ...
  partialContent,    // 中断生成的部分内容
  bridging,          // 生成间过渡
  generationState,   // Agent 状态变更
  sidekickInsight,   // 主动洞察推送
}
```

### 12.3 事件处理

**partial_content 事件：**

```dart
void _handlePartialContent(Map<String, dynamic> data) {
  final generationId = data['generation_id'];
  final partialText = data['partial_text'];
  final interruptedBy = data['interrupted_by'];

  // 将当前 streaming 消息标记为 partial
  _updateMessageAsPartial(generationId, partialText);

  // 更新 UI 状态
  emit(state.copyWith(
    hasPartialMessage: true,
    interruptionType: interruptedBy,
  ));
}
```

**bridging 事件：**

```dart
void _handleBridging(Map<String, dynamic> data) {
  final signalType = data['signal_type'];
  final newGenerationId = data['new_generation_id'];

  // 根据介入类型决定 UI 行为
  switch (signalType) {
    case 'correction':
      // 准备替换 partial 消息的内容
      _prepareMessageReplacement(newGenerationId);
      break;
    case 'digression':
      // 不做特殊处理，新内容将作为新气泡
      break;
  }

  emit(state.copyWith(
    currentGenerationId: newGenerationId,
    hasPartialMessage: false,
  ));
}
```

### 12.4 partial 消息的 UI 呈现

对于 `is_partial=true` 的消息，在 `ChatBubble` 中：
- 降低透明度至 50%
- 显示小标签 "已更新" 或 "已取消"
- CORRECTION 场景：partial 消息被新生成内容替换时，使用过渡动画
- CANCEL 场景：partial 消息保留在对话流中，降低视觉权重

### 12.5 已排队消息的介入感知

现有 `_queuedMessages` 机制已支持用户在 AI 响应期间发送消息。新增的变化是 API 返回 `signal_accepted` 而非 `job_created`：

```dart
Future<void> _sendMessage(String text) async {
  final response = await _chatApi.sendMessage(text, sessionId);

  if (response.status == 'signal_accepted') {
    // 介入信号已接受，不创建新的 shadow message
    // 而是更新现有 streaming 消息的状态
    _showSignalAcceptedHint(response.signalType);
  } else {
    // 正常流程：创建 shadow message, 等待 SSE/WebSocket
    _startStreamMessage(text, response);
  }
}
```

`_showSignalAcceptedHint` 在输入区域上方显示一个短暂提示，如 "纠正信号已发送" 或 "补充信息已注入"，2 秒后自动消失。

---

## 13. 秘书行为模式与系统行为的映射

本节说明真实秘书的行为模式如何映射到系统的技术实现，确保 AI 秘书的交互体验符合用户对"专业秘书"的直觉预期。

### 13.1 纠错打断 → CORRECTION

**秘书行为**：立即停止当前输出，用"好的"+"复述关键词"确认接收，把注意力交还老板。

**系统映射**：`interrupt()` + `query()`。`partial_content` 事件让客户端知道"秘书停住了"。新 query 的 stitching prompt 中嵌入用户的纠正内容，Agent 的回复自然以确认语气开始（"好的，北京的天气..."），而非机械地说"检测到纠正指令"。

### 13.2 补充打断 → ADDITIVE

**秘书行为**：不中断主任务，用极简确认词吸收补充信息（"收到，靠窗"），然后无缝继续。

**系统映射**：TOOL_EXECUTING 期间 `query()` 合并到当前 turn。`[SUPPLEMENTARY_INFO]` 标签告诉 Agent 这是补充条件，不是新任务，Agent 会将其纳入当前推理而不单独回复。对应秘书行为中"便签贴到任务上"的模式。

### 13.3 跳跃打断 → DIGRESSION

**秘书行为**：自然响应新话题，尝试建立关联，用"对了..."把原话题挂起。

**系统映射**：DIGRESSION 排入 FIFO 队列，当前 turn 正常完成（原话题处理完毕），然后下一 turn 处理新话题。SDK 内部对话历史保留了完整上下文，Agent 可以在新话题回复后主动提及原话题进展（"对了，刚才的酒店我继续帮您看着"）。

### 13.4 否定打断 → CANCEL

**秘书行为**：不纠结沉没成本，接受变化，前瞻善后（"我把预订取消"）。

**系统映射**：`interrupt()` 后 Agent 收到 error ResultMessage。下一 turn 的 stitching prompt 包含被取消的操作信息，Agent 可以主动提出善后方案（"已取消查询，需要我帮您做别的吗？"），而非仅仅确认"已取消"。

### 13.5 主动信息植入 → SIDEKICK_INSIGHT

**秘书行为**：用"噢对了"、"顺便说一下"自然引入关联信息，附带解决方案，不强迫行动。

**系统映射**：Sidekick 注入的 `[SYSTEM_INSIGHT]` 标签 + "请在回复中自然融入"指令，让 Agent 模拟秘书的"自然植入"语气。Agent 可以选择以"顺便说一下..."的方式提及洞察，也可以在判断不相关时忽略它。

### 13.6 信息分级呈现 → 紧急度门控

**秘书行为**：紧急信息立刻打断（航班取消），重要信息等间隙（时间变更），日常信息攒批处理（快递到了）。

**系统映射**：
- urgency=high → TOOL_EXECUTING 期间注入（相当于"打断"）
- urgency=medium → 等待 IDLE 注入（相当于"话题间隙"）
- urgency=low → 不注入到活跃会话，等待下次 DailyBriefing 汇总播报

---

## 14. 场景演练

### 场景 1：用户纠正城市（CORRECTION）

```
用户: "帮我查上海明天的天气"
  → IntentRouter → Slow Path → Agent 开始查询上海天气
  → Agent: [thinking] 调用 get_weather("上海") 工具...

用户: "不对，查北京的"
  → API: GET session:status → state=TOOL_EXECUTING
  → InterventionClassifier: {type: "CORRECTION", confidence: 0.92}
  → PUBLISH session:signal → Actor 收到信号

Actor 行为:
  1. 检查 get_weather 是否在 NON_INTERRUPTIBLE_TOOLS → 不在
  2. 捕获 partial_text = ""（工具执行中还没输出文本）
  3. await client.interrupt()
  4. 保存 stitching: {completed_tools: [], partial_tool: {name: "get_weather", input: {city: "上海"}}}
  5. 推送 partial_content 事件
  6. 构建纠正 prompt: "用户的最新指示：查北京的天气"
  7. await client.query(corrected_prompt)

Agent 新 turn 回复: "好的，帮您查北京的天气。北京明天晴，最高5度..."
```

### 场景 2：用户补充条件（ADDITIVE）

```
用户: "帮我订杭州的酒店"
  → Agent 开始调用 search_hotels("杭州") 工具

用户: "要靠近西湖的"
  → API: GET session:status → state=TOOL_EXECUTING
  → InterventionClassifier: {type: "ADDITIVE", confidence: 0.88}
  → PUBLISH session:signal → Actor 收到信号

Actor 行为:
  1. 当前状态 TOOL_EXECUTING → ADDITIVE 可直接注入
  2. 构建补充 prompt: "[SUPPLEMENTARY_INFO] 用户补充: 要靠近西湖的 [/SUPPLEMENTARY_INFO]"
  3. await client.query(wrapped_prompt)
  4. SDK 将补充信息合并到当前 turn

Agent 回复（包含补充条件）: "收到。帮您在西湖附近找到了两家酒店：西湖国宾馆和..."
```

### 场景 3：话题跳跃（DIGRESSION）

```
用户: "帮我规划下周去深圳出差的行程"
  → Agent 正在生成行程方案（GENERATING 状态）

用户: "对了，明天下午的会议是几点？"
  → API: GET session:status → state=GENERATING
  → InterventionClassifier: {type: "DIGRESSION", confidence: 0.91}
  → PUBLISH session:signal → Actor 收到信号

Actor 行为:
  1. 当前状态 GENERATING → DIGRESSION 排入队列
  2. 当前 turn 正常完成
  3. Agent 回复完行程方案后 → ResultMessage → IDLE
  4. 取出队列中的 DIGRESSION 请求
  5. await client.query("明天下午的会议是几点？")
  6. Agent 查询后回复: "明天下午的会议是三点。对了，深圳行程的住宿我建议..."
```

### 场景 4：Sidekick 洞察注入

```
用户: "帮我看看下周去北京出差住哪里好"
  → Agent 调用 search_hotels("北京") 工具 → TOOL_EXECUTING

同时，CurationPipeline 检测到:
  - 用户下周去北京
  - 成员"张伟"也在北京（来自 trip_correlation）
  → SidekickWorker PUBLISH session:signal {type: sidekick_insight, insight_text: "张伟下周也在北京，上次他帮你接机"}

Actor 行为:
  1. 收到 sidekick_insight 信号
  2. 检查 urgency=medium → TOOL_EXECUTING 状态下 high 才注入 → 缓冲
  3. 工具完成 → GENERATING → ResultMessage → IDLE
  4. IDLE 时取出缓冲的 insight
  5. 检查相关性: "张伟" not in "北京出差住宿" → 但 "北京" 匹配 → 相关
  6. 注入: await client.query("[SYSTEM_INSIGHT] 张伟下周也在北京... [/SYSTEM_INSIGHT]")

Agent 回复: "酒店我推荐国贸附近的两家...顺便说一下，张伟下周也在北京呢，上次他帮您接过机，要不要顺便约一下？"
```

### 场景 5：快速连续纠正（去抖）

```
用户: "查上海天气"
  → Agent 开始查询

用户（0.5秒后）: "不对查北京"
  → InterventionClassifier: CORRECTION
  → Debouncer: 开始 1.5s 窗口

用户（0.8秒后）: "等等查广州"
  → InterventionClassifier: CORRECTION
  → Debouncer: 替换 pending（北京 → 广州），重置窗口

用户（2.5秒后无新消息）:
  → Debouncer: 窗口到期，执行最终信号（广州）
  → Actor: interrupt() + query("查广州天气")

结果: 只触发一次 interrupt + query，避免快速连续中断
```

### 场景 6：不可中断工具执行中的 CORRECTION

```
用户: "帮我给李总发条消息说周五的会改到下周一"
  → Agent 调用 send_message(to="李总", content="...") → TOOL_EXECUTING

用户: "不对，是改到下周二"
  → InterventionClassifier: CORRECTION
  → Actor 收到信号

Actor 行为:
  1. 检查 send_message 是否在 NON_INTERRUPTIBLE_TOOLS → 是
  2. 将 CORRECTION 存入 _deferred_intervention
  3. 等待 send_message 工具完成
  4. tool_result 到达后，检查 _deferred_intervention
  5. 执行 deferred CORRECTION: interrupt() + query()
  6. stitching prompt: "你已经给李总发了消息（周五改下周一），但用户纠正说应该是改到下周二。请处理这个更正。"

Agent 回复: "抱歉，我已经把消息发出去了说的是下周一。我再给李总发一条更正，改为下周二，您看可以吗？"
```

---

## 15. 故障模式与缓解

| 故障场景 | 发生概率 | 影响 | 缓解策略 |
|---------|---------|------|---------|
| Haiku 将 CORRECTION 误分为 ADDITIVE | 中 | 高（Agent 在错误方向继续，多了一条无用注入） | 降级到 ADDITIVE 是安全默认；用户下条消息自然会是更强的 CORRECTION |
| Haiku 将 ADDITIVE 误分为 CORRECTION | 低 | 中（不必要的 interrupt，但补充信息仍被处理） | 审计日志 + 置信度追踪，用于改进分类提示词 |
| interrupt() 在不可中断工具执行中被调用 | 极低 | 高（外部 API 操作已完成但 Agent 不知道） | NON_INTERRUPTIBLE_TOOLS 名单 + deferred 机制 |
| 累积介入导致 Token 溢出 | 中 | 中（SDK 自动压缩可能丢失重要上下文） | 介入预算 + 主动会话重置 |
| Sidekick 注入干扰当前任务 | 中 | 中（Agent 回复跑偏） | 实体交集检查 + 频率限制 + "如果无关则忽略" 指令 |
| 快速连续 CORRECTION | 低 | 中（多次 interrupt 浪费资源） | 1.5 秒去抖窗口 |
| Worker 崩溃导致生成丢失 | 低 | 高 | 30 秒心跳 TTL + SDK 会话恢复 + stitching_context |
| Redis 不可用 | 极低 | 高（状态不可见，信号不可达） | 降级为无介入模式，新消息走正常 FIFO 队列 |
| 缝合上下文丢失（Redis 驱逐） | 低 | 低 | 可接受的降级：Agent 开始新 turn，无断点上下文 |
| 上下文缓存在介入后过期未清 | 中 | 低 | 每次介入后触发 invalidate_context_cache() |

---

## 16. API 变更

### 16.1 POST /assistant/agent/chat（现有端点增强）

**新增响应格式**（当存在活跃生成时）：

```json
{
  "status": "signal_accepted",
  "signal_id": "uuid",
  "signal_type": "correction|additive|cancel|confirm|digression",
  "classification_confidence": 0.92
}
```

原有响应格式（无活跃生成时）不变。

### 16.2 GET /assistant/agent/status（现有端点增强）

**新增字段：**

```json
{
  "session_id": "...",
  "generation_state": "GENERATING|TOOL_EXECUTING|IDLE|WAITING_USER",
  "current_job_id": "...",
  "active_tool": "get_weather",
  "intervention_count": 2,
  "generation_count": 3
}
```

---

## 17. Implementation Notes

以下记录了实现过程中对原始设计的关键偏离，这些偏离均为工程改进：

### 17.1 回调式去抖器（非阻塞）替代 sleep 式（阻塞）

原始设计 (S9.5) 使用 `await asyncio.sleep(DEBOUNCE_WINDOW_SECONDS)` 实现去抖，这会阻塞当前协程 1.5 秒。实现改为**回调式去抖器**：使用 `asyncio.get_event_loop().call_later()` 注册延迟回调，在窗口到期时通过回调触发信号处理。这使得 Actor 主循环不被阻塞，可以继续处理其他事件（如 CANCEL 信号的立即执行）。

### 17.2 两阶段 asyncio.wait 优化

原始设计 (S3.4) 使用单一的三路 `asyncio.wait` 循环。实现改为两阶段：

- **Phase 1**（无活跃 SDK 工作）：仅等待 `queue_task` + `signal_task`（二路 wait），因为此时不存在活跃的 SDK client，不可能有 SDK 消息
- **Phase 2**（有活跃 SDK 工作）：完整三路 wait，加入 `message_task`

功能等价，但避免了 Phase 1 中 `message_task` 的无意义空转。

### 17.3 分离式信号缓冲区

原始设计使用单一的 `_deferred_intervention` 字段缓冲信号。实现改为**三个独立缓冲区**：

- `_buffered_additives: list` — 累积多条 ADDITIVE 信号，flush 时合并
- `_buffered_confirms: list` — 缓冲 CONFIRM 信号
- `_buffered_sidekicks: list` — 缓冲 SIDEKICK 信号

分离缓冲区避免了不同类型信号的互相覆盖，且允许同一 turn 内同时缓冲 ADDITIVE 和 SIDEKICK。

### 17.4 Actor 侧 Sidekick 速率限制（纵深防御）

原始设计将 Sidekick 注入频率限制放在 `SidekickWorker` 侧。实现在 Actor 侧增加了**独立的速率限制检查**作为纵深防御：即使 SidekickWorker 的限制被绕过或配置错误，Actor 仍然会拒绝超出预算的注入。这遵循了 "defense-in-depth" 安全原则。

### 17.5 异步缝合上下文保存

原始设计 (S5.1) 中缝合上下文的 Redis 保存是同步阻塞的 (`await self._save_stitching_context(stitching)`)。实现改为：

1. 在内存中构建 `StitchingContext`（零延迟）
2. 使用 `asyncio.create_task()` 在后台异步保存到 Redis
3. 主流程立即继续执行 `emit_partial_content` 和 `query()`

这将 CORRECTION 的端到端延迟降低了一次 Redis RTT（约 1-3ms），在快速纠正场景下体验更流畅。

### 17.6 partial_content 替换语义

`partial_content` 事件使用替换语义：后端发送完整的累积文本，而非增量差异。前端收到 `partial_content` 时用新文本完整替换当前生成内容。

### 17.7 Sidekick 刷新仅在 IDLE 转换时

Sidekick 缓冲信号仅在 generation 完成、状态转为 IDLE 时统一刷新（通过 `_flush_all_buffered()`），而非 S7.2 中描述的 TOOL_EXECUTING 期间注入。这避免了工具执行期间的上下文干扰。

### 17.8 CANCEL 仅取消活跃生成

CANCEL 信号仅取消当前活跃的生成，不影响队列中等待的请求。队列中的请求在当前请求完成（或取消）后正常处理。

### 17.9 预算检查前置（Pre-handler）

干预预算检查从 handler 执行后移至执行前。第 N 次超出预算的干预会被拒绝而非执行后再触发重置。CANCEL 信号豁免预算检查（始终允许执行）。

### 17.10 _defer_intervention 优先级比较

延迟干预使用优先级比较逻辑：CANCEL 始终覆盖已有延迟信号；高优先级（数值更小）覆盖低优先级；同优先级使用 last-write-wins 策略。防止低优先级信号覆盖已缓存的 CANCEL。

### 17.11 合并缓冲区刷新 (Combined Buffer Flush)

**设计原文**：各缓冲区（additive/confirm/sidekick）独立刷新，每类一次 `query()` 调用。

**实现调整**：`_flush_all_buffered()` 将所有缓冲区内容合并为单次 `query()` 调用，使用 `[SUPPLEMENTARY_INFO]` 标签区分不同类型的补充信息。

**原因**：避免 IDLE 转换时连续多次 SDK query 造成的延迟堆叠和 turn 碎片化。单次合并请求语义更清晰、延迟更低。

### 17.12 DIGRESSION 中断 WAITING_USER 的 Future 解析

当 DIGRESSION 在 WAITING_USER 状态下触发时，实现不仅执行 interrupt + partial_content + bridging + queue 流程，
还会将被中断请求的 Future 以 `stop_reason="digression_interrupt"` 解析，并弹出 `_pending`。
这意味着 AgentWorker 的 `await actor.submit()` 会收到一个带有 `digression_interrupt` 停止原因的 RunResult。
AgentWorker 必须优雅地处理此 stop_reason（视为正常完成，不重试）。

### 17.13 CORRECTION 中断后立即置为 IDLE

在 TOOL_EXECUTING 状态下处理 CORRECTION 时，`_interrupt_sdk()` 之后立即调用 `_set_state(IDLE)`，
而非等到 `_query_sdk()` 时才设为 GENERATING。这避免了 stitching 构建期间信号调度看到过期的 TOOL_EXECUTING 状态。
同样的模式应用于 `_do_cancel` 中的中断流程。

### 17.14 SidekickWorker 上下文相关性检查范围

`SidekickWorker._is_contextually_relevant()` 仅检查 `task_summary`（`user_input[:100]`），
不检查最近的工具调用结果。这是一个有意的简化：SidekickWorker 运行在 Actor 外部，无法访问 `_recent_tool_results`。
Actor 侧的防御性速率限制（每会话 3 次、每 turn 1 次、60 秒间隔）提供了额外保护。

### 17.15 Actor 侧 SIDEKICK 过期检查

`_do_sidekick` 在处理信号前检查 `payload.expires_at`，如已过期则返回 `reject_expired`。
这是对 SidekickWorker 预过滤的防御性补充，防止因 Redis 传输延迟导致过期洞察被注入。

### 17.16 CANCEL 后清空信号缓冲区

`_do_cancel` 在完成取消流程后，显式清空 `_buffered_additives`、`_buffered_confirms`、`_buffered_sidekicks` 三个缓冲区。
防止被取消生成期间积累的过期信号在下一次请求的 IDLE 转换时被 `_flush_all_buffered()` 错误地注入。

### 17.17 CANCEL 中 WAITING_USER 独立路径

`_do_cancel` 将 TOOL_EXECUTING 的非中断性检查（`_is_non_interruptible()`）与 WAITING_USER 分离为独立条件分支。
WAITING_USER 状态下 `_active_tool` 始终为 None，非中断性检查必然通过，但将两个状态混在同一分支会误导读者认为 WAITING_USER 可能被 defer。

### 17.18 CORRECTION 中 WAITING_USER 的完整断点保护

WAITING_USER 状态下处理 CORRECTION 时，增加了与 GENERATING 路径一致的完整流程：
1. `_set_state(IDLE)` 防止过期状态
2. `_create_stitching_context()` 构建缝合上下文
3. `asyncio.create_task()` 后台保存到 Redis
4. `_emit_partial_content()` 通知客户端
5. `_build_correction_prompt()` 使用缝合上下文构建纠正提示词

虽然 WAITING_USER 时 partial_text 通常很少，但完整流程确保了崩溃恢复的一致性，
并且纠正提示词可以包含 WAITING_USER 阶段已完成的工具信息。

### 17.19 CONFIRM 歧义标记与条件式二次确认

API 层 `_build_signal_payload` 在 CONFIRM 信号的关键词匹配中，当无法匹配到任何明确的肯定/否定词时，
默认设为 approve 但附加 `is_ambiguous: true` 标记。Actor 侧 `_do_confirm` 检测到该标记后，
对涉及支付、删除、发送等不可撤销操作的 PendingAction，指示 Agent 先向用户二次确认再执行。
这避免了模糊消息（如"嗯"、"那个"）被静默当作确认执行破坏性操作。

---

## 18. 与现有代码的对应关系

| 本方案组件 | 对应现有代码 | 变更类型 |
|-----------|------------|---------|
| ReactiveSessionActor | `session_streaming_executor.py:_SessionStreamingActor` | 替换（保留核心逻辑，新增信号监听和状态机） |
| InterventionClassifier | `intent_router.py:IntentRouter._call_unified_classifier` | 新增（InterventionClassifier 与 IntentRouter 共享 Haiku 客户端单例 (`get_haiku_client()`) 和模型配置 (`settings.intent_router_model`)，但使用独立的 `classify()` 实现，具有不同的 prompt 结构（专注于介入分类而非意图路由）） |
| InterventionSignal | 无 | 新增 dataclass |
| StitchingContext | 无 | 新增 dataclass |
| InterventionBudget | 无 | 新增 dataclass |
| InterventionDebouncer | 无 | 新增 |
| session:status Redis 结构 | `sdk_client_pool.py:sdk_pool:active:{session_id}` | 扩展（增加 state, job_id, task_summary 等字段） |
| session:signal Redis 通道 | 无 | 新增 PubSub 通道 |
| session:stitch Redis 结构 | 无 | 新增 |
| SidekickWorker | `insight/services/insight_orchestrator.py` | 新增 Worker，调用现有 InsightOrchestrator |
| 新 MessageType 枚举值 | `ai_engine/sdk/sdk_stream_handler.py:MessageType` | 扩展 |
| NON_INTERRUPTIBLE_TOOLS | `ai_engine/tools/` 各工具定义 | 新增属性标记 |
| intervention_audit_log 表 | 无 | 新建 |
| assistant_chat_messages 新列 | `modules/conversation/models.py` | ALTER TABLE |
| assistant_chat_sessions 新列 | `modules/conversation/models.py` | ALTER TABLE |
| Mobile StreamEventType 新值 | `mobile/lib/features/assistant/data/models/` | 扩展枚举 |
| Mobile partial_content 处理 | `mobile/lib/features/assistant/presentation/bloc/assistant_bloc.dart` | 新增事件处理 |
