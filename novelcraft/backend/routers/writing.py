"""
写作 API 路由

提供章节创建、生成、审查、修改和段落向量存储功能。
集成多智能体写作流水线，支持单句流式输出（SSE）与 Human-in-the-Loop 人工审核。
"""
import json
import asyncio
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langgraph.types import Command
from backend.models.database import get_db
from backend.models.db_models import Project, Outline, Chapter
from backend.models.schemas import (
    ChapterCreate, ChapterResponse, GenerateChapterRequest, HumanReviewDecision,
)
from backend.agents.graph import writing_graph
from backend.agents.state import WritingAgentState, StructuredReview
from backend.services.neo4j_service import neo4j_service
from backend.services.qdrant_service import qdrant_service
from backend.services.llm_service import llm_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/writing", tags=["writing"])

# Agent 中文名称映射（含人工审核节点）
AGENT_LABELS = {
    "supervisor": "总调度",
    "planner": "规划智能体",
    "writer": "写作智能体",
    "reviewer": "审查智能体",
    "reviser": "修改智能体",
    "human_review": "人工审核",
}


def _get_embedding_service():
    """获取嵌入服务（Qdrant 不可用时返回 None）"""
    if not qdrant_service.available:
        return None
    try:
        from backend.services.embedding_service import embedding_service
        return embedding_service
    except Exception:
        return None


@router.post("/chapters", response_model=ChapterResponse)
async def create_chapter(req: ChapterCreate, db: AsyncSession = Depends(get_db)):
    """创建新章节（幂等：同一 outline_id 已有章节则返回已存在的）"""
    # 防重复：同一大纲节点已创建过章节则直接返回
    if req.outline_id:
        existing = await db.execute(
            select(Chapter).where(Chapter.outline_id == req.outline_id)
        )
        existed = existing.scalar_one_or_none()
        if existed:
            return existed

    chapter = Chapter(
        project_id=req.project_id,
        outline_id=req.outline_id,
        title=req.title,
        chapter_number=req.chapter_number,
    )
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)
    return chapter


@router.get("/chapters/{chapter_id}", response_model=ChapterResponse)
async def get_chapter(chapter_id: str, db: AsyncSession = Depends(get_db)):
    """获取章节详情"""
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    return chapter


@router.get("/chapters/project/{project_id}", response_model=list[ChapterResponse])
async def list_chapters(project_id: str, db: AsyncSession = Depends(get_db)):
    """获取项目章节列表（按章节号排序）"""
    result = await db.execute(
        select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.chapter_number)
    )
    return result.scalars().all()


@router.get("/chapters", response_model=list[ChapterResponse])
async def list_all_chapters(db: AsyncSession = Depends(get_db)):
    """获取所有章节列表（按章节号排序），用于协同编辑等场景"""
    result = await db.execute(
        select(Chapter).order_by(Chapter.chapter_number)
    )
    return result.scalars().all()


