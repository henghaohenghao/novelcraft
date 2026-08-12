"""
分层记忆服务

实现"分层摘要 + 时序合并 + 重要性衰减"三级记忆压缩：
  - Level 1（章节摘要）：每章生成结构化摘要 + 重要性评分 + 向量化
  - Level 2（卷摘要）：每 VOLUME_SIZE 章合并一次
  - Level 3（全书纲要）：每 ARC_SIZE 章提炼一次

对外提供：
  - persist_chapter_memory：章节完成后写入 L1 + 触发 L2/L3 压缩
  - build_compressed_context：按距离分层组装前文记忆，token 稳定可控
  - decay_low_importance_memories：低重要性 + 长期未访问的章节归档
"""
import asyncio
import logging
from datetime import datetime
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.db_models import ChapterSummary, VolumeSummary
from backend.services.llm_service import llm_service
from backend.services.qdrant_service import qdrant_service

logger = logging.getLogger(__name__)

# 压缩触发阈值
VOLUME_SIZE = 5      # 每 5 章合并为 1 卷
ARC_SIZE = 15        # 每 15 章提炼 1 次全书纲要

# 衰减阈值（基于章节距离，不依赖墙钟时间）
DECAY_CHAPTER_DISTANCE = 20  # 距离当前章节 20 章以上才考虑归档
DECAY_IMPORTANCE = 0.3       # 重要性低于 0.3
DECAY_PROTECTED_SCORE = 0.5  # 重要性 ≥ 0.5 的章节永不归档（含伏笔/转折点）


def _get_embedding_service():
    """获取嵌入服务（Qdrant 不可用时返回 None）"""
    if not qdrant_service.available:
        return None
    try:
        from backend.services.embedding_service import embedding_service
        return embedding_service
    except Exception:
        return None


