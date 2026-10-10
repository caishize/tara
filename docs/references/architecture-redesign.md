# 生活秘书 — 架构设计文档

> **版本** 4.0 | **日期** 2026-02-12

---

## 目录

1. [设计目标与原则](#一设计目标与原则)
2. [系统架构总览](#二系统架构总览)
3. [产品模块映射](#三产品模块映射)
4. [后端架构设计](#四后端架构设计)
5. [移动端架构设计](#五移动端架构设计)
6. [数据模型设计](#六数据模型设计)
7. [核心基础设施](#七核心基础设施)
8. [跨模块通信](#八跨模块通信)
9. [扩展架构](#九扩展架构)
10. [错误处理策略](#十错误处理策略)
11. [测试架构](#十一测试架构)
12. [数据隐私与合规](#十二数据隐私与合规)

配套文档：
- [API 参考文档](./api-redesign.md)
- [PRD 产品需求](./PRD-生活秘书-统一版.md)

---

## 一、设计目标与原则

### 1.1 设计原则

| # | 原则 | 说明 |
|---|------|------|
| 1 | **模块 = 产品能力** | 每个模块对应一个用户可感知的产品能力 |
| 2 | **单一写入者** | 每张表只有一个模块能写入 |
| 3 | **事件驱动解耦** | 模块间通过领域事件通信，不直接引用 |
| 4 | **不建不用的** | 仅为当前版本功能建模块 |
| 5 | **AI 引擎一等公民** | AI 是系统核心，非边缘适配器 |
| 6 | **文件 ≤ 800 行，模块 ≤ 10K 行** | 通过子模块目录隔离复杂度 |
| 7 | **瞬时 Agent** | Agent 无状态，每次从 DB 重建上下文，任务结束即销毁 |
| 8 | **前后端对齐** | 前后端模块名称和边界一致 |

### 1.2 量化目标

| 维度 | 目标 |
|------|------|
| 后端模块数 | **12**（1 AI 引擎 + 11 领域） |
| 前端模块数 | **10** |
| 数据库表 | **~64 核心** |
| 最大模块行数 | **≤ 10K** |
| 最大文件行数 | **≤ 800** |
| API 端点 | **~130** |

---

## 二、系统架构总览

### 2.1 架构图

```
┌──────────────────────────────────────────────────────────────┐
│                    移动端 (Flutter 3.x)                        │
│  chat · views · trip · gifts · members · ...  (10 模块)      │
├────────────────────────┬─────────────────────────────────────┤
│       HTTP/SSE         │           WebSocket                   │
├────────────────────────┴─────────────────────────────────────┤
│                     API 网关 (FastAPI)                          │
│               JWT · RateLimit · CORS · RLS                     │
├──────────────────────────────────────────────────────────────┤
│   ┌─────────────────────────────────────────────────────┐    │
│   │              AI 引擎 (ai_engine/)                     │    │
│   │  意图路由 → Fast Worker (Haiku) ──→ SSE              │    │
│   │          → Hybrid Worker ──→ SSE + 后台增强          │    │
│   │          → Agent Worker (Sonnet) ──→ Skills + 异步   │    │
│   │  SDK Client Pool · PooledToolContext · Tool Gateway   │    │
│   └─────────────────────┬───────────────────────────────┘    │
│                          │ 工具调用                             │
│   ┌──────────────────────v──────────────────────────────┐    │
│   │                领域服务层 (11 个模块)                    │    │
│   │  conversation · memory · insight · curation · views    │    │
│   │  briefing · trip · gift · member · date_manager        │    │
│   │  relationship                                          │    │
│   └─────────────────────┬───────────────────────────────┘    │
│   ┌──────────────────────v──────────────────────────────┐    │
│   │             核心基础设施 (core/)                       │    │
│   │  Auth · EventBus · Scheduler · LLM · PubSub          │    │
│   │  WebSocket · Cache · RateLimit · Observability        │    │
│   └─────────────────────┬───────────────────────────────┘    │
├──────────────────────────v───────────────────────────────────┤
│         PostgreSQL (~64 表, RLS)    Redis (缓存/队列/调度/事件流) │
├──────────────────────────────────────────────────────────────┤
│  外部集成: 天气 (QWeather/Open-Meteo) · Anthropic API · OAuth  │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 请求处理流程

```
用户发消息 "帮我规划下周北京出差"
    │
    ▼
[API Gateway] POST /api/v1/chat/stream
    │
    ▼
[AI Engine: Intent Router]
    │ 检查 Redis 热会话标记
    │ → 有热会话? 跳过分类，直走 Slow Path
    │ → 无热会话? Haiku 两轴分类
    │
    ├── FAST (70%): Haiku 直答 → SSE 流式返回
    │
    ├── HYBRID (10%): Haiku 快答 → SSE + 后台 Sonnet 增强
    │     冷却: 同一 session 30s 内不重复触发
    │
    └── SLOW (20%): Celery Worker → Sonnet + MCP Tools
         │
         ├── memory.recall(...)       → 找到相关记忆
         ├── curation.create_event    → 创建策展事件
         ├── trip.create_plan         → 创建行程计划
         └── [Redis PubSub → WebSocket → Mobile]
```

---

## 三、产品模块映射

| PRD 功能 | 对应模块 | 优先级 |
|----------|---------|--------|
| 智能对话 | `ai_engine` + `conversation` | Core |
| 家庭看板 + 事件图谱 | `views` | Core |
| 智能简报 | `briefing` | Core |
| 家庭记忆 | `memory` + `insight` | Core |
| 旅行规划 | `trip` | Core |
| 礼物管理 | `gift` | Core |
| 重要日期 | `date_manager` | Core |
| 家庭档案 | `member` | Core |
| 人情管理 | `relationship` | Extension |
| 事件整理 | `curation` | Core (内部引擎) |

**决策**：只为当前版本功能建模块。成长记录、健康管理、家务管理、财务概览等远期功能不预建桩。

---

## 四、后端架构设计

### 4.1 模块总览

```
backend/src/
├── ai_engine/               # AI 引擎（系统大脑）
│   ├── router/              # 意图路由
│   ├── workers/             # Fast/Hybrid/Slow Worker
│   ├── sdk/                 # SDK Client Pool + PooledToolContext
│   ├── tools/               # MCP 工具定义
│   ├── skills/              # Skill 系统（提示级能力增强）
│   ├── queue/               # Redis Streams 任务队列
│   ├── gateway/             # 工具网关
│   └── sub_agents/          # 专项 Agent (deep_researcher, gift_advisor, travel_planner)
│
├── modules/
│   ├── conversation/        # 对话管理（会话生命周期）
│   ├── memory/              # 家庭记忆（提取/召回/合并）
│   ├── insight/             # 洞察引擎（统一洞察生成与分发）
│   ├── curation/            # 策展引擎（事件整理）
│   ├── views/               # 视图层（看板 + 图谱）
│   ├── briefing/            # 智能简报
│   ├── trip/                # 行程规划
│   ├── gift/                # 礼物管理
│   ├── member/              # 家庭成员与人物
│   ├── date_manager/        # 重要日期
│   └── relationship/        # 人情管理
│
├── core/                    # 基础设施（详见第七章）
├── api/v1/                  # API 路由层（薄层，只做路由+参数校验）
└── db/                      # 数据库 session + 迁移
```

### 4.2 AI 引擎 — `ai_engine/`

**定位**：系统大脑。封装所有 LLM 交互、意图路由、工具调用。

| 子模块 | 估算行数 | 职责 |
|--------|---------|------|
| `router/` | ~400 | Redis 热检测 + Haiku 两轴分类 |
| `workers/` | ~2,000 | 三路工作者 (Fast/Hybrid/Agent) |
| `sdk/` | ~2,500 | SDK 连接池 + PooledToolContext |
| `tools/` | ~1,500 | MCP 工具定义 (~42 个，按领域分组) |
| `skills/` | ~800 | Skill 注册 + 定义 |
| `queue/` | ~400 | Redis Streams 任务队列 |
| `gateway/` | ~500 | 权限验证 + 路由 |
| `sub_agents/` | ~800 | 专项 Agent 定义 (deep_researcher, gift_advisor, travel_planner) |
| 根文件 | ~600 | agent_context, worker_runner, interface, message_types |
| **合计** | **~9,500** | |

**工具分类**：

| 类别 | 工具 |
|------|------|
| 记忆 | `search_memory`, `save_memory`, `update_memory` |
| 事件 | `create_event`, `update_event`, `cancel_schedule`, `delete_event`, `search_events` |
| 行程 | `create_trip`, `query_trips`, `update_trip`, `cancel_trip`, `add_trip_itinerary`, `query_trip_bookings`, `query_external_calendar` |
| 礼物 | `recommend_gift`, `create_gift_task` |
| 人物 | `add_family_member`, `update_member_info`, `query_family_members`, `get_member_details`, `delete_family_member` |
| 日期 | `add_important_date`, `query_upcoming_dates`, `update_important_date`, `delete_important_date`, `convert_lunar_date` |
| 人情 | `record_favor`, `check_favor_balance`, `suggest_favor_return` |
| 任务 | `create_task`, `query_tasks`, `complete_task`, `update_task`, `delete_task`, `set_reminder` |
| 搜索 | `web_search` |
| 上下文 | `view_tool_details`, `recall_tool_result`（按 execution_id 查看 Layer 3 完整结果） |
| MCP | `call_mcp_tool`, `list_mcp_tools`（需已连接 MCP 服务器） |

> **注**：`get_weather` 由 FastWorker 内部调用，非注册工具。`ask_user_question` 和 `create_pending_action` 是 SDK 层钩子，非 MCP 工具。

**工具注入策略**：基于意图分类结果，只注入相关的工具子集（capability bundles），而非全量 42 个工具。

**工具执行器**：每个领域模块定义自己的工具执行器（如 `memory/executor.py`），ai_engine 通过模块接口调用，不直接持有业务逻辑。

#### 4.2.1 Skills 系统

Skill 是**提示级别**的能力增强，不创建新会话，零额外 API 开销。通过意图信号自动激活：

```python
@dataclass(frozen=True)
class Skill:
    name: str                          # "trip_planning"
    description: str
    system_prompt_addon: str          # 注入主 Agent system prompt
    required_tools: List[str]         # 需要的 MCP 工具子集
    output_format_hint: Optional[str]
    max_turns_override: Optional[int]
```

| Skill | 触发条件 | 注入行为 |
|-------|---------|---------|
| `trip_search` | action=lookup + keywords: 旅行/攻略 | 引导搜索策略：中文优先、多源对比 |
| `trip_planning` | action=plan + keywords: 行程/旅游 | 引导行程优化：多日排布、家庭适配 |

**激活机制**：`SkillRegistry` 在意图路由后、Agent 启动前检测。新增 Skill 只需添加定义文件 + 注册。

---

### 4.3 对话模块 — `modules/conversation/`

**定位**：管理会话生命周期——会话创建/关闭、消息存储、上下文管理、反馈。

| 服务 | 职责 |
|------|------|
| `session_service.py` | 会话创建/查询/关闭（4h 自动新建） |
| `message_service.py` | 消息存储/查询/标记 superseded |
| `context_service.py` | 上下文再水化 + 压缩 |
| `tool_execution_store.py` | 工具执行三层上下文管理 |
| `feedback_service.py` | 消息反馈 (👍/👎 + 原因) |
| `card_normalizer.py` | 卡片类型识别 + 标准化 |
| `pending_action_service.py` | PendingAction 确认生命周期 |
| `today_service.py` | 今日概览数据聚合 |
| `holiday_service.py` | 节日问候与上下文 |
| `scheduler_support.py` | 调度器集成支持 |
| `tool_summary_generator.py` | 工具执行摘要生成 |
| `jobs.py` / `tasks.py` | Celery 异步任务定义 |

#### 工具执行三层上下文

Agent 一次对话可能调用多个工具，每个工具返回大量数据。三层递进式上下文以 `execution_id` (UUID) 为索引：

| 层级 | 范围 | 内容 |
|------|------|------|
| Layer 1: Summary | 所有历史迭代 | 单行摘要 ~50 字：`"[#a1b2c3d4] search_web ✅ 找到3条结果"` |
| Layer 2: Key Results | 当前迭代 | 按工具类型裁剪的结构化子集（行程 7 项、成员 10 条等） |
| Layer 3: Full Result | 按需查看 | 完整结果存储在 `tool_execution_logs`，通过 `view_tool_details` 工具查看 |

**数据表** (3 张)：

| 表名 | 说明 |
|------|------|
| `assistant_chat_sessions` | 对话会话 (含压缩摘要字段 summary_content, compressed_up_to) |
| `assistant_chat_messages` | 消息 |
| `tool_execution_logs` | 工具执行日志（三层上下文） |

**API 端点**：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/chat/stream` | SSE 流式聊天 |
| POST | `/chat/regenerate` | 重新生成 |
| POST | `/chat/cancel` | 取消生成 |
| GET | `/chat/history` | 对话历史 |
| GET | `/chat/tool-execution/{id}` | 工具执行明细 (Layer 3) |
| DELETE | `/chat/session/{id}` | 清除会话 |
| POST | `/chat/feedback` | 消息反馈 |
| GET | `/chat/poll/{job_id}` | 轮询 Slow Path 结果 |

---

### 4.4 记忆模块 — `modules/memory/`

**定位**：从对话中自动提取信息，构建家庭知识库，支撑跨时空关联。

| 服务 | 职责 |
|------|------|
| `extraction/` | 统一提取器（从对话自动提取结构化记忆） |
| `recall_service.py` | 语义检索 + 关键词匹配召回 |
| `consolidation_service.py` | 定期合并/整理重复/矛盾记忆 |
| `bridge.py` | 为 AI 引擎提供记忆读写接口 |
| `embedding_service.py` | 向量嵌入生成 |

**数据表** (4 张)：

| 表名 | 说明 |
|------|------|
| `conversation_memories` | 家庭记忆 (type, content, entities JSONB, embedding, status) |
| `memory_associations` | 记忆间关联 |
| `memory_summaries` | 记忆摘要（定期合并归纳） |
| `secretary_notes` | 管家笔记（高层级结构化笔记） |

**API 端点**：`GET /memory/list`, `GET /memory/recall`, `GET /memory/search`, `PATCH /memory/{id}/status`, `DELETE /memory/{id}`, `POST /memory/consolidate`

---

### 4.5 洞察模块 — `modules/insight/`

**定位**：统一洞察引擎——聚合 memory、briefing、curation 等模块生成的洞察，提供统一查询、反馈、生命周期管理。

| 服务 | 职责 |
|------|------|
| `insight_service.py` | 洞察 CRUD + 生命周期管理 |
| `proactive_service.py` | 定时洞察生成（scheduler 触发） |
| `feedback_service.py` | 洞察反馈处理 + 质量优化 |

**数据表** (3 张)：

| 表名 | 说明 |
|------|------|
| `memory_insights` | 记忆洞察（从对话记忆自动生成的结构化洞察） |
| `insight_feedbacks` | 洞察反馈（用户对洞察的 👍/👎 + 原因） |
| `user_insight_settings` | 用户洞察偏好（频率、类型过滤、渠道设置） |

洞察来源通过 `insight_type` 字段区分 (memory/proactive/briefing/curation)。优先级（1-10）、生命周期（pending/shown/acted/dismissed）和关联实体（`related_entities` JSONB）存储在 `memory_insights` 表。

**API 端点**：`GET /insights`, `POST /insights/{id}/action`, `POST /insights/{id}/feedback`

---

### 4.6 策展模块 — `modules/curation/`

**定位**：秘书的"整理能力"——收集、去重、关联、排优先级。`curated_events` 表的**唯一写入者**。

| 服务 | 职责 |
|------|------|
| `curation_service.py` | 策展编排 |
| `collector.py` | 多源事件收集 |
| `dedup_service.py` | 事件去重 + 合并 |
| `association_service.py` | 事件间关联发现 |
| `storage_service.py` | curated_events 读写 |
| `rule_engine.py` | 优先级、分类规则 |
| `conflict_resolver.py` | 事件冲突检测与解决 |

**并发控制**：策展流水线使用 per-family Redis 分布式锁，防止同一家庭的并发策展任务冲突。

**数据表** (6 张)：

| 表名 | 说明 |
|------|------|
| `curated_events` | 策展事件 |
| `event_associations` | 事件关联 |
| `preparation_items` | 准备清单（独立表支持并发安全） |
| `curation_jobs` | 策展任务执行记录（幂等性 + 审计） |
| `hygiene_run_logs` | 数据卫生运行日志 |
| `social_intents` | 社交意图记录 |

**领域事件（接收）**：`TripCreated`, `MemoryExtracted`, `DateApproaching`, `EventRequested`

---

### 4.7 视图模块 — `modules/views/`

**定位**：读侧投影层——从策展事件构建看板视图和事件图谱。合并原 kanban + graph 两个模块。

| 服务 | 职责 |
|------|------|
| `kanban_service.py` | 语义分组 (本周重点/需要准备/月内/更远) |
| `memory_lane_service.py` | 回忆长廊 (那年今日 + 故事聚合) |
| `preparation_service.py` | 准备清单 CRUD（通过 curation 接口） |
| `graph_service.py` | 图谱构建 + 节点操作 |
| `search_service.py` | 事件搜索 |
| `task_service.py` | 家庭任务 CRUD |

**数据表** (3 张)：

| 表名 | 说明 |
|------|------|
| `family_tasks` | 家庭任务（轻量级任务，非策展事件） |
| `today_items` | 今日重点项（每日刷新的视图缓存） |
| `ai_suggestions` | AI 智能建议（看板上下文相关） |

**API 端点**：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/kanban` | 语义看板视图 |
| GET | `/kanban/memory-lane` | 回忆长廊 |
| GET | `/kanban/search` | 事件搜索 |
| PATCH | `/kanban/events/{id}/preparation` | 勾选准备项 |
| GET | `/graph/event/{event_id}` | 事件图谱 |
| GET | `/graph/trip/{trip_id}` | 行程图谱 |
| POST | `/graph/associations` | 管理关联 |

---

### 4.8 简报模块 — `modules/briefing/`

**定位**：秘书的"嘴"——把整理好的信息在合适的时机推送给用户。

| 服务 | 职责 |
|------|------|
| `briefing_service.py` | 三时段简报生成（晨/午/晚） |
| `suggestion_service.py` | 上下文智能建议（10 个策略类） |
| `push_service.py` | 异步推送 |
| `weather_service.py` | 天气信息获取（多数据源降级） |
| `insight_orchestrator.py` | 洞察编排（聚合 insight 模块数据到简报） |

建议策略：`preparation`, `location`, `person`, `gift`, `anniversary`, `memory`, `plan`, `relationship`, `favor`, `external_data`

**数据表** (3 张)：

| 表名 | 说明 |
|------|------|
| `user_briefing_settings` | 用户简报偏好 (含洞察偏好设置) |
| `preparation_plans` | 准备计划 |
| `preparation_tasks` | 准备任务项 |

**API 端点**：`GET /briefing/daily`, `GET /briefing/suggestions`, `POST /briefing/suggestions/{id}/action`, `GET/PUT /briefing/settings`

---

### 4.9 行程模块 — `modules/trip/`

**定位**：出行全链路管家。

| 服务 | 职责 |
|------|------|
| `trip_service.py` | 行程 CRUD + 去重 |
| `smart_itinerary_planner.py` | 智能行程生成（6 种风格） |
| `budget_tracker.py` | 预算追踪 |
| `trip_status.py` | 行程状态机 |
| `weather_service.py` | 目的地天气 |

通过发布 `TripCreated` 事件触发策展，不直接写 `curated_events`。

**数据表** (5 张)：`trips`, `trip_itineraries`, `trip_expenses`, `trip_memories`, `itinerary_versions`

**API 端点**：`/trips/*`, `/trips/{id}/itinerary/*`, `/trips/{id}/expenses/*`

---

### 4.10 礼物模块 — `modules/gift/`

**定位**：送礼助手——推荐、追踪、管理全流程。

| 服务 | 职责 |
|------|------|
| `recommendation_service.py` | 基于画像的智能推荐 |
| `task_service.py` | 礼物任务状态机 |
| `trending_service.py` | 热门礼物发现 |
| `price_tracker.py` | 价格监控 |
| `providers/` | 电商价格追踪 (jd, taobao, tmall, pdd) |

**数据表** (12 张)：

| 表名 | 说明 |
|------|------|
| `gift_recommendations` | LLM 推荐 |
| `gift_tasks` | 礼物任务状态机 |
| `gift_preferences` | 每成员偏好 |
| `gift_history` | 送礼历史 |
| `trending_gifts` | 热门礼物 |
| `user_gift_saves` | 用户收藏 |
| `occasions` | 送礼场景 |
| `occasion_gifts` | 场景-礼物关联 |
| `data_sources` | 电商数据源配置 |
| `update_logs` | 数据更新日志 |
| `gift_conversation_context` | 对话上下文 |
| `member_gift_memory` | 成员礼物记忆 |

**API 端点**：`/gifts/recommend`, `/gifts/tasks/*`, `/gifts/trending`, `/gifts/dashboard`, `/gifts/history`, `/gifts/browse/*`, `/gifts/memory/*`

---

### 4.11 成员与人物模块 — `modules/member/`

**定位**：统一人物管理——家庭成员 + 外部联系人。

**两层人物模型**：

```
person_profiles (所有人)
  ├── 家庭成员: member_id ≠ NULL, family_id = 所属家庭
  └── 外部联系人: member_id = NULL, family_id = 创建者家庭
```

- `members` 表：家庭核心成员，有 `family_id`，支持协同和权限控制
- `person_profiles` 表：所有人，通过 nullable `member_id` 关联
- 每个 `member_id` 值最多对应一个 `person_profiles` 行（部分唯一索引）
- 家庭成员 `members.name` 更新时同步 `person_profiles.name`（DB 触发器）

| 服务 | 职责 |
|------|------|
| `member_service.py` | 家庭成员 CRUD |
| `person_service.py` | 人物档案 CRUD |
| `profile_enrichment.py` | 从对话自动丰富人物画像 |
| `context_service.py` | 人物上下文构建 |
| `device_token_service.py` | 设备推送令牌管理 (FCM/APNs) |
| `work_history_service.py` | 工作经历管理 |
| `professional_relation_service.py` | 职业关系管理 |

**数据表** (11 张)：

| 表名 | 说明 |
|------|------|
| `families` | 家庭（多家庭隔离根实体） |
| `users` | 用户账户 |
| `members` | 家庭成员 |
| `person_profiles` | 统一人物档案 (含 favor_balance 冗余缓存) |
| `member_profiles` | 扩展档案（仅家庭成员：尺码、健康等） |
| `relationship_edges` | 人物间关系图 (type: colleague/friend/family/...) |
| `member_relations` | 家庭成员间亲属关系 |
| `work_histories` | 工作经历 |
| `professional_relations` | 职业关系 |
| `device_tokens` | 设备推送令牌 (FCM/APNs) |
| `proactive_insights` | 主动洞察（基于人物画像的关怀提醒） |

`person_profiles.favor_balance` 为冗余计算字段，由 relationship 模块记录人情后更新。

**API 端点**：`/members/*`, `/members/people/*`, `/members/people/neglected`, `/members/people/favors`, `/devices/*`

---

### 4.12 日期模块 — `modules/date_manager/`

**定位**：永远不忘记任何重要日子。

| 服务 | 职责 |
|------|------|
| `date_service.py` | 日期 CRUD + 节日模板 |
| `reminder_service.py` | 统一提醒管理 |
| `lunar_provider.py` | 农历日期转换 |
| `calendar_adapter.py` | 中国节假日适配 |

**数据表** (7 张)：

| 表名 | 说明 |
|------|------|
| `important_dates` | 重要日期 (type, date, recurrence, member_id) |
| `date_reminders` | 日期提醒（绑定 important_dates，支持 offset_days） |
| `event_reminders` | 事件提醒（绑定策展事件/行程等，支持 trigger_time） |
| `smart_reminders` | 智能提醒（AI 学习用户行为模式后自动生成） |
| `chinese_holiday_plans` | 节假日计划 |
| `date_occurrences` | 日期发生记录（农历转换后的确切日期实例） |
| `user_activity_patterns` | 用户活动模式（智能提醒学习数据） |

三种提醒表的设计理由：不同提醒来源有不同的生命周期和字段需求。`date_reminders` 与 `important_dates` 紧耦合（offset_days）；`event_reminders` 需要 trigger_time + channel；`smart_reminders` 由 AI 自动生成，有独立的置信度和学习反馈字段。

共享字段：`status` (pending/sent/acknowledged/snoozed/cancelled/expired/failed)、`channel` (push/sms/email)、`retry_count`/`max_retries`。

**API 端点**：`/dates/*`, `/dates/upcoming`, `/dates/holidays`, `/dates/convert/*`

---

### 4.13 人情模块 — `modules/relationship/`

**定位**：维护人情世故——记录人情往来、可视化关系健康度、智能关怀建议。

| 服务 | 职责 |
|------|------|
| `favor_service.py` | 人情记录 + 收支平衡 |
| `care_service.py` | 关怀建议 + 关系健康度计算 |

人物档案和关系图由 `member` 模块拥有，本模块通过接口读取。

**数据表** (2 张)：`favor_records`, `social_events`

**API 端点**：`/relationships/health`, `/relationships/favors/*`, `/relationships/suggestions`

---

### 4.14 模块行数汇总

| 模块 | 预估行数 | 表数 | API 端点数 |
|------|---------|------|-----------|
| `ai_engine` | ~9,500 | 1 (pending_actions) | — |
| `conversation` | ~5,500 | 4 | 8 |
| `memory` | ~4,000 | 4 | 6 |
| `insight` | ~2,000 | 3 | 3 |
| `curation` | ~7,500 | 6 | 3 |
| `views` | ~4,500 | 3 | 7 |
| `briefing` | ~3,500 | 4 | 6 |
| `trip` | ~5,500 | 5 | ~12 |
| `gift` | ~6,000 | 12 | ~10 |
| `member` | ~4,000 | 11 | ~13 |
| `date_manager` | ~3,500 | 7 | ~7 |
| `relationship` | ~3,000 | 2 | ~5 |
| `core` | ~6,000 | 2 (event_outbox, job_executions) | — |
| `api` (路由层) | ~5,800 | — | ~130 |
| **合计** | **~70,000** | **~64** | **~130** |

---

## 五、移动端架构设计

### 5.1 导航架构

3 个底部 Tab：对话（主入口）、看板（第二入口）、我的（收纳其他功能）。

### 5.2 目录结构

```
mobile/lib/
├── features/                  # Clean Architecture 分层
│   ├── chat/                  # 对话（主入口）
│   │   ├── data/              #   datasources/ + models/ + repositories/
│   │   ├── domain/            #   entities/ + repositories/ + usecases/
│   │   └── presentation/      #   bloc/ + pages/ + widgets/
│   ├── kanban/                # 看板 + 回忆 + 图谱
│   ├── trip/                  # 行程规划
│   ├── gifts/                 # 礼物管理
│   ├── members/               # 家庭成员
│   ├── dates/                 # 重要日期
│   ├── relationships/         # 人情管理
│   ├── profile/               # 个人中心 (Tab 3)
│   ├── settings/              # 设置
│   └── auth/                  # 登录注册
├── shared/widgets/            # 公共组件 (cards, action bars)
├── core/
│   ├── network/               # Dio + SSE + WebSocket
│   ├── auth/                  # Token 管理 (flutter_secure_storage)
│   ├── events/                # AppEventBus (跨 BLoC 通信)
│   ├── config/                # 环境配置
│   ├── error/                 # 错误处理
│   └── storage/               # Hive 本地缓存
├── app/
│   ├── di/                    # GetIt DI 注册
│   ├── router/                # go_router 路由
│   └── theme/                 # 主题系统 (亮/暗)
└── main.dart
```

### 5.3 状态管理

- **全局 BLoC** (Auth, User, Connectivity): GetIt 单例注入
- **功能 BLoC**: BlocProvider 随页面创建/销毁
- **跨 BLoC 通信**: AppEventBus（StreamController.broadcast + typed events）

```dart
// core/events/app_event_bus.dart
class AppEventBus {
  static final instance = AppEventBus._();
  final _controller = StreamController<AppEvent>.broadcast();
  Stream<T> on<T extends AppEvent>() => _controller.stream.whereType<T>();
  void fire(AppEvent event) => _controller.add(event);
}

sealed class AppEvent {}
class PreparationToggled extends AppEvent { ... }
class TripStatusUpdated extends AppEvent { ... }
class SessionCleared extends AppEvent { ... }
```

AppEventBus 仅用于 UI 层状态同步，不替代后端领域事件。

### 5.4 安全存储

| 数据 | 存储方式 | 说明 |
|------|---------|------|
| JWT Tokens | `flutter_secure_storage` | iOS Keychain / Android Keystore |
| 用户偏好 | SharedPreferences | 非敏感设置 |
| 聊天缓存 | Hive | 最近 100 条（轻量 NoSQL，无需 FFI） |
| 看板缓存 | Hive | TTL 30min |

### 5.5 离线与弱网

在线优先 (Online-First)。弱网时写操作入 Hive 队列，按指数退避重试；读操作返回本地缓存。离线时只读模式，恢复后自动同步。

### 5.6 卡片系统

聊天中的业务卡片统一路由：`switch(message.cardType)` → BriefingCard / TripCard / GiftCard / GraphPreviewCard / ReminderCard / AskUserQuestionCard / PendingActionCard / MarkdownBubble。所有卡片 Widget 放在 `shared/widgets/cards/` 下。

### 5.7 深度链接

go_router 处理推送通知跳转、分享链接：`/chat`, `/kanban`, `/trips/:id`, `/event/:id`, `/gift/:id`。

---

## 六、数据模型设计

### 6.1 表清单 (~64 核心表)

| # | 模块 | 表名 | 说明 |
|---|------|------|------|
| 1 | conversation | `assistant_chat_sessions` | 对话会话 (含 summary_content, compressed_up_to) |
| 2 | conversation | `assistant_chat_messages` | 消息 |
| 3 | conversation | `tool_execution_logs` | 工具执行日志（三层上下文） |
| 4 | conversation | `session_summaries` | 会话摘要（压缩归档） |
| 5 | memory | `conversation_memories` | 家庭记忆 (type, content, entities, embedding, status) |
| 6 | memory | `memory_associations` | 记忆间关联 |
| 7 | memory | `memory_summaries` | 记忆摘要（定期合并归纳） |
| 8 | memory | `secretary_notes` | 管家笔记 |
| 9 | insight | `memory_insights` | 记忆洞察 (insight_type, priority 1-10, related_entities JSONB) |
| 10 | insight | `insight_feedbacks` | 洞察反馈（用户对洞察的 👍/👎 + 原因） |
| 11 | insight | `user_insight_settings` | 用户洞察偏好（频率、类型过滤、渠道设置） |
| 12 | curation | `curated_events` | 策展事件 |
| 13 | curation | `event_associations` | 事件关联 |
| 14 | curation | `preparation_items` | 准备清单 |
| 15 | curation | `curation_jobs` | 策展任务执行记录（幂等性 + 审计） |
| 16 | curation | `hygiene_run_logs` | 数据卫生运行日志 |
| 17 | curation | `social_intents` | 社交意图记录 |
| 18 | views | `family_tasks` | 家庭任务 |
| 19 | views | `today_items` | 今日重点项 |
| 20 | views | `ai_suggestions` | AI 智能建议 |
| 21 | briefing | `user_briefing_settings` | 简报偏好 (含洞察偏好) |
| 22 | briefing | `preparation_plans` | 准备计划 |
| 23 | briefing | `preparation_tasks` | 准备任务项 |
| 24 | briefing | `user_insights` | 用户洞察缓存（简报聚合） |
| 25 | trip | `trips` | 行程计划 |
| 26 | trip | `trip_itineraries` | 每日行程 |
| 27 | trip | `trip_expenses` | 行程费用 |
| 28 | trip | `trip_memories` | 行程回忆（日记/照片/打卡） |
| 29 | trip | `itinerary_versions` | 行程版本历史 |
| 30 | gift | `gift_recommendations` | 礼物推荐 |
| 31 | gift | `gift_tasks` | 礼物任务 |
| 32 | gift | `gift_preferences` | 成员偏好 |
| 33 | gift | `gift_history` | 送礼历史 |
| 34 | gift | `trending_gifts` | 热门礼物 |
| 35 | gift | `user_gift_saves` | 用户收藏 |
| 36 | gift | `occasions` | 送礼场景 |
| 37 | gift | `occasion_gifts` | 场景-礼物关联 |
| 38 | gift | `data_sources` | 电商数据源配置 |
| 39 | gift | `update_logs` | 数据更新日志 |
| 40 | gift | `gift_conversation_context` | 对话上下文 |
| 41 | gift | `member_gift_memory` | 成员礼物记忆 |
| 42 | member | `families` | 家庭 |
| 43 | member | `users` | 用户账户 |
| 44 | member | `members` | 家庭成员 |
| 45 | member | `person_profiles` | 统一人物档案 |
| 46 | member | `member_profiles` | 扩展档案（仅家庭成员） |
| 47 | member | `relationship_edges` | 人物间关系图 |
| 48 | member | `member_relations` | 家庭成员间亲属关系 |
| 49 | member | `work_histories` | 工作经历 |
| 50 | member | `professional_relations` | 职业关系 |
| 51 | member | `device_tokens` | 设备推送令牌 (FCM/APNs) |
| 52 | member | `proactive_insights` | 主动洞察（基于人物画像的关怀提醒） |
| 53 | date_manager | `important_dates` | 重要日期 |
| 54 | date_manager | `date_reminders` | 日期提醒（绑定 important_dates，支持 offset_days） |
| 55 | date_manager | `event_reminders` | 事件提醒（绑定策展事件/行程等，支持 trigger_time） |
| 56 | date_manager | `smart_reminders` | 智能提醒（AI 学习用户行为模式后自动生成） |
| 57 | date_manager | `chinese_holiday_plans` | 节假日计划 |
| 58 | date_manager | `date_occurrences` | 日期发生记录 |
| 59 | date_manager | `user_activity_patterns` | 用户活动模式（智能提醒学习数据） |
| 60 | relationship | `favor_records` | 人情记录 |
| 61 | relationship | `social_events` | 社交事件 |
| 62 | ai_engine | `pending_actions` | 待确认操作 (sensitivity: low/medium/high/critical) |
| 63 | core | `event_outbox` | Transactional Outbox（可靠事件投递） |
| 64 | core | `job_executions` | 调度任务执行记录 |

**V2 预留表**：`audit_logs`（审计日志）、`token_blocklist`（JWT 撤销记录持久化）。

### 6.2 实体关系

```
Family ──1:N── Member ──┬──1:1── MemberProfile
  │                      │ 0..1
  │ 1:N                  ▼
  │              PersonProfile ──N:M── RelationshipEdge
  │              │
  │              └──1:N── FavorRecord
  │
User ──N:1── Family (通过 Member)
  │
  ▼
ChatSession ──1:N── ChatMessage
  │
  └──1:N── ToolExecutionLog

CuratedEvent ──1:N── EventAssociation
  ├──1:N── PreparationItem
  │
  └── (trip_id FK)
Trip ──1:N── TripItinerary
  └──1:N── TripExpense

Memory ──1:N── Insight (via source_memory_id)
  └──N:M── MemoryAssociation

ImportantDate ──1:N── DateReminder
CuratedEvent  ──1:N── EventReminder
(AI-generated) ──── SmartReminder
```

### 6.3 数据完整性规则

| 规则 | 说明 |
|------|------|
| **family_id FK** | 所有 family_scoped 表的 `family_id` 必须有 `ForeignKey("families.id", ondelete="CASCADE")` |
| **RLS** | 所有 family_scoped 表启用 Row-Level Security，`USING (family_id = current_setting('app.current_family_id')::uuid)` |
| **person_profiles.member_id 部分唯一** | `CREATE UNIQUE INDEX ... ON person_profiles (member_id) WHERE member_id IS NOT NULL` |
| **favor_records.contact_id FK** | `ForeignKey("person_profiles.id", ondelete="SET NULL")`，删除人物后保留人情记录 |
| **member → person_profiles 名称同步** | DB 触发器：`members.name` 更新时同步 `person_profiles.name` |
| **提醒表 FK** | `date_reminders` 直接 FK → `important_dates`；`event_reminders` 直接 FK → `curated_events`/`trips`；`smart_reminders` 无 FK（AI 自动生成） |

### 6.4 索引策略

**原则**：

| 原则 | 说明 |
|------|------|
| 复合索引优先 | `family_id + 其他列`，而非单列索引 |
| BRIN 用于时间列 | 高写入追加表的 `created_at` |
| 部分索引用于热查询 | `WHERE status = 'active'` 等条件索引 |
| GIN 用于 JSONB/ARRAY | `@>` 包含查询 |
| HNSW/IVFFlat 用于向量 | `conversation_memories.embedding` 列 |

**高流量表关键索引**：

| 表 | 索引 |
|-----|------|
| `assistant_chat_messages` | `(session_id, sequence_number DESC) WHERE is_superseded = FALSE` |
| `conversation_memories` | `(family_id, importance DESC, created_at DESC) WHERE status = 'active'` |
| `conversation_memories` | `(family_id) WHERE embedding IS NOT NULL AND status = 'active'` (向量检索预过滤) |
| `conversation_memories` | HNSW on `embedding` (pgvector, 当数据量 > 10K 时启用) |
| `curated_events` | `(family_id, normalized_start) WHERE is_active = TRUE` |
| `curated_events` | `(trip_id, normalized_start) WHERE trip_id IS NOT NULL` (trip_id FK → trips) |
| `insights` | `(user_id, status, priority) WHERE status NOT IN ('dismissed', 'acted')` |
| `pending_actions` | `(user_id, status) WHERE status = 'pending' AND expires_at > now()` |
| `tool_execution_logs` | BRIN on `created_at` |

**索引命名规范**：`ix_{table}_{col1}_{col2}` (B-tree), `ix_{table}_{col}_brin` (BRIN), `ix_{table}_{col}_gin` (GIN), `uq_{table}_{col}` (唯一)。

### 6.5 分区策略

| 表 | 策略 | 分区键 | 间隔 | 触发点 |
|----|------|--------|------|--------|
| `conversation_memories` | RANGE | `created_at` | 月度 | 50 万行 |
| `curated_events` | RANGE | `normalized_start` | 季度 | 20 万行 |
| `assistant_chat_messages` | RANGE | `created_at` | 月度 | 100 万行 |
| `tool_execution_logs` | RANGE | `created_at` | 月度 | 100 万行 |

分区表的 PK 必须包含分区键（如 `PRIMARY KEY (id, created_at)`）。跨分区 FK 使用应用层引用完整性。通过 pg_partman 自动管理分区（`p_premake := 3` 预创建 3 个未来分区）。

---

## 七、核心基础设施

### 7.0 core/ 目录结构

```
core/
├── auth/              # JWT + RBAC + RLS + 加密
├── llm/               # LLM Provider + Factory（所有模块通过 ILLMProvider 注入）
├── events/            # Redis Streams + Transactional Outbox
├── scheduler/         # Redis Sorted Set + Celery Beat 调度
├── cache.py           # Redis cache utilities
├── interfaces/        # 跨模块 ABCs (ILLMProvider, INotificationProvider, ...)
├── pubsub/            # Redis PubSub (WebSocket relay)
├── push/              # FCM 推送
├── rate_limit/        # 分布式限流 (Redis + Lua 令牌桶)
├── observability/     # Metrics + Tracing + Health checks
├── utils/             # timezone, geocoding, city_pinyin
└── websocket/         # WebSocket 管理
```

### 7.1 认证与安全

**JWT 生命周期**：Access Token 15 分钟 + Refresh Token 30 天 + Redis-based token blocklist（jti + iat 声明）。

**权限模型**：

| 条件 | 角色 | 权限 |
|------|------|------|
| `user.id == family.owner_user_id` | ADMIN | 全部操作 |
| `user.family_id == family_id` | MEMBER | 除 VIEW_CONFIDENTIAL 外全部 |
| 其他 | GUEST | 仅 VIEW_MEMBER |

**CORS**：开发环境 `allow_origins=["*"]`；生产环境必须配置 `CORS_ORIGINS` 环境变量。

**RLS (Row-Level Security)**：所有 family_scoped 表启用 RLS。SQLAlchemy session event 自动 `SET LOCAL app.current_family_id`。管理/迁移操作使用 `BYPASSRLS` 角色。配合 IDOR 安全测试确保隔离。（V2：RLS 策略和 token blocklist 持久化尚未实现，当前通过应用层 family_id 过滤和 Redis-based token blocklist 替代。）

**WebSocket 认证**：通过 `Sec-WebSocket-Protocol` 子协议传递 token (`bearer.<jwt_token>`)。

**PendingAction 默认拒绝**：白名单 (`KNOWN_SAFE_ACTIONS`) 内的操作直接执行，未知操作一律需要用户确认。

**LLM 提示注入防御**：三层——输入清洗（长度截断 + 注入模式检测）、系统提示边界标记、输出枚举值校验。

**敏感数据加密**：

| 字段 | 方式 |
|------|------|
| `users.password_hash` | bcrypt |
| `members.preferences` (健康相关) | AES-256-GCM |
| `favor_records.amount` | AES-256-GCM |

加密密钥通过 `ENCRYPTION_MASTER_KEY` 环境变量注入，每个家庭使用 HKDF 派生独立子密钥。

**Flutter 安全存储**：`flutter_secure_storage` (iOS Keychain / Android Keystore)。

### 7.2 领域事件总线

**传输**：Redis Streams + Consumer Groups + Transactional Outbox。

**双重发布模式**：

| 模式 | 用途 | 保障 |
|------|------|------|
| `publish()` | 通知性事件（简报刷新等） | 最多一次 (best-effort) |
| `publish_with_outbox()` | 关键业务事件（记忆提取、事件策展） | 至少一次 (Outbox Relay 每 5s 投递) |

**Consumer Group 映射**：每个订阅模块一个 Consumer Group，多实例并行消费。

**DLQ 策略**：5 次重试、5 分钟 idle timeout、XAUTOCLAIM 转移、30 天 DLQ 保留。

事件定义详见[第八章](#八跨模块通信)。

### 7.3 调度器

所有定时任务使用 **Redis Sorted Set** + **Celery Beat** 调度（每 30s 轮询）。分布式 fencing 通过 Redis SET NX 锁 + Celery Beat leader election。

| 任务 | 频率 |
|------|------|
| 简报推送 | 3 次/天 (晨/午/晚) |
| 洞察生成 | 1 次/天 |
| 记忆合并 | 1 次/天 |
| 策展清理 | 1 次/天 |
| Outbox Relay | 每 5s |
| favor_balance 对账 | 1 次/天 |

### 7.4 LLM Provider

```
core/llm/
├── __init__.py         # get_llm_provider(), configure_llm_provider()
├── openai_adapter.py   # ILLMProvider 实现（OpenAI-compatible API）
└── factory.py          # 生命周期管理
```

所有模块通过构造器注入 `ILLMProvider`。API 路由用 `Depends(get_llm_provider)`，Celery 任务用 `get_llm_provider()` 工厂。

### 7.5 可观测性

**健康检查**：3-probe K8s 模型 — liveness (进程存活)、readiness (DB+Redis 可达)、startup (首次初始化)。

**Prometheus 指标**（V2：当前为 stub 实现，指标收集器已定义但未接入实际 Prometheus exporter）：

| 指标 | 类型 | 维度 |
|------|------|------|
| `llm_call_duration_seconds` | Histogram | model, path_type |
| `llm_call_errors_total` | Counter | model, error_type |
| `agent_task_duration_seconds` | Histogram | path_type |
| `ws_connections_active` | Gauge | — |
| `scheduler_task_runs_total` | Counter | task_name, status |
| `event_bus_messages_total` | Counter | event_type, consumer_group |

**SLI / SLO**：

| SLI | SLO |
|-----|-----|
| Chat P99 延迟 (Fast Path) | < 3s |
| Chat P99 延迟 (Slow Path) | < 30s |
| LLM 错误率 | < 1% |
| Event 投递延迟 (Outbox) | < 10s |
| 系统可用性 | 99.5% |

**结构化日志**：JSON 格式，request_id + user_id + trace_id 通过 ContextVars 传播。

---

## 八、跨模块通信

### 8.1 领域事件

所有跨模块协调通过领域事件实现，不使用 Saga 模式。

| 事件 | 发布者 | 订阅者 | 载荷 |
|------|--------|--------|------|
| `TravelPlanCreated` | trip | curation, memory | plan_id, destination, dates |
| `TravelPlanUpdated` | trip | curation | plan_id, destination |
| `TravelPlanCancelled` | trip | curation | plan_id |
| `TravelPlanDeleted` | trip | curation | plan_id |
| `TravelCompleted` | trip | memory | plan_id, travel_memory_ids |
| `MemoryExtracted` | memory | curation, briefing, member, relationship | memory_id, entities, mentioned_persons[] |
| `EventCurated` | curation | briefing, views | event_id, type, priority |
| `EventRequested` | ai_engine | curation | title, event_type, start_time, location |
| `PreparationToggled` | views | briefing | event_id, item_key, done |
| `FavorRecorded` | relationship | memory, briefing | person_id, direction |
| `DateApproaching` | date_manager | curation, briefing | date_id, days_until |
| `ImportantDateCreated` | date_manager | gift, curation | date_id, date_type, needs_gift |
| `ImportantDateUpdated` | date_manager | gift, curation | date_id, changes |
| `ImportantDateDeleted` | date_manager | gift, curation | date_id |
| `DateReminderTriggered` | date_manager | briefing | reminder_id, date_id, days_until |
| `GiftTaskCreated` | gift | briefing | task_id, occasion, scheduled_time |
| `GiftRecommendationGenerated` | gift | briefing, member | recommendation_id, options_count |
| `GiftOptionSelected` | gift | memory | recommendation_id, gift_name |
| `GiftRecommendationExpired` | gift | — | recommendation_id |
| `GiftHistoryRecorded` | gift | memory | history_id, gift_name, occasion |
| `GiftFeedbackReceived` | gift | member | history_id, feedback_rating |
| `GiftTaskStatusChanged` | gift | briefing | task_id, new_status |
| `MemberProfileUpdated` | member | memory | member_id, updated_fields |
| `MemberRelationChanged` | member | relationship | relation_id, relation_type |
| `PreferenceUpdated` | gift | member | preference_id, gift_category, new_score |
| `InsightGenerated` | insight | briefing | insight_id, type |

> **注**：旅行事件当前使用 `TravelPlan*` 命名（代码中 `domain_events.py`），计划在 V2 中重命名为 `Trip*` 以与模块命名保持一致。

### 8.2 跨模块操作示例：创建重要日期

```
用户: "记住妈妈生日是农历三月初五"
    │
    ▼
[ai_engine] → date_manager.create_date()
    │
    ├── 1. 创建 important_dates 记录
    ├── 2. 创建 reminders 记录 (30天/7天/1天/当天)
    └── 3. 发布 DateApproaching 事件
         │
         ├── curation: 创建策展事件
         ├── gift: 检查是否需要礼物任务
         └── briefing: 安排简报提醒
```

各订阅者异步处理，部分失败不影响日期创建的主流程。后续的 briefing/insight 周期会补偿漏处理的事件。

### 8.3 通信规则

| 规则 | 说明 |
|------|------|
| **单向依赖** | 领域模块不 import 其他领域模块，通过 `core/interfaces/` ABC 解耦 |
| **Outbox 事件** | `TripCreated`, `MemoryExtracted`, `EventCurated` 使用 Outbox 模式（至少一次） |
| **Best-effort 事件** | `PreparationToggled`, `GiftTaskStatusChanged` 使用直接发布（最多一次） |
| **幂等处理** | 所有事件处理器必须幂等（event_id 去重） |
| **模块接口** | 每个模块提供 `interface.py`，定义对外 API 契约 |

---

## 九、扩展架构

### 9.1 Redis 三层分离

| 层 | 驱逐策略 | 数据 |
|----|---------|------|
| Cache | allkeys-lru | 缓存、速率限制、断路器状态 |
| Durable | noeviction + AOF | Redis Streams、Sorted Set 调度、会话亲和 |
| PubSub | allkeys-lru | WebSocket relay |

开发环境可用单 `REDIS_URL` 降级。生产环境使用 `REDIS_CACHE_URL`、`REDIS_DURABLE_URL`、`REDIS_PUBSUB_URL` 三个独立实例。

### 9.2 LLM 成本模型

| 路径 | 模型 | 输入/输出 Token | 单次成本 |
|------|------|---------------|---------|
| Fast | Haiku | 1K / 0.5K | ~$0.001 |
| Slow | Sonnet (3 轮工具调用) | 8K / 2K | ~$0.21-0.32 |
| Hybrid | Haiku + Sonnet | Fast + Slow | ~$0.22-0.33 |

**成本控制**：

| 策略 | 说明 |
|------|------|
| 分层路由 | 70% Fast + 10% Hybrid + 20% Slow |
| 三层上下文 | Layer 2 裁剪降低 Sonnet 输入 Token |
| prompt caching | 利用 Anthropic prompt caching 降低重复系统提示成本 |
| 速率限制 | 三维限流：per-user、per-family、global (fail-closed) |

### 9.3 断路器（V2）

> V2 特性：断路器当前为设计规划，尚未实现。LLM 调用的容错当前通过重试 + 超时处理。

分布式 Redis-backed 断路器保护 LLM 调用：

```
CLOSED → (连续 5 次失败) → OPEN → (30s 冷却) → HALF_OPEN → (1 次成功) → CLOSED
                                                           → (失败) → OPEN
```

`ResilientLLMAdapter` 封装 primary provider + fallback provider + circuit breaker。断路器状态存储在 Redis 中，所有实例共享。

### 9.4 数据库连接池

```
App Instances ──→ PgBouncer (transaction mode) ──→ Primary (RW)
                                                 ──→ Read Replica (RO)
```

| 参数 | 值 |
|------|-----|
| PgBouncer max_client_conn | 200 |
| PgBouncer default_pool_size | 25 |
| SQLAlchemy pool_size | 5 per instance |
| SQLAlchemy max_overflow | 10 |

---

## 十、错误处理策略

### 10.1 全局错误分类

| 类别 | 处理方式 | 示例 |
|------|---------|------|
| 可重试 (Transient) | 指数退避重试 (max 3 次) | 网络超时、Redis 连接中断 |
| 不可重试 (Permanent) | 立即返回错误 + 记录日志 | 参数校验失败、权限拒绝 |
| 降级 (Degraded) | 返回部分结果 + 标记降级 | 天气 API 不可用（不返回假数据） |
| 严重 (Critical) | 告警 + 降级 | DB 不可达 |

### 10.2 场景处理

| 场景 | 处理 |
|------|------|
| SSE 流中 LLM 失败 | 发送 `{"type": "error", "message": "..."}` 事件，关闭流 |
| 领域事件处理器抛异常 | 重试 5 次后进入 DLQ，不影响其他处理器 |
| 调度任务 Redis 不可达 | 跳过本次执行，下次 Celery Beat 轮询时重试 |
| 策展流水线批量失败 | 单条事件失败不影响批次中其他事件，失败事件记录到结构化日志 |
| 外部数据源不可用 | 多数据源降级（主 → 备），全部失败时返回明确错误信息，**禁止返回假数据** |

---

## 十一、测试架构

### 11.1 测试层次

| 层次 | 覆盖目标 | 工具 |
|------|---------|------|
| 单元测试 | 服务层业务逻辑 | pytest + mock |
| 集成测试 | API 端点 + DB 操作 | pytest + TestClient + 真实 DB |
| 契约测试 | 领域事件 schema 兼容性 | 自定义 schema 校验 |
| 安全测试 | IDOR、注入、认证 | pytest 专项套件 |
| LLM 集成测试 | 意图路由准确性 | 固定 prompt 集 + 断言分类结果 |
| E2E 测试 | 关键用户流程 | Playwright (Flutter Web) |

### 11.2 关键测试策略

- **DB 隔离**：每个测试函数使用独立 schema (DROP/CREATE)
- **LLM Mock**：单元测试中 mock `ILLMProvider`，集成测试中可选真实调用
- **事件契约**：事件 schema 变更必须通过契约测试，确保消费者兼容
- **IDOR 测试**：每个 family_scoped API 必须有跨家庭访问测试
- **覆盖率目标**：≥ 80%

---

## 十二、数据隐私与合规

### 12.1 数据分类

| 类别 | 数据 | 处理方式 |
|------|------|---------|
| PII-高 | 密码、Token | bcrypt 哈希 / flutter_secure_storage |
| PII-中 | 健康信息、财务金额 | AES-256-GCM 静态加密 |
| PII-低 | 姓名、生日、偏好 | RLS 隔离 + 传输加密 (TLS) |
| 业务数据 | 事件、记忆、行程 | RLS 隔离 |

### 12.2 LLM 数据政策

| 规则 | 说明 |
|------|------|
| **数据传输** | 所有 LLM API 调用使用 HTTPS，Anthropic 承诺不使用客户数据训练模型 |
| **上下文最小化** | 三层上下文架构确保只传输必要数据给 LLM |
| **敏感字段过滤** | 发送给 LLM 前过滤加密字段原文（金额、健康信息） |
| **审计** | 所有 LLM 工具调用记录在 `tool_execution_logs` 中 |

### 12.3 数据保留

| 数据 | 保留期限 |
|------|---------|
| 聊天消息 | 永久（用户可手动删除会话） |
| 工具执行日志 | 90 天 |
| 事件 Outbox | 7 天（已投递） |
| Token 撤销记录 | 与 Token 剩余寿命对齐 |
| DLQ 消息 | 30 天 |

### 12.4 用户权利

- **数据导出**：支持用户导出全部个人数据 (GDPR Art. 20)
- **数据删除**：`families.id` CASCADE 删除全部关联数据
- **会话清除**：用户可随时删除聊天会话及关联的记忆

---

## 时区处理规范

| 层级 | 规范 |
|------|------|
| 数据库 | UTC，`TIMESTAMP WITH TIME ZONE` |
| API 传输 | ISO 8601 UTC，`2026-01-28T00:00:00Z` |
| 应用层 | 用户时区，展示前转换 |

统一函数：`to_utc()`, `to_local()`, `utc_now()`（位于 `core/utils/timezone.py`）。

---

## 环境变量清单

| 变量 | 说明 | 必须 |
|------|------|------|
| `DATABASE_URL` | PostgreSQL 连接串 | Y |
| `REDIS_URL` | Redis 连接串（开发环境统一入口） | Y |
| `REDIS_CACHE_URL` | Redis Cache 层（生产环境） | Prod |
| `REDIS_DURABLE_URL` | Redis Durable 层（生产环境） | Prod |
| `REDIS_PUBSUB_URL` | Redis PubSub 层（生产环境） | Prod |
| `JWT_SECRET` | JWT 签名密钥（≥ 32 chars, 随机生成） | Y |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 | Y |
| `ENCRYPTION_MASTER_KEY` | AES-256-GCM 主密钥 | Y |
| `CORS_ORIGINS` | 允许的 CORS Origin 列表 | Prod |
| `QWEATHER_API_KEY` | 和风天气 API 密钥 | N |
| `FCM_CREDENTIALS` | Firebase Cloud Messaging 凭证 | N |
