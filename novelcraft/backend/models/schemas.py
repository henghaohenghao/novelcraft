"""
Pydantic 请求/响应模型定义

定义所有 API 端点的输入校验和输出序列化模型，
使用 Pydantic v2 的 from_attributes 模式兼容 SQLAlchemy ORM。
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ProjectCreate(BaseModel):
    """创建项目请求"""
    title: str = Field(..., min_length=1, max_length=255)
    synopsis: str = ""
    genre: str = ""
    style: str = ""


class ProjectUpdate(BaseModel):
    """更新项目请求（所有字段可选）"""
    title: Optional[str] = None
    synopsis: Optional[str] = None
    genre: Optional[str] = None
    style: Optional[str] = None
    status: Optional[str] = None


class ProjectResponse(BaseModel):
    """项目响应模型"""
    id: str
    title: str
    synopsis: str
    genre: str
    style: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OutlineCreate(BaseModel):
    """创建大纲节点请求"""
    project_id: str
    parent_id: Optional[str] = None
    title: str
    content: str = ""
    node_type: str = "chapter"
    sort_order: int = 0
    depth: int = 0
    branch_label: Optional[str] = None


class OutlineUpdate(BaseModel):
    """更新大纲节点请求"""
    title: Optional[str] = None
    content: Optional[str] = None
    node_type: Optional[str] = None
    sort_order: Optional[int] = None
    branch_label: Optional[str] = None


class OutlineResponse(BaseModel):
    """大纲节点响应模型"""
    id: str
    project_id: str
    parent_id: Optional[str]
    title: str
    content: str
    node_type: str
    sort_order: int
    depth: int
    branch_label: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OutlineTreeResponse(BaseModel):
    """大纲树形响应（嵌套 children）"""
    id: str
    title: str
    content: str
    node_type: str
    sort_order: int
    depth: int
    branch_label: Optional[str]
    children: list["OutlineTreeResponse"] = []

    model_config = {"from_attributes": True}


class ChapterCreate(BaseModel):
    """创建章节请求"""
    project_id: str
    outline_id: Optional[str] = None
    title: str
    chapter_number: int = 0


class ChapterResponse(BaseModel):
    """章节响应模型"""
    id: str
    project_id: str
    outline_id: Optional[str]
    title: str
    content: str
    summary: str
    status: str
    revision_count: int
    review_feedback: Optional[str]
    chapter_number: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GenerateChapterRequest(BaseModel):
    """AI 生成章节请求"""
    chapter_id: str
    style: str = ""


class HumanReviewDecision(BaseModel):
    """人工审核决策请求（Human-in-the-Loop 恢复图执行）

    - approve: 接受当前草稿，直接结束流程
    - revise: 让修改 Agent 继续打磨，可附带反馈意见
    - replan: 回到规划阶段重新制定计划
    - edit: 用户手动编辑草稿后继续（需提供 edited_content）
    """
    chapter_id: str = Field(..., description="章节ID，同时作为图执行的 thread_id")
    action: str = Field(..., description="决策动作：approve / revise / replan / edit")
    feedback: str = Field(default="", description="用户给 Agent 的反馈意见")
    edited_content: str = Field(default="", description="action=edit 时用户编辑后的章节内容")


class CharacterCreate(BaseModel):
    """创建人物请求"""
    project_id: str
    name: str
    alias: Optional[str] = None
    description: str = ""
    personality: str = ""
    background: str = ""
    appearance: str = ""
    abilities: str = ""
    status: str = "alive"


class CharacterUpdate(BaseModel):
    """更新人物请求"""
    name: Optional[str] = None
    alias: Optional[str] = None
    description: Optional[str] = None
    personality: Optional[str] = None
    background: Optional[str] = None
    appearance: Optional[str] = None
    abilities: Optional[str] = None
    status: Optional[str] = None


class CharacterResponse(BaseModel):
    """人物响应模型"""
    id: str
    project_id: str
    name: str
    alias: Optional[str]
    description: str
    personality: str
    background: str
    appearance: str
    abilities: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RelationshipCreate(BaseModel):
    """创建人物关系请求"""
    project_id: str
    source_id: str
    target_id: str
    relation_type: str
    description: str = ""


class RelationshipResponse(BaseModel):
    """人物关系响应模型"""
    source_id: str
    source_name: str
    target_id: str
    target_name: str
    relation_type: str
    description: str


class FactionCreate(BaseModel):
    """创建阵营请求"""
    project_id: str
    name: str
    description: str = ""
    goal: str = ""


class FactionResponse(BaseModel):
    """阵营响应模型"""
    id: str
    project_id: str
    name: str
    description: str
    goal: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LocationCreate(BaseModel):
    """创建地点请求"""
    project_id: str
    name: str
    description: str = ""
    location_type: str = "general"


class LocationResponse(BaseModel):
    """地点响应模型"""
    id: str
    project_id: str
    name: str
    description: str
    location_type: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EventCreate(BaseModel):
    """创建事件请求"""
    project_id: str
    name: str
    description: str = ""
    event_time: Optional[str] = None
    chapter_id: Optional[str] = None


class EventResponse(BaseModel):
    """事件响应模型"""
    id: str
    project_id: str
    name: str
    description: str
    event_time: Optional[str]
    chapter_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GenerateOutlineRequest(BaseModel):
    """AI 生成大纲请求"""
    project_id: str
    synopsis: str
    chapter_count: int = 10


class SSEMessage(BaseModel):
    """SSE 推送消息模型"""
    event: str
    data: dict


class UserRegister(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_-]+$")
    email: str = Field(..., pattern="^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$")
    password: str = Field(..., min_length=8, max_length=72, description="密码长度 8-72 字符（bcrypt 限制）")
    full_name: Optional[str] = Field(None, max_length=100)


class UserLogin(BaseModel):
    """用户登录请求"""
    username: str = Field(..., description="用户名或邮箱")
    password: str


class TokenResponse(BaseModel):
    """Token 响应"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserResponse"


class UserResponse(BaseModel):
    """用户响应模型"""
    id: str
    username: str
    email: str
    full_name: Optional[str]
    avatar_url: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """更新用户信息请求"""
    full_name: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = Field(None, max_length=500)


class PasswordChange(BaseModel):
    """修改密码请求"""
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=72, description="密码长度 8-72 字符（bcrypt 限制）")