async def _build_context(project_id: str, chapter_id: str, db: AsyncSession) -> dict:
    """构建章节生成所需的上下文：大纲、前文摘要、角色、世界观设定"""
    from backend.models.db_models import Character

    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()

    chapter_result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = chapter_result.scalar_one_or_none()

    outline_content = ""
    if chapter and chapter.outline_id:
        outline_result = await db.execute(select(Outline).where(Outline.id == chapter.outline_id))
        outline = outline_result.scalar_one_or_none()
        if outline:
            outline_content = f"{outline.title}\n{outline.content}"

    previous_summary = ""
    if chapter:
        # 分层记忆组装：近章 L1 全文 + 中程 L2 卷摘要 + 远程 L3 全书纲要 + 语义召回 + 伏笔清单
        try:
            logger.info(f"[记忆系统集成] _build_context 调用分层记忆 ch{chapter.chapter_number}")
            from backend.services.memory_service import build_compressed_context
            previous_summary = await build_compressed_context(
                project_id, chapter.chapter_number, outline_content, db
            )
        except Exception as e:
            logger.warning(f"[记忆系统集成] 分层记忆组装失败，回退到前 3 章拼接: {e}")
            prev_result = await db.execute(
                select(Chapter)
                .where(Chapter.project_id == project_id, Chapter.chapter_number < chapter.chapter_number)
                .order_by(Chapter.chapter_number.desc())
                .limit(3)
            )
            prev_chapters = prev_result.scalars().all()
            summaries = [f"第{ch.chapter_number}章 {ch.title}: {ch.summary}" for ch in reversed(prev_chapters) if ch.summary]
            previous_summary = "\n".join(summaries)

    if neo4j_service.available:
        graph_context = await asyncio.to_thread(neo4j_service.get_project_graph, project_id)
        character_context = json.dumps(graph_context, ensure_ascii=False, indent=2)
    else:
        char_result = await db.execute(select(Character).where(Character.project_id == project_id))
        chars = char_result.scalars().all()
        character_context = json.dumps(
            [
                {
                    "name": c.name,
                    "personality": c.personality,
                    "background": c.background,
                    "status": c.status,
                }
                for c in chars
            ],
            ensure_ascii=False,
            indent=2,
        )

    setting_context = ""
    embedding_svc = _get_embedding_service()
    if outline_content and embedding_svc is not None:
        try:
            query_embedding = await asyncio.to_thread(embedding_svc.encode_single, outline_content)
            results = await asyncio.to_thread(qdrant_service.search_settings, project_id, query_embedding, 5)
            setting_context = "\n".join([s["text"] for s in results])
        except Exception:
            setting_context = ""

    return {
        "outline": outline_content,
        "previous_summary": previous_summary,
        "character_context": character_context,
        "setting_context": setting_context,
        "style": project.style if project else "",
    }


async def _persist_paragraphs(project_id: str, chapter_id: str, content: str):
    """将章节段落向量化并存入 Qdrant"""
    embedding_svc = _get_embedding_service()
    if embedding_svc is None:
        return
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    for i, para in enumerate(paragraphs):
        if len(para) > 50:
            try:
                embedding = await asyncio.to_thread(embedding_svc.encode_single, para)
                await asyncio.to_thread(
                    qdrant_service.upsert_paragraph,
                    project_id=project_id,
                    chapter_id=chapter_id,
                    paragraph_index=i,
                    text=para,
                    embedding=embedding,
                )
            except Exception:
                continue


async def _persist_chapter_memory(
    project_id: str, chapter_id: str, chapter_number: int, content: str, db: AsyncSession
):
    """章节完成后写入分层记忆：L1 结构化摘要 + 评分 + 向量化 + 触发 L2/L3 压缩

    替代旧的 generate_summary + Chapter.summary 单字段存储，
    由 memory_service 负责生成结构化摘要并按需触发卷/全书压缩。
    失败不阻塞主流程。
    """
    try:
        logger.info(f"[记忆系统集成] _persist_chapter_memory 调用 ch{chapter_number}")
        from backend.services.memory_service import persist_chapter_memory
        cs = await persist_chapter_memory(project_id, chapter_id, chapter_number, content, db)
        if cs:
            # 回写到 Chapter.summary 保持前端列表展示兼容
            chapter_result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
            ch = chapter_result.scalar_one_or_none()
            if ch:
                ch.summary = cs.level1_detail
                await db.commit()
                logger.info(f"[记忆系统集成] Chapter.summary 回写完成 ch{chapter_number}")
    except Exception as e:
        logger.warning(f"[记忆系统集成] 分层记忆写入失败 ch{chapter_number}: {e}", exc_info=True)
        # 兜底：至少保证 Chapter.summary 有内容
        try:
            logger.info(f"[记忆系统集成] 走兜底路径 generate_summary ch{chapter_number}")
            summary = await llm_service.generate_summary(content)
            chapter_result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
            ch = chapter_result.scalar_one_or_none()
            if ch:
                ch.summary = summary
                await db.commit()
        except Exception as fallback_err:
            logger.error(f"兜底摘要生成也失败: {fallback_err}")