async def persist_chapter_memory(
    project_id: str,
    chapter_id: str,
    chapter_number: int,
    chapter_content: str,
    db: AsyncSession,
) -> ChapterSummary | None:
    """章节完成后写入 Level 1 记忆，并按需触发 L2/L3 压缩

    流程：
      1. LLM 生成结构化摘要（情节/关键事件/人物变化/伏笔）
      2. 规则评分得到 importance_score
      3. 持久化到 ChapterSummary 表
      4. 向量化 level1_detail 入 Qdrant（突破时序召回）
      5. 回写本章回收的历史伏笔 resolved=True
      6. 每 VOLUME_SIZE 章触发 L2 合并；每 ARC_SIZE 章触发 L3 提炼

    Returns:
        写入的 ChapterSummary 对象；失败返回 None
    """
    try:
        logger.info(f"[记忆系统] 开始写入第 {chapter_number} 章分层记忆...")
        # 1. 生成结构化摘要
        structured = await llm_service.generate_structured_summary(chapter_content, chapter_number)
        summary_text = structured.get("summary", "")
        key_events = structured.get("key_events", [])
        character_changes = structured.get("character_changes", [])
        foreshadows = structured.get("foreshadows", [])
        resolved_ids = structured.get("resolved_foreshadow_ids", [])

        logger.info(
            f"[记忆系统] L1摘要生成完成 ch{chapter_number} | "
            f"摘要长度={len(summary_text)}字 关键事件={len(key_events)}个 "
            f"人物变化={len(character_changes)}条 伏笔={len(foreshadows)}个 "
            f"回收伏笔={len(resolved_ids)}个"
        )

        # 2. 重要性评分
        importance = await llm_service.score_importance(structured)
        logger.info(f"[记忆系统] 重要性评分 ch{chapter_number}: {importance}")

        # 3. 持久化（覆盖式：同一章节重新生成则更新）
        existing = await db.execute(
            select(ChapterSummary).where(
                ChapterSummary.project_id == project_id,
                ChapterSummary.chapter_id == chapter_id,
            )
        )
        cs = existing.scalar_one_or_none()
        if cs:
            cs.level1_detail = summary_text
            cs.key_events = key_events
            cs.character_changes = character_changes
            cs.foreshadows = foreshadows
            cs.importance_score = importance
            cs.last_accessed_at = datetime.utcnow()
            cs.access_count = cs.access_count or 0
        else:
            cs = ChapterSummary(
                project_id=project_id,
                chapter_id=chapter_id,
                chapter_number=chapter_number,
                level1_detail=summary_text,
                key_events=key_events,
                character_changes=character_changes,
                foreshadows=foreshadows,
                importance_score=importance,
            )
            db.add(cs)
        await db.flush()

        # 4. 向量化入库
        embedding_svc = _get_embedding_service()
        if embedding_svc is not None and summary_text:
            try:
                embedding = await asyncio.to_thread(embedding_svc.encode_single, summary_text)
                point_id = await asyncio.to_thread(
                    qdrant_service.upsert_summary,
                    project_id,
                    chapter_id,
                    chapter_number,
                    summary_text,
                    embedding,
                    importance,
                )
                cs.embedding_id = point_id
                logger.info(f"[记忆系统] Qdrant向量化成功 ch{chapter_number} point_id={point_id}")
            except Exception as e:
                logger.warning(f"[记忆系统] 章节摘要向量化失败 ch{chapter_number}: {e}")
        else:
            logger.info(f"[记忆系统] 跳过向量化 ch{chapter_number}（embedding服务不可用或摘要为空）")

        # 5. 回写本章回收的历史伏笔
        if resolved_ids:
            logger.info(f"[记忆系统] 回写历史伏笔回收标记 ch{chapter_number} ids={resolved_ids}")
            await _mark_foreshadows_resolved(project_id, resolved_ids, db)

        await db.commit()

        # 6. 触发压缩（提交后执行，避免事务嵌套）
        if chapter_number % VOLUME_SIZE == 0:
            logger.info(f"[记忆系统] 触发L2卷合并 ch{chapter_number}（每{VOLUME_SIZE}章一次）")
            try:
                await _compress_to_volume(project_id, chapter_number, db)
            except Exception as e:
                logger.warning(f"[记忆系统] 卷摘要合并失败 ch{chapter_number}: {e}")

        if chapter_number % ARC_SIZE == 0:
            logger.info(f"[记忆系统] 触发L3全书纲要提炼 ch{chapter_number}（每{ARC_SIZE}章一次）")
            try:
                await _compress_to_arc(project_id, chapter_number, db)
            except Exception as e:
                logger.warning(f"[记忆系统] 全书纲要提炼失败 ch{chapter_number}: {e}")

        # 每 VOLUME_SIZE 章触发一次归档清理（与 L2 压缩同节奏）
        # 衰减基于"章节距离"而非墙钟时间，用户搁置写作不会导致关键章节被误归档
        if chapter_number % VOLUME_SIZE == 0:
            try:
                archived = await decay_low_importance_memories(
                    project_id, db, chapter_number
                )
                if archived:
                    logger.info(f"[记忆系统] 归档清理完成 ch{chapter_number} 归档{archived}条")
            except Exception as e:
                logger.warning(f"[记忆系统] 归档清理失败 ch{chapter_number}: {e}")

        logger.info(
            f"[记忆系统] 第{chapter_number}章记忆写入完成 | "
            f"importance={importance} events={len(key_events)} foreshadows={len(foreshadows)}"
        )
        return cs

    except Exception as e:
        logger.error(f"写入章节记忆失败 ch{chapter_number}: {e}", exc_info=True)
        await db.rollback()
        return None


async def _mark_foreshadows_resolved(
    project_id: str, resolved_ids: list[str], db: AsyncSession
):
    """把本章回收的历史伏笔标记为 resolved=True

    foreshadows 存在 ChapterSummary.foreshadows JSON 数组里，
    需要把每条记录的 resolved 字段更新为 True。
    """
    if not resolved_ids:
        return

    logger.info(f"[记忆系统] 扫描历史伏笔标记回收 project={project_id} ids={resolved_ids}")
    result = await db.execute(
        select(ChapterSummary).where(
            ChapterSummary.project_id == project_id,
            ChapterSummary.foreshadows.isnot(None),
        )
    )
    marked_count = 0
    for cs in result.scalars():
        changed = False
        for fs in (cs.foreshadows or []):
            if fs.get("id") in resolved_ids and not fs.get("resolved"):
                fs["resolved"] = True
                changed = True
                marked_count += 1
                logger.info(
                    f"[记忆系统] 伏笔回收 ch{cs.chapter_number}: "
                    f"id={fs.get('id')} desc={fs.get('desc', '')[:30]}"
                )
        if changed:
            # SQLAlchemy JSON 字段变更需要显式标记
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(cs, "foreshadows")
    logger.info(f"[记忆系统] 伏笔回收标记完成 共标记{marked_count}个")


