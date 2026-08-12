"""
人工审核智能体（Human-in-the-Loop）

基于 LangGraph 的 interrupt 机制实现：当审查未通过时，图执行在此节点暂停，
把审查结果和当前草稿抛给前端，等待用户提交决策后恢复执行。

这是从"全自动流水线"升级为"人机协同"的关键节点：
- approve：用户认可当前草稿，直接结束
- revise：用户让修改 Agent 继续打磨（可附带反馈）
- replan：用户认为方向有问题，回到规划阶段重来
- edit：用户直接编辑草稿内容后继续

恢复机制：前端调用 resume 接口，通过 Command(resume=decision) 把决策注入图，
interrupt() 返回该决策，节点据此更新状态后回到 Supervisor 重新路由。
"""
import logging
from langgraph.types import interrupt
from backend.agents.state import WritingAgentState, StructuredReview

logger = logging.getLogger(__name__)


def _build_interrupt_payload(state: WritingAgentState) -> dict:
    """构建抛给前端的人工审核信息"""
    review_result = state.get("review_result")
    payload = {
        "chapter_id": state.get("chapter_id", ""),
        "revision_count": state.get("revision_count", 0),
        "draft": state.get("draft", ""),
        "review_summary": "",
        "overall_score": None,
        "passed": False,
        "issues": [],
        "recommended_action": "revise_full",
    }

    if isinstance(review_result, StructuredReview):
        payload["review_summary"] = review_result.summary
        payload["overall_score"] = review_result.overall_score
        payload["passed"] = review_result.passed
        payload["recommended_action"] = review_result.recommended_action
        payload["issues"] = [issue.model_dump() for issue in review_result.issues]
    elif review_result:
        payload["review_summary"] = str(review_result)[:500]

    return payload


def human_review_node(state: WritingAgentState) -> dict:
    """人工审核节点：调用 interrupt 暂停图执行，等待用户决策

    interrupt(payload) 会把 payload 返回给图的调用方（后端 SSE 接口），
    并暂停图执行。前端展示决策面板，用户提交后通过 Command(resume=decision) 恢复，
    interrupt 返回值即为 decision。
    """
    logger.info(f"[人工审核] 章节暂停等待人工决策: {state.get('chapter_id')}")

    payload = _build_interrupt_payload(state)

    # 暂停并等待人工决策；恢复后 decision 为用户提交的决策 dict
    decision = interrupt(payload)

    logger.info(f"[人工审核] 收到用户决策: {decision.get('action') if isinstance(decision, dict) else decision}")

    result: dict = {"human_decision": decision}

    # 用户手动编辑了草稿：直接写入 draft，后续 Supervisor 会路由到 reviewer 重新审查
    if isinstance(decision, dict) and decision.get("action") == "edit":
        edited = decision.get("edited_content", "")
        if edited:
            result["draft"] = edited
            logger.info(f"[人工审核] 用户编辑了草稿，新长度: {len(edited)} 字符")

    # 清除 review_result，避免 Supervisor 误判为"已审查通过"而直接结束
    # 用户既然介入了，说明需要重新走流程（approve 除外，approve 由 Supervisor 路由到 FINISH）
    if isinstance(decision, dict) and decision.get("action") != "approve":
        result["review_result"] = None

    return result
