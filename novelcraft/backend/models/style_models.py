"""
风格迁移相关数据模型

简化版本，去掉缓存相关表
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.database import Base


def gen_uuid():
    """生成 UUID 字符串"""
    return str(uuid.uuid4())


class StyleTransferTask(Base):
    """风格迁移任务记录"""
    __tablename__ = "style_transfer_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    style_id: Mapped[str] = mapped_column(String(100), nullable=False)  # 目标作家风格标识
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    transformed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, processing, completed, failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    inference_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 推理耗时（毫秒）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class StyleModelInfo(Base):
    """风格模型信息表"""
    __tablename__ = "style_model_info"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    style_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)  # 风格标识（如 "gulong"）
    style_name: Mapped[str] = mapped_column(String(100), nullable=False)  # 作家名称（如 "古龙"）
    description: Mapped[str] = mapped_column(Text, nullable=False)  # 风格描述
    author_example: Mapped[str | None] = mapped_column(Text, nullable=True)  # 作家代表作品示例
    lora_adapter_name: Mapped[str | None] = mapped_column(String(200), nullable=True)  # LoRA 适配器名称
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # 是否启用
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
