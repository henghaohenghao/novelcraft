# NovelCraft（AI 小说工坊）

多智能体协同的小说创作平台。本仓库为 V1.0 实现，包含项目管理、AI 大纲规划、人物工坊、多智能体（计划-写作-审查-修改）章节生成、可选的图谱与向量检索增强。

> 完整设计请见 [技术文档.md](../%E6%8A%80%E6%9C%AF%E6%96%87%E6%A1%A3.md)。本 README 仅描述当前已实现的功能与本地启动方式。

## 一、当前实现状态

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| 项目管理 / 大纲 / 章节 / 人物 CRUD | 已实现 | FastAPI + SQLAlchemy |
| AI 大纲规划 | 已实现 | 调用 OpenAI 兼容接口 |
| 多智能体写作循环（计划-写作-审查-修改） | 已实现 | LangGraph 状态机，SSE 流式推送 |
| 人物关系图谱 | 可选 | 启动 Neo4j 后启用，否则降级为列表 |
| 向量检索增强（设定/段落） | 可选 | 启动 Qdrant + sentence-transformers 后启用 |
| 一致性本地模型 / 风格迁移 / Yjs 协同 / Celery / Temporal / 插画生成 / 导出 | 未实现 | 见技术文档 V2.0+ 规划 |

## 二、目录结构

```
novelcraft/
├─ backend/              # FastAPI 后端
│  ├─ agents/            # LangGraph 多智能体（plan/write/review/revise）
│  ├─ models/            # SQLAlchemy ORM + Pydantic schema
│  ├─ routers/           # REST 路由
│  ├─ services/          # LLM / Neo4j / Qdrant / Embedding 服务
│  ├─ config.py          # 设置（env_prefix=NOVELCRAFT_）
│  └─ main.py            # 入口
├─ frontend/             # Next.js 14 (App Router) + Tailwind
├─ requirements.txt
├─ .env.example
└─ start_windows.ps1     # Windows 一键启动
```

## 三、本地启动（无需 Docker）

### 3.1 前置依赖

- Python 3.11+（推荐 3.12）
- Node.js 18+
- 一个 OpenAI 兼容的 LLM API Key（OpenAI / DeepSeek / 智谱 / 百炼 / Ollama 等）
- 可选：Neo4j 5.x、Qdrant 1.x（不装也能跑）

### 3.2 配置 .env

复制模板并填入 LLM Key：

```powershell
Copy-Item .env.example .env
```

编辑 [.env](.env) 至少改这一项：

```
NOVELCRAFT_LLM_API_KEY=你的key
```

如使用国产模型，把 `LLM_BASE_URL` 和 `LLM_MODEL` 改为对应值，例如：

```
NOVELCRAFT_LLM_BASE_URL=https://api.deepseek.com/v1
NOVELCRAFT_LLM_MODEL=deepseek-chat
NOVELCRAFT_LLM_PLANNER_MODEL=deepseek-chat
NOVELCRAFT_LLM_WRITER_MODEL=deepseek-chat
NOVELCRAFT_LLM_REVIEWER_MODEL=deepseek-chat
```

