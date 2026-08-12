"""
WebSocket 协同编辑路由

提供实时协同编辑的 WebSocket 接口
"""
import json
import logging
import asyncio
from typing import Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.database import get_async_session
from backend.services.collaboration_service import collaboration_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/collaboration", tags=["实时协同"])


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        # room_id -> {connection_id: websocket}
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, room_id: str, connection_id: str, websocket: WebSocket):
        """建立连接"""
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = {}
        self.active_connections[room_id][connection_id] = websocket
        logger.info("WebSocket 连接建立 (room=%s, conn=%s)", room_id, connection_id)

    def disconnect(self, room_id: str, connection_id: str):
        """断开连接"""
        if room_id in self.active_connections:
            self.active_connections[room_id].pop(connection_id, None)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]
        logger.info("WebSocket 连接断开 (room=%s, conn=%s)", room_id, connection_id)

    async def broadcast(self, room_id: str, message: dict, exclude_connection: str = None):
        """广播消息到房间内所有连接"""
        if room_id not in self.active_connections:
            return

        disconnected = []
        for connection_id, websocket in self.active_connections[room_id].items():
            if connection_id == exclude_connection:
                continue
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error("发送消息失败 (conn=%s): %s", connection_id, e)
                disconnected.append(connection_id)

        # 清理断开的连接
        for connection_id in disconnected:
            self.disconnect(room_id, connection_id)


manager = ConnectionManager()


async def _read_pubsub(pubsub) -> dict | None:
    """从 Redis pubsub 读取一条消息"""
    try:
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
        return message
    except Exception:
        return None


