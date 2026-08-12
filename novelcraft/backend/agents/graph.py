"""
多智能体写作流水线图（Supervisor 架构 + Human-in-the-Loop）

核心改进：用 Supervisor + 动态路由 替代 固定流水线，并基于 LangGraph interrupt
实现人机协同：审查未通过时图执行暂停，等待人工决策后恢复。

新架构（Multi-Agent + HITL）：
  Supervisor 动态决定下一步调用哪个 Agent
  - Supervisor 是 LLM 驱动的，根据当前状态做运行时决策
  - 每个 Agent 是 ReAct Agent，拥有工具，可自主决策
  - 审查结果结构化，支持精准路由（人物问题→定向修改人物）
  - 支持回退到规划（replan），而非只能修改
  - human_review 节点通过 interrupt 暂停，交由人工确认（Human-in-the-Loop）

Checkpointer：使用 MemorySaver 持久化图状态，支持 interrupt 暂停/恢复。
  生产环境可替换为 SqliteSaver/PostgresSaver 实现跨进程持久化。
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from backend.agents.state import WritingAgentState
from backend.agents.supervisor import supervisor_node
from backend.agents.planner import plan_node
from backend.agents.writer import write_node
from backend.agents.reviewer import review_node
from backend.agents.revisor import revise_node
from backend.agents.human_review import human_review_node


def route_from_supervisor(state: WritingAgentState) -> str:
    """根据 Supervisor 的决策路由到对应 Agent"""
    next_agent = state.get("next_agent", "")

    if next_agent == "FINISH" or not next_agent:
        return "FINISH"

    valid_agents = {"planner", "writer", "reviewer", "reviser", "human_review"}
    if next_agent in valid_agents:
        return next_agent

    # 无效路由回退
    return "FINISH"


def build_writing_graph():
    """构建 Supervisor 架构的写作图（带 checkpointer 支持 HITL）

    架构：
        ┌──────────────────────────────────────────────────────┐
        │                   Supervisor                          │
        │  (LLM 驱动，动态决定调用哪个 Agent；优先处理人工决策)  │
        └──┬─────┬──────┬──────┬───────────┬──────────────────┘
           │     │      │      │           │
           ▼     ▼      ▼      ▼           ▼
       planner writer reviewer reviser  human_review
           │     │      │      │       (interrupt 暂停)
           └─────┴──────┴──────┴───────────┘
                    │
              回到 Supervisor
                    │
               ┌────▼────┐
               │  FINISH  │
               └─────────┘
    """
    workflow = StateGraph(WritingAgentState)

    # 注册节点
    workflow.add_node("supervisor", supervisor_node)        # Supervisor 调度
    workflow.add_node("planner", plan_node)                 # 规划 Agent（ReAct）
    workflow.add_node("writer", write_node)                 # 写作 Agent（ReAct）
    workflow.add_node("reviewer", review_node)              # 审查 Agent（ReAct）
    workflow.add_node("reviser", revise_node)               # 修改 Agent（ReAct）
    workflow.add_node("human_review", human_review_node)    # 人工审核（HITL，interrupt）

    # 入口：先经过 Supervisor
    workflow.set_entry_point("supervisor")

    # Supervisor 条件路由：根据 LLM 决策分发到不同 Agent
    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "planner": "planner",
            "writer": "writer",
            "reviewer": "reviewer",
            "reviser": "reviser",
            "human_review": "human_review",
            "FINISH": END,
        },
    )

    # 所有 Agent 执行完毕后，回到 Supervisor 重新评估
    workflow.add_edge("planner", "supervisor")
    workflow.add_edge("writer", "supervisor")
    workflow.add_edge("reviewer", "supervisor")
    workflow.add_edge("reviser", "supervisor")
    workflow.add_edge("human_review", "supervisor")

    # Checkpointer：持久化图状态，使 interrupt 可暂停、Command(resume=) 可恢复
    checkpointer = MemorySaver()

    return workflow.compile(checkpointer=checkpointer)


writing_graph = build_writing_graph()
