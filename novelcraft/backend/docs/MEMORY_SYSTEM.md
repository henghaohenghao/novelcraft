# 分层记忆系统（Hierarchical Memory System）

实现"**分层摘要 + 时序合并 + 重要性衰减**"三级记忆压缩，解决长篇小说创作中前文记忆丢失、token 线性增长、伏笔遗忘等问题。

---

## 一、设计目标

| 问题 | 现状 | 目标 |
|------|------|------|
| 前文记忆截断 | 仅取前 3 章摘要拼接，第 4 章前完全失忆 | 分层组装，第 50 章仍可看到第 1 章伏笔 |
| Token 线性增长 | 章节越多，`previous_summary` 越长 | token 稳定在 ~2000 字以内 |
| 无差别保留 | 日常描写与关键转折同等对待 | 重要性评分 + 衰减归档 |
| 伏笔遗忘 | 无结构化追踪，靠 LLM"凭感觉" | 强制注入未回收伏笔清单 |
| 时序召回限制 | 只能看前 N 章 | Qdrant 语义召回突破时序 |

---

## 二、三级记忆架构

```
            ┌─────────────────────┐
   Level 3  │   全书纲要 (Arc)     │  每 15 章提炼，≤500 字
            │  主线进展+核心矛盾   │  Postgres: ChapterSummary.level3_arc
            └──────────┬──────────┘
                       │
            ┌──────────┴──────────┐
   Level 2  │   卷摘要 (Volume)   │  每 5 章合并，~300 字
            │  本卷主线+未回收伏笔 │  Postgres: VolumeSummary + ChapterSummary.level2_volume
            └──────────┬──────────┘
                       │
            ┌──────────┴──────────┐
   Level 1  │  章节摘要 (Chapter) │  每章生成，~200 字
            │  情节+人物变化+伏笔  │  Postgres: ChapterSummary + Qdrant 向量
            └─────────────────────┘
```

### 各层职责

| 层级 | 触发时机 | 存储 | 检索方式 |
|------|---------|------|---------|
| L1 章节摘要 | 每章完成后 | Postgres `ChapterSummary` + Qdrant 向量 | 时序（前 2 章）+ 语义召回 |
| L2 卷摘要 | 每 5 章自动合并 | Postgres `VolumeSummary` | 时序（前 3~10 章） |
| L3 全书纲要 | 每 15 章自动提炼 | Postgres `ChapterSummary.level3_arc` | 时序（10 章以前） |

---

## 三、数据模型

### 3.1 ChapterSummary（L1 章节摘要）

