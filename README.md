# NovelCraft - AI 小说工坊

> 面向长篇网文创作多智能体协同平台：LangGraph 多智能体写作流水线 + 风格迁移 + 实时协同编辑 + 分层记忆与知识图谱

## 核心功能

### 1. 多智能体写作流水线（LangGraph + Human-in-the-Loop）
- 基于 LangGraph 的 Supervisor 架构：总调度（LLM 驱动）动态决定下一步调用哪个 Agent
- 四个 ReAct Agent：规划 / 写作 / 审查 / 修改，各 Agent 拥有工具可自主决策
- 审查结果结构化（评分 + 问题清单 + 分类），支持精准路由（如人物问题→定向修改）
- Human-in-the-Loop：审查未通过时通过 `interrupt` 暂停图执行，等待人工决策后用 `Command(resume=...)` 恢复
- SSE 流式输出：逐节点推送 Agent 步骤、工具调用记录、章节内容 chunk
- Checkpointer（MemorySaver）持久化图状态，支持暂停 / 恢复

### 2. 风格迁移
- 调用 vLLM 部署的 Qwen3-8B-Instruct 模型进行风格转换（古龙、金庸、曹文轩等）
- 基于系统提示词的风格引导，自动剥离 Qwen3 思考模式 `<think>` 标签
- 任务记录持久化到数据库，可查询任务状态与推理耗时
- 提供 LoRA 训练脚本（基于 LLaMA Factory）与 vLLM 部署脚本

### 3. 多人实时协同编辑
- 基于 Yjs CRDT 算法的无冲突协同编辑（前端 TipTap Collaboration 扩展）
- WebSocket 实时同步，Redis Pub/Sub 支持多实例广播（无 Redis 时自动降级为内存存储）
- 房间管理（创建 / 列表 / 删除）、在线用户列表、加入 / 离开通知
- 实时光标位置共享与 Yjs 文档快照保存

### 4. 分层记忆系统
- 三级记忆：L1 章节摘要（结构化抽取情节 / 人物变化 / 伏笔）→ L2 卷摘要 → L3 全书纲要
- 章节完成后自动写入 L1，按需触发 L2 / L3 压缩合并
- 重要性评分 + 访问统计驱动召回权重，Qdrant 向量召回相关历史段落
- 写作上下文自动组装：近章 L1 全文 + 中程 L2 卷摘要 + 远程 L3 纲要 + 语义召回 + 伏笔清单

### 5. 知识图谱与向量检索
- Neo4j 存储人物节点与关系，章节生成后通过 LLM 自动抽取人物 / 关系并写入图谱
- Qdrant 向量化章节段落与世界观设定，支持语义检索
- Embedding 模型：BAAI/bge-small-zh-v1.5

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        接入层                                │
│  API Gateway (FastAPI) + WebSocket 协同端点                  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      业务服务层                              │
│  认证 │ 项目/大纲 │ 写作流水线 │ 人物 │ 风格迁移 │ 协同编辑  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      AI 编排层                               │
│  LangGraph 多智能体 (Supervisor + ReAct) │ 云端 LLM (OpenAI) │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    数据与记忆层                              │
│  PostgreSQL │ Neo4j │ Qdrant │ Redis                        │
└─────────────────────────────────────────────────────────────┘
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI、SQLAlchemy 2.0 (async)、Pydantic、JWT |
| AI 编排 | LangGraph、LangChain、OpenAI 兼容 LLM |
| 风格迁移 | vLLM、Qwen3-8B-Instruct、LLaMA Factory (LoRA) |
| 协同编辑 | Yjs、TipTap、WebSocket、Redis Pub/Sub |
| 数据库 | PostgreSQL（支持 SQLite 降级）、Neo4j、Qdrant、Redis |
| 前端 | Next.js 14、React 18、TypeScript、TailwindCSS、ReactFlow、ECharts |
| 状态管理 | Zustand、TanStack React Query |

## 快速开始

### 前置要求

- Docker & Docker Compose
- Python 3.12+
- Node.js 18+

### 方式一：Docker 一键启动（生产编排）

