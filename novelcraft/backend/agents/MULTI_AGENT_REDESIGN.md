# NovelCraft 多智能体架构重构说明

## 一、问题诊断

原始系统的核心问题：**它是一个 Workflow，不是 Multi-Agent**。

| 特征 | Workflow | Multi-Agent |
|------|----------|-------------|
| 控制流位置 | 在代码里，路径预定义 | 在 LLM 里，运行时动态决策 |
| Agent 本质 | 单次 LLM 调用的函数包装 | 拥有工具、可自主决策的 ReAct Agent |
| 路由方式 | 硬编码 `plan→write→review→revise` | Supervisor 根据状态动态调度 |
| 审查判断 | `"审查通过" in feedback` 字符串匹配 | `StructuredReview` 结构化输出 |
| 修改策略 | 每次全文重写 | 可精准局部修改 |
| 错误恢复 | 只能 revise | 支持 replan 回退到规划阶段 |

原代码中的典型 Workflow 痕迹：

```python
# graph.py — 硬编码的固定流水线
workflow.set_entry_point("plan")
workflow.add_edge("plan", "write")       # 写死的流转
workflow.add_edge("write", "review")     # 写死的流转
workflow.add_conditional_edges("review", should_continue, ...)  # 字符串匹配路由
workflow.add_edge("revise", "review")

# reviewer.py — 字符串匹配判断
if "审查通过" in feedback or "内容合格" in feedback:  # 脆弱的路由逻辑

# planner.py — 单次 LLM 调用，无工具
plan = await llm_service.plan_chapter(...)  # 只能做一次调用，不能主动查信息
```

## 二、架构设计

### 2.1 整体架构：Supervisor + ReAct Agent

```
         ┌──────── Supervisor (LLM 驱动) ────────┐
         │  读取当前状态 → LLM 决策 → 路由到 Agent  │
         └──┬─────┬──────┬──────┬───────────────┘
            │     │      │      │
            ▼     ▼      ▼      ▼
        planner writer reviewer reviser
        (ReAct) (ReAct) (ReAct) (ReAct)
         │工具    │工具    │工具    │工具
         ▼       ▼       ▼       ▼
      Neo4j   Qdrant  LLM验证  精准修改
            └─────┴──────┴──────┘
                   │
             回到 Supervisor 重新评估
                   │
              ┌────▼────┐
              │  FINISH  │
              └─────────┘
```

### 2.2 三层改进

#### 第一层：Supervisor 动态调度

**文件**：`agents/supervisor.py`

Supervisor 是 LLM 驱动的中央调度器，替代硬编码的固定流水线：

```python
async def supervisor_node(state: WritingAgentState) -> dict:
    """Supervisor 节点：LLM 驱动的动态路由决策"""
    # 1. 构建当前状态摘要
    status_summary = _build_status_summary(state)

    # 2. 让 LLM 决策下一步调用哪个 Agent
    decision = await llm_service.chat(
        messages=[
            {"role": "system", "content": system_prompt},  # 包含所有 Agent 的职责描述
            {"role": "user", "content": f"当前创作状态：\n{status_summary}"},
        ],
        temperature=0.3,  # 低温度，决策要稳定
    )

    # 3. 解析决策 + 合法性校验
    next_agent = decision.strip().lower()
    if next_agent not in valid_agents:
        next_agent = _fallback_route(state)  # 规则回退

    return {"next_agent": next_agent}
```

**关键设计决策**：

- Supervisor 用 `llm_planner_model`（更强的模型），温度 0.3（决策要稳定）
- 有 `_fallback_route` 规则回退，LLM 决策无效时降级为确定性规则
- Supervisor 能理解结构化审查结果，做出精准路由（如人物问题→reviser 重点改人物）

#### 第二层：ReAct Agent 自主决策

每个 Agent 从"单次 LLM 调用"升级为"拥有工具的 ReAct Agent"：