async def _compress_to_volume(project_id: str, chapter_number: int, db: AsyncSession):
    """Level 1 → Level 2：合并最近 VOLUME_SIZE 章为一条卷摘要"""
    start = chapter_number - VOLUME_SIZE + 1
    end = chapter_number
    logger.info(f"[记忆系统] L2卷合并开始 project={project_id} ch{start}-{end}")

    result = await db.execute(
        select(ChapterSummary)
        .where(
            ChapterSummary.project_id == project_id,
            ChapterSummary.chapter_number >= start,
            ChapterSummary.chapter_number <= end,
        )
        .order_by(ChapterSummary.chapter_number)
    )
    chapter_summaries = result.scalars().all()
    if not chapter_summaries:
        logger.warning(f"[记忆系统] L2卷合并跳过：未找到 ch{start}-{end} 的章节摘要")
        return

    volume_number = end // VOLUME_SIZE
    payload = [
        {
            "chapter_number": cs.chapter_number,
            "level1_detail": cs.level1_detail,
            "key_events": cs.key_events or [],
            "foreshadows": cs.foreshadows or [],
        }
        for cs in chapter_summaries
    ]
    logger.info(f"[记忆系统] L2卷合并 LLM调用 v{volume_number} 输入{len(payload)}章摘要")

    compressed = await llm_service.compress_to_volume(payload, volume_number)
    summary_text = compressed.get("summary", "")
    unresolved = compressed.get("unresolved_foreshadows", [])

    # 覆盖式写入（同一卷重新触发则更新）
    existing = await db.execute(
        select(VolumeSummary).where(
            VolumeSummary.project_id == project_id,
            VolumeSummary.volume_number == volume_number,
        )
    )
    vs = existing.scalar_one_or_none()
    if vs:
        vs.summary = summary_text
        vs.unresolved_foreshadows = unresolved
        vs.updated_at = datetime.utcnow()
        logger.info(f"[记忆系统] L2卷合并更新现有卷 v{volume_number}")
    else:
        vs = VolumeSummary(
            project_id=project_id,
            volume_number=volume_number,
            start_chapter=start,
            end_chapter=end,
            summary=summary_text,
            unresolved_foreshadows=unresolved,
        )
        db.add(vs)
        logger.info(f"[记忆系统] L2卷合并新建卷 v{volume_number}")

    # 回填 Level 2 摘要到对应章节，便于跨章检索复用
    level2_text = f"[卷{volume_number}摘要] {summary_text}"
    for cs in chapter_summaries:
        cs.level2_volume = level2_text

    await db.commit()
    logger.info(
        f"[记忆系统] L2卷合并完成 v{volume_number} (ch{start}-{end}) | "
        f"摘要长度={len(summary_text)}字 未回收伏笔={len(unresolved)}个"
    )


async def _compress_to_arc(project_id: str, chapter_number: int, db: AsyncSession):
    """Level 2 → Level 3：把已有卷摘要提炼为全书纲要片段"""
    logger.info(f"[记忆系统] L3全书纲要提炼开始 project={project_id} ch{chapter_number}")
    result = await db.execute(
        select(VolumeSummary)
        .where(VolumeSummary.project_id == project_id)
        .order_by(VolumeSummary.volume_number)
    )
    volumes = result.scalars().all()
    if not volumes:
        logger.warning(f"[记忆系统] L3全书纲要提炼跳过：无卷摘要可用")
        return

    payload = [
        {
            "volume_number": v.volume_number,
            "start_chapter": v.start_chapter,
            "end_chapter": v.end_chapter,
            "summary": v.summary,
        }
        for v in volumes
    ]
    logger.info(f"[记忆系统] L3全书纲要 LLM调用 输入{len(payload)}卷摘要")

    arc_text = await llm_service.compress_to_arc(payload)

    # 把全书纲要回填到所有章节的 level3_arc 字段
    await db.execute(
        update(ChapterSummary)
        .where(ChapterSummary.project_id == project_id)
        .values(level3_arc=arc_text)
    )
    await db.commit()
    logger.info(
        f"[记忆系统] L3全书纲要提炼完成 ch{chapter_number} | "
        f"长度={len(arc_text)}字 已回填到所有章节"
    )


