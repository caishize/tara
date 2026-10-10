# Tara · 生活秘书

> 一个"有家庭记忆的 AI 代理人"的实验项目 · AI-Powered Family Secretary
>
> ⚠️ **项目已暂停维护。** 这里公开的是它停下来时的样子，希望能给做类似方向的朋友一些启发。

---

## 项目的由来

### 什么时候开始的

这个项目从 **2025 年 11 月** 开始写，内部代号一直叫 `Secretary`（生活秘书），所以代码里大量出现 `secretary` 这个名字。它是我工作之余的个人项目，前后断断续续做了大约五个月。

### 想解决什么问题

作为一个普通的职场人，我常常觉得"身在外，心在家，力不从心"：

- **忘记承诺**：随口答应的事转头就忘，坐在高铁上才想起"下次去北京要约老同学吃饭"。
- **无暇顾家**：知道妈妈生日快到了，却没时间准备；孩子兴趣班的时间总记不清。
- **人情负担**：同事帮了忙不知道怎么答谢，逢年过节送礼绞尽脑汁。
- **琐事堆积**：净水器换滤芯、车险续保、体检预约……每一件都不大，堆在一起就成了心理负担。
- **信息碎片**：家人的尺码、常用药、喜好散落在脑子里和各种 App 里，真正要用的时候找不到。

日历、备忘录加上一个通用聊天机器人，能解决一部分问题，但它们都需要你**主动填表、主动去问**，而且彼此不相通。我想做的是一个"像多年老秘书一样"的助手：

- **不填表**：所有输入都通过自然对话完成，由 AI 自动提取成结构化信息。
- **会串联**：把新旧信息自动关联起来，比如"北京出差 → 那位老同学 → 当地天气 → 顺便见一面"。
- **懂分寸**：适度提醒，不打扰，不制造焦虑。
- **能执行**：不只是提醒，还能帮你把事情落实；但涉及他人或不可撤回的操作，一定先让你确认（Human-in-the-loop）。
- **有温度**：说话像家人之间的叮嘱，而不是一套冷冰冰的 ERP。

完整的产品思考写在 [docs/PRD-生活秘书-统一版.md](docs/PRD-生活秘书-统一版.md) 里。

### 大致的演进过程

| 时间 | 主要工作 |
|------|---------|
| 2025-11 | 立项，写产品规格与架构文档；搭起成员与家庭、重要日期、人情往来、孩子成长、礼物推荐、Web 前端等基础模块 |
| 2025-12 | 跨模块联动：智能事件管理、成员时间线、旅行规划、价格监控 |
| 2026-01 | 用 Claude Agent SDK 重新设计 LLM 架构；做出时间线策展（Curation）和 AI 洞察的第一版；Flutter 移动端逐步成为主力 |
| 2026-02 | 全面接入 Agent SDK：Sub-agent、Skill 系统、工具执行器、会话池；增加语音输入；先后打了 v1.0 ~ v3.0 几个版本 |
| 2026-03 | 大量打磨：洞察引擎、看板与时光轴、每日简报；同时搭建了一套让 AI 编码助手"守规矩"的工程化约束（架构分层检查、约定文档、工作流命令） |

### 为什么停了，为什么现在放出来

最后一次提交是在 **2026 年 3 月下旬**。之后因为工作越来越忙，实在抽不出足够的精力继续推进，项目就这样停了好几个月。

与其让它一直躺在硬盘里，不如把它开放出来。它离一个成熟的产品还很远，但里面有不少我踩过的坑和做过的尝试。如果你也在做个人助理、家庭场景的 AI 应用，或者在探索怎么用 Agent SDK 搭一个真实可用的系统，希望这里的代码和文档能给你一些启发。

---

## 也许值得一看的部分

- **双脑路由**：用快模型处理约 80% 的简单请求（Fast Path），复杂请求再交给强模型（Slow Path），兼顾速度和成本。见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 和 `backend/src/ai_engine/`。
- **短命 Agent + 状态回填**：Agent 不长期驻留，每次从数据库重建上下文；配合 5 层上下文组装和 token 预算管理（`backend/src/ai_engine/context_assembler.py`）。
- **PendingAction 机制**：敏感操作从不由 Agent 直接执行，而是生成待确认动作，用户确认后才执行（`backend/src/modules/conversation/`）。
- **记忆系统**：对话中的记忆提取、压缩、召回，以及 GraphRAG（`backend/src/modules/memory/`）。
- **事件策展与洞察**：冲突检测、关联发现、多引擎洞察生成（`backend/src/modules/curation/`、`backend/src/modules/insight/`）。
- **与 AI 编码助手协作的工程实践**：这个项目大部分代码是我和 AI 编码助手一起写的。仓库里保留了当时的协作约定，包括根目录和各模块的 `CLAUDE.md`、[docs/CONVENTIONS.md](docs/CONVENTIONS.md)、[docs/WORKFLOW.md](docs/WORKFLOW.md)，以及用测试机械地检查架构分层的 `backend/tests/test_architecture.py`。

---

## 当前状态