@router.websocket("/ws/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
    user_id: str = Query(...),
    user_name: str = Query(...),
    connection_id: str = Query(...),
):
    """
    WebSocket 协同编辑端点

    客户端连接后可以：
    1. 接收其他用户的 Yjs 更新
    2. 发送自己的 Yjs 更新
    3. 接收和发送光标位置
    4. 接收用户加入/离开通知
    """
    # 建立连接
    await manager.connect(room_id, connection_id, websocket)

    # 获取数据库会话
    async for db in get_async_session():
        try:
            # 用户加入房间
            join_result = await collaboration_service.join_room(
                room_id=room_id,
                user_id=user_id,
                user_name=user_name,
                connection_id=connection_id,
                db=db,
            )

            # 发送欢迎消息
            await websocket.send_json({
                "type": "welcome",
                "session_id": join_result["session_id"],
                "user_count": join_result["user_count"],
            })

            # 广播更新后的用户列表给房间内所有人
            users = await collaboration_service.get_room_users(room_id, db)
            await manager.broadcast(room_id, {
                "type": "user_list",
                "users": users,
            })

            # 订阅 Redis 事件
            pubsub = await collaboration_service.subscribe_room_events(room_id)

            # 主消息循环：并发监听客户端消息和 Redis pubsub
            try:
                while True:
                    # 并发等待：客户端消息 or Redis pubsub 消息
                    ws_task = asyncio.create_task(websocket.receive_text())
                    pubsub_task = asyncio.create_task(_read_pubsub(pubsub)) if pubsub else asyncio.create_task(asyncio.sleep(3600))

                    done, pending = await asyncio.wait(
                        [ws_task, pubsub_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    # 取消未完成的任务
                    for task in pending:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass

                    # 处理客户端消息
                    if ws_task in done:
                        try:
                            data = ws_task.result()
                            message = json.loads(data)
                            message_type = message.get("type")

                            if message_type == "yjs_update":
                                # Yjs 文档更新
                                update_hex = message.get("update")
                                if update_hex:
                                    update_bytes = bytes.fromhex(update_hex)
                                    # 广播到其他用户
                                    await collaboration_service.broadcast_yjs_update(
                                        room_id=room_id,
                                        update_data=update_bytes,
                                        sender_connection_id=connection_id,
                                    )
                                    # 通过 WebSocket 广播
                                    await manager.broadcast(
                                        room_id,
                                        {
                                            "type": "yjs_update",
                                            "sender": connection_id,
                                            "update": update_hex,
                                        },
                                        exclude_connection=connection_id,
                                    )

                            elif message_type == "cursor_update":
                                # 光标位置更新
                                cursor_position = message.get("position")
                                if cursor_position:
                                    await collaboration_service.update_cursor_position(
                                        room_id=room_id,
                                        user_id=user_id,
                                        connection_id=connection_id,
                                        cursor_position=cursor_position,
                                        db=db,
                                    )
                                    # 广播光标位置
                                    await manager.broadcast(
                                        room_id,
                                        {
                                            "type": "cursor_update",
                                            "user_id": user_id,
                                            "connection_id": connection_id,
                                            "position": cursor_position,
                                        },
                                        exclude_connection=connection_id,
                                    )

                            elif message_type == "save_snapshot":
                                # 保存文档快照
                                state_vector_hex = message.get("state_vector")
                                document_hex = message.get("document")
                                if state_vector_hex and document_hex:
                                    await collaboration_service.save_snapshot(
                                        room_id=room_id,
                                        yjs_state_vector=bytes.fromhex(state_vector_hex),
                                        yjs_document=bytes.fromhex(document_hex),
                                        db=db,
                                    )
                                    await websocket.send_json({
                                        "type": "snapshot_saved",
                                        "success": True,
                                    })

                            elif message_type == "ping":
                                # 心跳
                                await websocket.send_json({"type": "pong"})

                        except WebSocketDisconnect:
                            break
                        except Exception as e:
                            logger.error("处理客户端消息错误: %s", e)

                    # 处理 Redis pubsub 消息
                    if pubsub_task in done and pubsub:
                        try:
                            pubsub_msg = pubsub_task.result()
                            if pubsub_msg and pubsub_msg.get("type") == "message":
                                event_data = json.loads(pubsub_msg["data"])
                                event_type = event_data.get("type")

                                if event_type in ("user_joined", "user_left"):
                                    # 用户加入/离开：广播更新后的用户列表
                                    users = await collaboration_service.get_room_users(room_id, db)
                                    await manager.broadcast(room_id, {
                                        "type": "user_list",
                                        "users": users,
                                    })
                                elif event_type == "yjs_update":
                                    # Redis 广播的 Yjs 更新（来自其他服务器实例）
                                    sender = event_data.get("sender")
                                    if sender != connection_id:
                                        await websocket.send_json({
                                            "type": "yjs_update",
                                            "sender": sender,
                                            "update": event_data.get("update"),
                                        })
                                elif event_type == "cursor_update":
                                    sender_conn = event_data.get("connection_id")
                                    if sender_conn != connection_id:
                                        await websocket.send_json(event_data)
                        except Exception as e:
                            logger.error("处理 Redis pubsub 消息错误: %s", e)

            except WebSocketDisconnect:
                logger.info("WebSocket 客户端断开 (room=%s, conn=%s)", room_id, connection_id)
            except Exception as e:
                logger.error("WebSocket 错误 (room=%s, conn=%s): %s", room_id, connection_id, e)
            finally:
                # 用户离开房间
                await collaboration_service.leave_room(
                    room_id=room_id,
                    user_id=user_id,
                    connection_id=connection_id,
                    db=db,
                )
                manager.disconnect(room_id, connection_id)
                if pubsub:
                    await pubsub.close()

        except Exception as e:
            logger.error("协同编辑会话错误: %s", e)
            manager.disconnect(room_id, connection_id)


from pydantic import BaseModel


class CreateRoomRequest(BaseModel):
    chapter_id: str
    room_name: str


@router.post("/rooms")
async def create_room(
    request: CreateRoomRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """创建协同编辑房间"""
    try:
        room = await collaboration_service.create_or_get_room(
            chapter_id=request.chapter_id,
            room_name=request.room_name,
            db=db,
        )
        return room
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/rooms")
async def list_rooms(
    db: AsyncSession = Depends(get_async_session),
):
    """获取所有协同编辑房间"""
    from sqlalchemy import select
    from backend.models.collaboration_models import CollaborationRoom

    try:
        result = await db.execute(select(CollaborationRoom).order_by(CollaborationRoom.created_at.desc()))
        rooms = result.scalars().all()

        return {
            "rooms": [
                {
                    "room_id": room.id,
                    "room_name": room.room_name,
                    "chapter_id": room.chapter_id,
                    "created_at": room.created_at.isoformat() if room.created_at else None,
                    "active_users_count": room.active_users_count,
                }
                for room in rooms
            ]
        }
    except Exception as e:
        logger.error(f"获取房间列表失败: {e}")
        return {"rooms": []}


@router.delete("/rooms/{room_id}")
async def delete_room(
    room_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    """删除协同编辑房间"""
    from sqlalchemy import select, delete
    from backend.models.collaboration_models import CollaborationRoom, CollaborationSession, CollaborationEvent
    from fastapi import HTTPException

    try:
        # 检查房间是否存在
        result = await db.execute(select(CollaborationRoom).where(CollaborationRoom.id == room_id))
        room = result.scalar_one_or_none()

        if not room:
            raise HTTPException(status_code=404, detail="房间不存在")

        # 删除相关的会话记录
        await db.execute(delete(CollaborationSession).where(CollaborationSession.room_id == room_id))

        # 删除相关的事件记录
        await db.execute(delete(CollaborationEvent).where(CollaborationEvent.room_id == room_id))

        # 删除房间
        await db.delete(room)
        await db.commit()

        logger.info(f"删除协同编辑房间: {room_id}")
        return {"success": True, "message": "房间已删除"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除房间失败: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"删除房间失败: {str(e)}")


@router.get("/rooms/{room_id}/snapshot")
async def get_room_snapshot(
    room_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    """获取房间文档快照"""
    from sqlalchemy import select
    from backend.models.collaboration_models import CollaborationRoom

    result = await db.execute(select(CollaborationRoom).where(CollaborationRoom.id == room_id))
    room = result.scalar_one_or_none()

    if not room:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="房间不存在")

    return {
        "room_id": room.id,
        "yjs_document": room.yjs_document.hex() if room.yjs_document else None,
        "yjs_state_vector": room.yjs_state_vector.hex() if room.yjs_state_vector else None,
        "last_snapshot_at": room.last_snapshot_at.isoformat() if room.last_snapshot_at else None,
    }


@router.get("/rooms/{room_id}/users")
async def get_room_users(
    room_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    """获取房间内的在线用户"""
    users = await collaboration_service.get_room_users(room_id, db)
    return {"users": users}
