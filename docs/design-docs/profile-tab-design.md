# "我的" Tab 功能设计文档

> **版本** 1.0 | **日期** 2026-02-13 | **设计团队** profile-design

---

## 一、总览

"我的"是底部导航第三个 Tab，承载用户的**个人管理、关系网络、数据控制和秘书监控**四大核心能力。

### 设计原则

| # | 原则 | 说明 |
|---|------|------|
| 1 | **零新模块** | 所有功能映射到现有 13 个后端模块，不新建模块 |
| 2 | **薄 API 层** | 仅添加必要的聚合/统计端点，复用已有 CRUD |
| 3 | **渐进展示** | 首屏展示概览卡片，下钻查看详情 |
| 4 | **安全优先** | 敏感操作需密码确认，数据清除不可逆 |

### 页面结构总览

```
我的 (Tab 3)
├── 1. 个人信息卡片 (头像+姓名+家庭+天数)
├── 2. 成员管理入口卡片 (按分类统计)
├── 3. 数据连接入口卡片 (已连接数)
├── 4. 秘书工作报告入口卡片 (本周事务数)
├── 5. 记忆管理入口卡片 (记忆总数+最新洞察)
├── 6. 设置区域
│   ├── 通知偏好
│   ├── 隐私与安全
│   └── 关于
├── 7. 清空数据 (danger zone)
└── 8. 退出登录
```

---

## 二、功能模块详细设计

---

### 2.1 成员管理

**所属模块**: `member` + `relationship`（只读引用）

**现有基础**:
- 后端: member CRUD, person_profiles (两层人物模型), relationship_edges, work_histories
- 移动端: members 列表页, 4 种筛选 (family/work/friend/other)
- API: `/members/*` 完整 CRUD (~13 端点)

#### 2.1.1 Profile 页入口卡片

```
┌─────────────────────────────────────┐
│  👥 我的关系网                        │
│                                     │
│  家人 5   朋友 12   同事 8   亲戚 3    │
│  ━━━━━   ━━━━━━   ━━━━━   ━━━━━    │
│                                     │
│  🔔 3 位联系人需要关注    查看全部 >    │
└─────────────────────────────────────┘
```

- 数字统计: 调用 `GET /members?group_by=relation_type` (需新增聚合参数)
- "需要关注": 调用 `GET /members/people/neglected`
- 点击 → 成员列表页

#### 2.1.2 成员列表页

**顶部**: 搜索栏 (关键词搜索成员名/备注)

**Tab 筛选**:
| Tab | 对应 relation_type | 数据源 |
|-----|-------------------|--------|
| 全部 | * | `GET /members` |
| 家人 | family | `GET /members?relation_type=family` |
| 朋友 | friend | `GET /members?relation_type=friend` |
| 同事 | colleague | `GET /members?relation_type=colleague` |
| 亲戚 | relative | `GET /members?relation_type=relative` |

**成员卡片**:
```
┌──────────────────────────────────┐
│ 🟢 [头像]  张三                    │
│            好友 · 上次提及 3天前     │
│            关系健康度 ████░░ 72%    │
│                         [查看]    │
└──────────────────────────────────┘
```

- 关系健康度: `GET /relationships/health` (已有)
- 上次提及: 基于 conversation_memories 中 entities 字段

#### 2.1.3 添加成员

**快速添加** (P0):
- 最少信息: 姓名 + 关系类型
- 调用: `POST /members` (已有)
- 后续通过对话自动丰富 (profile_enrichment 服务已有)

**完整添加** (P1):
- 根据关系类型展示不同字段:
  - 家人: 姓名、关系、生日(支持农历)、血型、尺码
  - 同事: 姓名、公司、职位、部门
  - 朋友/亲戚: 姓名、关系、备注

#### 2.1.4 成员详情页

