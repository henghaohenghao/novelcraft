"""
人物 API 路由

提供人物创建、更新、删除、关系管理和图谱查询功能。
"""
import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.database import get_db
from backend.models.db_models import Character, Faction, Location, Event, Project
from backend.models.schemas import (
    CharacterCreate, CharacterUpdate, CharacterResponse,
    RelationshipCreate, RelationshipResponse,
    FactionCreate, FactionResponse,
    LocationCreate, LocationResponse,
    EventCreate, EventResponse,
)
from backend.services.neo4j_service import neo4j_service
from backend.services.llm_service import llm_service

router = APIRouter(prefix="/api/characters", tags=["characters"])


@router.post("", response_model=CharacterResponse)
async def create_character(req: CharacterCreate, db: AsyncSession = Depends(get_db)):
    """创建人物"""
    character = Character(
        project_id=req.project_id,
        name=req.name,
        alias=req.alias,
        description=req.description,
        personality=req.personality,
        background=req.background,
        appearance=req.appearance,
        abilities=req.abilities,
        status=req.status,
    )
    db.add(character)
    await db.commit()
    await db.refresh(character)

    await asyncio.to_thread(neo4j_service.create_character, req.project_id, {
        "id": character.id,
        "name": character.name,
        "alias": character.alias,
        "description": character.description,
        "personality": character.personality,
        "background": character.background,
        "appearance": character.appearance,
        "abilities": character.abilities,
        "status": character.status,
    })

    return character


@router.get("/project/{project_id}", response_model=list[CharacterResponse])
async def list_characters(project_id: str, db: AsyncSession = Depends(get_db)):
    """获取项目人物列表"""
    result = await db.execute(
        select(Character).where(Character.project_id == project_id).order_by(Character.created_at)
    )
    return result.scalars().all()


@router.get("/{character_id}", response_model=CharacterResponse)
async def get_character(character_id: str, db: AsyncSession = Depends(get_db)):
    """获取人物详情"""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="人物不存在")
    return character


@router.put("/{character_id}", response_model=CharacterResponse)
async def update_character(character_id: str, req: CharacterUpdate, db: AsyncSession = Depends(get_db)):
    """更新人物信息"""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="人物不存在")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(character, key, value)

    await db.commit()
    await db.refresh(character)

    await asyncio.to_thread(neo4j_service.update_character, character_id, update_data)

    return character


@router.delete("/{character_id}")
async def delete_character(character_id: str, db: AsyncSession = Depends(get_db)):
    """删除人物及其图数据"""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="人物不存在")

    await asyncio.to_thread(neo4j_service.delete_character, character_id)
    await db.delete(character)
    await db.commit()
    return {"message": "人物已删除"}


@router.post("/relationships", response_model=RelationshipResponse)
async def create_relationship(req: RelationshipCreate, db: AsyncSession = Depends(get_db)):
    """创建人物关系"""
    source_result = await db.execute(select(Character).where(Character.id == req.source_id))
    target_result = await db.execute(select(Character).where(Character.id == req.target_id))
    source = source_result.scalar_one_or_none()
    target = target_result.scalar_one_or_none()

    if not source or not target:
        raise HTTPException(status_code=404, detail="人物不存在")

    await asyncio.to_thread(neo4j_service.create_relationship, req.source_id, req.target_id, req.relation_type, req.description)

    return RelationshipResponse(
        source_id=req.source_id,
        source_name=source.name,
        target_id=req.target_id,
        target_name=target.name,
        relation_type=req.relation_type,
        description=req.description,
    )


@router.get("/{character_id}/relations", response_model=list[RelationshipResponse])
async def get_character_relations(character_id: str):
    """查询人物关系列表"""
    relations = await asyncio.to_thread(neo4j_service.get_character_relations, character_id)
    return [
        RelationshipResponse(
            source_id=character_id,
            source_name=r["source_name"],
            target_id=r["target_id"],
            target_name=r["target_name"],
            relation_type=r["relation_type"],
            description=r.get("description", ""),
        )
        for r in relations
    ]


@router.delete("/relationships")
async def delete_relationship(source_id: str, target_id: str, relation_type: str):
    """删除人物关系"""
    await asyncio.to_thread(neo4j_service.delete_relationship, source_id, target_id, relation_type)
    return {"message": "关系已删除"}


@router.get("/project/{project_id}/graph")
async def get_project_graph(project_id: str):
    """获取项目完整人物关系图谱"""
    return await asyncio.to_thread(neo4j_service.get_project_graph, project_id)


@router.post("/factions", response_model=FactionResponse)
async def create_faction(req: FactionCreate, db: AsyncSession = Depends(get_db)):
    """创建阵营"""
    faction = Faction(
        project_id=req.project_id,
        name=req.name,
        description=req.description,
        goal=req.goal,
    )
    db.add(faction)
    await db.commit()
    await db.refresh(faction)

    await asyncio.to_thread(neo4j_service.create_faction, req.project_id, {
        "id": faction.id,
        "name": faction.name,
        "description": faction.description,
        "goal": faction.goal,
    })

    return faction


@router.get("/factions/project/{project_id}", response_model=list[FactionResponse])
async def list_factions(project_id: str, db: AsyncSession = Depends(get_db)):
    """获取项目阵营列表"""
    result = await db.execute(select(Faction).where(Faction.project_id == project_id))
    return result.scalars().all()


