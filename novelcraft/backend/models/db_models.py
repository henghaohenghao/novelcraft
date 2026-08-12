"""
数据库 ORM 模型定义

定义小说工坊的所有数据实体：项目、大纲、章节、人物、
阵营、地点、事件等，使用 SQLAlchemy 2.0 Mapped 映射。
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, Float, ForeignKey, JSON, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.database import Base
import enum


def gen_uuid():
    """生成 UUID 字符串，作为主键默认值"""
    return str(uuid.uuid4())


class ProjectStatus(str, enum.Enum):
    """项目状态枚举"""
    DRAFT = "draft"           # 草稿
    IN_PROGRESS = "in_progress"  # 进行中
    COMPLETED = "completed"    # 已完成
    ARCHIVED = "archived"      # 已归档


class ChapterStatus(str, enum.Enum):
    """章节流转状态枚举"""
    PLANNED = "planned"       # 已规划
    WRITING = "writing"       # 写作中
    REVIEWING = "reviewing"   # 审查中
    REVISING = "revising"     # 修改中
    COMPLETED = "completed"   # 已完成


class Project(Base):
    """小说项目 — 每个项目代表一本小说的创作工程"""
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    synopsis: Mapped[str] = mapped_column(Text, default="")
    genre: Mapped[str] = mapped_column(String(100), default="")
    style: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(20), default=ProjectStatus.DRAFT.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="projects")
    outlines: Mapped[list["Outline"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    chapters: Mapped[list["Chapter"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    characters: Mapped[list["Character"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    factions: Mapped[list["Faction"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    locations: Mapped[list["Location"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    events: Mapped[list["Event"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Outline(Base):
    """大纲节点 — 支持多级树形结构，可分支、可拖拽排序"""
    __tablename__ = "outlines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("outlines.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    node_type: Mapped[str] = mapped_column(String(50), default="chapter")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    depth: Mapped[int] = mapped_column(Integer, default=0)
    branch_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="outlines")
    children: Mapped[list["Outline"]] = relationship(back_populates="parent", remote_side="Outline.id")
    parent: Mapped["Outline | None"] = relationship(back_populates="children", remote_side="Outline.parent_id")


class Chapter(Base):
    """章节 — 小说的基本创作单元，由多智能体流水线生成"""
    __tablename__ = "chapters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    outline_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("outlines.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default=ChapterStatus.PLANNED.value)
    revision_count: Mapped[int] = mapped_column(Integer, default=0)
    agent_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    review_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    chapter_number: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="chapters")
    outline: Mapped["Outline | None"] = relationship()


class Character(Base):
    """人物 — 小说角色，包含性格、背景、外貌等设定"""
    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    alias: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    personality: Mapped[str] = mapped_column(Text, default="")
    background: Mapped[str] = mapped_column(Text, default="")
    appearance: Mapped[str] = mapped_column(Text, default="")
    abilities: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="alive")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="characters")


class Faction(Base):
    """阵营/势力 — 小说中的组织或团体"""
    __tablename__ = "factions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    goal: Mapped[str] = mapped_column(Text, default="")  # 阵营目标
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="factions")


class Location(Base):
    """地点 — 小说中的场景和地理位置"""
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    location_type: Mapped[str] = mapped_column(String(50), default="general")  # 地点类型
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="locations")


class Event(Base):
    """事件 — 小说中的重要剧情节点"""
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    event_time: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 事件发生时间
    chapter_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("chapters.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="events")


class ChapterSummary(Base):
    """章节摘要 — 分层记忆的 Level 1，替代 Chapter.summary 单字段

    存储结构化抽取的情节/人物变化/伏笔，并附带重要性评分与访问统计，
    供 memory_service 做分层组装、相关性召回与衰减归档使用。
    """
    __tablename__ = "chapter_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    chapter_id: Mapped[str] = mapped_column(String(36), ForeignKey("chapters.id"), nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # 三级内容：Level1 为完整章节摘要；Level2/Level3 在合并后回填，供跨章检索复用
    level1_detail: Mapped[str] = mapped_column(Text, default="")
    level2_volume: Mapped[str | None] = mapped_column(Text, nullable=True)
    level3_arc: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 结构化抽取
    key_events: Mapped[list] = mapped_column(JSON, default=list)
    character_changes: Mapped[list] = mapped_column(JSON, default=list)
    foreshadows: Mapped[list] = mapped_column(JSON, default=list)

    # 重要性评分（0-1）+ 访问统计，驱动衰减与召回权重
    importance_score: Mapped[float] = mapped_column(Float, default=0.5)
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    access_count: Mapped[int] = mapped_column(Integer, default=0)

    # Qdrant 向量 point_id，便于按相关性召回
    embedding_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped["Project"] = relationship()


class VolumeSummary(Base):
    """卷摘要 — Level 2，每 N 章合并一次，承载中程记忆"""
    __tablename__ = "volume_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    volume_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_chapter: Mapped[int] = mapped_column(Integer, nullable=False)
    end_chapter: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    unresolved_foreshadows: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped["Project"] = relationship()


class User(Base):
    """用户 — 平台用户账号"""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_superuser: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    projects: Mapped[list["Project"]] = relationship(back_populates="user", cascade="all, delete-orphan")