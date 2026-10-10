# Secretary Development Guidelines (Gemini Edition)

> 智能家庭助手 · AI-Powered Family Secretary

## 技术栈

| 层 | 技术 |
|---|------|
| Backend | Python 3.11 · FastAPI · SQLAlchemy · Celery |
| Mobile | Flutter 3.x · Dart · BLoC · GetIt (DI) |
| Database | PostgreSQL · Redis · SQLite (本地) |
| **LLM** | **Claude Agent SDK** · Anthropic API (Note: Now also using Gemini CLI for development) |
| Auth | JWT · OAuth2 |

## 快速启动

```bash
cd backend && uvicorn src.main:app --reload   # 后端
cd mobile && flutter run                       # 移动端
cd backend && alembic upgrade head             # 数据库迁移
```

**环境变量**: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `ANTHROPIC_API_KEY`

## 目录结构

```
backend/src/
├── adapters/claude_agent/   # Claude Agent SDK 适配器 (LLM 唯一入口)
├── modules/<name>/services/ # 业务服务
├── modules/<name>/api/      # API 路由
├── core/                    # 认证、配置、接口
└── db/migrations/           # 数据库迁移

mobile/lib/
├── features/<name>/presentation/bloc/   # BLoC 逻辑
├── features/<name>/presentation/pages/  # 页面 UI
├── core/                                 # 网络、工具类
└── shared/                               # 共享组件
```

---

## LLM 架构规范 (双脑路由 & 状态再水化)

### 核心原则

**系统采用“双脑路由”架构，严格区分快反射与深思考链路，禁止构建长驻内存的有状态 Agent。**

| 规范 | 说明 |
|------|------|
| **双脑路由** | **Fast Path (80%)**: Claude 3.5 Haiku 处理简单查询。<br>**Slow Path (20%)**: Claude 3.5 Sonnet 处理复杂推理。 |
| **状态再水化** | Agent 必须是**瞬时 (Ephemeral)** 的。每次任务开始时从 DB 重建上下文，任务结束即销毁。 |
| **指令分离** | Agent **禁止**直接执行敏感操作（如支付）。必须生成 `PendingAction`，经用户确认后由 `Tool Gateway` 执行。 |
| **异步通信** | 慢思考链路通过 Redis Streams/PubSub 异步处理，并通过 WebSocket 推送结果。 |

### 架构层次

```
用户请求 (User Input)
    ↓
意图路由 (Router - Haiku): 决定 Fast/Slow/Hybrid 路径
    ↙                    ↘
快反射 (Fast Worker)      深思考 (Agent Worker - Sonnet)
    ↓                        ↓ 1. Rehydrate (Memory DB)
直接调用 API / 查库           ↓ 2. Reason & Tool Call
    ↘                    ↙ 3. Generate PendingAction
      结果推送 (Redis Pub/Sub -> WebSocket)
```

### 关键组件

*   **IntentRouter**: 基于 Haiku 的意图分类器。
*   **AgentWorker**: 基于 Celery/Redis Streams 的异步 Worker，负责“深思考”。
*   **MemoryService**: 负责构建上下文 (Context Building) 和保存历史 (History Saving)。
*   **ToolGateway**: 负责执行实际的外部工具调用，并进行鉴权和审计。

### 禁止事项

| 禁止 | 原因 |
|------|------|
| **长驻内存 Agent** | 违反“状态再水化”原则，难以扩展。 |
| **直接执行敏感操作** | 必须经过 `PendingAction` + 用户确认 (Human-in-the-loop)。 |
| **同步等待深思考** | 复杂推理必须走异步队列，防止阻塞 API 网关。 |
| **Agent 持有 API Key** | Agent 仅持有内部 Token，通过网关调用外部服务。 |

---

## 时区处理规范

### 核心原则

| 层级 | 规范 |
|------|------|
| **数据库** | UTC，使用 `TIMESTAMP WITH TIME ZONE` |
| **API 传输** | ISO 8601 UTC，格式: `2026-01-28T00:00:00Z` |
| **应用层** | 用户时区，展示前转换 |

### 处理流程

```
用户输入 "明天下午3点"
    ↓ LLM 基于用户时区解析
本地时间 2026-01-29T15:00:00+08:00
    ↓ to_utc()
UTC 时间 2026-01-29T07:00:00Z  →  存入数据库
    ↓ to_local()
本地时间 2026-01-29T15:00:00+08:00  →  展示给用户
```

### 关键函数

```python
# backend - 存储前转 UTC
def to_utc(local_dt: datetime, user_tz: timezone) -> datetime

# backend - 展示前转本地
def to_local(utc_dt: datetime, user_tz: timezone) -> datetime

# mobile - 解析 API 时间
DateTime parseApiTime(String iso) => DateTime.parse(iso).toLocal()

# mobile - 发送给 API
String toApiTime(DateTime local) => local.toUtc().toIso8601String()
```

### 数据库字段

```sql
-- 正确
created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
start_time TIMESTAMP WITH TIME ZONE NOT NULL

-- 错误 (禁止)
start_time TIMESTAMP NOT NULL
```

---

## 安全规范

| 类别 | 要求 |
|------|------|
| API 密钥 | `.env` + `.gitignore`，禁止提交 |
| SQL 注入 | ORM 参数化查询 (SQLAlchemy) |
| 认证 | 所有 API 需要 JWT |
| **硬编码** | **禁止任何硬编码**，使用环境变量或配置文件 |

---

## 数据模型

```
User ──1:N── Member ──1:N── Event ──1:1── Reminder
  │              │
  │ 1:N          │ 1:N
  ↓              ↓
Memory         Gift
  │
  │ 1:N
  ↓
Insight        Notebook ──1:N── Note
```

---

## 验证要求

开发完成后必须运行应用验证，不要仅依赖编译成功。

```bash
cd backend && pytest          # 后端测试
cd mobile && flutter test     # 移动端测试
```