`novelcraft/docker-compose.yml` 编排了 postgres、redis、neo4j、qdrant、backend、frontend 六个服务。

```bash
# 1. 准备环境变量（docker-compose 读取 novelcraft/.env）
cp novelcraft/backend/.env.example novelcraft/.env
# 编辑 .env，至少填入 NOVELCRAFT_LLM_API_KEY

# 2. 构建并启动全部服务
cd novelcraft
docker compose up -d --build

# 3. 运行数据库迁移
docker compose exec backend python migrations/migrate_v2.py
docker compose exec backend python migrations/init_styles.py
```

启动后：
- 前端：http://localhost:3000
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

### 方式二：本地开发

```bash
# 1. 启动基础设施（仅数据层）
cd novelcraft
docker compose up -d postgres redis neo4j qdrant

# 2. 配置后端环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入 LLM API Key、数据库连接等

# 3. 运行数据库迁移
cd backend
python migrations/migrate_v2.py
python migrations/init_styles.py

# 4. 启动后端（支持热重载）
uvicorn backend.main:app --reload

# 5. 启动前端
cd ../frontend
npm install
npm run dev
```

### 验证安装

```bash
# 健康检查（返回各服务的可用状态）
curl http://localhost:8000/api/health
```

> 说明：Neo4j、Qdrant、Redis 启动失败时后端会自动降级，不阻塞整体启动。SQLite 可作为 PostgreSQL 的零依赖替代（设置 `NOVELCRAFT_DB_DRIVER=sqlite`）。

## API 文档

启动服务后访问 Swagger UI：http://localhost:8000/docs

### 认证（JWT）

```bash
# 注册
POST /api/auth/register
{ "username": "alice", "email": "a@b.com", "password": "******" }

# 登录，返回 access_token
POST /api/auth/login
{ "username": "alice", "password": "******" }

# 获取当前用户
GET /api/auth/me          # Authorization: Bearer <token>
```

### 写作流水线（SSE 流式 + HITL）

```bash
# 创建章节（幂等：同一 outline_id 已存在则返回旧章节）
POST /api/writing/chapters
{ "project_id": "...", "outline_id": "...", "title": "第一章", "chapter_number": 1 }

# 启动多智能体生成（SSE 流式响应，含 Agent 步骤 / 工具调用 / 内容 chunk）
POST /api/writing/chapters/generate
{ "chapter_id": "...", "style": "古龙" }

# 人工审核后恢复生成（Human-in-the-Loop）
POST /api/writing/chapters/{chapter_id}/resume
{ "chapter_id": "...", "action": "accept", "feedback": "", "edited_content": "" }

# 同步生成（无流式，HITL 暂停时保存当前草稿）
POST /api/writing/chapters/generate-sync
```

SSE 事件类型：`status`、`agent_step`、`content`、`human_review_required`、`result` 等。

### 风格迁移

```bash
# 执行风格迁移（直接调用 Qwen3-8B，无缓存）
POST /api/style-transfer/transfer
{ "original_text": "夜色如墨，月光洒在青石板路上。", "style_id": "gulong", "project_id": "proj-123" }

# 查询任务状态
GET /api/style-transfer/task/{task_id}

# 列出可用风格
GET /api/style-transfer/styles
```

### 实时协同

```bash
# 创建房间
POST /api/collaboration/rooms
{ "chapter_id": "ch-001", "room_name": "第一章" }

# 列出 / 删除房间
GET  /api/collaboration/rooms
DELETE /api/collaboration/rooms/{room_id}

# 房间在线用户 / 文档快照
GET /api/collaboration/rooms/{room_id}/users
GET /api/collaboration/rooms/{room_id}/snapshot

# WebSocket 连接
ws://localhost:8000/api/collaboration/ws/{room_id}?user_id=user1&user_name=张三&connection_id=conn1
```

WebSocket 消息类型：`yjs_update`、`cursor_update`、`save_snapshot`、`ping`；服务端推送 `welcome`、`user_list`、`user_joined`、`user_left` 等。

### 项目 / 大纲 / 人物