```
┌──────────────────────────────────┐
│ [头像]  张三                       │
│ 好友 · 大学同学                     │
│                                  │
│ ── 基本信息 ──                     │
│ 生日: 1990-05-15                  │
│ 电话: 138****1234                 │
│                                  │
│ ── 关系健康 ──                     │
│ 健康度 72%  上次互动 3天前           │
│ 人情余额: +2 (你多帮了2次)          │
│                                  │
│ ── 互动记忆 ──                     │
│ · 上周一起吃了火锅 (2月10日)        │
│ · 他喜欢打篮球 (1月28日)            │
│                                  │
│ ── 重要日期 ──                     │
│ · 生日: 5月15日 (还有91天)          │
│                                  │
│ ── 送礼历史 ──                     │
│ · 春节送了茶叶礼盒 (2月)            │
│                                  │
│ [编辑] [删除]                      │
└──────────────────────────────────┘
```

**数据来源映射**:
| 区块 | API | 模块 |
|------|-----|------|
| 基本信息 | `GET /members/{id}` | member |
| 关系健康 | `GET /relationships/health?person_id={id}` | relationship |
| 人情余额 | `GET /relationships/favors?person_id={id}` | relationship |
| 互动记忆 | `GET /memory/list?entity_id={id}` | memory |
| 重要日期 | `GET /dates?member_id={id}` | date_manager |
| 送礼历史 | `GET /gifts/history?member_id={id}` | gift |

#### 2.1.5 新增/变更的 API

| 方法 | 路径 | 说明 | 优先级 |
|------|------|------|--------|
| GET | `/members/stats` | 按关系类型统计成员数 | P0 |
| GET | `/members/{id}/timeline` | 聚合成员相关的记忆+事件+礼物 | P1 |

> 注: `/members/stats` 在 `user_services.py` 中已有部分实现 (family_member_count)，需扩展为分类统计。

---

### 2.2 数据连接 (MCP)

**所属模块**: `member` (扩展用户配置管理) + `ai_engine` (MCP 执行)

**现有基础**:
- `IMCPProvider` 接口 (MCPTool, MCPServerInfo, 连接状态)
- `mcp_executor.py` / `mcp_tool_server.py` 工具执行
- AI 工具: `call_mcp_tool`, `list_mcp_tools`

#### 2.2.1 数据模型

**新增表: `user_data_connections`** (归属 member 模块)

```sql
CREATE TABLE user_data_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    family_id UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,

    -- 连接标识
    provider_type VARCHAR(50) NOT NULL,   -- calendar, email, contacts, notes, smart_home, transport, shopping, custom
    provider_name VARCHAR(100) NOT NULL,  -- google_calendar, gmail, notion, etc.
    display_name VARCHAR(200) NOT NULL,   -- "Google 日历"
    icon_url VARCHAR(500),

    -- 连接状态
    connection_status VARCHAR(20) NOT NULL DEFAULT 'disconnected',  -- disconnected/connecting/connected/error
    auth_type VARCHAR(20) NOT NULL DEFAULT 'oauth2',                -- oauth2/api_key/mcp_direct

    -- 凭证 (AES-256-GCM 加密)
    encrypted_credentials BYTEA,          -- 加密的 JSON: {access_token, refresh_token, expires_at, ...}
    scopes JSONB DEFAULT '[]'::jsonb,     -- 授权范围: ["read_events", "write_events"]

    -- MCP 配置
    mcp_server_url VARCHAR(500),          -- 自定义 MCP server URL
    mcp_server_config JSONB,              -- MCP server 额外配置

    -- 状态追踪
    last_sync_at TIMESTAMP WITH TIME ZONE,
    last_error TEXT,
    sync_frequency_minutes INT DEFAULT 60,
    metadata JSONB DEFAULT '{}'::jsonb,

    -- 通用字段
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT uq_user_provider UNIQUE (user_id, provider_name)
);

CREATE INDEX ix_user_data_connections_user_status
    ON user_data_connections (user_id, connection_status)
    WHERE is_active = TRUE;
```

> **为何放 member 模块**: member 模块已管理 users, device_tokens 等用户级配置。数据连接本质也是用户级配置。

