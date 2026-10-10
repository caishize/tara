# 对话流优化方案

> 基于 `docs/chat-flow-review.md` 审计的 25 个问题，由产品体验官、后端架构师、安全/SRE 三个视角交叉讨论产出。
>
> **团队讨论记录**：三方各自独立分析后，发现 25 个问题形成四条因果链。产品体验官从"秘书信任度"切入，识别出移动端切后台消息丢失是最高频痛点；架构师从连接池压力和可靠性切入，确认 PubSub fire-and-forget 是消息丢失的根因；安全/SRE 在 cancel 权限校验上给出了 API 层 + Worker 层双重防护方案，并提出用 hostname+pid 替代随机 UUID 从根源消除僵尸 consumer。

---

## 核心洞察：四条因果链

审计的 25 个问题不是 25 个独立 bug，它们形成了四条因果链，每条链上的问题互相放大。方案按因果链组织，每条链内的改动构成闭环。

```
链A 消息丢失链 (#2 → #8 → #4 → #25)
  PubSub fire-and-forget → 重连间隙丢消息 → 异常时前端无兜底 → 非关键事件静默丢弃
  结果：用户问了问题，秘书回了答案，但用户永远看不到

链B 卡死链 (#1 → #9 → #7 → #15)
  streaming-input 无超时 → Worker 与 API 共进程 → SIGKILL 恢复要 2 分钟 → DLQ 无告警
  结果：秘书"思考中..."永远不结束，用户杀掉 App 重进也没用

链C 失忆链 (#3 → #10 → #13 → #19)
  Hybrid Fast→Slow 上下文截断 → 双重加载浪费且不一致 → upgrade_to_slow 不存盘 → 缓存返回过时上下文
  结果：秘书刚说完天气 25 度，下一秒又去查了一遍天气

链D 安全链 (#5 → #23 → #16)
  cancel 无归属校验 → WS 认证绕过 → edit 并发写入竞争
  结果：别人可以打断你和秘书的对话
```

---

## 链A：消息可靠投递

### 场景

> 妈妈在地铁里问秘书："爸爸的生日是哪天？帮我提前准备一下。"
> 秘书回复了生日日期和蛋糕预订确认卡片。但地铁过隧道时 WebSocket 断了 2 秒。
> 妈妈重新打开 App，看到的是空白——秘书的回复消失了。

技术上：WS 断连但 PubSub 订阅尚未取消，`receivers > 0`，消息不进 offline queue 也到不了客户端。重连后 offline queue 为空。

### A1. 引入 Job Message Log

**核心思路**：每条关键消息在 PubSub 发布的同时写入 per-job 有序日志（Redis ZSET），客户端重连时按 `job_id + last_seq` 补齐。不依赖 `receivers` 计数。

**新建文件** `core/pubsub/job_message_log.py`

```python
class JobMessageLog:
    """Per-job ordered message log for gap recovery.

    使用 Redis ZSET，score = seq，member = JSON payload。
    写入 O(log N)，范围查询 O(log N + M)。
    TTL 1 小时后自动清理。
    """
    KEY_PREFIX = "job_log"
    DEFAULT_TTL = 3600

    async def append(self, job_id: str, seq: int, message: dict) -> None:
        key = f"{self.KEY_PREFIX}:{job_id}"
        payload = json.dumps(message, ensure_ascii=False)
        await self._redis.zadd(key, {payload: seq})
        await self._redis.expire(key, self.DEFAULT_TTL)

    async def get_after(self, job_id: str, after_seq: int) -> list[dict]:
        """返回 seq > after_seq 的所有消息，按 seq 排序。"""
        key = f"{self.KEY_PREFIX}:{job_id}"
        raw = await self._redis.zrangebyscore(key, f"({after_seq}", "+inf")
        return [json.loads(r) for r in raw]
```

### A2. PubSub 双写

**改动文件** `core/pubsub/redis_pubsub.py` — `publish()` 方法