```python
# 旧：单次调用，无自主权
async def plan_node(state):
    plan = await llm_service.plan_chapter(...)
    state["plan"] = plan
    return state

# 新：ReAct Agent，可自主使用工具
async def plan_node(state):
    model = llm_service._get_chat_model(settings.llm_planner_model)
    agent = create_react_agent(
        model=model,
        tools=PLANNER_TOOLS,           # 拥有工具集
        prompt=PLANNER_SYSTEM_PROMPT,   # 专属 system prompt
    )
    result = await agent.ainvoke({"messages": [HumanMessage(content=user_message)]})
    return {"plan": result["messages"][-1].content}
```

**ReAct 循环**：Agent 可以在"推理→调用工具→观察结果→继续推理"之间循环，直到完成任务。

四个 Agent 的工具分配：

| Agent | 工具 | 能力 |
|-------|------|------|
| Planner | `search_character_relations`, `search_world_setting`, `get_previous_chapter_summary` | 主动查询角色关系、世界观、前章摘要 |
| Writer | `check_character_consistency`, `lookup_style_guide` | 写作过程中验证角色行为、查询风格 |
| Reviewer | `verify_plot_logic`, `verify_character_behavior`, `verify_setting_consistency` | 多维度专业审查 |
| Reviser | `targeted_revise` | 精准局部修改 |

#### 第三层：工具赋能

**文件**：`agents/agent_tools.py`

工具是 Agent 与外部系统交互的接口，让 Agent 从"只能做单次 LLM 调用"变为"能主动获取信息、验证假设"：

```python
@tool
async def search_character_relations(character_name: str) -> str:
    """查询角色的人际关系网络"""
    relations = await neo4j_service.get_character_relations(character_name)
    # ... 格式化返回

@tool
async def verify_plot_logic(chapter_content: str, outline: str) -> str:
    """专门验证情节逻辑"""
    result = await llm_service.chat(messages=[...], temperature=0.3)
    return result
```

**工具设计原则**：
- 每个工具职责单一，描述清晰（LLM 靠描述选择工具）
- 工具内部做异常处理，返回友好错误信息而非抛异常
- 审查工具是"专家子 Agent"，专注单一维度

### 工具分类详解

#### 规划 Agent 工具集（PLANNER_TOOLS）

| 工具 | 功能 | 数据源 | 用途 |
|------|------|--------|------|
| `search_character_relations` | 查询角色的人际关系网络 | Neo4j 图数据库 | 规划情节时了解角色间的关联 |
| `search_world_setting` | 查询世界观设定信息 | Qdrant 向量数据库 | 确保写作计划不违背世界观设定 |
| `get_previous_chapter_summary` | 获取前一章摘要 | PostgreSQL chapters 表 | 确保章节间情节衔接 |

#### 写作 Agent 工具集（WRITER_TOOLS）

| 工具 | 功能 | 数据源 | 用途 |
|------|------|--------|------|
| `check_character_consistency` | 检查角色行为是否符合性格设定 | PostgreSQL characters 表 + LLM 判断 | 写作时实时验证角色行为合理性 |
| `lookup_style_guide` | 查询写作风格指南 | Qdrant 向量数据库 | 保持文风一致 |

#### 审查 Agent 工具集（REVIEWER_TOOLS）

| 工具 | 功能 | 数据源 | 用途 |
|------|------|--------|------|
| `verify_plot_logic` | 验证情节逻辑、剧情漏洞和前后矛盾 | LLM 专项审查 | 深度分析因果链、伏笔合理性 |
| `verify_character_behavior` | 验证人物行为一致性 | LLM 专项审查 | 检查角色言行是否符合设定 |
| `verify_setting_consistency` | 验证世界观设定一致性 | LLM 专项审查 | 检查章节内容与世界观有无冲突 |

#### 修改 Agent 工具集（REVISER_TOOLS）

| 工具 | 功能 | 数据源 | 用途 |
|------|------|--------|------|
| `targeted_revise` | 针对特定问题进行局部修改 | LLM 重写 | 精准修改指定位置，保持其他内容不变 |

