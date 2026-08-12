"""
多智能体写作状态定义

支持 Supervisor 架构的多智能体协作状态：
- 共享消息历史（Agent 间通信）
- 结构化审查结果（替代字符串匹配）
- 各 Agent 私有草稿区（避免上下文爆炸）
- 动态路由信息
"""
from typing import TypedDict, Annotated, Sequence, Literal
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


class ReviewIssue(BaseModel):
    """单条审查问题"""
    category: Literal["character", "plot", "setting", "style", "logic", "dialogue"] = Field(
        description="问题类别：人物/情节/设定/风格/逻辑/对话"
    )
    severity: Literal["critical", "major", "minor"] = Field(
        description="严重程度：关键/主要/次要"
    )
    location: str = Field(description="问题位置描述")
    description: str = Field(description="问题描述")
    suggestion: str = Field(description="修改建议")


class StructuredReview(BaseModel):
    """结构化审查结果（替代字符串匹配）"""
    passed: bool = Field(description="是否通过审查")
    overall_score: float = Field(ge=0, le=10, description="总体评分 0-10")
    issues: list[ReviewIssue] = Field(default_factory=list, description="发现的问题列表")
    summary: str = Field(description="审查总结")
    recommended_action: Literal["approve", "revise_character", "revise_plot", "revise_style", "revise_full", "replan"] = Field(
        description="推荐下一步动作"
    )


class AgentScratchpad(TypedDict, total=False):
    """Agent 私有草稿区：各 Agent 可维护自己的中间推理"""
    planner_thoughts: str       # 规划 Agent 的思考过程
    writer_thoughts: str        # 写作 Agent 的思考过程
    reviewer_thoughts: str      # 审查 Agent 的思考过程
    reviser_thoughts: str       # 修改 Agent 的思考过程


class ToolCallRecord(BaseModel):
    """单次工具调用记录"""
    tool_name: str = Field(description="工具名称")
    tool_args: dict = Field(default_factory=dict, description="工具输入参数")
    tool_output: str = Field(default="", description="工具输出结果")
    status: Literal["running", "completed", "error"] = Field(default="running", description="调用状态")


class AgentStepRecord(BaseModel):
    """单个 Agent 执行步骤记录"""
    agent_name: str = Field(description="Agent 名称（supervisor/planner/writer/reviewer/reviser/human_review）")
    agent_label: str = Field(default="", description="Agent 中文标签")
    started_at: str = Field(default="", description="开始时间")
    finished_at: str = Field(default="", description="结束时间")
    status: Literal["running", "completed", "error"] = Field(default="running", description="执行状态")
    summary: str = Field(default="", description="执行摘要")
    tool_calls: list[ToolCallRecord] = Field(default_factory=list, description="工具调用记录")
    output_preview: str = Field(default="", description="输出预览（截断）")


class HumanDecision(BaseModel):
    """人工审核决策（Human-in-the-Loop 恢复时由用户提交）"""
    action: Literal["approve", "revise", "replan", "edit"] = Field(
        description="决策动作：approve 接受当前草稿 / revise 让修改Agent继续 / replan 重新规划 / edit 用户手动编辑后继续"
    )
    feedback: str = Field(default="", description="用户给 Agent 的反馈意见")
    edited_content: str = Field(default="", description="action=edit 时用户编辑后的章节内容")


class WritingAgentState(TypedDict):
    """多智能体写作流转状态（Supervisor 架构）"""
    # --- 基础信息 ---
    chapter_id: str
    project_id: str
    outline: str
    previous_summary: str
    character_context: str
    setting_context: str
    style: str

    # --- 工作产出 ---
    plan: str
    draft: str
    review_result: StructuredReview       # 结构化审查结果
    review_feedback: str                  # 兼容旧格式的审查反馈文本
    revision_count: int
    status: str

    # --- Agent 私有草稿区 ---
    scratchpad: AgentScratchpad

    # --- Supervisor 路由 ---
    next_agent: str                       # Supervisor 决定的下一个 Agent
    human_decision: dict | None           # 人工审核决策（Human-in-the-Loop），恢复后由 human_review 节点写入

    # --- Agent 执行追踪 ---
    agent_trace: list[dict]               # AgentStepRecord 序列化列表，记录完整执行链

    # --- 消息历史（Agent 间通信） ---
    messages: Annotated[Sequence[BaseMessage], add_messages]