```python
# 关键消息类型：无条件写入 Job Message Log
_CRITICAL_TYPES = {
    MessageType.CONTENT,
    MessageType.COMPLETE,
    MessageType.ERROR,
    MessageType.CONFIRM_CARD,
    MessageType.TOOL_EXECUTION,
    MessageType.ASK_USER_QUESTION,
}

async def publish(self, user_id: str, message: PubSubMessage) -> int:
    message_json = json.dumps(message.to_dict(), ensure_ascii=False)

    # 双写：无条件写 Job Log（不依赖 receivers 计数）
    if message.job_id and message.seq and message.message_type in self._CRITICAL_TYPES:
        await self._job_log.append(message.job_id, message.seq, message.to_dict())

    receivers = await self._publisher.publish(channel, message_json)

    # offline queue 保留作为 user 级兜底
    if receivers == 0:
        await get_offline_queue().push(user_id, message.to_dict())

    return receivers
```

**为什么不直接去掉 offline queue？** offline queue 覆盖"用户完全离线 1 小时后重连"的场景（Job Log TTL 只有 1 小时），两者互补而非替代。

### A3. 重连补齐协议

**改动文件** `core/websocket/manager.py` — `start_listening()` 方法

WebSocket 连接建立后的恢复顺序（解决 #8 重连间隙问题）：

```python
async def start_listening(self, user_id: str, websocket: WebSocket):
    # 1. 先 drain offline queue（覆盖完全离线期间的消息）
    await self._drain_offline_to_ws(user_id, websocket)

    # 2. subscribe Redis PubSub
    await self._subscribe(user_id)

    # 3. 二次 drain（覆盖步骤 1-2 之间到达的消息）
    await self._drain_offline_to_ws(user_id, websocket)

    # 4. 如果客户端携带 resume 参数，从 Job Log 补齐
    if resume_job_id and last_seq is not None:
        missed = await self._job_log.get_after(resume_job_id, last_seq)
        for msg in missed:
            await websocket.send_json(msg)
```

**客户端协议扩展**：WebSocket 握手时支持 query param `?resume_job_id=xxx&last_seq=5`。

### A4. Fast/Hybrid 异常兜底 (解决 #4)

**改动文件** `chat.py` — `_dispatch_ws_chat_job()`

```python
task = asyncio.create_task(publish_fast_path(...))
task.add_done_callback(lambda t: _on_background_task_done(t, job_id, user_id, session_id))

async def _on_background_task_done(task, job_id, user_id, session_id):
    """background task 异常时写 Redis 标记，前端 poll 端点可查到。"""
    exc = task.exception()
    if exc is None:
        return
    logger.error("Background task %s failed: %s", job_id, exc)
    try:
        await redis_client.set(
            f"job_status:{job_id}",
            json.dumps({"status": "error", "message": "处理失败，请重试"}),
            ttl=300,
        )
    except Exception:
        pass
```

### A5. SDK stream handler 非关键事件丢失补偿 (解决 #25)

**改动文件** `ai_engine/sdk/sdk_stream_handler.py`

当前只有 `content_publish_failed` flag。增加 `tool_execution_publish_failed`：

```python
# 在 _emit() 中：
except Exception as e:
    if event_type == "content":
        self._content_publish_failed = True
    elif event_type == "tool_execution":
        self._tool_publish_failed = True
    # 非关键事件不中断流，但记录到 metadata
    self._failed_events.append({"type": event_type, "error": str(e)})
```

AgentWorker 在 `_publish_content(is_final=True)` 时，把 `_failed_events` 附到 final payload 中，前端可根据此信息做 UI 降级（如显示"部分工具执行状态未能实时展示"）。

### 链A 闭环验证

| 场景 | 断连时机 | 恢复路径 | 消息丢失？ |
|------|---------|---------|-----------|
| 地铁闪断 2s | Fast 正在 streaming | 重连 → Job Log 补齐 | 否 |
| 切后台 30s | Slow COMPLETE 已发 | offline queue + Job Log 双保险 | 否 |
| 飞行模式 1h | Job Log 未过期 | Job Log 补齐 | 否 |
| 飞行模式 2h | Job Log 已过期 | offline queue（如果当时 receivers=0）+ 历史 API 兜底 | 部分（可接受） |
| Redis PubSub 宕机 | Fast 内部异常 | done_callback 写 Redis 标记 → 前端 poll 查到 error | 否 |

---

## 链B：超时卡死根治