async def _extract_and_create_characters(project_id: str, chapter_content: str, db: AsyncSession):
    """从章节内容中提取人物和关系，并自动创建到数据库和图谱中"""
    import logging
    logger = logging.getLogger(__name__)

    try:
        # 调用LLM提取人物和关系
        raw_response = await llm_service.extract_characters_and_relations(chapter_content)

        # 解析JSON响应
        if "```json" in raw_response:
            raw_response = raw_response.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_response:
            raw_response = raw_response.split("```")[1].split("```")[0].strip()

        data = json.loads(raw_response)
        characters_data = data.get("characters", [])
        relationships_data = data.get("relationships", [])

        logger.info(f"从章节中提取到 {len(characters_data)} 个人物和 {len(relationships_data)} 个关系")

        # 创建人物映射表（姓名 -> character_id）
        character_map = {}

        # 查询已存在的人物
        from backend.models.db_models import Character
        existing_chars_result = await db.execute(
            select(Character).where(Character.project_id == project_id)
        )
        existing_chars = existing_chars_result.scalars().all()
        for char in existing_chars:
            character_map[char.name] = char.id

        # 创建新人物
        for char_data in characters_data:
            name = char_data.get("name", "")
            if not name or name in character_map:
                continue

            character = Character(
                project_id=project_id,
                name=name,
                personality=char_data.get("personality", ""),
                background=char_data.get("background", ""),
                appearance=char_data.get("appearance", ""),
                abilities=char_data.get("abilities", ""),
                description=char_data.get("description", ""),
                status="alive",
            )
            db.add(character)
            await db.flush()

            # 添加到Neo4j图谱
            if neo4j_service.available:
                await asyncio.to_thread(neo4j_service.create_character, project_id, {
                    "id": character.id,
                    "name": character.name,
                    "alias": "",
                    "description": character.description,
                    "personality": character.personality,
                    "background": character.background,
                    "appearance": character.appearance,
                    "abilities": character.abilities,
                    "status": character.status,
                })

            character_map[name] = character.id
            logger.info(f"创建新人物: {name}")

        await db.commit()

        # 创建人物关系
        if neo4j_service.available:
            for rel_data in relationships_data:
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

    except json.JSONDecodeError as e:
        logger.error(f"解析人物提取结果失败: {str(e)}")
    except Exception as e:
        logger.error(f"提取人物和关系失败: {str(e)}", exc_info=True)


def _extract_tool_calls_from_messages(messages: list) -> list[dict]:
    """从 LangChain 消息中提取工具调用记录"""
    tool_records = []
    for msg in messages:
        # AI 消息中的 tool_calls
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_records.append({
                    "tool_name": tc.get("name", ""),
                    "tool_args": tc.get("args", {}),
                    "status": "running",
                })
        # ToolMessage 表示工具返回结果
        if hasattr(msg, "name") and hasattr(msg, "content") and msg.__class__.__name__ == "ToolMessage":
            # 找到对应的 running 记录并更新
            for tr in reversed(tool_records):
                if tr["tool_name"] == msg.name and tr["status"] == "running":
                    tr["status"] = "completed"
                    tr["tool_output"] = str(msg.content)[:500] if msg.content else ""
                    break
    return tool_records


def _build_step_output(node_name: str, state: dict) -> str:
    """根据节点类型构建输出预览"""
    if node_name == "planner":
        plan = state.get("plan", "")
        return plan[:300] + "..." if len(plan) > 300 else plan
    elif node_name == "writer":
        draft = state.get("draft", "")
        return f"章节草稿，{len(draft)} 字"
    elif node_name == "reviewer":
        review = state.get("review_result")
        if isinstance(review, StructuredReview):
            return f"评分: {review.overall_score}/10, {'通过' if review.passed else '未通过'}, {len(review.issues)} 个问题"
        return state.get("review_feedback", "")[:200]
    elif node_name == "reviser":
        return f"第 {state.get('revision_count', 0)} 次修改完成"
    elif node_name == "supervisor":
        return f"调度 → {state.get('next_agent', '?')}"
    elif node_name == "human_review":
        return "等待人工审核决策"
    return ""


