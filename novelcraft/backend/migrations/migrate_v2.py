"""
数据库迁移脚本 - V2.0（简化版）

添加风格迁移相关表（无缓存表）
"""
from sqlalchemy import create_engine
from backend.models.database import Base
from backend.models.db_models import (
    Project, Outline, Chapter, Character, Faction, Location, Event
)
from backend.models.style_models import StyleTransferTask, StyleModelInfo
from backend.models.collaboration_models import (
    CollaborationRoom, CollaborationSession, CollaborationEvent
)
from backend.config import get_settings

settings = get_settings()


def run_migration():
    """运行数据库迁移"""
    print("开始数据库迁移 (V2.0 - 简化版)...")

    # 创建同步引擎
    engine = create_engine(settings.database_url_sync)

    # 创建所有表
    Base.metadata.create_all(engine)

    print("数据库迁移完成！")
    print("\n新增表：")
    print("  - style_transfer_tasks (风格迁移任务)")
    print("  - style_model_info (风格模型信息)")
    print("  - collaboration_rooms (协同编辑房间)")
    print("  - collaboration_sessions (协同会话)")
    print("  - collaboration_events (协同事件)")


if __name__ == "__main__":
    run_migration()