### 场景

> 用户问秘书："帮我规划这周全家出游的行程。"
> Slow path SDK 子进程调用行程规划 tool，tool 内部死锁。
> 用户看到"思考中..."转圈 10 分钟。杀掉 App 重进，还是转圈。
> 因为 streaming-input 模式禁用了超时，Worker semaphore 槽位被永久占用。
> 其他用户的请求也开始排队。

### B1. Streaming-input 最大执行时间上限 (解决 #1)

**改动文件** `worker_runner.py` — `_process_task()`（约第 128 行附近）

```python
if _should_disable_worker_timeout(task):
    # streaming-input 模式也需要绝对上限，防止无限卡死
    max_timeout = settings.streaming_input_max_timeout_seconds  # 默认 600s
    await asyncio.wait_for(worker.process(task, pubsub), timeout=max_timeout)
else:
    await asyncio.wait_for(
        worker.process(task, pubsub),
        timeout=settings.worker_task_timeout_seconds,
    )
```

**新增配置** `config/settings.py`:
```python
streaming_input_max_timeout_seconds: int = 600  # 10 minutes
```

**为什么是 10 分钟？** 行程规划等复杂 tool chain 实测最长约 3-5 分钟。10 分钟留足余量同时防止永久卡死。

### B2. Worker 恢复加速 (解决 #7)

**改动文件** `task_queue.py` — `_claim_stale_messages()`

```python
# 原值: claim_timeout_ms = 90000 (90s)
# 新值: claim_timeout_ms = 35000 (35s，略大于 heartbeat TTL 30s)
```

恢复延迟：30s (heartbeat TTL 过期) + 35s (claim) = ~65s，从 ~2 分钟缩短到 ~1 分钟。

### B3. DLQ 写入时通知用户 (解决 #15)

**改动文件** `task_queue.py` — `move_to_dlq()` 方法

```python
async def move_to_dlq(self, task_data, reason, message_id):
    # ... 现有 DLQ 写入逻辑 ...

    # 新增：通知用户请求已失败
    try:
        task = TaskPayload.from_dict(task_data)
        pubsub = get_pubsub_manager()
        await pubsub.publish_error(
            user_id=task.user_id,
            error_message="处理请求时出现异常，请重新发送。",
            error_code="DLQ_MOVED",
            trace_id=task.job_id,
            session_id=task.session_id,
        )
    except Exception:
        pass  # DLQ 通知是 best-effort
```

### B4. DLQ 深度监控 (解决 #15 运维侧)

**新建文件** `ai_engine/queue/dlq_monitor.py`

```python
class DLQMonitor:
    """定期检查 DLQ 深度，超阈值触发告警。"""
    CHECK_INTERVAL = 60
    ALERT_THRESHOLD = 10

    async def run(self):
        while True:
            await asyncio.sleep(self.CHECK_INTERVAL)
            depth = await self._redis.xlen("agent:tasks:dlq")
            dlq_depth_gauge.set(depth)
            if depth >= self.ALERT_THRESHOLD:
                logger.critical("DLQ depth %d exceeds threshold", depth)
```

**集成点**：在 `worker_runner.py:run_agent_worker_loop()` 启动时 `asyncio.create_task(DLQMonitor().run())`。

### 链B 闭环验证

| 场景 | 当前结果 | 改后结果 |
|------|---------|---------|
| Tool 死锁 | 永远卡住 | 10min 后超时，用户收到"处理超时，请重试" |
| Worker SIGKILL | 2min 后恢复 | ~65s 后恢复 |
| 任务进 DLQ | 静默消失 | 用户收到错误通知 + Prometheus 告警 |

---

## 链C：上下文一致性

### 场景

> 用户问："今天南澳天气怎么样？"
> Hybrid Fast leg 查了天气并回复"南澳今天 25°C，多云"。
> Hybrid Slow leg 启动时，`fast_result_summary` 只截取了 500 字符的摘要。
> Slow leg 的 system prompt 里只有一句模糊提示，不知道具体温度。
> 于是 Slow leg 又调了一次天气 API，回复"南澳目前 25°C，建议穿薄外套"。
> 用户看到两条天气回复，觉得秘书在自言自语。