#### 2.2.2 推荐连接列表

内置在后端配置中 (非 DB 存储)，通过 API 返回可用连接列表:

| 分类 | 连接名 | provider_name | auth_type | 说明 |
|------|--------|---------------|-----------|------|
| 📅 日历 | Google 日历 | google_calendar | oauth2 | 读取/写入日程 |
| 📅 日历 | Apple 日历 | apple_calendar | oauth2 | 读取日程 |
| 📅 日历 | Outlook 日历 | outlook_calendar | oauth2 | 读取/写入日程 |
| 📧 邮箱 | Gmail | gmail | oauth2 | 读取邮件摘要 |
| 📧 邮箱 | Outlook | outlook_mail | oauth2 | 读取邮件摘要 |
| 📧 邮箱 | QQ 邮箱 | qq_mail | oauth2 | 读取邮件摘要 |
| 📝 笔记 | Notion | notion | oauth2 | 读取/写入笔记 |
| 📝 笔记 | Apple 备忘录 | apple_notes | mcp_direct | 本地 MCP |
| 🚗 出行 | 高德地图 | amap | api_key | 位置/路线查询 |
| 🛒 购物 | 京东 | jd | oauth2 | 订单历史(只读) |
| 🏠 智能家居 | 米家 | mi_home | oauth2 | 设备控制 |
| ⚙️ 自定义 | MCP Server | custom | mcp_direct | 用户自定义 MCP |

#### 2.2.3 UI 设计

**Profile 页入口卡片**:
```
┌─────────────────────────────────────┐
│  🔗 数据连接                          │
│                                     │
│  已连接 3 个服务    管理 >             │
│  [Google日历✅] [Gmail✅] [Notion✅]   │
└─────────────────────────────────────┘
```

**连接管理页**:
```
┌─────────────────────────────────────┐
│  数据连接                    [+ 自定义] │
│                                     │
│  ── 已连接 ──                        │
│  ✅ Google 日历  同步于 5分钟前  [管理] │
│  ✅ Gmail       同步于 1小时前  [管理] │
│  ✅ Notion      同步于 30分钟前 [管理] │
│                                     │
│  ── 推荐连接 ──                      │
│  📅 日历                              │
│  ○ Apple 日历                [连接]  │
│  ○ Outlook 日历              [连接]  │
│                                     │
│  📧 邮箱                              │
│  ○ Outlook                   [连接]  │
│  ○ QQ 邮箱                   [连接]  │
│                                     │
│  📝 笔记                              │
│  ○ Apple 备忘录              [连接]  │
│                                     │
│  🚗 出行                              │
│  ○ 高德地图                  [连接]  │
│                                     │
│  🏠 智能家居                          │
│  ○ 米家                      [连接]  │
└─────────────────────────────────────┘
```

**连接详情/管理页**:
```
┌─────────────────────────────────────┐
│  Google 日历                         │
│  ✅ 已连接                            │
│                                     │
│  权限范围:                            │
│  ☑ 读取日程事件                       │
│  ☑ 创建/修改日程                      │
│  ☐ 删除日程                           │
│                                     │
│  上次同步: 5分钟前                     │
│  同步频率: 每小时                      │
│                                     │
│  [手动同步]     [断开连接]             │
└─────────────────────────────────────┘
```

#### 2.2.4 API 端点

| 方法 | 路径 | 说明 | 优先级 |
|------|------|------|--------|
| GET | `/connections` | 列出用户所有连接 | P0 |
| GET | `/connections/available` | 列出可用连接(含推荐) | P0 |
| POST | `/connections/{provider}/authorize` | 发起 OAuth 授权 | P0 |
| GET | `/connections/{provider}/callback` | OAuth 回调 | P0 |
| DELETE | `/connections/{id}` | 断开连接 | P0 |
| PATCH | `/connections/{id}` | 更新权限/配置 | P1 |
| POST | `/connections/{id}/sync` | 手动触发同步 | P1 |
| POST | `/connections/custom` | 添加自定义 MCP server | P2 |