- **不再积极维护**，Issue 和 PR 可能无法及时回复，敬请谅解。
- 代码停在开发中途，**存在已知 bug 和未完成的功能**，不建议直接用于生产环境。
- 依赖版本锁定在当时的环境（后端基于 Python 3.11），在更新的 Python 版本上，部分依赖可能需要升级才能安装。
- 部分测试需要本地的 PostgreSQL / Redis，以及真实的 LLM API Key。
- `mobile/trash/` 下是已废弃但暂未删除的旧代码。

---

## 技术栈

| 层 | 技术 |
|---|------|
| Backend | Python 3.11 · FastAPI · SQLAlchemy 2.0 · Celery · Pydantic 2 |
| Mobile | Flutter 3.x · Dart · BLoC · GoRouter · GetIt (DI) |
| Database | PostgreSQL (asyncpg) · Redis · Milvus（向量）· Neo4j（可选） |
| LLM | Claude Agent SDK · Anthropic API · OpenAI / DashScope（可选） |
| Auth | JWT · OAuth2 (Google/Microsoft) |
| Search | DuckDuckGo · Tavily · Serper |
| Push | Firebase Cloud Messaging |

## 快速启动

```bash
# 一键初始化：创建虚拟环境、安装依赖、生成 backend/.env、执行数据库迁移
./scripts/bootstrap.sh

# 编辑 backend/.env，填入数据库、Redis 和 LLM API Key，然后分别启动：
cd backend && uvicorn src.main:app --reload          # 后端 API
cd backend && python -m src.ai_engine.worker_main    # Agent Worker（单独进程）
cd mobile && flutter run                             # 移动端

# 或者一次启动全部服务
./scripts/start.sh all
```

**核心环境变量**：`DATABASE_HOST`、`DATABASE_PASSWORD`、`REDIS_HOST`、`JWT_SECRET`、`ANTHROPIC_API_KEY`、`OPENAI_API_KEY`。完整列表见 [backend/.env.example](backend/.env.example) 和 `backend/src/config/settings.py`。

## 目录结构

```
backend/src/
├── ai_engine/                    # AI 引擎 (双脑路由 + Agent SDK)
│   ├── router/                   #   意图路由
│   ├── workers/                  #   Fast/Slow/Hybrid Worker
│   ├── sdk/                      #   Claude Agent SDK 适配层 (client pool, MCP server, hooks)
│   ├── tools/                    #   Tool 注册 + 执行器 (executors/)
│   ├── sub_agents/               #   Sub-agent (researcher, gift advisor, travel planner)
│   ├── skills/                   #   技能注册 (travel planning/search)
│   ├── gateway/                  #   Tool Gateway (鉴权 + 审计)
│   ├── intervention/             #   用户干预 (classifier, debouncer)
│   ├── queue/                    #   Redis Stream 任务队列 + DLQ
│   ├── context_assembler.py      #   5 层上下文组装 (token 预算)
│   └── worker_runner.py          #   异步 Worker 主循环
├── modules/                      # 业务模块
│   ├── briefing/                 #   每日简报、天气、建议
│   ├── conversation/             #   会话管理、PendingAction、反馈
│   ├── curation/                 #   事件策展 (规则引擎、冲突检测、关联发现、编排)
│   ├── date_manager/             #   重要日期、假期、提醒、农历
│   ├── gift/                     #   礼物推荐、预算、趋势
│   ├── insight/                  #   洞察生成 (3 引擎 + 编排器)
│   ├── member/                   #   成员、家庭、设备、信任、职业关系
│   ├── memory/                   #   记忆提取/压缩/召回、GraphRAG、embedding
│   ├── relationship/             #   关系温度计、关怀建议、衰减算法
│   ├── trip/                     #   旅行规划、行程、预算、天气
│   └── views/                    #   看板、时间线、知识图谱、搜索
├── core/                         # 基础设施 (认证、审计、事件总线、调度、WebSocket、限流)
├── config/settings.py            # Pydantic BaseSettings (所有环境变量)
├── api/v1/                       # REST API 路由
├── db/migrations/                # Alembic 迁移
└── external_apis/                # 外部 API 适配器

mobile/lib/
├── app/              # 应用入口、DI、GoRouter、主题
├── features/         # auth, chat, dates, gifts, kanban, members, profile, relationships, settings, trip
├── core/             # 网络 (Dio)、认证、事件总线、推送、存储、WebSocket
└── shared/           # 共享组件
```

## 文档

- 产品需求：[docs/PRD-生活秘书-统一版.md](docs/PRD-生活秘书-统一版.md)
- 架构：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 编码约定：[docs/CONVENTIONS.md](docs/CONVENTIONS.md)
- 架构决策记录（ADR）：[docs/DECISIONS.md](docs/DECISIONS.md)
- 测试：[docs/TESTING.md](docs/TESTING.md)
- API 参考：[docs/api-reference.md](docs/api-reference.md)
- 设计文档：[docs/design-docs/](docs/design-docs/)
- 历史参考：[docs/references/](docs/references/)

## 验证

```bash
cd backend && pytest                                              # 后端测试
cd backend && black --check src/ && flake8 src/ && mypy src/      # Lint + 类型检查
cd mobile && flutter test                                         # 移动端测试
```

## 许可证

本项目基于 [Apache License 2.0](LICENSE) 开源。

## 最后

欢迎 Fork、借鉴、改造。如果它对你有一点点帮助，那就是它最好的归宿。