### C1. Hybrid Fast→Slow 完整传递 (解决 #3)

**改动文件** `ws_publishers.py` — `publish_hybrid_path()` 第 604-611 行

```python
context_snapshot: Dict[str, Any] = {
    "hybrid_hint": True,
    "fast_action": intent.action.value if getattr(intent, "action", None) else "",
    "fast_lookup_filter": intent.lookup_filter or "",
    # 改动：从 500 扩展到 2000 字符，覆盖绝大多数 Fast 回复
    "fast_result_summary": full_text[:2000] if full_text else "",
    "fast_response_text": full_text[:2000] if full_text else "",
    # 新增：传递工具调用摘要，让 Slow leg 知道哪些工具已执行
    "fast_tool_calls": [
        {"name": tc.get("tool_name", ""), "summary": str(tc.get("result", ""))[:200]}
        for tc in tool_calls
        if tc.get("type") == "tool_result"
    ],
}
```

**改动文件** `agent_worker.py` — `_build_system_prompt()` 中 `hybrid_background` 分支

```python
if task and task.route_type == "hybrid_background":
    snapshot = task.context_snapshot or {}
    fast_text = snapshot.get("fast_response_text", "")
    fast_tools = snapshot.get("fast_tool_calls", [])

    if fast_text or fast_tools:
        sections = ["## 快速回复已完成的内容（请勿重复查询或重复回答）"]
        if fast_text:
            sections.append(f"已回复用户的文本:\n{fast_text}")
        if fast_tools:
            tool_names = ", ".join(t["name"] for t in fast_tools if t.get("name"))
            sections.append(f"已调用的工具: {tool_names}")
        sections.append("请在此基础上提供补充分析或建议，不要重复上述内容。")
        prompt += "\n\n" + "\n".join(sections)
```

### C2. 消除 AgentWorker 双重上下文加载 (解决 #10)

**改动文件** `agent_worker.py:process()` — 第 247-257 行

```python
# 1. ContextAssembler（L1-L4 全层）
assembled_context_text = await self._try_assemble_context(task, action_type)

# 2. Legacy rehydration：当 assembler 成功时跳过对话历史加载
context = await self._rehydrate_context(
    task,
    skip_conversation_history=bool(assembled_context_text),
)
```

**改动文件** `agent_worker.py:_rehydrate_context()` — 增加参数

```python
async def _rehydrate_context(self, task, skip_conversation_history=False):
    context = await self.rehydration_service.build_context(
        user_id=UUID(task.user_id),
        family_id=UUID(task.family_id),
        session_id=task.session_id,
        # 当 ContextAssembler 已提供 L2 时，不重复加载对话历史
        max_conversation_turns=0 if skip_conversation_history else 10,
    )
    # partial_context 处理保持不变（Fast→Slow upgrade 场景仍需要）
    ...
    return context
```

**省下的查询**：每个 Slow path 请求减少一次 `conversation_messages` 表的全 session 扫描。

### C3. ContextAssembler 减少 DB 连接数 (解决 #11)

**改动文件** `context_assembler.py:_collect()` + `context_fetchers.py`

当前 4 个 fetcher 各自 `async with get_db_session()` 开独立连接。改为 L1/L2/L3 共享一个 session，L4（memory recall，涉及 embedding 向量查询）保持独立。

```python
async def _collect(self, user_id, family_id, session_id, user_message, resolved_ids):
    # L1/L2/L3 共享 session（省 2 个连接）
    async with async_session_maker() as shared_db:
        l1, l2, l3 = await asyncio.gather(
            _fetch(self._l1_fetcher, user_id, family_id, db=shared_db),
            _fetch(self._l2_fetcher, user_id, session_id, db=shared_db),
            _fetch(self._l3_fetcher, user_id, family_id, resolved_ids, db=shared_db),
        )

    # L4 独立 session（向量查询可能慢，不阻塞其他层）
    l4 = await _fetch(self._l4_fetcher, user_id, user_message)

    return l1, l2, l3, l4
```

**前提**：每个 fetcher 需支持接收外部 `db` 参数。当前签名是 `async def fetch_l1_notes(user_id, family_id)`，需扩展为 `async def fetch_l1_notes(user_id, family_id, db=None)`，内部判断 `db` 是否为 None 来决定是否创建新 session。