#### 2.2.5 与 AI Engine 集成

```
用户连接 Google Calendar
    ↓
user_data_connections 记录 status=connected
    ↓
ai_engine 收到聊天请求时:
    ↓ 查询用户活跃连接
    ↓ 动态注入对应 MCP 工具 (query_external_calendar 等)
    ↓ Agent 可使用 call_mcp_tool 调用
```

AI Engine 已有 `list_mcp_tools` 和 `call_mcp_tool`，只需在工具注入阶段查询 `user_data_connections` 表。

---

### 2.3 秘书工作报告

**所属模块**: 聚合查询，跨 `curation` + `conversation` + `memory` + `insight` + `briefing`

**现有基础**:
- `curation_jobs` 表: 策展任务执行记录
- `tool_execution_logs` 表: 工具执行日志
- `conversation_memories` 表: 记忆
- `memory_insights` 表: 洞察
- Mobile: `work_report_page.dart`, `curation_detail_page.dart` 已有框架

#### 2.3.1 Profile 页入口卡片

```
┌─────────────────────────────────────┐
│  📊 秘书工作报告                      │
│                                     │
│  本周处理了 47 件事务                  │
│  ■■■■■■■░░░ (相比上周 +12%)         │
│                                     │
│  记忆 12 · 事件 8 · 洞察 5 · 提醒 22  │
│                            查看 >    │
└─────────────────────────────────────┘
```

#### 2.3.2 工作报告详情页

```
┌─────────────────────────────────────┐
│  秘书工作报告                         │
│  [今天] [本周] [本月] [自定义]         │
│                                     │
│  ── 总览 ──                          │
│  📋 事务总数: 47                      │
│  ⏱ 平均响应: 2.3s                    │
│  ✅ 成功率: 98.5%                     │
│                                     │
│  ── 分类统计 ──                      │
│  🧠 记忆提取    12 条  ████████░░    │
│  📅 事件管理     8 个  █████░░░░░    │
│  💡 洞察生成     5 条  ███░░░░░░░    │
│  ⏰ 提醒发送    22 条  ██████████    │
│  📰 简报推送     3 次  ██░░░░░░░░    │
│  🎁 礼物追踪     2 个  █░░░░░░░░░    │
│                                     │
│  ── 活动时间线 ──                     │
│  14:30 提取了一条记忆: "张三喜欢..."   │
│  14:00 发送了下午简报                  │
│  11:22 创建了策展事件: "周五聚餐"      │
│  09:00 发送了晨间简报                  │
│  08:45 生成了 3 条洞察                 │
│  ...                                │
│                      [加载更多]       │
└─────────────────────────────────────┘
```

#### 2.3.3 API 端点

| 方法 | 路径 | 说明 | 数据源 | 优先级 |
|------|------|------|--------|--------|
| GET | `/report/summary` | 聚合统计 (支持 range 参数) | 跨模块聚合 | P0 |
| GET | `/report/timeline` | 活动时间线 (分页) | tool_execution_logs + curation_jobs | P0 |
| GET | `/report/trend` | 趋势数据 (周对比) | 聚合计算 | P1 |

**聚合逻辑** (report_service.py 新增到 conversation 或新建薄服务):

```python
# GET /report/summary?range=week
{
    "range": "2026-02-07/2026-02-13",
    "total_actions": 47,
    "avg_response_time_ms": 2300,
    "success_rate": 0.985,
    "breakdown": {
        "memories_extracted": 12,    # COUNT from conversation_memories WHERE created_at in range
        "events_managed": 8,         # COUNT from curated_events WHERE created_at in range
        "insights_generated": 5,     # COUNT from memory_insights WHERE created_at in range
        "reminders_sent": 22,        # COUNT from event_reminders WHERE status='sent' AND sent_at in range
        "briefings_sent": 3,         # COUNT from curation_jobs WHERE job_type='briefing' in range
        "gifts_tracked": 2           # COUNT from gift_tasks WHERE updated_at in range
    },
    "comparison": {
        "vs_last_period": 0.12       # +12%
    }
}
```