### 2.3 结构化审查

**文件**：`agents/state.py`

用 Pydantic 模型替代字符串匹配：

```python
class ReviewIssue(BaseModel):
    category: Literal["character", "plot", "setting", "style", "logic", "dialogue"]
    severity: Literal["critical", "major", "minor"]
    location: str
    description: str
    suggestion: str

class StructuredReview(BaseModel):
    passed: bool
    overall_score: float  # 0-10
    issues: list[ReviewIssue]
    summary: str
    recommended_action: Literal[
        "approve",           # 通过
        "revise_character",  # 人物问题→定向修改人物
        "revise_plot",       # 情节问题→定向修改情节
        "revise_style",      # 风格问题→调整文风
        "revise_full",       # 多维度问题→全面修改
        "replan",            # 问题严重→重新规划
    ]
```

**好处**：
- `recommended_action` 让 Supervisor 能精准路由，而非只能 `revise`
- `severity` 让 Reviser 能决定修改策略（minor→局部修改，critical→全文重写）
- Pydantic 校验保证输出格式正确

### 2.4 图结构重构

**文件**：`agents/graph.py`

```python
# 旧：固定流水线
workflow.set_entry_point("plan")
workflow.add_edge("plan", "write")
workflow.add_edge("write", "review")
workflow.add_conditional_edges("review", should_continue, ...)
workflow.add_edge("revise", "review")

# 新：Supervisor 动态调度
workflow.set_entry_point("supervisor")
workflow.add_conditional_edges("supervisor", route_from_supervisor, {
    "planner": "planner",
    "writer": "writer",
    "reviewer": "reviewer",
    "reviser": "reviser",
    "FINISH": END,
})
# 所有 Agent 执行后回到 Supervisor
workflow.add_edge("planner", "supervisor")
workflow.add_edge("writer", "supervisor")
workflow.add_edge("reviewer", "supervisor")
workflow.add_edge("reviser", "supervisor")
```

**关键区别**：
- 旧：Agent 之间直接连接，流转路径固定
- 新：所有 Agent 都回到 Supervisor，由 Supervisor 重新评估状态后决定下一步

## 三、文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `agents/state.py` | 重构 | 新增 `StructuredReview`, `ReviewIssue`, `AgentScratchpad`，扩展 `WritingAgentState` |
| `agents/supervisor.py` | 新增 | Supervisor Agent，LLM 驱动的动态路由 |
| `agents/agent_tools.py` | 新增 | 8 个 Agent 工具（查询/验证/修改） |
| `agents/graph.py` | 重构 | Supervisor 架构替代固定流水线 |
| `agents/planner.py` | 重构 | ReAct Agent + 工具集 |
| `agents/writer.py` | 重构 | ReAct Agent + 工具集 |
| `agents/reviewer.py` | 重构 | ReAct Agent + 专业审查工具 + 结构化输出 |
| `agents/revisor.py` | 重构 | ReAct Agent + 精准修改工具 |
| `services/llm_service.py` | 修改 | 新增 `_get_chat_model()` 方法 |

## 四、依赖变更

需在 `requirements.txt` 中添加：

```
langchain-openai>=0.3.0
```

`create_react_agent` 来自 `langgraph.prebuilt`，已包含在 `langgraph` 包中。

## 五、扩展方向

当前架构支持以下进一步改进：

1. **Human-in-the-Loop**：在 Supervisor 路由中增加 `human_review` 节点，让用户在关键节点审核
2. **Swarm 模式**：Agent 之间可直接 Handoff（如 Writer 发现角色问题直接交给 Reviewer），不经过 Supervisor
3. **层级架构**：Supervisor 下再分 Team（如审查 Team 包含情节审查、人物审查、设定审查三个子 Agent）
4. **记忆机制**：Agent Scratchpad 持久化，跨章节复用规划经验
5. **并行执行**：Reviewer 的三个审查工具可并行调用，提升效率