**连接数变化**：每请求 4 连接 → 2 连接。

### C4. upgrade_to_slow 时持久化 Fast 阶段结果 (解决 #13)

**改动文件** `ws_publishers.py:publish_fast_path()` — `upgrade_to_slow` 分支（第 277 行附近）

```python
elif chunk_type == "upgrade_to_slow":
    # 先持久化已产出的 Fast 内容
    partial_text = "".join(collected_text)
    if partial_text:
        await msg_svc.save_assistant_message(
            session_id=UUID(session_id),
            content=partial_text,
            path_type="fast",
            tool_calls=tool_calls if tool_calls else None,
            metadata={"upgraded_to_slow": True, "job_id": job_id},
        )
        await db.commit()

    # 然后执行升级（原有逻辑不变）
    ...
```

**同理** `publish_hybrid_path()` 中的 `upgrade_to_slow` 分支也需同样处理。

### C5. 缓存事件驱动失效 (解决 #19)

**改动文件** 在关键写入点主动失效 ContextAssembler 缓存

```python
# modules/conversation/message_service.py — save_assistant_message() 末尾
from ...ai_engine.context_assembler import ContextAssembler
await ContextAssembler.invalidate_context_cache(user_id)

# modules/memory/memory_service.py — extract_and_save() 末尾
await ContextAssembler.invalidate_context_cache(user_id)
```

5 分钟 TTL 保留作为兜底（防止写入点遗漏），但热路径通过事件驱动失效保证新消息立即可见。

### 链C 闭环验证

| 场景 | 当前结果 | 改后结果 |
|------|---------|---------|
| Hybrid "南澳天气" | Slow leg 重新查天气，用户看到两条重复 | Slow leg 知道天气已查，只补充穿衣建议 |
| Slow path 上下文加载 | ContextAssembler + ContextService 各查一次对话历史 | ContextAssembler 查一次，ContextService 跳过 |
| Fast→Slow upgrade | Fast 阶段已回复的文本丢失 | 持久化后再升级，对话历史完整 |
| 连续对话 | 5min 内缓存可能返回旧上下文 | 写入新消息时立即失效缓存 |

---

## 链D：安全加固

### 场景

> 恶意用户 Bob 从共享 iPad 的浏览器存储中获取了 Alice 的 session_id。
> Bob 调用 `POST /chat/cancel`，传入 Alice 的 session_id。
> Alice 正在和秘书规划春节出行，突然回复中断，显示"已取消"。
> Alice 完全不知道发生了什么。

### D1. cancel_generation 双重归属校验 (解决 #5)

安全/SRE 提出 API 层 + Worker 层双重防护，防止单点绕过。

**改动文件 1** `chat.py:cancel_generation()` — 第 724-744 行（API 层）

```python
@router.post("/cancel")
async def cancel_generation(
    request: CancelRequest,
    db: AsyncSession = Depends(get_db),  # 新增 DB 依赖
):
    _check_agent_enabled()
    user_id, _ = require_auth()

    # 新增：校验 session 属于当前用户
    session_uuid = _validate_uuid(request.session_id, "session_id")
    result = await db.execute(
        select(AssistantChatSession).where(
            AssistantChatSession.id == session_uuid,
            AssistantChatSession.user_id == user_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Session not found")

    cancel_key = f"cancel:{request.session_id}"
    # value 存入 user_id，Worker 侧可二次校验
    await redis_client.set(cancel_key, str(user_id), ttl=60)
    return {"status": "cancelled", "session_id": request.session_id}
```

**改动文件 2** `agent_worker.py:_check_cancel()` — 第 160-175 行（Worker 层）

```python
async def _check_cancel(self, session_id, task_user_id=None):
    cancel_key = f"{self.CANCEL_KEY_PREFIX}{session_id}"
    cancel_value = await redis_client.get(cancel_key)
    if cancel_value:
        # 二次校验：cancel 发起者必须是 session 所有者
        if task_user_id and cancel_value != task_user_id:
            logger.warning(
                "Cancel key user_id mismatch: key=%s, task=%s",
                cancel_value, task_user_id,
            )
            await redis_client.delete(cancel_key)  # 清除非法 key
            return False
        await redis_client.delete(cancel_key)
        self._cancelled = True
        return True
    return False
```