> **模块归属决策**: report 是只读聚合，不拥有任何表。建议在 `api/v1/` 新增 `report.py` 路由，直接跨模块查询。或归入 `conversation` 模块（已有 today_service 聚合模式）。

---

### 2.4 个人中心

**所属模块**: `core/auth` + `member` + `briefing` (设置)

**现有基础**:
- Auth: register/login/logout, profile edit, password change, account deletion
- User 模型: id, username, email, phone, timezone, avatar_url, is_active
- Mobile: edit_profile, change_password, delete_account 页面已有

#### 2.4.1 Profile 页顶部卡片

```
┌─────────────────────────────────────┐
│                                     │
│        [头像📷]                      │
│        王小明                        │
│        小明的家庭                     │
│        已加入 128 天                  │
│                                     │
│        [编辑资料]                     │
│                                     │
└─────────────────────────────────────┘
```

#### 2.4.2 账户管理

| 功能 | 现有 | 需新增 | API | 优先级 |
|------|------|--------|-----|--------|
| 编辑昵称/用户名 | ✅ | - | `PUT /auth/profile` | P0 |
| 修改密码 | ✅ | - | `POST /auth/change-password` | P0 |
| 上传头像 | ⚠️ 字段有, 上传无 | 文件上传端点 | `POST /auth/avatar` | P1 |
| 绑定手机 | ⚠️ 字段有, 流程无 | SMS 验证流程 | `POST /auth/bind-phone` | P1 |
| 绑定邮箱 | ⚠️ 字段有, 流程无 | 邮件验证流程 | `POST /auth/bind-email` | P1 |
| 时区设置 | ⚠️ 字段有, UI 无 | 下拉选择 UI | `PUT /auth/profile` 扩展 | P1 |
| 语言偏好 | ❌ | users 表加字段 | `PUT /auth/profile` 扩展 | P2 |

#### 2.4.3 通知偏好

```
┌─────────────────────────────────────┐
│  通知设置                             │
│                                     │
│  简报推送          ─────────── [开]   │
│    晨间简报 08:00   ✅               │
│    午间简报 12:00   ✅               │
│    晚间简报 20:00   ✅               │
│                                     │
│  洞察推送          ─────────── [开]   │
│    推送频率         [中等 ▼]         │
│                                     │
│  提醒推送          ─────────── [开]   │
│  人情提醒          ─────────── [开]   │
└─────────────────────────────────────┘
```

**数据存储**:
- 简报偏好 → `user_briefing_settings` 表 (已有)
- 洞察偏好 → `user_insight_settings` 表 (已有)
- 通用推送偏好 → 扩展 `user_briefing_settings` 或新增字段

**API**:
- `GET/PUT /briefing/settings` (已有)
- `GET/PUT /settings/notifications` (新增统一通知设置端点)

---

### 2.5 记忆管理

**所属模块**: `memory` + `insight`

**现有基础**:
- Memory API: `GET /memory/list`, `GET /memory/recall`, `GET /memory/search`, `PATCH /memory/{id}/status`, `DELETE /memory/{id}`
- Insight API: `GET /insights`, `POST /insights/{id}/action`, `POST /insights/{id}/feedback`
- 记忆类型: preference, fact, event, relationship, opinion
- 洞察类型: reminder, suggestion, observation, correlation, followup

#### 2.5.1 Profile 页入口卡片

```
┌─────────────────────────────────────┐
│  🧠 秘书记忆库                        │
│                                     │
│  已记住 156 条信息                     │
│                                     │
│  最新洞察:                            │
│  💡 张三的生日快到了，去年送的是书...    │
│                            查看 >    │
└─────────────────────────────────────┘
```

#### 2.5.2 记忆浏览器页