[db_models.py](../models/db_models.py#L169)

```python
class ChapterSummary(Base):
    __tablename__ = "chapter_summaries"

    id: Mapped[str]                     # 主键
    project_id: Mapped[str]             # 项目 ID（索引）
    chapter_id: Mapped[str]             # 章节 ID（外键）
    chapter_number: Mapped[int]         # 章节序号（索引）

    # 三级内容
    level1_detail: Mapped[str]          # L1 完整摘要
    level2_volume: Mapped[str | None]   # L2 卷摘要回填（跨章检索复用）
    level3_arc: Mapped[str | None]      # L3 全书纲要回填

    # 结构化抽取
    key_events: Mapped[list]            # [{"event": "...", "importance": 0.8}]
    character_changes: Mapped[list]     # [{"name": "...", "change": "..."}]
    foreshadows: Mapped[list]           # [{"id": "fs_3_1", "desc": "...", "resolved": false}]

    # 重要性评分 + 访问统计
    importance_score: Mapped[float]     # 0-1，驱动衰减与召回权重
    last_accessed_at: Mapped[datetime]  # 最近访问时间
    access_count: Mapped[int]           # 累计访问次数

    embedding_id: Mapped[str | None]    # Qdrant point_id
```

### 3.2 VolumeSummary（L2 卷摘要）

[db_models.py](../models/db_models.py#L206)

```python
class VolumeSummary(Base):
    __tablename__ = "volume_summaries"

    id: Mapped[str]
    project_id: Mapped[str]
    volume_number: Mapped[int]          # 卷序号
    start_chapter: Mapped[int]          # 起始章
    end_chapter: Mapped[int]            # 结束章
    summary: Mapped[str]                # 卷摘要正文
    unresolved_foreshadows: Mapped[list] # 跨章未回收伏笔汇总
    created_at / updated_at: Mapped[datetime]
```

---

## 四、核心流程

### 4.1 写入流程：`persist_chapter_memory`

[memory_service.py](../services/memory_service.py#L50)

```
章节生成完成
    │
    ▼
1. LLM 生成结构化摘要
   generate_structured_summary()
   → {summary, key_events, character_changes, foreshadows, resolved_foreshadow_ids}
    │
    ▼
2. 规则评分 importance_score
   score_importance()
   → 转折点 0.35 + 伏笔 0.25 + 人物变化 0.15 + 事件均值 0.15 + 基础 0.2
    │
    ▼
3. 持久化到 ChapterSummary 表（覆盖式）
    │
    ▼
4. 向量化 level1_detail 入 Qdrant
   upsert_summary()
   → 突破时序召回
    │
    ▼
5. 回写本章回收的历史伏笔 resolved=True
   _mark_foreshadows_resolved()
   → 用 flag_modified 确保 JSON 字段变更生效
    │
    ▼
6. 触发压缩（提交后执行，避免事务嵌套）
   ├─ chapter_number % 5 == 0  → _compress_to_volume()
   └─ chapter_number % 15 == 0 → _compress_to_arc()
```

**容错策略**：
- LLM JSON 解析失败 → 回退到 `generate_summary` 纯文本摘要
- 向量化失败 → 仅记录 warning，不阻塞主流程
- 压缩失败 → 仅记录 warning，主流程继续
- 全流程异常 → 回退到旧 `Chapter.summary` 单字段写入

### 4.2 读取流程：`build_compressed_context`

[memory_service.py](../services/memory_service.py#L243)

按距离当前章节远近，分层组装前文记忆：

| 步骤 | 范围 | 来源 | 内容 |
|------|------|------|------|
| 1. 近章 | 前 2 章 | L1 全文 | `level1_detail` + `character_changes` |
| 2. 中程 | 前 3~10 章 | L2 卷摘要 | `VolumeSummary.summary` + `unresolved_foreshadows` |
| 3. 远程 | 10 章以前 | L3 全书纲要 | `level3_arc`（截断 800 字保底） |
| 4. 语义召回 | 全书 | Qdrant | 与当前大纲相关的历史片段（score>0.5，避免与近章重复） |
| 5. 伏笔清单 | 全书 | L1 foreshadows | 未回收伏笔强制注入（最多 10 条，防遗忘） |
| 6. 访问统计 | - | - | 更新被读取章节的 `access_count` + `last_accessed_at` |

**集成位置**：[writing.py](../routers/writing.py#L114) 的 `_build_context` 函数，替代原"前 3 章摘要拼接"逻辑，失败回退到旧逻辑。

### 4.3 压缩流程

#### L1 → L2 卷合并（每 5 章）

[memory_service.py](../services/memory_service.py#L196) `_compress_to_volume`

```
输入：第 N-4 ~ N 章的 level1_detail + key_events + foreshadows
    │
    ▼
LLM 合并（compress_to_volume）
要求：
  - summary：主线进展 3-5 句 + 人物状态净变化
  - unresolved_foreshadows：跨章未回收伏笔清单
  - 丢弃：日常描写、重复铺垫、已回收伏笔细节
    │
    ▼
输出：
  - 写入 VolumeSummary 表
  - 回填到对应章节的 level2_volume 字段（跨章检索复用）
```

#### L2 → L3 全书纲要（每 15 章）

[memory_service.py](../services/memory_service.py#L223) `_compress_to_arc`

```
输入：所有 VolumeSummary
    │
    ▼
LLM 提炼（compress_to_arc）
要求：
  - 主线推进阶段（起/承/转/合）
  - 核心矛盾当前状态
  - 主要人物成长弧线位置
  - 全局未回收关键伏笔
  - ≤500 字
    │
    ▼
输出：回填到所有 ChapterSummary.level3_arc 字段
```

### 4.4 衰减流程：`decay_low_importance_memories`

[memory_service.py](../services/memory_service.py#L386)

低重要性 + 长期未访问的章节摘要降级归档：

```python
归档条件（同时满足）：
  - importance_score < 0.3
  - last_accessed_at < 30 天前
  - access_count < 2

归档动作：
  - level1_detail = "[已归档·低重要性] 关键事件：{前3条}"
  - 保留 key_events / foreshadows / importance_score 不变
```

建议通过 APScheduler 每日凌晨触发。

---

## 五、LLM 服务方法

[llm_service.py](../services/llm_service.py#L326)

| 方法 | 作用 | 模型 | 备注 |
|------|------|------|------|
| `generate_structured_summary` | L1 结构化摘要 | `llm_model` | 输出 JSON，含伏笔 ID 命名规范 |
| `compress_to_volume` | L2 卷合并 | `llm_model` | 输出 JSON |
| `compress_to_arc` | L3 全书纲要 | `llm_planner_model` | 输出纯文本 |
| `score_importance` | 重要性评分 | 无 LLM | 规则评分，节省成本 |
| `_extract_json` | JSON 容错解析 | - | 三级兜底：代码块→纯文本→花括号截取 |

### 伏笔 ID 规范

```
fs_{chapter_number}_{seq}

示例：
  fs_3_1   → 第 3 章第 1 个伏笔
  fs_3_2   → 第 3 章第 2 个伏笔
```

章节生成时，LLM 在 `resolved_foreshadow_ids` 字段中填写本章回收的历史伏笔 ID，`_mark_foreshadows_resolved` 据此回写 `resolved=True`。

---

## 六、向量检索

[qdrant_service.py](../services/qdrant_service.py#L174)

### 6.1 Collection: `chapter_summaries`

存储 Level 1 章节摘要向量，payload：

```python
{
    "project_id": str,
    "chapter_id": str,
    "chapter_number": int,
    "text": str,                # Level 1 摘要正文
    "importance_score": float,  # 供召回加权
}
```

### 6.2 方法

| 方法 | 作用 |
|------|------|
| `upsert_summary` | 插入/更新章节摘要向量 |
| `search_summaries` | 语义召回历史章节摘要（按 project_id 过滤） |

**为什么只有 L1 入 Qdrant**：L2/L3 是按时序分层组装的，不需要语义检索；只有 L1 需要 Qdrant 做相关性召回，突破时序限制。

---

## 七、集成点

### 7.1 章节生成入口

[writing.py](../routers/writing.py) 的两个生成路径：

| 路径 | 改造点 |
|------|--------|
| `generate`（SSE 流式） | 章节完成后调用 `_persist_chapter_memory` |
| `generate-sync`（同步） | 章节完成后调用 `_persist_chapter_memory` |

### 7.2 上下文构建

[writing.py](../routers/writing.py#L114) `_build_context`：
- 用 `build_compressed_context` 替代"前 3 章摘要拼接"
- 失败回退到原逻辑（保证向后兼容）

### 7.3 向后兼容

`Chapter.summary` 字段仍然保留，`_persist_chapter_memory` 写入分层记忆后同步回写 `Chapter.summary`，前端章节列表展示无感知。

---

## 八、配置参数

[memory_service.py](../services/memory_service.py#L22)

```python
# 压缩触发阈值
VOLUME_SIZE = 5          # 每 5 章合并为 1 卷
ARC_SIZE = 15            # 每 15 章提炼 1 次全书纲要

# 衰减阈值
DECAY_DAYS = 30          # 30 天未访问
DECAY_IMPORTANCE = 0.3   # 重要性低于 0.3
DECAY_ACCESS_COUNT = 2   # 访问次数少于 2 次
```

---

## 九、预期收益

| 指标 | 改进前 | 改进后 |
|------|--------|--------|
| 第 50 章前文 token | ~5000 字（前 3 章摘要） | ~2000 字（分层+召回） |
| 第 1 章伏笔在第 50 章可见性 | 不可见 | 强制注入伏笔清单 |
| 上下文信噪比 | 低（全量拼接） | 高（按重要性+相关性筛选） |
| 存储增长 | 线性 O(N) | 近似 O(log N)（卷摘要合并） |
| 跨章节一致性 | 靠 LLM 记忆 | 结构化伏笔追踪 |
| 进程崩溃恢复 | MemorySaver 内存丢失 | Postgres 持久化（待接入 PostgresSaver） |

---

## 十、技术选型取舍

- **零新依赖**：全部基于现有 Postgres + Qdrant + LangGraph，不引入 Mem0/Zep/Letta
- **失败不阻塞**：所有压缩/向量化/记忆组装都有 try-except 兜底，主流程（章节生成）不受影响
- **评分免 LLM**：`score_importance` 用规则评分而非额外 LLM 调用，节省成本
- **JSON 容错**：`_extract_json` 三级兜底，LLM 输出不规范时回退到拼接摘要
- **向后兼容**：`Chapter.summary` 保留并回写，前端无感知

技术含金量体现在**分层压缩算法 + 重要性衰减 + 伏笔追踪**三个机制上，而非堆砌框架。

---

## 十一、后续优化方向

### 11.1 大纲驱动卷划分（替代固定 5 章/卷）

当前 `VOLUME_SIZE=5` 是硬编码。未来可让 LLM 在生成大纲时标注 `node_type="volume"` 父节点，`VolumeSummary` 按卷节点合并，更贴合剧情节奏。

### 11.2 Synopsis 作为 L3 种子

当前 L3 全书纲要是每 15 章压缩生成。可改用用户创建项目时的 `synopsis` 作为 L3 初始种子，后续压缩时以此为基准对齐主线进展，避免压缩偏离用户原意。

### 11.3 PostgresSaver 替换 MemorySaver

当前 LangGraph checkpointer 仍是 `MemorySaver`（纯内存），进程重启即丢失。接入 `AsyncPostgresSaver` 后可实现 HITL 跨天恢复。

### 11.4 Agent 间黑板（scratchpad）

[state.py](../agents/state.py) 的 `scratchpad` 字段已定义但未启用。可改为各 Agent 把关键发现写入，后续 Agent 读取复用，减少重复工具调用。

### 11.5 一致性冲突检测

新章节写入前，用 LLM + 已有记忆做冲突检测，发现与历史设定/角色状态/伏笔的矛盾。

---

## 十二、相关文件

| 文件 | 作用 |
|------|------|
| [memory_service.py](../services/memory_service.py) | 分层记忆核心服务 |
| [llm_service.py](../services/llm_service.py#L326) | LLM 压缩/评分方法 |
| [qdrant_service.py](../services/qdrant_service.py#L174) | 章节摘要向量检索 |
| [db_models.py](../models/db_models.py#L169) | ChapterSummary / VolumeSummary 数据模型 |
| [writing.py](../routers/writing.py) | 路由集成（写入 + 读取） |