### D2. WebSocket 生产认证白名单 + 启动断言 (解决 #23)

安全/SRE 指出 `settings.environment` 默认值为 `"development"`，配置漂移风险高。方案包含两层防护。

**改动文件 1** `core/websocket/websocket.py` — `verify_websocket_token()`

白名单逻辑——只有明确 `== "development"` 时才降级：

```python
except JWTError:
    if settings.environment == "development" and not settings.strict_auth_enabled:
        logger.warning("WS auth dev fallback for path user_id=%s", user_id)
        return _DEFAULT_USER_ID, _DEFAULT_FAMILY_ID
    # 所有非 "development" 环境一律拒绝
    raise HTTPException(status_code=401, detail="Invalid token")
```

**改动文件 2** `main.py` — lifespan 启动检查

```python
# 生产环境强制要求 strict_auth
if settings.environment != "development" and not settings.strict_auth_enabled:
    raise RuntimeError(
        "STRICT_AUTH_ENABLED must be true in non-development environments. "
        f"Current environment={settings.environment}"
    )
```

### D3. feedback JSONB 变更检测 (解决 #17)

**改动文件** `chat.py` — feedback 端点（约第 962-970 行）

```python
from sqlalchemy.orm.attributes import flag_modified

message.message_metadata = {**(message.message_metadata or {}), **new_feedback_data}
flag_modified(message, "message_metadata")  # 确保 SQLAlchemy 检测到 JSONB 变更
await db.commit()
```

### D4. edit_message 悲观锁 (解决 #16)

安全/SRE 分析了并发 edit + chat 写入竞争的攻击路径。

**改动文件** `chat.py` — `edit_message()` 第 590 行附近

在标记 `is_superseded` 前对 session 行加悲观锁，防止并发写入导致历史分叉：

```python
# 先锁定 session，防止并发写入
await db.execute(
    select(AssistantChatSession)
    .where(AssistantChatSession.id == session_uuid)
    .with_for_update()
)
# 然后标记 is_superseded 和后续操作
```

### 链D 闭环验证

| 攻击路径 | 当前结果 | 改后结果 |
|---------|---------|---------|
| Bob 用 Alice 的 session_id 调 cancel | Alice 对话被中断 | API 层 404 + Worker 层 user_id 校验双重拦截 |
| environment 配错为 "prod" | WS 认证静默降级 | 启动断言直接 crash + 401 拒绝连接 |
| 并发 feedback 写入 | JSONB 变更可能丢失 | flag_modified 确保 flush |
| 并发 edit + chat 写入 | 历史分叉 | FOR UPDATE 悲观锁串行化 |

---

## 独立优化项

以下问题不属于四条因果链，但值得独立修复。

### E1. Session Lock 去重 (解决 #18)

**问题**：`ws_publishers.py:38-57` 和 `worker_runner.py:37-71` 存在两份几乎相同的 `_acquire_session_lock` 实现。

**新建文件** `core/concurrency/session_lock.py`

```python
class SessionLockManager:
    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}
        self._refs: Dict[str, int] = {}
        self._guard = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self, session_id: Optional[str]):
        if not session_id:
            yield
            return
        async with self._guard:
            if session_id not in self._locks:
                self._locks[session_id] = asyncio.Lock()
                self._refs[session_id] = 0
            self._refs[session_id] += 1
        lock = self._locks[session_id]
        await lock.acquire()
        try:
            yield
        finally:
            lock.release()
            async with self._guard:
                self._refs[session_id] -= 1
                if self._refs[session_id] <= 0 and not lock.locked():
                    self._locks.pop(session_id, None)
                    self._refs.pop(session_id, None)
```

`ws_publishers.py` 和 `worker_runner.py` 各自引用 `SessionLockManager` 的独立实例。

### E2. cancel 轮询延迟优化 (解决 #12)

当前 heartbeat 10s 一次，最坏延迟 10s。改为 `_run_heartbeat` 中 `asyncio.sleep(3)` 但只在 `has_pending_tools` 时发 progress 消息（每 10s），cancel 检查频率提升到 3s。

