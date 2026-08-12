"""
规划智能体

改进：从单次 LLM 调用 → 拥有工具的 ReAct Agent
- 可主动查询角色关系网络
- 可主动查询世界观设定
- 可获取前章摘要
- 自主决定需要收集哪些信息后再制定计划
"""
import logging
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from backend.agents.state import WritingAgentState
from backend.agents.agent_tools import PLANNER_TOOLS
from backend.services.llm_service import llm_service
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

PLANNER_SYSTEM_PROMPT = """你是一位专业的小说写作规划师。你的任务是为当前章节制定详细的写作计划。

你可以使用以下工具来收集必要信息：
- search_character_relations: 查询角色的人际关系
- search_world_setting: 查询世界观设定
- get_previous_chapter_summary: 获取前一章摘要

工作流程：
1. 先分析大纲，确定需要哪些额外信息
2. 主动使用工具查询角色关系、世界观设定、前章摘要
3. 综合所有信息，制定详细的写作计划

计划应包含：
1. 本章核心事件
2. 出场人物及其状态
3. 情感基调与节奏
4. 需要呼应的伏笔
5. 具体场景划分（3-5个场景）

请先使用工具收集信息，再制定计划。"""


async def plan_node(state: WritingAgentState) -> dict:
    """规划 Agent 节点：ReAct 模式，可主动使用工具收集信息"""
    logger.info(f"[规划Agent] 开始为章节 {state.get('chapter_id')} 制定写作计划")

    # 构建 ReAct Agent
    model = llm_service._get_chat_model(settings.llm_planner_model)
    agent = create_react_agent(
        model=model,
        tools=PLANNER_TOOLS,
        prompt=PLANNER_SYSTEM_PROMPT,
    )

    # 准备输入
    user_message = f"""请为以下章节制定写作计划。

项目ID：{state.get("project_id", "")}

章节大纲：
{state["outline"]}

前情摘要：
{state.get("previous_summary") or "（这是第一章，无前情）"}

相关人物信息：
{state.get("character_context", "暂无")}

相关设定信息：
{state.get("setting_context", "暂无")}

注意：调用 search_world_setting 工具时，请将上面的项目ID作为 project_id 参数传入。"""

    # 执行 ReAct 循环
    try:
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=user_message)]},
        )
    except Exception as e:
        logger.error(f"[规划Agent] ReAct 执行失败: {type(e).__name__}: {e}")
        # 降级：直接用 LLM 生成计划，不使用工具
        logger.info("[规划Agent] 降级为直接 LLM 调用")
        plan_text = await llm_service.plan_chapter(
            outline=state["outline"],
            previous_summary=state.get("previous_summary", ""),
            character_context=state.get("character_context", ""),
            setting_context=state.get("setting_context", ""),
        )
        return {
            "plan": plan_text,
            "status": "planned",
            "messages": [HumanMessage(content=user_message), AIMessage(content=plan_text)],
        }

    # 提取最终回复
    final_message = result["messages"][-1].content if result["messages"] else ""

    logger.info(f"[规划Agent] 写作计划生成完成，长度: {len(final_message)} 字符")

    return {
        "plan": final_message,
        "status": "planned",
        "messages": result["messages"],
    }
