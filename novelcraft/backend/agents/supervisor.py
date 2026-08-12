"""
Supervisor 智能体

核心改进：用 LLM 驱动的 Supervisor 替代硬编码的固定流水线。
Supervisor 根据当前状态动态决定下一步调用哪个 Agent，
而不是按 plan → write → review → revise 的固定顺序执行。

这是从"Workflow"升级为"Multi-Agent"的关键转变：
- Workflow：控制流在代码里，路径预定义
- Supervisor Agent：控制流在 LLM 里，运行时动态决策
"""
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import MessagesState
from backend.agents.state import WritingAgentState, StructuredReview
from backend.services.llm_service import llm_service
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Supervisor 可调度的 Agent 列表
AVAILABLE_AGENTS = {
    "planner": "规划智能体 - 制定章节写作计划，查询角色关系和世界观设定",
    "writer": "写作智能体 - 根据计划创作章节正文，检查角色一致性",
    "reviewer": "审查智能体 - 多维度审查章节质量（情节逻辑、人物行为、设定一致性）",
    "reviser": "修改智能体 - 根据审查意见精准修改章节内容",
    "human_review": "人工审核 - 审查未通过时暂停，交由人类作者确认是否接受/修改/重新规划",
    "FINISH": "完成 - 章节质量达标，结束流程",
}

SUPERVISOR_SYSTEM_PROMPT = """你是一个小说创作团队的总监（Supervisor），负责协调以下智能体的工作：

{agent_descriptions}

你的职责是根据当前创作状态，决定下一步应该由哪个智能体来执行。

决策规则：
1. 如果还没有写作计划（plan 为空），调度 planner
2. 如果有了计划但还没有草稿（draft 为空），调度 writer
3. 如果有了草稿但还没审查（review_result 为空），调度 reviewer
4. 如果审查未通过，根据 recommended_action 决定：
   - "revise_character" / "revise_plot" / "revise_style" / "revise_full" → 调度 reviser
   - "replan" → 调度 planner（需要重新规划）
5. 如果审查未通过且已经修改过至少一次（revision_count >= 1），调度 human_review，让人类作者介入确认下一步
6. 如果审查通过（passed=True）或修改次数已达上限，选择 FINISH
7. 如果修改后需要重新审查，调度 reviewer

重要：你不仅要看状态字段，还要结合审查结果的具体问题来决策。
例如，如果审查发现主要是人物行为问题，可以让 reviser 重点修改人物部分。
当问题反复修改仍无法解决、或涉及创作方向取舍时，优先调度 human_review 让人工介入。

请只输出你要调度的智能体名称，不要输出其他内容。"""


async def supervisor_node(state: WritingAgentState) -> dict:
    """Supervisor 节点：LLM 驱动的动态路由决策"""
    # --- 优先处理人工审核决策（Human-in-the-Loop 恢复后）---
    # human_review 节点 interrupt 恢复后会写入 human_decision，
    # Supervisor 据此直接路由，无需再调用 LLM（人工决策优先级最高）
    decision = state.get("human_decision")
    if decision and isinstance(decision, dict) and decision.get("action"):
        next_agent = _route_from_human_decision(decision)
        logger.info(f"[Supervisor] 应用人工决策: {decision.get('action')} → 调度 {next_agent}")
        # 清除 human_decision，避免后续重复触发
        return {"next_agent": next_agent, "human_decision": None}

    logger.info(f"[Supervisor] 评估当前状态，决定下一步")

    # 构建当前状态摘要
    status_summary = _build_status_summary(state)

    # 构建 Agent 描述
    agent_descriptions = "\n".join(
        f"- {name}: {desc}" for name, desc in AVAILABLE_AGENTS.items()
    )

    system_prompt = SUPERVISOR_SYSTEM_PROMPT.format(agent_descriptions=agent_descriptions)

    # 让 LLM 决策
    decision_resp = await llm_service.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"当前创作状态：\n{status_summary}\n\n请决定下一步调度哪个智能体。"},
        ],
        model=settings.llm_planner_model,
        temperature=0.1,
        max_tokens=64,
    )

    # 解析决策
    next_agent = decision_resp.strip().lower()

    # 验证决策合法性
    valid_agents = set(AVAILABLE_AGENTS.keys())
    if next_agent not in valid_agents:
        logger.warning(f"[Supervisor] LLM 返回了无效的 Agent 名称: '{next_agent}'，回退到规则路由")
        next_agent = _fallback_route(state)

    logger.info(f"[Supervisor] 决策：下一步调度 → {next_agent}")

    return {"next_agent": next_agent}


def _route_from_human_decision(decision: dict) -> str:
    """根据人工审核决策映射到下一个 Agent"""
    action = decision.get("action", "approve")
    mapping = {
        "approve": "FINISH",
        "revise": "reviser",
        "replan": "planner",
        "edit": "reviewer",  # 用户编辑后重新审查
    }
    return mapping.get(action, "FINISH")


def _build_status_summary(state: WritingAgentState) -> str:
    """构建当前状态摘要，供 Supervisor 决策"""
    lines = []
    lines.append(f"章节ID: {state.get('chapter_id', '未知')}")
    lines.append(f"当前状态: {state.get('status', '未知')}")
    lines.append(f"修改次数: {state.get('revision_count', 0)}/{settings.max_revision_rounds}")

    has_plan = bool(state.get("plan"))
    has_draft = bool(state.get("draft"))
    review_result = state.get("review_result")

    lines.append(f"已有写作计划: {'是' if has_plan else '否'}")
    lines.append(f"已有章节草稿: {'是' if has_draft else '否'}")

    if isinstance(review_result, StructuredReview):
        lines.append(f"审查结果: {'通过' if review_result.passed else '未通过'}")
        lines.append(f"总体评分: {review_result.overall_score}/10")
        lines.append(f"推荐动作: {review_result.recommended_action}")
        if review_result.issues:
            lines.append(f"问题数量: {len(review_result.issues)}")
            for issue in review_result.issues[:5]:
                lines.append(f"  - [{issue.severity}][{issue.category}] {issue.description}")
    elif review_result:
        lines.append(f"审查结果: 已审查（旧格式）")
    else:
        lines.append(f"审查结果: 未审查")

    return "\n".join(lines)


def _fallback_route(state: WritingAgentState) -> str:
    """规则路由回退：当 LLM 决策无效时使用确定性规则"""
    revision_count = state.get("revision_count", 0)

    if not state.get("plan"):
        return "planner"
    if not state.get("draft"):
        return "writer"

    review_result = state.get("review_result")
    if not review_result:
        return "reviewer"

    if isinstance(review_result, StructuredReview):
        if review_result.passed or revision_count >= settings.max_revision_rounds:
            return "FINISH"
        # --- Human-in-the-Loop 触发点 ---
        # 审查未通过且已修改次数达到阈值，暂停交由人工确认
        if (
            settings.enable_human_review
            and revision_count >= settings.human_review_revision_threshold
        ):
            return "human_review"
        if review_result.recommended_action == "replan":
            return "planner"
        return "reviser"

    # 旧格式兼容
    if revision_count >= settings.max_revision_rounds:
        return "FINISH"
    if (
        settings.enable_human_review
        and revision_count >= settings.human_review_revision_threshold
    ):
        return "human_review"
    return "reviser"
