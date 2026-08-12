"""
实时协同编辑服务

基于 Yjs CRDT 算法和 Redis 实现多用户无冲突协同编辑
"""
import json
import logging
import asyncio
from typing import Dict, Set, Optional, List
from datetime import datetime
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.collaboration_models import CollaborationRoom, CollaborationSession, CollaborationEvent
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CollaborationService:
    """协同编辑服务"""

    def __init__(self):
        self.redis: Optional[Redis] = None
        self.rooms: Dict[str, Set[str]] = {}  # room_id -> set of connection_ids
        self._lock = asyncio.Lock()

    async def init_redis(self):
        """初始化 Redis 连接"""
        if not self.redis:
            try:
                self.redis = Redis.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                # 测试连接
                await self.redis.ping()
                logger.info("CollaborationService Redis 连接已建立")
            except Exception as e:
                logger.warning(f"Redis 连接失败，使用内存存储: {e}")
                self.redis = None

    async def close(self):
        """关闭 Redis 连接"""
        if self.redis:
            await self.redis.close()
            logger.info("CollaborationService Redis 连接已关闭")

    async def create_or_get_room(
        self,
        chapter_id: str,
        room_name: str,
        db: AsyncSession,
    ) -> dict:
        """创建或获取协同编辑房间"""
        # 先检查房间名称是否已存在
        stmt = select(CollaborationRoom).where(CollaborationRoom.room_name == room_name)
        result = await db.execute(stmt)
        existing_room = result.scalar_one_or_none()

        if existing_room:
            # 房间名称已存在，返回错误
            raise ValueError(f"房间名称 '{room_name}' 已存在")

        # 创建新房间
        room = CollaborationRoom(
            chapter_id=chapter_id,
            room_name=room_name,
        )
        db.add(room)
        await db.commit()
        await db.refresh(room)
        logger.info("创建协同编辑房间 (room_id=%s, chapter_id=%s)", room.id, chapter_id)

        return {
            "room_id": room.id,
            "chapter_id": room.chapter_id,
            "room_name": room.room_name,
            "active_users_count": room.active_users_count,
        }

    async def join_room(
        self,
        room_id: str,
        user_id: str,
        user_name: str,
        connection_id: str,
        db: AsyncSession,
    ) -> dict:
        """用户加入房间"""
        await self.init_redis()

        # 创建会话记录
        session = CollaborationSession(
            room_id=room_id,
            user_id=user_id,
            user_name=user_name,
            connection_id=connection_id,
            is_active=True,
        )
        db.add(session)

        # 记录事件
        event = CollaborationEvent(
            room_id=room_id,
            user_id=user_id,
            event_type="join",
            event_data={"user_name": user_name, "connection_id": connection_id},
        )
        db.add(event)

        await db.commit()

        # 更新房间用户列表
        if self.redis:
            # 使用 Redis
            redis_key = f"room:{room_id}:users"
            await self.redis.sadd(redis_key, connection_id)
            await self.redis.expire(redis_key, 86400)  # 24小时过期
            user_count = await self.redis.scard(redis_key)
        else:
            # 使用内存存储
            if room_id not in self.rooms:
                self.rooms[room_id] = set()
            self.rooms[room_id].add(connection_id)
            user_count = len(self.rooms[room_id])

        # 更新房间在线人数
        stmt = (
            update(CollaborationRoom)
            .where(CollaborationRoom.id == room_id)
            .values(active_users_count=user_count)
        )
        await db.execute(stmt)
        await db.commit()

        # 广播用户加入事件
        await self._broadcast_event(
            room_id,
            {
                "type": "user_joined",
                "user_id": user_id,
                "user_name": user_name,
                "connection_id": connection_id,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        logger.info("用户加入房间 (room_id=%s, user=%s, conn=%s)", room_id, user_name, connection_id)

        return {
            "session_id": session.id,
            "room_id": room_id,
            "user_count": user_count,
        }

    async def leave_room(
        self,
        room_id: str,
        user_id: str,
        connection_id: str,
        db: AsyncSession,
    ):
        """用户离开房间"""
        await self.init_redis()

        # 更新会话状态
        stmt = (
            update(CollaborationSession)
            .where(
                CollaborationSession.room_id == room_id,
                CollaborationSession.connection_id == connection_id,
            )
            .values(is_active=False, left_at=datetime.utcnow())
        )
        await db.execute(stmt)

        # 记录事件
        event = CollaborationEvent(
            room_id=room_id,
            user_id=user_id,
            event_type="leave",
            event_data={"connection_id": connection_id},
        )
        db.add(event)
        await db.commit()

        # 从用户列表移除
        if self.redis:
            # 使用 Redis
            redis_key = f"room:{room_id}:users"
            await self.redis.srem(redis_key, connection_id)
            user_count = await self.redis.scard(redis_key)
        else:
            # 使用内存存储
            if room_id in self.rooms:
                self.rooms[room_id].discard(connection_id)
                user_count = len(self.rooms[room_id])
                if user_count == 0:
                    del self.rooms[room_id]
            else:
                user_count = 0

        # 更新房间在线人数
        stmt = (
            update(CollaborationRoom)
            .where(CollaborationRoom.id == room_id)
            .values(active_users_count=user_count)
        )
        await db.execute(stmt)
        await db.commit()

        # 广播用户离开事件
        await self._broadcast_event(
            room_id,
            {
                "type": "user_left",
                "user_id": user_id,
                "connection_id": connection_id,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        logger.info("用户离开房间 (room_id=%s, user_id=%s, conn=%s)", room_id, user_id, connection_id)

    async def broadcast_yjs_update(
        self,
        room_id: str,
        update_data: bytes,
        sender_connection_id: str,
    ):
        """广播 Yjs 更新到房间内其他用户"""
        await self.init_redis()

        if self.redis:
            # 发布到 Redis 频道
            channel = f"room:{room_id}:yjs"
            message = {
                "type": "yjs_update",
                "sender": sender_connection_id,
                "update": update_data.hex(),  # 转换为十六进制字符串
                "timestamp": datetime.utcnow().isoformat(),
            }
            await self.redis.publish(channel, json.dumps(message))

        logger.debug("广播 Yjs 更新 (room_id=%s, sender=%s)", room_id, sender_connection_id)

    async def update_cursor_position(
        self,
        room_id: str,
        user_id: str,
        connection_id: str,
        cursor_position: dict,
        db: AsyncSession,
    ):
        """更新用户光标位置"""
        await self.init_redis()

        # 更新数据库
        stmt = (
            update(CollaborationSession)
            .where(
                CollaborationSession.room_id == room_id,
                CollaborationSession.connection_id == connection_id,
            )
            .values(cursor_position=cursor_position)
        )
        await db.execute(stmt)
        await db.commit()

        # 广播光标位置
        await self._broadcast_event(
            room_id,
            {
                "type": "cursor_update",
                "user_id": user_id,
                "connection_id": connection_id,
                "position": cursor_position,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def save_snapshot(
        self,
        room_id: str,
        yjs_state_vector: bytes,
        yjs_document: bytes,
        db: AsyncSession,
    ):
        """保存 Yjs 文档快照"""
        stmt = (
            update(CollaborationRoom)
            .where(CollaborationRoom.id == room_id)
            .values(
                yjs_state_vector=yjs_state_vector,
                yjs_document=yjs_document,
                last_snapshot_at=datetime.utcnow(),
            )
        )
        await db.execute(stmt)
        await db.commit()

        logger.info("保存 Yjs 快照 (room_id=%s)", room_id)

    async def get_room_users(self, room_id: str, db: AsyncSession) -> List[dict]:
        """获取房间内的在线用户列表"""
        stmt = (
            select(CollaborationSession)
            .where(
                CollaborationSession.room_id == room_id,
                CollaborationSession.is_active == True,
            )
            .order_by(CollaborationSession.joined_at)
        )
        result = await db.execute(stmt)
        sessions = result.scalars().all()

        return [
            {
                "user_id": session.user_id,
                "user_name": session.user_name,
                "connection_id": session.connection_id,
                "cursor_position": session.cursor_position,
                "joined_at": session.joined_at.isoformat(),
            }
            for session in sessions
        ]

    async def _broadcast_event(self, room_id: str, event: dict):
        """广播事件到房间"""
        await self.init_redis()
        if self.redis:
            channel = f"room:{room_id}:events"
            await self.redis.publish(channel, json.dumps(event))

    async def subscribe_room_events(self, room_id: str):
        """订阅房间事件（用于 WebSocket 连接）"""
        await self.init_redis()
        if self.redis:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(f"room:{room_id}:events", f"room:{room_id}:yjs")
            return pubsub
        return None


# 全局单例
collaboration_service = CollaborationService()
