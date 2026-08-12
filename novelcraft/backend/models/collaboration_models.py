"""
实时协同编辑相关数据模型
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, JSON, LargeBinary, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.database import Base


def gen_uuid():
    """生成 UUID 字符串"""
    return str(uuid.uuid4())


class CollaborationRoom(Base):
    """协同编辑房间"""
    __tablename__ = "collaboration_rooms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    chapter_id: Mapped[str] = mapped_column(String(36), ForeignKey("chapters.id"), nullable=False, unique=True)
    room_name: Mapped[str] = mapped_column(String(255), nullable=False)
    yjs_state_vector: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)  # Yjs 状态向量
    yjs_document: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)  # Yjs 文档快照
    last_snapshot_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 最后快照时间
    active_users_count: Mapped[int] = mapped_column(Integer, default=0)  # 当前在线用户数
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CollaborationSession(Base):
    """用户协同会话记录"""
    __tablename__ = "collaboration_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    room_id: Mapped[str] = mapped_column(String(36), ForeignKey("collaboration_rooms.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)  # 用户ID
    user_name: Mapped[str] = mapped_column(String(100), nullable=False)  # 用户名
    connection_id: Mapped[str] = mapped_column(String(100), nullable=False)  # WebSocket 连接ID
    cursor_position: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 光标位置
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # 是否在线
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    left_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CollaborationEvent(Base):
    """协同编辑事件日志"""
    __tablename__ = "collaboration_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    room_id: Mapped[str] = mapped_column(String(36), ForeignKey("collaboration_rooms.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # join, leave, edit, cursor_move
    event_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