```
┌─────────────────────────────────────┐
│  [🔍 搜索记忆...]                     │
│                                     │
│  [全部] [偏好] [事实] [事件] [关系] [观点]│
│                                     │
│  ── 最近记忆 ──                      │
│  ┌────────────────────────────────┐ │
│  │ 🏷️ 偏好  ⭐⭐⭐                  │ │
│  │ 张三喜欢打篮球，周末经常去...     │ │
│  │ 👤 张三  📅 2月10日              │ │
│  │                    [归档] [删除] │ │
│  └────────────────────────────────┘ │
│  ┌────────────────────────────────┐ │
│  │ 📌 事实  ⭐⭐                    │ │
│  │ 李四在字节跳动工作，做产品经理    │ │
│  │ 👤 李四  📅 2月8日               │ │
│  └────────────────────────────────┘ │
│                                     │
│  ── 洞察 (5 条待查看) ──              │
│  ┌────────────────────────────────┐ │
│  │ 💡 提醒                          │ │
│  │ 妈妈的生日还有15天，去年送的...   │ │
│  │ [有用 👍] [没用 👎]              │ │
│  └────────────────────────────────┘ │
│                      [加载更多]      │
└─────────────────────────────────────┘
```

#### 2.5.3 API 映射

| 功能 | API | 现有 | 优先级 |
|------|-----|------|--------|
| 记忆列表 | `GET /memory/list?type=X&page=N` | ✅ | P0 |
| 语义搜索 | `GET /memory/recall?query=X` | ✅ | P0 |
| 关键词搜索 | `GET /memory/search?keyword=X` | ✅ | P0 |
| 归档记忆 | `PATCH /memory/{id}/status` (→ archived) | ✅ | P0 |
| 删除记忆 | `DELETE /memory/{id}` | ✅ | P0 |
| 记忆统计 | `GET /memory/stats` | ❌ 需新增 | P0 |
| 洞察列表 | `GET /insights` | ✅ | P0 |
| 洞察反馈 | `POST /insights/{id}/feedback` | ✅ | P0 |

**仅需新增 1 个端点**: `GET /memory/stats` (按类型统计记忆数)

---

### 2.6 清空数据

**所属模块**: `core/auth` + 各模块 (级联删除)

#### 2.6.1 数据管理页

```
┌─────────────────────────────────────┐
│  数据管理                             │
│                                     │
│  ── 数据统计 ──                      │
│  聊天记录    156 条对话               │
│  家庭记忆    89 条记忆                │
│  洞察记录    45 条洞察                │
│  策展事件    32 个事件                │
│                                     │
│  ── 数据操作 ──                      │
│  [清空聊天记录]          ⚠️           │
│  [清空家庭记忆]          ⚠️           │
│  [清空洞察记录]          ⚠️           │
│  [清空策展事件]          ⚠️           │
│                                     │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━    │
│  [清空所有数据]          🔴           │
│                                     │
│  [导出我的数据]          📦 P2        │
└─────────────────────────────────────┘
```

#### 2.6.2 清空确认流程

```
用户点击 "清空聊天记录"
    ↓
确认弹窗: "确定清空所有聊天记录? 此操作不可恢复。"
    ↓ [确认]
输入密码验证
    ↓ 验证通过
执行清空 + 显示进度
    ↓
成功提示 + 返回
```

#### 2.6.3 API 端点

| 方法 | 路径 | 说明 | 影响的表 | 优先级 |
|------|------|------|---------|--------|
| GET | `/data/stats` | 各类数据统计 | 只读聚合 | P0 |
| DELETE | `/data/chat-history` | 清空聊天 | chat_sessions, chat_messages, tool_execution_logs | P0 |
| DELETE | `/data/memories` | 清空记忆 | conversation_memories, memory_associations, memory_summaries, secretary_notes, memory_insights, insight_feedbacks | P0 |
| DELETE | `/data/events` | 清空事件 | curated_events, event_associations, preparation_items | P1 |
| DELETE | `/data/all` | 清空全部(保留账户) | 上述所有 + trips, gifts, dates, relationships | P1 |
| POST | `/data/export` | 导出数据 (异步) | 只读，生成 JSON/ZIP | P2 |