> 所有变量名都需以 `NOVELCRAFT_` 为前缀，否则不会被读取（[backend/config.py:44](backend/config.py#L44)）。

`NOVELCRAFT_DB_DRIVER` 默认为 `sqlite`，数据文件会写到 `backend/../data/novelcraft.db`，无需启动 Postgres。如要切回 Postgres，把 `NOVELCRAFT_DB_DRIVER` 改为 `postgresql` 并填好其余字段。

### 3.3 一键脚本（推荐）

```powershell
# 第一次：安装 python + node 依赖（首装会下载 PyTorch / 嵌入模型，~1GB）
.\start_windows.ps1 -Install

# 启动（前端 / 后端各开一个窗口，日志直接可见）
.\start_windows.ps1
```

可选参数：

- `-NoCheck`：跳过对 PG/Neo4j/Qdrant/Redis 的端口探测
- `-BackendOnly` / `-FrontendOnly`：只起一边

启动成功后访问：

- 前端：http://localhost:3000
- 后端：http://localhost:8000
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/health （会返回 neo4j / qdrant 是否可用）

### 3.4 手动启动（不用脚本）

后端：

```powershell
pip install -r requirements.txt
$env:PYTHONPATH = (Get-Location).Path
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

## 四、可选增强服务

不装这两项也能完整生成章节，仅图谱 / 向量检索功能会降级。

### 4.1 Neo4j（启用人物关系图谱）

下载 Neo4j Community Edition（5.x），创建数据库并设置密码 `novelcraft123`（与 `.env` 一致），启动后保持监听 `bolt://localhost:7687`。

后端 [main.py](backend/main.py) 启动时会探测连接，连不上则自动降级，[characters.py](backend/routers/characters.py) 中所有写图方法变为 no-op，关系图谱页面显示为空，但人物 CRUD 仍正常。

### 4.2 Qdrant（启用向量检索）

最简单的方式：

```powershell
# 下载 qdrant 单二进制：https://github.com/qdrant/qdrant/releases
.\qdrant.exe
```

默认监听 `:6333`。启用后 [writing.py](backend/routers/writing.py) 会在生成章节时把段落入库，并在写作前把大纲做检索增强。

> 首次访问 Qdrant 路径时会加载 sentence-transformers 模型（默认 `BAAI/bge-small-zh-v1.5`，约 100MB），第一次会下载。设备默认 `cpu`，如有 GPU 可改 `NOVELCRAFT_EMBEDDING_DEVICE=cuda`。

### 4.3 Postgres（可选，替代 SQLite）

```
NOVELCRAFT_DB_DRIVER=postgresql
NOVELCRAFT_DB_HOST=localhost
NOVELCRAFT_DB_PORT=5432
NOVELCRAFT_DB_USER=novelcraft
NOVELCRAFT_DB_PASSWORD=novelcraft123
NOVELCRAFT_DB_NAME=novelcraft
```

需先在 Postgres 中 `CREATE DATABASE novelcraft;`，表结构会在启动时自动创建。

## 五、使用流程

1. 浏览器打开 http://localhost:3000，点击 **开始创作 → 新建项目**，填写标题和梗概。
2. 进入项目详情页：
   - **大纲规划**：点击 **AI 生成大纲** → 每个大纲节点点 **创建章节**
   - **人物工坊**：点击 **AI 生成人物**（基于梗概）
   - **章节写作**：在已创建章节上点 **AI 生成**，触发 LangGraph 循环，SSE 流式回显进度
   - **关系图谱**：查看 Neo4j 中该项目的人物 / 势力 / 地点节点（需启用 Neo4j）
3. 章节生成的循环：`plan → write → review → (revise → review)*N → end`，最多修改 3 轮（`max_revision_rounds`）。

## 六、本次本地化改动相对原仓库的关键修复

- [.env.example](.env.example) / [.env](.env)：所有变量统一加 `NOVELCRAFT_` 前缀，与 [backend/config.py](backend/config.py) 的 `env_prefix` 对齐；默认 `DB_DRIVER=sqlite`，无需 Docker 即可跑通。
- [backend/services/neo4j_service.py](backend/services/neo4j_service.py) / [backend/services/qdrant_service.py](backend/services/qdrant_service.py)：新增 `available` 标志，所有方法在服务不可用时返回空值而非抛错。
- [backend/main.py](backend/main.py)：lifespan 打印每个外部服务的连接状态，`/api/health` 暴露当前可用性。
- [backend/routers/writing.py](backend/routers/writing.py)：Neo4j 不可用时改用 SQLite 中的人物表构造上下文；Qdrant 不可用时跳过段落入库与设定检索（同时不再加载 sentence-transformers）。
- [backend/services/qdrant_service.py](backend/services/qdrant_service.py)：嵌入维度从硬编码 512 改为按实际模型 `dimension` 动态创建集合。
- [requirements.txt](requirements.txt)：修正 `qdrant-client>=1.12.0.0` 这个无效版本号。
- [start_windows.ps1](start_windows.ps1)：改用独立 cmd 窗口启动前后端，日志可直接看到；新增 `-Install` / `-BackendOnly` / `-FrontendOnly` / `-NoCheck` 选项。

## 七、技术文档与本实现的差距（待办）

下面这些在 [技术文档.md](../%E6%8A%80%E6%9C%AF%E6%96%87%E6%A1%A3.md) 里有规划但 V1.0 尚未实现，部署到服务器时如果没用到，可暂忽略：

- 风格迁移本地 LoRA 模型 / vLLM 服务
- 一致性审查本地 Qwen3-8B 微调模型
- Celery 异步任务（依赖已装但未接入路由）
- Temporal 整书工作流编排
- Yjs / Socket.IO 实时协同编辑
- 插画生成（通义万相 / ERNIE-Image）
- EPUB / PDF 导出
- Prometheus / Grafana / ELK / Sentry 监控

## 八、部署到服务器（速记）

部署时建议保留 SQLite + 本进程的最小形态先跑通，再按需挂 Postgres / Neo4j / Qdrant。

```bash
# 服务器上
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..

# 后端（建议用 systemd 或 pm2 守护）
PYTHONPATH=. uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 前端
cd frontend && npm run start  # 监听 :3000
```

前端通过 `NEXT_PUBLIC_API_URL` 指向后端域名，例如 build 前在 `frontend/.env.local` 写：

```
NEXT_PUBLIC_API_URL=https://your-domain.com
```

反向代理（nginx）将 `/` → 3000，`/api` 与 `/docs` → 8000，并启用 HTTPS 即可。