```bash
# 项目 CRUD
POST   /api/projects
GET    /api/projects
GET    /api/projects/{id}
PUT    /api/projects/{id}
DELETE /api/projects/{id}

# 大纲（树形结构）
POST /api/outlines
GET  /api/outlines/project/{project_id}

# 人物
POST /api/characters
GET  /api/characters/project/{project_id}
```

## 项目结构

```
novelcraft/
├── backend/
│   ├── agents/                # LangGraph 多智能体
│   │   ├── graph.py           # Supervisor 架构写作图 + Checkpointer
│   │   ├── supervisor.py      # 总调度（LLM 动态路由）
│   │   ├── planner.py         # 规划 Agent (ReAct)
│   │   ├── writer.py          # 写作 Agent (ReAct)
│   │   ├── reviewer.py        # 审查 Agent (结构化评分)
│   │   ├── revisor.py         # 修改 Agent (ReAct)
│   │   ├── human_review.py    # 人工审核节点 (interrupt)
│   │   ├── agent_tools.py     # Agent 可用工具
│   │   └── state.py           # 共享状态 / StructuredReview
│   ├── routers/               # API 路由
│   │   ├── auth.py            # JWT 认证
│   │   ├── projects.py        # 项目管理
│   │   ├── outlines.py        # 大纲管理
│   │   ├── writing.py         # 写作流水线 (SSE + HITL)
│   │   ├── characters.py      # 人物管理
│   │   ├── style_transfer.py  # 风格迁移
│   │   └── collaboration.py   # WebSocket 协同编辑
│   ├── services/              # 业务服务
│   │   ├── llm_service.py     # LLM 调用 (OpenAI 兼容)
│   │   ├── style_transfer_service.py   # 风格迁移 (vLLM 直调)
│   │   ├── collaboration_service.py    # Yjs + Redis 协同
│   │   ├── memory_service.py  # 分层记忆 (L1/L2/L3)
│   │   ├── neo4j_service.py   # 知识图谱
│   │   ├── qdrant_service.py  # 向量检索
│   │   └── embedding_service.py # bge-small-zh-v1.5
│   ├── models/                # 数据模型
│   │   ├── db_models.py       # ORM (Project/Chapter/Character/ChapterSummary...)
│   │   ├── schemas.py         # Pydantic 校验模型
│   │   ├── collaboration_models.py
│   │   ├── style_models.py
│   │   └── database.py        # 连接 / 会话管理
│   ├── migrations/            # 数据库迁移
│   │   ├── migrate_v2.py
│   │   ├── migrate_add_users.py
│   │   └── init_styles.py     # 初始化风格数据
│   ├── utils/auth.py          # JWT / 密码哈希
│   ├── config.py              # 配置管理
│   └── main.py                # 应用入口
├── frontend/                  # Next.js 14 前端
│   ├── app/
│   │   ├── login/  register/  # 认证页
│   │   ├── projects/          # 项目列表与详情 (大纲/人物/写作/图谱 Tab)
│   │   ├── style-transfer/    # 风格迁移页
│   │   └── collaboration/     # 协同编辑页
│   └── components/
│       ├── CollaborationEditor.tsx       # Yjs 协同编辑器
│       ├── AgentTimeline.tsx             # Agent 执行时间线
│       └── Navigation.tsx / ProtectedRoute.tsx
├── scripts/                   # 风格模型训练与部署
│   ├── train_style_model.py   # 生成 LoRA 训练配置与示例数据
│   ├── train_all_styles.sh    # 一键训练所有风格
│   ├── deploy_vllm.sh         # 部署 vLLM 服务 (加载 LoRA 适配器)
│   └── test_style_transfer.py # 风格迁移测试
├── Dockerfile.backend
├── Dockerfile.frontend
└── docker-compose.yml         # postgres/redis/neo4j/qdrant/backend/frontend
```

## 风格模型训练与部署

风格迁移支持两种方式：直接用基座 Qwen3-8B + 风格提示词（开箱即用），或训练 LoRA 适配器获得更强风格效果。

### 训练 LoRA 适配器（基于 LLaMA Factory）