**安全要求**:
- 所有 DELETE 操作需要请求体中包含 `password` 字段进行密码验证
- 操作记录到审计日志
- 「清空所有」需二次确认

---

### 2.7 退出登录

**所属模块**: `core/auth`

**现有**: 完整实现
- 后端: `POST /auth/logout`
- 移动端: AuthBloc 处理登出, 清除 secure storage
- UI: settings_page.dart 已有登出按钮 + 确认弹窗

**设计**: 在"我的"页面底部放置红色退出按钮

```
┌─────────────────────────────────────┐
│                                     │
│         [退出登录]  (红色文字)         │
│                                     │
│         版本 1.0.0                   │
└─────────────────────────────────────┘
```

无需任何代码变更，直接在新布局中复用现有逻辑。

---

## 三、新增 API 端点汇总

| # | 方法 | 路径 | 所属路由文件 | 描述 | 优先级 |
|---|------|------|------------|------|--------|
| 1 | GET | `/members/stats` | members.py (扩展) | 成员分类统计 | P0 |
| 2 | GET | `/members/{id}/timeline` | members.py (扩展) | 成员交互时间线 | P1 |
| 3 | GET | `/connections` | connections.py (新) | 用户连接列表 | P0 |
| 4 | GET | `/connections/available` | connections.py (新) | 可用连接列表 | P0 |
| 5 | POST | `/connections/{provider}/authorize` | connections.py (新) | 发起 OAuth | P0 |
| 6 | GET | `/connections/{provider}/callback` | connections.py (新) | OAuth 回调 | P0 |
| 7 | DELETE | `/connections/{id}` | connections.py (新) | 断开连接 | P0 |
| 8 | PATCH | `/connections/{id}` | connections.py (新) | 更新连接配置 | P1 |
| 9 | POST | `/connections/{id}/sync` | connections.py (新) | 手动同步 | P1 |
| 10 | POST | `/connections/custom` | connections.py (新) | 自定义 MCP | P2 |
| 11 | GET | `/report/summary` | report.py (新) | 工作报告聚合 | P0 |
| 12 | GET | `/report/timeline` | report.py (新) | 活动时间线 | P0 |
| 13 | GET | `/report/trend` | report.py (新) | 趋势对比 | P1 |
| 14 | GET | `/memory/stats` | memory.py (扩展) | 记忆统计 | P0 |
| 15 | GET | `/data/stats` | data.py (新) | 数据统计 | P0 |
| 16 | DELETE | `/data/chat-history` | data.py (新) | 清空聊天 | P0 |
| 17 | DELETE | `/data/memories` | data.py (新) | 清空记忆 | P0 |
| 18 | DELETE | `/data/events` | data.py (新) | 清空事件 | P1 |
| 19 | DELETE | `/data/all` | data.py (新) | 清空全部 | P1 |
| 20 | POST | `/data/export` | data.py (新) | 导出数据 | P2 |
| 21 | POST | `/auth/avatar` | auth.py (扩展) | 上传头像 | P1 |
| 22 | POST | `/auth/bind-phone` | auth.py (扩展) | 绑定手机 | P1 |
| 23 | POST | `/auth/bind-email` | auth.py (扩展) | 绑定邮箱 | P1 |
| 24 | GET/PUT | `/settings/notifications` | settings.py (新) | 通知偏好 | P1 |

**新增路由文件**: connections.py, report.py, data.py, settings.py (4 个)
**扩展现有路由**: members.py, memory.py, auth.py (3 个)

---

## 四、新增数据表汇总

| # | 表名 | 所属模块 | 说明 |
|---|------|---------|------|
| 1 | `user_data_connections` | member | 用户外部数据连接 (MCP) |

**仅新增 1 张表**。其余功能全部复用现有 64 张表。

---

## 五、移动端页面清单