```python
async def _run_heartbeat(self, pubsub, task):
    _progress_interval = 10
    _check_interval = 3
    _last_progress = 0
    while True:
        await asyncio.sleep(_check_interval)
        # cancel 检查：每 3s
        if await self._check_cancel(task.session_id):
            await self._publish_cancelled(task, pubsub)
            return
        # progress 发布：每 10s（仅有 pending tools 时）
        now = time.monotonic()
        if now - _last_progress >= _progress_interval and has_pending_tools:
            await pubsub.publish_tool_execution(...)
            _last_progress = now
```

### E3. Worker consumer_name 稳定标识 + zombie 清理 (解决 #20)

安全/SRE 指出：随机 UUID consumer_name 是僵尸累积的根因，定期清理只是治标。用 hostname+pid 从根源消除。

**改动文件** `worker_runner.py` — 第 247 行

```python
# 原: consumer_name = f"worker-{uuid4()}"
# 改: 稳定标识，重启后重用同一 consumer 名
import socket, os
consumer_name = f"worker-{socket.gethostname()}-{os.getpid()}"
```

**优点**：
- 重启后自动续接 PEL 中的挂起消息
- 无僵尸 consumer 累积
- session affinity map 中的 worker ID 保持稳定

**辅助清理**：仍保留定期清理作为防御层

```python
# task_queue.py — 新增方法
async def cleanup_zombie_consumers(self, group: str, idle_threshold_ms: int = 300000):
    consumers = await self._redis.xinfo_consumers(self.stream_key, group)
    for c in consumers:
        if c["idle"] > idle_threshold_ms and c["pending"] == 0:
            await self._redis.xgroup_delconsumer(self.stream_key, group, c["name"])
            logger.info("Cleaned zombie consumer: %s (idle %dms)", c["name"], c["idle"])
```

### E4. poll fallback JSONB 索引 (解决 #22)

**新建 migration**

```sql
CREATE INDEX idx_conversation_messages_metadata_job_id
ON conversation_messages
USING GIN ((message_metadata->'job_id'));
```

### E5. AsyncOpenAI client 复用 (解决 #24)

**改动文件** `chat.py` — `_transcribe_voice_upload()` 附近

```python
_openai_client: Optional[AsyncOpenAI] = None

def _get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client
```

### E6. SDK Pool marker TTL 对齐 (解决 #6)

**改动文件** `sdk_client_pool.py`

```python
# marker TTL 应 = idle_timeout + cleanup_interval + buffer
MARKER_TTL = settings.sdk_client_pool_idle_timeout_seconds + 120
# 而非当前的 1800s（30 分钟）
```

确认 `_cleanup_idle()` → `_close_client()` → `_clear_active_marker()` 调用链完整。

### E7. 三套 Session 序列化统一 (解决 #21)

**新建文件** `ai_engine/session_strategy.py`

```python
class SessionExecutionStrategy(ABC):
    @abstractmethod
    async def execute(self, task: TaskPayload, process_fn) -> None: ...

class LockStrategy(SessionExecutionStrategy): ...
class MailboxStrategy(SessionExecutionStrategy): ...
class StreamingActorStrategy(SessionExecutionStrategy): ...

def resolve_strategy(task: TaskPayload) -> SessionExecutionStrategy:
    if settings.sdk_streaming_input_enabled and task.route_type in {"slow", "hybrid_background"}:
        return StreamingActorStrategy()
    if settings.session_mailbox_enabled and task.session_id:
        return MailboxStrategy()
    return LockStrategy()
```

`worker_runner.py` 中的 `_should_use_session_mailbox` / `_should_acquire_session_lock` / `_should_disable_worker_timeout` 合并为一次 `resolve_strategy()` 调用。

---

## 实施矩阵

按因果链 + 独立项排列，每行标注改动范围和前置依赖。