def _sse(event: str, data: dict) -> str:
    """构建一条 SSE 事件字符串"""
    return f"data: {json.dumps({'event': event, 'data': data}, ensure_ascii=False)}\n\n"


async def _stream_graph_events(
    graph_input,
    config: dict,
    chapter: Chapter,
    db: AsyncSession,
    is_resume: bool = False,
):
    """公共的图执行 SSE 流处理

    处理 writing_graph.astream 的输出，逐节点 yield SSE 事件。
    当 human_review 节点触发 interrupt 暂停时，yield human_review_required 事件并保存暂停状态。
    图正常结束后保存章节、生成摘要、向量化段落、提取人物。

    Args:
        graph_input: 初始状态（generate 时）或 Command(resume=...)（resume 时）
        config: LangGraph 配置，含 thread_id，用于 checkpointer 暂停/恢复
        chapter: 章节对象
        db: 数据库会话
        is_resume: 是否为恢复调用（影响初始状态加载）
    """
    last_draft_len = 0
    final_state: dict = {}

    # resume 时先加载 checkpointer 中的已有状态，避免丢失历史节点产出
    if is_resume:
        try:
            ckpt_state = await writing_graph.aget_state(config)
            if ckpt_state and ckpt_state.values:
                final_state = dict(ckpt_state.values)
                last_draft_len = len(final_state.get("draft", "") or "")
        except Exception as e:
            logger.warning(f"加载 checkpoint 状态失败: {e}")

    try:
        async for event in writing_graph.astream(graph_input, config=config, stream_mode="updates"):
            # event 是 {node_name: {output_dict}} 格式
            for node_name, node_output in event.items():
                # interrupt 暂停时 node_output 可能不是 dict，跳过非字典输出
                if not isinstance(node_output, dict):
                    logger.info(f"节点 {node_name} 输出非字典（可能是 interrupt），跳过")
                    continue

                # 累积最终状态
                final_state.update(node_output)

                now = datetime.now().isoformat()
                agent_label = AGENT_LABELS.get(node_name, node_name)

                # --- 提取工具调用记录 ---
                tool_call_records = []
                messages = node_output.get("messages", [])
                if messages:
                    tool_call_records = _extract_tool_calls_from_messages(messages)

                # --- 构建 Agent 步骤记录 ---
                step_summary = _build_step_output(node_name, node_output)
                step_record = {
                    "agent_name": node_name,
                    "agent_label": agent_label,
                    "started_at": now,
                    "finished_at": now,
                    "status": "completed",
                    "summary": step_summary,
                    "tool_calls": tool_call_records,
                    "output_preview": "",
                }

                # --- 发送 agent_step 事件（前端用于渲染时间线） ---
                yield _sse("agent_step", step_record)

                # --- 根据节点类型发送具体的状态事件 ---
                if node_name == "supervisor":
                    next_agent = node_output.get("next_agent", "")
                    if next_agent and next_agent != "FINISH":
                        next_label = AGENT_LABELS.get(next_agent, next_agent)
                        yield _sse("status", {"status": "supervisor_routing", "message": f"总调度决定：调用 {next_label}"})
                    elif next_agent == "FINISH":
                        yield _sse("status", {"status": "supervisor_routing", "message": "总调度决定：章节质量达标，结束流程"})

                elif node_name == "planner":
                    plan = node_output.get("plan", "")
                    plan_preview = plan[:500] + "..." if len(plan) > 500 else plan
                    step_record["output_preview"] = plan_preview
                    yield _sse("status", {"status": "planned", "message": "写作计划制定完成", "plan": plan_preview})

                elif node_name == "writer":
                    draft = node_output.get("draft", "")
                    yield _sse("status", {"status": "writing", "message": f"章节草稿完成，{len(draft)} 字"})
                    # 流式输出章节内容
                    chunk_size = 10
                    for i in range(0, len(draft), chunk_size):
                        chunk = draft[i:i + chunk_size]
                        yield _sse("content", {"chunk": chunk})
                        await asyncio.sleep(0.05)
                    last_draft_len = len(draft)

                elif node_name == "reviewer":
                    review_result = node_output.get("review_result")
                    review_feedback = node_output.get("review_feedback", "")

                    if isinstance(review_result, StructuredReview):
                        feedback_text = f"评分: {review_result.overall_score}/10\n{'通过' if review_result.passed else '未通过'}\n{review_result.summary}"
                        if review_result.issues:
                            feedback_text += "\n问题：\n" + "\n".join(
                                f"- [{i.severity}][{i.category}] {i.description}" for i in review_result.issues[:5]
                            )
                        yield _sse("status", {"status": "reviewed", "message": f"审查完成，评分 {review_result.overall_score}/10", "feedback": feedback_text})
                    else:
                        fb_preview = review_feedback[:300] if len(review_feedback) > 300 else review_feedback
                        yield _sse("status", {"status": "reviewed", "message": "审查完成", "feedback": fb_preview})

                elif node_name == "reviser":
                    revision_count = node_output.get("revision_count", 0)
                    revised_draft = node_output.get("draft", "")
                    yield _sse("status", {"status": "revised", "message": f"第 {revision_count} 次修改完成"})
                    # 流式输出修改后的内容
                    yield _sse("revision_content_start", {"revision": revision_count})
                    chunk_size = 10
                    for i in range(0, len(revised_draft), chunk_size):
                        chunk = revised_draft[i:i + chunk_size]
                        yield _sse("content", {"chunk": chunk})
                        await asyncio.sleep(0.05)
                    yield _sse("revision_content_end", {"revision": revision_count})
                    last_draft_len = len(revised_draft)

                elif node_name == "human_review":
                    # 该节点会 interrupt 暂停，正常不会走到这里的流式输出
                    yield _sse("status", {"status": "human_review_pending", "message": "等待人工审核..."})

    except Exception as e:
        # GraphInterrupt 是 interrupt() 正常触发的暂停异常，不是错误，跳过到暂停检测
        if "GraphInterrupt" in type(e).__name__ or "interrupt" in str(e).lower():
            logger.info(f"图被 interrupt 暂停（正常行为）: {e}")
        else:
            logger.error(f"图执行失败: {str(e)}", exc_info=True)
            yield _sse("error", {"message": f"生成失败: {str(e)}"})
            return

    # --- stream 结束，检查是否被 interrupt 暂停（Human-in-the-Loop）---
    try:
        ckpt_state = await writing_graph.aget_state(config)
    except Exception as e:
        logger.warning(f"获取图状态失败: {e}")
        ckpt_state = None

    # state.next 非空表示图未结束（被 interrupt 暂停）
    if ckpt_state and ckpt_state.next:
        interrupt_payload = None
        for task in ckpt_state.tasks:
            if getattr(task, "interrupts", None):
                interrupt_payload = task.interrupts[0].value
                break

        if interrupt_payload:
            logger.info(f"章节 {chapter.id} 暂停等待人工审核")
            # 保存暂停状态，便于前端查询和恢复
            chapter.status = "awaiting_human_review"
            chapter.agent_state = {
                "plan": final_state.get("plan", ""),
                "status": "awaiting_human_review",
                "thread_id": config["configurable"]["thread_id"],
                "awaiting_human": True,
                "agent_trace": final_state.get("agent_trace", []),
            }
            await db.commit()

            yield _sse("human_review_required", {
                "thread_id": config["configurable"]["thread_id"],
                "chapter_id": chapter.id,
                "review_summary": interrupt_payload.get("review_summary", ""),
                "overall_score": interrupt_payload.get("overall_score"),
                "passed": interrupt_payload.get("passed", False),
                "recommended_action": interrupt_payload.get("recommended_action", "revise_full"),
                "issues": interrupt_payload.get("issues", []),
                "revision_count": interrupt_payload.get("revision_count", 0),
                "draft": interrupt_payload.get("draft", ""),
            })
            return

    # --- 图正常结束，保存章节 ---
    # 从 checkpoint 获取完整状态（resume 场景下 final_state 可能不完整）
    if ckpt_state and ckpt_state.values:
        final_state.update(ckpt_state.values)

    chapter.content = final_state.get("draft", "") or chapter.content
    chapter.status = "completed"
    chapter.revision_count = final_state.get("revision_count", 0) or 0

    review_result = final_state.get("review_result")
    if isinstance(review_result, StructuredReview):
        chapter.review_feedback = review_result.summary
    else:
        chapter.review_feedback = final_state.get("review_feedback", "")

    chapter.agent_state = {
        "plan": final_state.get("plan", ""),
        "status": "completed",
        "agent_trace": final_state.get("agent_trace", []),
    }

    yield _sse("status", {"status": "summarizing", "message": "正在生成章节摘要与分层记忆..."})
    # 分层记忆写入：L1 结构化摘要 + 评分 + 向量化 + 触发 L2/L3 压缩（兜底走旧摘要）
    await _persist_chapter_memory(
        chapter.project_id, chapter.id, chapter.chapter_number, chapter.content, db
    )
    await db.refresh(chapter)

    # 向量化段落
    yield _sse("status", {"status": "vectorizing", "message": "正在向量化段落..."})
    await _persist_paragraphs(chapter.project_id, chapter.id, chapter.content)

    # 自动提取人物和关系
    yield _sse("status", {"status": "extracting_characters", "message": "正在提取人物信息..."})
    await _extract_and_create_characters(chapter.project_id, chapter.content, db)

    logger.info(f"章节 {chapter.id} 生成完成")
    yield _sse("status", {"status": "completed", "message": "章节生成完成", "revision_count": chapter.revision_count})
    yield _sse("result", {
        "chapter_id": chapter.id,
        "title": chapter.title,
        "content": chapter.content,
        "summary": chapter.summary,
    })