```bash
# 训练单个风格（自动生成示例数据 + 训练配置）
python scripts/train_style_model.py \
    --style-name 古龙 --style-id gulong \
    --generate-sample --num-samples 500

# 一键训练所有预置风格（古龙/曹文轩/金庸/刘慈欣/王小波/鲁迅）
bash scripts/train_all_styles.sh
```

训练配置保存在 `outputs/{style_id}-style-lora/train_config.yaml`，使用 `llamafactory-cli train` 执行训练，LoRA 适配器输出到 `outputs/{style_id}-style-lora/final`。

### 部署 vLLM 服务

```bash
# 启动 vLLM，加载所有已训练的 LoRA 适配器
bash scripts/deploy_vllm.sh
```

该脚本以 OpenAI 兼容 API 形式启动 vLLM（默认 `0.0.0.0:8000`），加载 Qwen3-8B-Instruct 基座与所有 `outputs/*-style-lora/final` 下的 LoRA 适配器。随后将 `NOVELCRAFT_VLLM_BASE_URL` 指向该地址即可。

### 测试风格迁移

```bash
python scripts/test_style_transfer.py
```

包含直接调用 vLLM、后端 API、性能测试三组用例。

## 开发指南

### 运行测试

```bash
# 后端功能测试
python backend/test_v2_features.py

# 完整性检查
python backend/check_v2_integrity.py

# 快速验证
python backend/quick_verify.py
```

### 监控指标

```bash
# 系统健康（返回各服务可用性）
GET /api/health
```

### 日志查看

```bash
# Docker 部署
docker compose logs -f backend
docker compose logs -f frontend

# 本地开发直接查看终端输出
```

## 使用示例

### 示例 1：启动多智能体章节生成（Python）

```python
import httpx

async def generate_chapter():
    async with httpx.AsyncClient(timeout=300) as client:
        # SSE 流式接收
        async with client.stream(
            "POST",
            "http://localhost:8000/api/writing/chapters/generate",
            json={"chapter_id": "ch-001", "style": "古龙"},
        ) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    print(line[6:])  # 解析 SSE 事件
```

### 示例 2：协同编辑（前端）

```javascript
// 连接 WebSocket
const ws = new WebSocket(
  'ws://localhost:8000/api/collaboration/ws/room-123?user_id=user1&user_name=张三&connection_id=conn1'
);

// 发送 Yjs 更新
ws.send(JSON.stringify({
  type: 'yjs_update',
  update: yDocUpdate.toString('hex')
}));

// 接收更新
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'yjs_update') {
    // 应用更新到本地 Yjs 文档
  }
};
```

### 示例 3：风格迁移

```python
import httpx

async def transfer_style():
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            "http://localhost:8000/api/style-transfer/transfer",
            json={
                "original_text": "他走进了房间，看到桌上放着一封信。",
                "style_id": "gulong",
                "project_id": "my-novel",
            }
        )
        result = resp.json()
        print(f"转换后: {result['transformed_text']}")
        print(f"耗时: {result['inference_time_ms']}ms")
```

## 安全配置

生产环境部署前请修改以下默认配置：

```bash
# 数据库与图数据库密码
NOVELCRAFT_DB_PASSWORD=strong-password
NOVELCRAFT_NEO4J_PASSWORD=strong-password

# JWT 密钥
NOVELCRAFT_SECRET_KEY=random-secret-key

# 关闭调试模式
NOVELCRAFT_DEBUG=false

# LLM API Key
NOVELCRAFT_LLM_API_KEY=your-api-key
```

> 注意：`backend/main.py` 默认 CORS `allow_origins=["*"]`，生产环境建议改为具体域名。

## 故障排查

**1. 风格迁移失败**
```bash
# 检查 vLLM 服务是否可达
curl ${NOVELCRAFT_VLLM_BASE_URL}/v1/models

# 查看后端日志
docker compose logs backend
```

**2. 协同编辑断连**
```bash
# 检查 Redis 连接
docker compose exec redis redis-cli ping

# 查看 WebSocket 日志
docker compose logs backend | grep WebSocket
```

**3. 知识图谱 / 向量检索不生效**
- Neo4j 或 Qdrant 未启动时后端会自动降级，不影响主流程；启动对应服务后重启后端即可恢复。

## 许可证

MIT License