| ID | 改动 | 涉及文件 | 新建文件 | 前置依赖 |
|----|------|----------|----------|----------|
| **链A** | | | | |
| A1 | Job Message Log | — | `core/pubsub/job_message_log.py` | 无 |
| A2 | PubSub 双写 | `core/pubsub/redis_pubsub.py` | — | A1 |
| A3 | 重连补齐协议 | `core/websocket/manager.py` | — | A1 |
| A4 | Fast/Hybrid 异常兜底 | `chat.py` | — | 无 |
| A5 | 非关键事件丢失补偿 | `sdk_stream_handler.py` | — | 无 |
| **链B** | | | | |
| B1 | Streaming-input 超时上限 | `worker_runner.py`, `settings.py` | — | 无 |
| B2 | Worker 恢复加速 | `task_queue.py` | — | 无 |
| B3 | DLQ 通知用户 | `task_queue.py` | — | 无 |
| B4 | DLQ 监控 | `worker_runner.py` | `ai_engine/queue/dlq_monitor.py` | 无 |
| **链C** | | | | |
| C1 | Hybrid 完整传递 | `ws_publishers.py`, `agent_worker.py` | — | 无 |
| C2 | 消除双重上下文加载 | `agent_worker.py` | — | 无 |
| C3 | 减少 DB 连接数 | `context_assembler.py`, `context_fetchers.py` | — | 无 |
| C4 | upgrade_to_slow 持久化 | `ws_publishers.py` | — | 无 |
| C5 | 缓存事件失效 | `context_assembler.py`, 各 service | — | 无 |
| **链D** | | | | |
| D1 | cancel 归属校验 | `chat.py` | — | 无 |
| D2 | WS 认证白名单 | `websocket.py` | — | 无 |
| D3 | JSONB flag_modified | `chat.py` | — | 无 |
| **独立** | | | | |
| E1 | Session Lock 去重 | `ws_publishers.py`, `worker_runner.py` | `core/concurrency/session_lock.py` | 无 |
| E2 | cancel 轮询加速 | `agent_worker.py` | — | 无 |
| E3 | zombie consumer 清理 | `task_queue.py`, `worker_runner.py` | — | 无 |
| E4 | JSONB 索引 | — | migration | 无 |
| E5 | OpenAI client 复用 | `chat.py` | — | 无 |
| E6 | SDK marker TTL 对齐 | `sdk_client_pool.py` | — | 无 |
| E7 | Session 策略统一 | `worker_runner.py` | `ai_engine/session_strategy.py` | E1 |
| E8 | Hybrid Leg2 完成通知 | `agent_worker.py`, Flutter push | — | 无 |
| E9 | ContextAssembler 缓存 key 加 last_message_id | `context_assembler.py` | — | 无 |

---

## 团队讨论中的补充洞察

### E8. Hybrid Leg2 完成时 push 通知（产品体验官提出）

Hybrid 模式的"正在思考是否还有关联事项..."发出后，用户可能已离开当前对话界面。Leg2 完成时静默更新 UI，用户可能永远看不到补充内容。

**改动文件** `agent_worker.py:process()` — 当 `task.route_type == "hybrid_background"` 且产出有价值内容时

```python
# 在 _publish_content(is_final=True) 后，如果有实质性内容
if task.route_type == "hybrid_background" and final_content and len(final_content) > 50:
    try:
        from ...core.push.fcm_service import send_push_notification
        await send_push_notification(
            user_id=task.user_id,
            title="秘书有补充内容",
            body=final_content[:100] + "...",
            data={"session_id": task.session_id, "type": "hybrid_supplement"},
        )
    except Exception:
        pass  # best-effort
```

### E9. ContextAssembler 缓存 key 加 last_message_id（安全/SRE 提出）

安全/SRE 指出 5 分钟时间桶可能返回陈旧上下文。除 C5 的事件驱动失效外，在缓存 key 中加入 `last_message_id` 进一步保证一致性：

**改动文件** `context_assembler.py:_compute_context_hash()`

```python
@staticmethod
def _compute_context_hash(
    user_id, family_id, session_id, user_message,
    facts_version="", exclusion_version="",
    last_message_id="",  # 新增
):
    payload = json.dumps([
        str(user_id), str(family_id), session_id, user_message,
        facts_version, exclusion_version, last_message_id,
    ], sort_keys=True)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()
```

调用方在 assemble() 前查询 session 最新消息 ID 传入，新消息写入后 hash 自然变化，缓存自动失效。
