import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.database import get_db
from backend.models.db_models import Outline, Project
from backend.models.schemas import (
    OutlineCreate, OutlineUpdate, OutlineResponse,
    OutlineTreeResponse, GenerateOutlineRequest,
)
from backend.services.llm_service import llm_service

router = APIRouter(prefix="/api/outlines", tags=["outlines"])


@router.post("", response_model=OutlineResponse)
async def create_outline(req: OutlineCreate, db: AsyncSession = Depends(get_db)):
    outline = Outline(
        project_id=req.project_id,
        parent_id=req.parent_id,
        title=req.title,
        content=req.content,
        node_type=req.node_type,
        sort_order=req.sort_order,
        depth=req.depth,
        branch_label=req.branch_label,
    )
    db.add(outline)
    await db.commit()
    await db.refresh(outline)
    return outline


@router.get("/project/{project_id}", response_model=list[OutlineResponse])
async def list_outlines(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Outline).where(Outline.project_id == project_id).order_by(Outline.sort_order)
    )
    return result.scalars().all()


@router.get("/project/{project_id}/tree", response_model=list[OutlineTreeResponse])
async def get_outline_tree(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Outline)
        .where(Outline.project_id == project_id)
        .order_by(Outline.sort_order)
    )
    outlines = result.scalars().all()

    outline_map = {}
    roots = []
    for o in outlines:
        node = OutlineTreeResponse(
            id=o.id,
            title=o.title,
            content=o.content,
            node_type=o.node_type,
            sort_order=o.sort_order,
            depth=o.depth,
            branch_label=o.branch_label,
            children=[],
        )
        outline_map[o.id] = node

    for o in outlines:
        node = outline_map[o.id]
        if o.parent_id and o.parent_id in outline_map:
            outline_map[o.parent_id].children.append(node)
        else:
            roots.append(node)

    return roots


@router.put("/{outline_id}", response_model=OutlineResponse)
async def update_outline(outline_id: str, req: OutlineUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Outline).where(Outline.id == outline_id))
    outline = result.scalar_one_or_none()
    if not outline:
        raise HTTPException(status_code=404, detail="大纲节点不存在")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(outline, key, value)

    await db.commit()
    await db.refresh(outline)
    return outline


@router.delete("/{outline_id}")
async def delete_outline(outline_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Outline).where(Outline.id == outline_id))
    outline = result.scalar_one_or_none()
    if not outline:
        raise HTTPException(status_code=404, detail="大纲节点不存在")

    child_result = await db.execute(select(Outline).where(Outline.parent_id == outline_id))
    children = child_result.scalars().all()
    for child in children:
        child.parent_id = outline.parent_id

    await db.delete(outline)
    await db.commit()
    return {"message": "大纲节点已删除"}


@router.post("/generate")
async def generate_outline(req: GenerateOutlineRequest, db: AsyncSession = Depends(get_db)):
    """AI生成大纲并将大纲内容向量化存储到Qdrant

    当项目中已存在大纲时，接着已有大纲的最后一章继续生成，避免每次都从第一章开始。
    """
    import logging
    logger = logging.getLogger(__name__)

    project_result = await db.execute(select(Project).where(Project.id == req.project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 查询已有大纲，确定续写的起始位置并为 LLM 提供上下文
    existing_result = await db.execute(
        select(Outline)
        .where(Outline.project_id == req.project_id)
        .order_by(Outline.sort_order)
    )
    existing_outlines = existing_result.scalars().all()

    if existing_outlines:
        max_sort_order = max(o.sort_order for o in existing_outlines)
        start_sort_order = max_sort_order + 1
        existing_context = "\n".join(
            f"第{o.sort_order + 1}章 {o.title}：{o.content}"
            for o in existing_outlines
            if o.content
        )
    else:
        start_sort_order = 0
        existing_context = ""

    start_chapter_display = start_sort_order + 1

    raw_response = await llm_service.generate_outline(
        req.synopsis,
        req.chapter_count,
        existing_outlines=existing_context,
        start_chapter=start_chapter_display,
    )

    try:
        if "```json" in raw_response:
            raw_response = raw_response.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_response:
            raw_response = raw_response.split("```")[1].split("```")[0].strip()
        chapters = json.loads(raw_response)
    except json.JSONDecodeError:
        chapters = [
            {"title": f"第{start_sort_order + i + 1}章", "content": "待规划"}
            for i in range(req.chapter_count)
        ]

    created_outlines = []
    for i, ch in enumerate(chapters):
        outline = Outline(
            project_id=req.project_id,
            title=ch.get("title", f"第{start_sort_order + i + 1}章"),
            content=ch.get("content", ""),
            node_type="chapter",
            sort_order=start_sort_order + i,
            depth=0,
        )
        db.add(outline)
        created_outlines.append(outline)

    await db.commit()
    for o in created_outlines:
        await db.refresh(o)

    # 将大纲内容向量化存储到Qdrant
    from backend.services.qdrant_service import qdrant_service
    if qdrant_service.available:
        try:
            from backend.services.embedding_service import embedding_service
            logger.info(f"开始向量化 {len(created_outlines)} 个大纲节点")

            for outline in created_outlines:
                if outline.content and len(outline.content) > 20:
                    try:
                        # 生成嵌入向量
                        text = f"{outline.title}\n{outline.content}"
                        embedding = await asyncio.to_thread(embedding_service.encode_single, text)

                        # 存储到Qdrant
                        await asyncio.to_thread(
                            qdrant_service.upsert_setting,
                            project_id=req.project_id,
                            setting_id=outline.id,
                            text=text,
                            embedding=embedding,
                            metadata={
                                "type": "outline",
                                "title": outline.title,
                                "sort_order": outline.sort_order,
                            }
                        )
                        logger.info(f"大纲节点 '{outline.title}' 已向量化")
                    except Exception as e:
                        logger.warning(f"向量化大纲节点 '{outline.title}' 失败: {str(e)}")

        except Exception as e:
            logger.error(f"向量化大纲失败: {str(e)}", exc_info=True)

    return [OutlineResponse.model_validate(o) for o in created_outlines]