@router.post("/chapters/generate")
async def generate_chapter(req: GenerateChapterRequest, db: AsyncSession = Depends(get_db)):
    """启动多智能体流水线生成章节（SSE 流式响应，含 Agent/Tool 追踪与 HITL 人工审核）"""
    chapter_result = await db.execute(select(Chapter).where(Chapter.id == req.chapter_id))
    chapter = chapter_result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    context = await _build_context(chapter.project_id, req.chapter_id, db)

    initial_state: WritingAgentState = {
        "chapter_id": req.chapter_id,
        "project_id": chapter.project_id,
        "outline": context["outline"],
        "previous_summary": context["previous_summary"],
        "character_context": context["character_context"],
        "setting_context": context["setting_context"],
        "style": req.style or context["style"],
        "plan": "",
        "draft": "",
        "review_feedback": "",
        "revision_count": 0,
        "status": "started",
        "scratchpad": {},
        "next_agent": "",
        "human_decision": None,
        "agent_trace": [],
        "messages": [],
    }

    # thread_id 用章节ID，保证同一章节的暂停/恢复共享同一 checkpoint
    config = {"configurable": {"thread_id": req.chapter_id}}

    async def event_stream():
        logger.info(f"开始生成章节 {req.chapter_id}")
        yield _sse("status", {"status": "started", "message": "多智能体流水线启动..."})
        async for sse_msg in _stream_graph_events(initial_state, config, chapter, db, is_resume=False):
            yield sse_msg

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/chapters/{chapter_id}/resume")
async def resume_chapter(
    chapter_id: str,
    decision: HumanReviewDecision,
    db: AsyncSession = Depends(get_db),
):
    """恢复被人工审核暂停的章节生成（Human-in-the-Loop）

    前端在收到 human_review_required 事件后展示决策面板，
    用户提交决策后调用本接口，通过 Command(resume=decision) 恢复图执行。
    """
    if decision.chapter_id != chapter_id:
        raise HTTPException(status_code=400, detail="chapter_id 不匹配")

    chapter_result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = chapter_result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    # 校验章节确实处于等待人工审核状态
    agent_state = chapter.agent_state or {}
    if not agent_state.get("awaiting_human"):
        raise HTTPException(status_code=400, detail="该章节未处于人工审核暂停状态")

    config = {"configurable": {"thread_id": chapter_id}}

    # 构建恢复指令：把用户决策注入图，interrupt() 返回该决策
    resume_value = {
        "action": decision.action,
        "feedback": decision.feedback,
        "edited_content": decision.edited_content,
    }

    async def event_stream():
        logger.info(f"恢复章节 {chapter_id} 生成，人工决策: {decision.action}")
        yield _sse("status", {"status": "resumed", "message": f"已应用人工决策：{decision.action}"})
        async for sse_msg in _stream_graph_events(
            Command(resume=resume_value), config, chapter, db, is_resume=True
        ):
            yield sse_msg

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/chapters/generate-sync", response_model=ChapterResponse)
async def generate_chapter_sync(req: GenerateChapterRequest, db: AsyncSession = Depends(get_db)):
    """同步调用多智能体流水线生成章节"""
    chapter_result = await db.execute(select(Chapter).where(Chapter.id == req.chapter_id))
    chapter = chapter_result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    context = await _build_context(chapter.project_id, req.chapter_id, db)

    initial_state: WritingAgentState = {
        "chapter_id": req.chapter_id,
        "project_id": chapter.project_id,
        "outline": context["outline"],
        "previous_summary": context["previous_summary"],
        "character_context": context["character_context"],
        "setting_context": context["setting_context"],
        "style": req.style or context["style"],
        "plan": "",
        "draft": "",
        "review_feedback": "",
        "revision_count": 0,
        "status": "started",
        "scratchpad": {},
        "next_agent": "",
        "human_decision": None,
        "agent_trace": [],
        "messages": [],
    }

    # 同步接口需传 thread_id（图带 checkpointer）；HITL 暂停时直接保存当前草稿
    config = {"configurable": {"thread_id": f"sync-{req.chapter_id}"}}
    try:
        final_state = await writing_graph.ainvoke(initial_state, config=config)
    except Exception as e:
        # 触发 interrupt 或其他异常时，从 checkpoint 取回当前状态
        logger.warning(f"同步生成遇到中断: {e}，尝试取回当前状态")
        try:
            ckpt = await writing_graph.aget_state(config)
            final_state = ckpt.values if ckpt and ckpt.values else initial_state
        except Exception:
            final_state = initial_state

    chapter.content = final_state.get("draft", "") or ""
    chapter.status = "completed"
    chapter.revision_count = final_state.get("revision_count", 0) or 0
    review_result = final_state.get("review_result")
    if isinstance(review_result, StructuredReview):
        chapter.review_feedback = review_result.summary
    else:
        chapter.review_feedback = final_state.get("review_feedback", "")
    chapter.agent_state = {
        "plan": final_state.get("plan", ""),
        "status": final_state.get("status", ""),
    }

    await db.commit()

    # 分层记忆写入：结构化摘要 + 评分 + 向量化 + 触发 L2/L3 压缩（兜底走旧摘要）
    await _persist_chapter_memory(
        chapter.project_id, chapter.id, chapter.chapter_number, chapter.content, db
    )
    await db.refresh(chapter)

    await _persist_paragraphs(chapter.project_id, chapter.id, chapter.content)

    return chapter


@router.put("/chapters/{chapter_id}", response_model=ChapterResponse)
async def update_chapter(chapter_id: str, content: dict, db: AsyncSession = Depends(get_db)):
    """手动更新章节内容"""
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    if "content" in content:
        chapter.content = content["content"]
    if "title" in content:
        chapter.title = content["title"]

    await db.commit()
    await db.refresh(chapter)
    return chapter