async def build_compressed_context(
    project_id: str,
    current_chapter_number: int,
    outline: str,
    db: AsyncSession,
) -> str:
    """分层组装前文记忆，token 稳定可控

    检索策略：
      - 近章（前 2 章）：Level 1 全文
      - 中程（前 3~10 章）：Level 2 卷摘要
      - 远程（10 章以前）：Level 3 全书纲要（截断保底）
      - 语义召回：与当前大纲相关的历史片段（突破时序限制）
      - 强制注入：未回收伏笔清单（防遗忘）

    同时更新被读取章节的访问统计（用于后续衰减判定）。
    """
    parts: list[str] = []
    logger.info(f"[记忆系统] 开始组装前文记忆 context for ch{current_chapter_number}")

    # 1. 近章：Level 1 全文
    recent_result = await db.execute(
        select(ChapterSummary)
        .where(
            ChapterSummary.project_id == project_id,
            ChapterSummary.chapter_number >= current_chapter_number - 2,
            ChapterSummary.chapter_number < current_chapter_number,
        )
        .order_by(ChapterSummary.chapter_number)
    )
    recent = recent_result.scalars().all()
    accessed_ids: list[str] = []
    for cs in recent:
        parts.append(f"【第{cs.chapter_number}章】{cs.level1_detail}")
        if cs.character_changes:
            parts.append(f"  人物变化：{cs.character_changes}")
        accessed_ids.append(cs.id)
    logger.info(f"[记忆系统] L1近章召回 ch{current_chapter_number}: {len(recent)}章（前2章）")

    # 2. 中程：Level 2 卷摘要
    mid_result = await db.execute(
        select(VolumeSummary)
        .where(
            VolumeSummary.project_id == project_id,
            VolumeSummary.end_chapter < current_chapter_number - 2,
            VolumeSummary.start_chapter >= current_chapter_number - 10,
        )
        .order_by(VolumeSummary.volume_number)
    )
    mid_volumes = mid_result.scalars().all()
    for vs in mid_volumes:
        parts.append(f"【第{vs.volume_number}卷摘要（ch{vs.start_chapter}-{vs.end_chapter}）】{vs.summary}")
        if vs.unresolved_foreshadows:
            parts.append(f"  未回收伏笔：{vs.unresolved_foreshadows}")
    logger.info(f"[记忆系统] L2卷摘要召回 ch{current_chapter_number}: {len(mid_volumes)}卷（前3-10章）")

    # 3. 远程：Level 3 全书纲要（取最新一条，截断保底）
    arc_result = await db.execute(
        select(ChapterSummary.level3_arc)
        .where(
            ChapterSummary.project_id == project_id,
            ChapterSummary.level3_arc.isnot(None),
            ChapterSummary.chapter_number < current_chapter_number - 10,
        )
        .order_by(ChapterSummary.chapter_number.desc())
        .limit(1)
    )
    arc_row = arc_result.first()
    if arc_row and arc_row[0]:
        parts.append(f"【全书纲要】{arc_row[0][-800:]}")
        logger.info(f"[记忆系统] L3全书纲要召回 ch{current_chapter_number}: 长度={len(arc_row[0])}字")
    else:
        logger.info(f"[记忆系统] L3全书纲要召回 ch{current_chapter_number}: 无（10章前无纲要）")

    # 4. 语义召回：与当前大纲相关的历史片段
    embedding_svc = _get_embedding_service()
    if embedding_svc is not None and outline:
        try:
            query_embedding = await asyncio.to_thread(embedding_svc.encode_single, outline)
            hits = await asyncio.to_thread(
                qdrant_service.search_summaries, project_id, query_embedding, 3
            )
            semantic_used = 0
            for hit in hits:
                hit_ch = hit.get("chapter_number", 0)
                # 避免与近章重复
                if hit_ch < current_chapter_number - 2 and hit.get("score", 0) > 0.5:
                    parts.append(f"【相关回忆·第{hit_ch}章】{hit.get('text', '')}")
                    semantic_used += 1
            logger.info(
                f"[记忆系统] 语义召回 ch{current_chapter_number}: "
                f"候选={len(hits)}条 使用={semantic_used}条 "
                f"scores={[round(h.get('score', 0), 3) for h in hits]}"
            )
        except Exception as e:
            logger.warning(f"[记忆系统] 语义召回章节摘要失败 ch{current_chapter_number}: {e}")
    else:
        logger.info(f"[记忆系统] 跳过语义召回 ch{current_chapter_number}（embedding服务不可用）")

    # 5. 强制注入未回收伏笔清单（防遗忘）
    unresolved_result = await db.execute(
        select(ChapterSummary.chapter_number, ChapterSummary.foreshadows)
        .where(
            ChapterSummary.project_id == project_id,
            ChapterSummary.chapter_number < current_chapter_number,
        )
        .order_by(ChapterSummary.chapter_number)
    )
    all_fs: list[str] = []
    for ch_num, fs_list in unresolved_result.all():
        for fs in (fs_list or []):
            if not fs.get("resolved"):
                all_fs.append(f"第{ch_num}章：{fs.get('desc', '')}")
    if all_fs:
        parts.append("【待回收伏笔清单】\n" + "\n".join(all_fs[:10]))
        logger.info(f"[记忆系统] 未回收伏笔清单 ch{current_chapter_number}: {len(all_fs)}个（注入前10个）")
    else:
        logger.info(f"[记忆系统] 未回收伏笔清单 ch{current_chapter_number}: 无")

    # 6. 更新访问统计（用于衰减判定）
    if accessed_ids:
        await db.execute(
            update(ChapterSummary)
            .where(ChapterSummary.id.in_(accessed_ids))
            .values(
                access_count=ChapterSummary.access_count + 1,
                last_accessed_at=datetime.utcnow(),
            )
        )
        await db.commit()

    context_text = "\n\n".join(parts)
    logger.info(
        f"[记忆系统] 前文记忆组装完成 ch{current_chapter_number} | "
        f"总长度={len(context_text)}字 段数={len(parts)}"
    )
    return context_text


