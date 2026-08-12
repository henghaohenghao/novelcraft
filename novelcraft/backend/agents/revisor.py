"""
修改智能体

改进：从全文重写 → 拥有精准修改工具的 ReAct Agent
- 可使用 targeted_revise 工具进行局部修改
- 根据审查结果的具体问题，决定是局部修改还是全文重写
- 支持按问题类别（人物/情节/风格）定向修改
"""
import logging
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from backend.agents.state import WritingAgentState, StructuredReview
from backend.agents.agent_tools import REVISER_TOOLS
from backend.services.llm_service import llm_service
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

REVISER_SYSTEM_PROMPT = """你是一位专业的小说修改编辑。请根据审查意见修改章节内容。

你可以使用以下工具：
- targeted_revise: 针对特定问题进行局部修改（推荐，保持其他内容不变）

工作流程：
1. 仔细阅读审查意见，理解每个问题
2. 根据问题严重程度决定修改策略：
   - minor 级别问题：使用 targeted_revise 逐条修改
   - major/critical 级别问题：如果问题较多（3个以上），考虑全文重写
   - 如果 recommended_action 是 revise_character/revise_plot/revise_style，重点修改对应维度
3. 确保修改后的内容解决所有指出的问题
4. 保持原有文风和叙事节奏

修改原则：
- 优先使用 targeted_revise 进行精准修改
- 只在问题严重且分散时才全文重写
- 修改后人物行为必须与设定一致
- 情节逻辑必须通顺"""


async def revise_node(state: WritingAgentState) -> dict:
    """修改 Agent 节点：ReAct 模式，可使用精准修改工具"""
    revision_count = state.get("revision_count", 0) + 1
    logger.info(f"[修改Agent] 开始第 {revision_count} 次修改章节 {state.get('chapter_id')}")

    model = llm_service._get_chat_model(settings.llm_writer_model)
    agent = create_react_agent(
        model=model,
        tools=REVISER_TOOLS,
        prompt=REVISER_SYSTEM_PROMPT,
    )

    # 构建审查意见摘要
    review_summary = _build_review_summary(state)

    user_message = f"""请根据审查意见修改以下章节。

{review_summary}

写作计划：
{state.get("plan", "暂无")}

人物信息：
{state.get("character_context", "暂无")}

设定信息：
{state.get("setting_context", "暂无")}

原文：
{state["draft"]}"""

    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=user_message)]},
    )

    final_message = result["messages"][-1].content if result["messages"] else ""

    logger.info(f"[修改Agent] 修改完成，修改后字数: {len(final_message)} 字符")

    return {
        "draft": final_message,
        "revision_count": revision_count,
        "status": "revised",
        "messages": result["messages"],
    }


def _build_review_summary(state: WritingAgentState) -> str:
    """构建审查意见摘要"""
    review_result = state.get("review_result")

    if isinstance(review_result, StructuredReview):
        lines = [f"审查评分: {review_result.overall_score}/10"]
        lines.append(f"审查总结: {review_result.summary}")
        lines.append(f"推荐动作: {review_result.recommended_action}")

        if review_result.issues:
            lines.append(f"\n发现 {len(review_result.issues)} 个问题：")
            for i, issue in enumerate(review_result.issues, 1):
                lines.append(
                    f"  {i}. [{issue.severity}][{issue.category}] {issue.description}\n"
                    f"     位置: {issue.location}\n"
                    f"     建议: {issue.suggestion}"
                )
        return "\n".join(lines)

    # 旧格式兼容
    feedback = state.get("review_feedback", "")
    return f"审查意见：\n{feedback}"
