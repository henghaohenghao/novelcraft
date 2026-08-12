"""
写作智能体

改进：从单次 LLM 调用 → 拥有工具的 ReAct Agent
- 可主动检查角色行为一致性
- 可查询风格指南
- 自主决定在写作过程中需要验证哪些内容
"""
import logging
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from backend.agents.state import WritingAgentState
from backend.agents.agent_tools import WRITER_TOOLS
from backend.services.llm_service import llm_service
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

WRITER_SYSTEM_PROMPT = """你是一位才华横溢的小说作家。请根据写作计划创作章节内容。

你可以使用以下工具来确保写作质量：
- check_character_consistency: 检查角色行为是否符合设定
- lookup_style_guide: 查询写作风格指南

工作流程：
1. 仔细阅读写作计划和大纲
2. 创作章节内容
3. 在写作过程中，如果对某个角色的行为是否合理有疑问，使用 check_character_consistency 工具验证
4. 如果需要确认风格要求，使用 lookup_style_guide 工具查询
5. 输出完整的章节正文

要求：
1. 字数在3000-5000字之间
2. 语言流畅，描写生动
3. 人物性格和行为保持一致
4. 注意场景转换的自然过渡
5. 适当埋设伏笔

{style_instruction}"""


async def write_node(state: WritingAgentState) -> dict:
    """写作 Agent 节点：ReAct 模式，可主动使用工具验证内容"""
    logger.info(f"[写作Agent] 开始创作章节 {state.get('chapter_id')}")

    style_instruction = f"\n写作风格要求：{state['style']}" if state.get("style") else ""
    system_prompt = WRITER_SYSTEM_PROMPT.format(style_instruction=style_instruction)

    model = llm_service._get_chat_model(settings.llm_writer_model)
    agent = create_react_agent(
        model=model,
        tools=WRITER_TOOLS,
        prompt=system_prompt,
    )

    user_message = f"""请根据以下信息创作本章内容。

项目ID：{state.get("project_id", "")}

写作计划：
{state["plan"]}

章节大纲：
{state["outline"]}

前情摘要：
{state.get("previous_summary") or "（这是第一章）"}

人物信息：
{state.get("character_context", "暂无")}

设定信息：
{state.get("setting_context", "暂无")}

注意：调用 lookup_style_guide 工具时，请将上面的项目ID作为 project_id 参数传入。"""

    try:
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=user_message)]},
        )
    except Exception as e:
        logger.error(f"[写作Agent] ReAct 执行失败: {type(e).__name__}: {e}")
        # 降级：直接用 LLM 写作，不使用工具
        logger.info("[写作Agent] 降级为直接 LLM 调用")
        draft_text = await llm_service.write_chapter(
            plan=state["plan"],
            outline=state["outline"],
            previous_summary=state.get("previous_summary", ""),
            character_context=state.get("character_context", ""),
            setting_context=state.get("setting_context", ""),
            style=state.get("style", ""),
        )
        return {
            "draft": draft_text,
            "status": "drafted",
            "messages": [HumanMessage(content=user_message), AIMessage(content=draft_text)],
        }

    final_message = result["messages"][-1].content if result["messages"] else ""

    logger.info(f"[写作Agent] 章节草稿创作完成，字数: {len(final_message)} 字符")

    return {
        "draft": final_message,
        "status": "drafted",
        "messages": result["messages"],
    }
