# 异步阻塞问题排查与修复

## 问题描述

当 Agent 请求 LLM 生成内容时（耗时较长），其他用户的登录、页面访问等请求无法响应，表现为整个服务"卡住"。

## 根本原因

FastAPI 基于 `asyncio` 事件循环运行。在 `async` 函数中直接调用**同步阻塞操作**，会阻塞整个事件循环，导致所有其他请求排队等待，无法并发处理。

核心公式：

```
事件循环被阻塞 = 所有协程暂停 = 服务无响应
```

### 阻塞源清单

| 阻塞源 | 类型 | 典型耗时 | 影响范围 |
|--------|------|----------|----------|
| `bcrypt.checkpw` / `hashpw` / `gensalt` | CPU 密集 | 100-300ms（rounds=12） | 登录、注册、改密码 |
| `neo4j_service.*`（13 处） | 网络 I/O | 10-100ms/次 | 人物 CRUD、关系管理、图谱查询 |
| `qdrant_service.*`（多处） | 网络 I/O | 10-50ms/次 | 向量搜索、段落存储 |
| `embedding_service.encode_single` | CPU 密集 | 20-100ms/次 | 向量编码 |

### 为什么 LLM 请求不是阻塞源？

LLM 请求使用 `AsyncOpenAI`（真正的异步 HTTP 客户端），`await` 时会释放事件循环给其他协程。但 Agent 内部的工具调用（neo4j、qdrant、bcrypt）是同步的，这些才是真正的阻塞点。

### 连锁效应

```
用户A: 点击生成 → Agent 调用 LLM（异步，不阻塞）
                   → Agent 调用 neo4j_service.get_character_relations()（同步，阻塞事件循环 50ms）
                   → Agent 调用 qdrant_service.search_settings_by_keyword()（同步，阻塞 30ms）
                   → Agent 调用 LLM（异步）
                   → Agent 调用 bcrypt 相关（如果触发）...
                   
用户B: 此时尝试登录 → 请求排队等待事件循环 → 无法响应
```

每次同步调用虽然只阻塞几十毫秒，但 Agent 的 ReAct 循环会多次调用工具，累积阻塞可达数秒，足以让用户感知到明显的延迟甚至超时。

## 修复方案

将所有同步阻塞调用包装到 `asyncio.to_thread()` 中，将其转移到线程池执行，不阻塞事件循环：

```python
# 修复前（阻塞事件循环）
relations = neo4j_service.get_character_relations(character_name)
results = qdrant_service.search_settings(project_id, query_embedding, limit=5)
return bcrypt.checkpw(password_bytes, hashed_bytes)

# 修复后（在线程池中执行，不阻塞事件循环）
relations = await asyncio.to_thread(neo4j_service.get_character_relations, character_name)
results = await asyncio.to_thread(qdrant_service.search_settings, project_id, query_embedding, 5)
return await asyncio.to_thread(bcrypt.checkpw, password_bytes, hashed_bytes)
```

### `asyncio.to_thread` 原理

```
主线程（事件循环）              线程池
┌─────────────────┐           ┌──────────────────┐
│ async def foo() │           │                  │
│   result =      │──提交──→  │ bcrypt.checkpw() │
│   await to_thread│          │ neo4j.query()    │
│   ...           │←──结果──  │ qdrant.search()  │
│   继续处理      │           │                  │
└─────────────────┘           └──────────────────┘
     ↑ 其他协程可以继续执行
```

## 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `utils/auth.py` | `verify_password` / `get_password_hash` 改为 async + `asyncio.to_thread` |
| `routers/auth.py` | 调用处加 `await` |
| `routers/characters.py` | 13 处 `neo4j_service.*` → `asyncio.to_thread` |
| `routers/projects.py` | neo4j 删除、qdrant 删除 → `asyncio.to_thread` |
| `routers/outlines.py` | embedding 编码、qdrant 存储 → `asyncio.to_thread` |
| `routers/writing.py` | neo4j 查询/创建、qdrant 搜索/存储、embedding 编码 → `asyncio.to_thread` |
| `agents/agent_tools.py` | neo4j 查询、qdrant 搜索 → `asyncio.to_thread` |

## 预防规则

在 FastAPI async 路由或任何 async 函数中：

1. **绝不直接调用同步 I/O**（文件、数据库驱动、HTTP 客户端的同步 API）
2. **绝不直接调用 CPU 密集操作**（加密、压缩、大量计算）
3. **用 `asyncio.to_thread()` 包装**同步调用，或使用原生异步库替代

```python
# 检查清单：以下模式都是危险的
bcrypt.checkpw(...)          # CPU 密集 → asyncio.to_thread
requests.get(...)            # 同步 HTTP → 用 httpx.AsyncClient
neo4j_driver.session()       # 同步驱动 → 用 neo4j AsyncSession / asyncio.to_thread
qdrant_client.search(...)    # 同步客户端 → asyncio.to_thread
sentence_transformers.encode()  # CPU 密集 → asyncio.to_thread
subprocess.run(...)          # 进程调用 → asyncio.create_subprocess_exec
```