async def decay_low_importance_memories(
    project_id: str, db: AsyncSession, current_chapter_number: int | None = None
):
    """低重要性 + 距离当前章节较远的章节摘要降级归档

    归档策略：清空 level1_detail，仅保留 key_events 摘要前 3 条，
    避免长期不被检索的日常过渡章节占据上下文 token。

    判定基于"章节距离"而非墙钟时间——用户搁置写作 2 个月不该导致
    关键伏笔章节被归档；只有当某章距离最新章节超过 20 章且重要性
    极低时，才认为它已被卷/全书摘要充分覆盖，可降级。

    Args:
        project_id: 项目 ID
        db: 数据库会话
        current_chapter_number: 当前最新章节号；None 时自动查询项目最大章节号
    """
    # 1. 确定当前章节号
    if current_chapter_number is None:
        latest = await db.execute(
            select(func.max(ChapterSummary.chapter_number)).where(
                ChapterSummary.project_id == project_id
            )
        )
        current_chapter_number = latest.scalar() or 0

    if current_chapter_number <= DECAY_CHAPTER_DISTANCE:
        logger.info(
            f"[记忆系统] 衰减归档跳过 project={project_id} | "
            f"当前仅 ch{current_chapter_number}，不足 {DECAY_CHAPTER_DISTANCE} 章距离"
        )
        return 0

    threshold_chapter = current_chapter_number - DECAY_CHAPTER_DISTANCE
    logger.info(
        f"[记忆系统] 开始衰减归档 project={project_id} | "
        f"当前章 ch{current_chapter_number} 归档阈值: ch<{threshold_chapter} "
        f"且 importance<{DECAY_IMPORTANCE} (importance≥{DECAY_PROTECTED_SCORE} 永不归档)"
    )

    # 2. 查询候选：距离远 + 重要性低 + 未受保护
    result = await db.execute(
        select(ChapterSummary).where(
            ChapterSummary.project_id == project_id,
            ChapterSummary.chapter_number < threshold_chapter,
            ChapterSummary.importance_score < DECAY_IMPORTANCE,
            ChapterSummary.importance_score < DECAY_PROTECTED_SCORE,
        )
    )
    archived = 0
    for cs in result.scalars():
        # 保护机制：含未回收伏笔的章节不归档
        has_unresolved_fs = any(
            not fs.get("resolved") for fs in (cs.foreshadows or [])
        )
        if has_unresolved_fs:
            logger.info(
                f"[记忆系统] 跳过归档 ch{cs.chapter_number}（含未回收伏笔，受保护）"
            )
            continue

        top_events = (cs.key_events or [])[:3]
        cs.level1_detail = f"[已归档·低重要性] 关键事件：{top_events}"
        archived += 1
        logger.info(
            f"[记忆系统] 归档章节 ch{cs.chapter_number} | "
            f"importance={cs.importance_score} 距当前章距离={current_chapter_number - cs.chapter_number}"
        )
    if archived:
        await db.commit()
        logger.info(f"[记忆系统] 衰减归档完成 project={project_id} 归档{archived}条")
    else:
        logger.info(f"[记忆系统] 衰减归档完成 project={project_id} 无符合条件的章节")
    return archived
