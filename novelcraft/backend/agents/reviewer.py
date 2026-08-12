"""
审查智能体

改进：从单次 LLM 调用 → 拥有专业审查工具的 ReAct Agent
- 可调用 verify_plot_logic 专门验证情节逻辑
- 可调用 verify_character_behavior 专门验证人物行为
- 可调用 verify_setting_consistency 专门验证设定一致性
- 输出结构化审查结果（StructuredReview），替代字符串匹配
- 自主决定需要执行哪些维度的审查
"""
import logging
import json
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from backend.agents.state import WritingAgentState, StructuredReview, ReviewIssue
from backend.agents.agent_tools import REVIEWER_TOOLS
from backend.services.llm_service import llm_service
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

REVIEWER_SYSTEM_PROMPT = """你是一位严格的小说审稿编辑。你需要对章节内容进行多维度审查。

你可以使用以下专业审查工具：
- verify_plot_logic: 验证情节逻辑，检查剧情漏洞和前后矛盾
- verify_character_behavior: 验证人物行为一致性，检查角色言行是否符合设定
- verify_setting_consistency: 验证世界观设定一致性，检查设定冲突

工作流程：
1. 先通读章节内容和大纲要求
2. 根据内容特点，决定需要调用哪些审查工具（至少调用2个）
3. 综合工具返回的结果和你的判断，输出结构化审查报告

审查报告必须严格按以下 JSON 格式输出：
{
    "passed": true/false,
    "overall_score": 0-10的评分,
    "issues": [
        {
            "category": "character/plot/setting/style/logic/dialogue",
            "severity": "critical/major/minor",
            "location": "问题位置描述",
            "description": "问题描述",
            "suggestion": "修改建议"
        }
    ],
    "summary": "审查总结",
    "recommended_action": "approve/revise_character/revise_plot/revise_style/revise_full/replan"
}

recommended_action 说明：
- approve: 审查通过，无需修改
- revise_character: 主要是人物行为问题，需修改人物相关内容
- revise_plot: 主要是情节逻辑问题，需修改情节
- revise_style: 主要是风格问题，需调整文风
- revise_full: 多维度问题，需全面修改
- replan: 问题严重，需要重新规划

请先使用审查工具，再输出最终的 JSON 审查报告。"""


async def review_node(state: WritingAgentState) -> dict:
    """审查 Agent 节点：ReAct 模式，可调用专业审查工具"""
    logger.info(f"[审查Agent] 开始审查章节 {state.get('chapter_id')}")

    model = llm_service._get_chat_model(settings.llm_reviewer_model)
    agent = create_react_agent(
        model=model,
        tools=REVIEWER_TOOLS,
        prompt=REVIEWER_SYSTEM_PROMPT,
    )

    user_message = f"""请审查以下章节内容。

章节大纲要求：
{state["outline"]}

人物设定：
{state.get("character_context", "暂无")}

世界观设定：
{state.get("setting_context", "暂无")}

章节正文：
{state["draft"]}"""

    try:
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=user_message)]},
        )
    except Exception as e:
        logger.error(f"[审查Agent] ReAct 执行失败: {type(e).__name__}: {e}")
        # 降级：直接用 LLM 审查
        logger.info("[审查Agent] 降级为直接 LLM 调用")
        review_text = await llm_service.review_chapter(
            chapter_content=state["draft"],
            outline=state["outline"],
            character_context=state.get("character_context", ""),
            setting_context=state.get("setting_context", ""),
        )
        review_result = _parse_review_result(review_text)
        return {
            "review_result": review_result,
            "review_feedback": review_text,
            "status": "reviewed",
            "messages": [HumanMessage(content=user_message), AIMessage(content=review_text)],
        }

    final_message = result["messages"][-1].content if result["messages"] else ""

    # 解析结构化审查结果
    review_result = _parse_review_result(final_message)

    if review_result.passed:
        logger.info(f"[审查Agent] 审查通过，评分: {review_result.overall_score}/10")
    else:
        logger.warning(
            f"[审查Agent] 审查未通过，评分: {review_result.overall_score}/10，"
            f"问题数: {len(review_result.issues)}，推荐动作: {review_result.recommended_action}"
        )

    return {
        "review_result": review_result,
        "status": "reviewed",
        "messages": result["messages"],
    }


def _parse_review_result(raw_output: str) -> StructuredReview:
    """从 LLM 输出中解析结构化审查结果"""
    # 尝试提取 JSON
    try:
        # 查找 JSON 块
        json_str = raw_output
        if "```json" in raw_output:
            json_str = raw_output.split("```json")[1].split("```")[0]
        elif "```" in raw_output:
            json_str = raw_output.split("```")[1].split("```")[0]

        data = json.loads(json_str.strip())
        return StructuredReview(**data)
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning(f"[审查Agent] 结构化解析失败: {e}，使用回退逻辑")

        # 回退：从文本中推断结果
        passed = "通过" in raw_output and "未通过" not in raw_output
        return StructuredReview(
            passed=passed,
            overall_score=7.0 if passed else 5.0,
            issues=[],
            summary=raw_output[:500],
            recommended_action="approve" if passed else "revise_full",
        )