@router.post("/locations", response_model=LocationResponse)
async def create_location(req: LocationCreate, db: AsyncSession = Depends(get_db)):
    """创建地点"""
    location = Location(
        project_id=req.project_id,
        name=req.name,
        description=req.description,
        location_type=req.location_type,
    )
    db.add(location)
    await db.commit()
    await db.refresh(location)

    await asyncio.to_thread(neo4j_service.create_location, req.project_id, {
        "id": location.id,
        "name": location.name,
        "description": location.description,
        "location_type": location.location_type,
    })

    return location


@router.get("/locations/project/{project_id}", response_model=list[LocationResponse])
async def list_locations(project_id: str, db: AsyncSession = Depends(get_db)):
    """获取项目地点列表"""
    result = await db.execute(select(Location).where(Location.project_id == project_id))
    return result.scalars().all()


@router.post("/events", response_model=EventResponse)
async def create_event(req: EventCreate, db: AsyncSession = Depends(get_db)):
    """创建事件"""
    event = Event(
        project_id=req.project_id,
        name=req.name,
        description=req.description,
        event_time=req.event_time,
        chapter_id=req.chapter_id,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    await asyncio.to_thread(neo4j_service.create_event, req.project_id, {
        "id": event.id,
        "name": event.name,
        "description": event.description,
        "event_time": event.event_time,
        "chapter_id": event.chapter_id,
    })

    return event


@router.get("/events/project/{project_id}", response_model=list[EventResponse])
async def list_events(project_id: str, db: AsyncSession = Depends(get_db)):
    """获取项目事件列表"""
    result = await db.execute(select(Event).where(Event.project_id == project_id))
    return result.scalars().all()


@router.post("/generate-from-synopsis")
async def generate_characters_from_synopsis(project_id: str, synopsis: str, db: AsyncSession = Depends(get_db)):
    """根据梗概 AI 自动生成人物列表和人物关系"""
    import logging
    logger = logging.getLogger(__name__)

    # 生成人物列表
    raw_response = await llm_service.generate_characters_from_synopsis(synopsis)

    try:
        if "```json" in raw_response:
            raw_response = raw_response.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_response:
            raw_response = raw_response.split("```")[1].split("```")[0].strip()
        characters_data = json.loads(raw_response)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="人物生成解析失败")

    created = []
    character_map = {}  # 姓名 -> character_id 映射

    # 创建人物
    for char_data in characters_data:
        character = Character(
            project_id=project_id,
            name=char_data.get("name", "未命名"),
            personality=char_data.get("personality", ""),
            background=char_data.get("background", ""),
            appearance=char_data.get("appearance", ""),
            abilities=char_data.get("abilities", ""),
            description=char_data.get("role", ""),
        )
        db.add(character)
        await db.flush()

        await asyncio.to_thread(neo4j_service.create_character, project_id, {
            "id": character.id,
            "name": character.name,
            "alias": "",
            "description": character.description,
            "personality": character.personality,
            "background": character.background,
            "appearance": character.appearance,
            "abilities": character.abilities,
            "status": "alive",
        })
        created.append(character)
        character_map[character.name] = character.id

    await db.commit()
    for c in created:
        await db.refresh(c)

    # 自动生成人物关系
    if len(created) > 1 and neo4j_service.available:
        logger.info(f"开始为 {len(created)} 个人物生成关系")
        try:
            # 调用LLM分析人物关系
            relations_prompt = f"""根据以下人物信息和梗概，分析人物之间可能存在的关系。

梗概：
{synopsis}

人物列表：
{json.dumps([{'name': c.name, 'role': c.description, 'personality': c.personality} for c in created], ensure_ascii=False, indent=2)}

请输出人物之间的关系，格式为JSON数组，每个元素包含：
- source_name: 源人物姓名
- target_name: 目标人物姓名
- relation_type: 关系类型（必须是以下之一：FRIEND, ENEMY, RELATIVE, MENTOR, LOVER, COLLEAGUE, RIVAL, SUBORDINATE, MASTER, ALLY）
- description: 关系描述

请直接输出JSON数组。"""

            messages = [
                {"role": "system", "content": "你是一位专业的小说人物关系分析师。"},
                {"role": "user", "content": relations_prompt}
            ]
            relations_response = await llm_service.chat(messages, temperature=0.7, max_tokens=2048)

            # 解析关系数据
            if "```json" in relations_response:
                relations_response = relations_response.split("```json")[1].split("```")[0].strip()
            elif "```" in relations_response:
                relations_response = relations_response.split("```")[1].split("```")[0].strip()

            relations_data = json.loads(relations_response)

            # 创建关系
            for rel_data in relations_data:
                source_name = rel_data.get("source_name", "")
                target_name = rel_data.get("target_name", "")
                relation_type = rel_data.get("relation_type", "ALLY")
                description = rel_data.get("description", "")

                if source_name in character_map and target_name in character_map:
                    source_id = character_map[source_name]
                    target_id = character_map[target_name]

                    try:
                        await asyncio.to_thread(
                            neo4j_service.create_relationship,
                            source_id=source_id,
                            target_id=target_id,
                            rel_type=relation_type,
                            description=description
                        )
                        logger.info(f"创建关系: {source_name} --[{relation_type}]--> {target_name}")
                    except Exception as e:
                        logger.warning(f"创建关系失败: {source_name} -> {target_name}, 错误: {str(e)}")

        except Exception as e:
            logger.error(f"生成人物关系失败: {str(e)}", exc_info=True)

    return [CharacterResponse.model_validate(c) for c in created]