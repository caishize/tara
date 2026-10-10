# Secretary - Member Management Backend

家庭秘书系统 - 成员管理模块后端服务

## 功能特性

- ✅ **对话式成员添加** - 通过自然语言对话添加家庭成员
- ✅ **字段级加密** - AES-256-GCM加密敏感信息
- ✅ **权限控制** - 基于角色的访问控制(RBAC)
- ✅ **关系图谱** - 家庭成员关系管理
- 🚧 **语义搜索** - 基于向量数据库的自然语言查询
- 🚧 **OCR识别** - 身份证自动识别
- 🚧 **持续完善** - 对话中自动提取并更新成员画像

## 技术栈

- **Framework**: FastAPI 0.109+
- **Database**: PostgreSQL 15+ (主存储)
- **Cache**: Redis 7.0+
- **Vector DB**: Milvus 2.3+ (语义搜索)
- **LLM**: OpenAI GPT-4 / Anthropic Claude
- **Testing**: pytest + pytest-asyncio

## 快速开始

### 1. 安装依赖

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件,填写必要的配置
```

### 3. 初始化数据库

```bash
# 创建数据库
createdb secretary

# 运行迁移
alembic upgrade head
```

### 4. 启动服务

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

访问:
- API文档: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## 项目结构

```
backend/
├── src/
│   ├── core/                    # 核心基础设施
│   │   ├── interfaces/          # 接口定义
│   │   ├── security/            # 加密、权限
│   │   └── context/             # 对话引擎(TODO)
│   ├── modules/
│   │   └── member_management/   # 成员管理模块
│   │       ├── models/          # 数据模型
│   │       ├── repositories/    # 数据访问层
│   │       ├── services/        # 业务逻辑
│   │       └── actions/         # 对话动作(TODO)
│   ├── api/v1/                  # REST API
│   ├── adapters/                # 外部服务适配器
│   ├── db/migrations/           # 数据库迁移
│   └── main.py                  # 应用入口
├── tests/
│   ├── unit/                    # 单元测试
│   ├── integration/             # 集成测试
│   └── contract/                # 契约测试
└── requirements.txt

```

## API端点

### Members

- `POST /api/v1/members` - 创建成员
- `GET /api/v1/members` - 列出成员
- `GET /api/v1/members/{id}` - 获取成员详情
- `PUT /api/v1/members/{id}` - 更新成员
- `DELETE /api/v1/members/{id}` - 删除成员(软删除)

### Health

- `GET /health` - 总体健康检查
- `GET /health/db` - 数据库健康检查
- `GET /health/redis` - Redis健康检查

## 运行测试

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/

# 生成覆盖率报告
pytest --cov=src --cov-report=html
```

## 部署

详见 `DEPLOYMENT.md` (TODO)

## 开发状态

### ✅ 已完成

- Phase 0: 项目设置与基础设施
- Phase 1: 核心数据模型与数据库
- Phase 2: 核心服务(加密、权限、LLM适配器)
- API基础框架

### 🚧 进行中

- Phase 3: MVP功能(对话式添加、自然语言查询)
- Phase 4: OCR识别
- Phase 5: 持续完善
- Phase 6: 关系图谱可视化

## License

Private Project