| # | 页面 | 路由 | 状态 | 优先级 |
|---|------|------|------|--------|
| 1 | Profile 主页 | `/profile` | ✅ 已有, 需重构布局 | P0 |
| 2 | 成员列表 | `/profile/members` | ✅ 已有 | P0 |
| 3 | 成员详情 | `/profile/members/{id}` | ⚠️ 需增强 | P0 |
| 4 | 添加成员 | `/profile/members/add` | ⚠️ 需增强 | P0 |
| 5 | 连接管理 | `/profile/connections` | ❌ 新建 | P0 |
| 6 | 连接详情 | `/profile/connections/{id}` | ❌ 新建 | P1 |
| 7 | 工作报告 | `/profile/work-report` | ✅ 已有框架 | P0 |
| 8 | 记忆浏览器 | `/profile/memories` | ❌ 新建 | P0 |
| 9 | 记忆详情 | `/profile/memories/{id}` | ❌ 新建 | P1 |
| 10 | 编辑资料 | `/profile/account/edit` | ✅ 已有 | P0 |
| 11 | 修改密码 | `/profile/account/password` | ✅ 已有 | P0 |
| 12 | 通知设置 | `/profile/notifications` | ❌ 新建 | P1 |
| 13 | 数据管理 | `/profile/data` | ⚠️ 有框架 | P0 |
| 14 | 关于 | `/profile/about` | ✅ 已有 | P2 |

**新建页面**: 4 个 (connections, connection detail, memories, memory detail)
**重构页面**: 3 个 (profile 主页, member detail, data management)
**直接复用**: 7 个

---

## 六、后端模块影响分析

| 模块 | 变更类型 | 变更内容 |
|------|---------|---------|
| `member` | **扩展** | 新增 `user_data_connections` 表 + connection_service.py + stats 聚合 |
| `memory` | **扩展** | 新增 stats 端点 |
| `conversation` | **扩展** | 新增 report 聚合查询 (可选) |
| `core/auth` | **扩展** | avatar 上传, bind phone/email |
| `api/v1/` | **新增路由** | connections.py, report.py, data.py, settings.py |
| `ai_engine` | **微调** | 工具注入时查询 user_data_connections |
| insight | 无变更 | API 已完整 |
| curation | 无变更 | 只被聚合查询 |
| briefing | 无变更 | settings API 已有 |
| views | 无变更 | - |
| trip | 无变更 | - |
| gift | 无变更 | - |
| date_manager | 无变更 | - |
| relationship | 无变更 | API 已完整 |

**结论**: 无新模块，6 个模块小幅扩展，4 个新路由文件。

---

## 七、实施优先级

### P0 (MVP, Week 1-2)
1. Profile 主页布局重构 (卡片式入口)
2. 成员管理增强 (分类统计卡片 + 详情页增强)
3. 记忆浏览器 (列表 + 搜索 + 洞察反馈)
4. 秘书工作报告 (聚合统计 + 时间线)
5. 数据管理 (统计 + 清空聊天/记忆)
6. 数据连接基础 (列表展示 + 连接/断开)

### P1 (Enhancement, Week 3-4)
7. 连接详情管理 (权限范围 + 手动同步)
8. 成员交互时间线
9. 通知偏好设置
10. 头像上传 / 手机绑定 / 邮箱绑定
11. 清空事件 / 清空全部
12. 工作报告趋势对比

### P2 (Future)
13. 自定义 MCP 连接
14. 数据导出
15. 记忆详情页 (关联记忆网络)
16. 语言偏好

---

## 八、安全考量

| 功能 | 安全措施 |
|------|---------|
| 数据清空 | 密码二次验证 + 不可逆警告 |
| MCP 连接 | OAuth token AES-256-GCM 加密存储, per-user 密钥派生 |
| 头像上传 | 文件类型/大小校验, 内容扫描 |
| 手机/邮箱绑定 | 验证码限频 (60s), 绑定操作需当前密码 |
| 记忆管理 | family_id 隔离, 只能管理自己家庭的记忆 |
| 工作报告 | 只读聚合, 无写操作风险 |
