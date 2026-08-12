import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.database import get_db
from backend.models.db_models import Project, User, Chapter
from backend.models.schemas import ProjectCreate, ProjectUpdate, ProjectResponse
from backend.utils.auth import get_current_user

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse)
async def create_project(
    req: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    project = Project(
        title=req.title,
        synopsis=req.synopsis,
        genre=req.genre,
        style=req.style,
        user_id=current_user.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Project)
        .where(Project.user_id == current_user.id)
        .order_by(Project.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    req: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)

    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}")
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """删除项目及其在Neo4j和Qdrant中的所有相关数据"""
    import logging
    logger = logging.getLogger(__name__)

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 删除Neo4j中的项目图谱数据
    from backend.services.neo4j_service import neo4j_service
    if neo4j_service.available:
        try:
            def _delete_neo4j_data():
                with neo4j_service.driver.session() as session:
                    session.run(
                        "MATCH (n) WHERE n.project_id = $project_id DETACH DELETE n",
                        project_id=project_id
                    )
            await asyncio.to_thread(_delete_neo4j_data)
            logger.info(f"已删除项目 {project_id} 在Neo4j中的所有数据")
        except Exception as e:
            logger.error(f"删除Neo4j数据失败: {str(e)}", exc_info=True)

    # 删除Qdrant中的项目向量数据
    from backend.services.qdrant_service import qdrant_service
    if qdrant_service.available:
        try:
            await asyncio.to_thread(qdrant_service.delete_project_data, project_id)
            logger.info(f"已删除项目 {project_id} 在Qdrant中的所有数据")
        except Exception as e:
            logger.error(f"删除Qdrant数据失败: {str(e)}", exc_info=True)

    # 删除协同编辑相关数据（collaboration_rooms 引用了 chapters，需在级联删除 chapters 前清理）
    from backend.models.collaboration_models import CollaborationRoom, CollaborationSession, CollaborationEvent
    from sqlalchemy import delete as sa_delete

    chapter_ids_result = await db.execute(
        select(Chapter.id).where(Chapter.project_id == project_id)
    )
    chapter_ids = [row[0] for row in chapter_ids_result.all()]

    if chapter_ids:
        room_ids_result = await db.execute(
            select(CollaborationRoom.id).where(CollaborationRoom.chapter_id.in_(chapter_ids))
        )
        room_ids = [row[0] for row in room_ids_result.all()]

        if room_ids:
            await db.execute(sa_delete(CollaborationEvent).where(CollaborationEvent.room_id.in_(room_ids)))
            await db.execute(sa_delete(CollaborationSession).where(CollaborationSession.room_id.in_(room_ids)))
            await db.execute(sa_delete(CollaborationRoom).where(CollaborationRoom.id.in_(room_ids)))
            logger.info(f"已删除项目 {project_id} 关联的 {len(room_ids)} 个协同编辑房间")

    # 删除PostgreSQL中的项目数据（级联删除相关表）
    await db.delete(project)
    await db.commit()

    logger.info(f"项目 {project_id} 已完全删除")
    return {"message": "项目已删除，包括Neo4j和Qdrant中的所有相关数据"}