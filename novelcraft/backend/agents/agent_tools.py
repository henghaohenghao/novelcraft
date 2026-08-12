"""
Agent 工具集

为每个 Agent 提供可调用的工具，使其具备自主检索和操作能力。
这是从"流水线节点"升级为"真正 Agent"的关键：
Agent 不再只是被动执行单次 LLM 调用，而是可以主动使用工具获取信息、做出决策。
"""
import logging
import asyncio
from langchain_core.tools import tool
from backend.services.neo4j_service import neo4j_service
from backend.services.qdrant_service import qdrant_service
from backend.services.llm_service import llm_service

logger = logging.getLogger(__name__)


# ============================================================
# 规划 Agent 工具
# ============================================================

@tool
async def search_character_relations(character_name: str) -> str:
    """查询角色的人际关系网络，包括朋友、敌人、亲属等关系。

    规划 Agent 在制定写作计划时，可主动查询角色关系，
    确保情节安排符合已有的人物关系设定。

    Args:
        character_name: 角色姓名
    """
    try:
        relations = await asyncio.to_thread(neo4j_service.get_character_relations, character_name)
        if not relations:
            return f"未找到角色 '{character_name}' 的关系信息"
        result_lines = [f"角色 '{character_name}' 的关系网络："]
        for rel in relations:
            result_lines.append(
                f"  - {rel.get('target_name', '?')} ({rel.get('relation_type', '?')}): {rel.get('description', '')}"
            )
        return "\n".join(result_lines)
    except Exception as e:
        logger.warning(f"查询角色关系失败: {e}")
        return f"查询失败: {e}"


@tool
async def search_world_setting(keyword: str, project_id: str) -> str:
    """查询世界观设定信息，如地理、历史、魔法体系等。

    规划 Agent 可主动查询设定，确保写作计划不与已有设定冲突。

    Args:
        keyword: 设定关键词（如"魔法体系"、"帝国历史"等）
        project_id: 项目ID
    """
    try:
        results = await asyncio.to_thread(qdrant_service.search_settings_by_keyword, project_id, keyword, 3)
        if not results:
            return f"未找到与 '{keyword}' 相关的世界观设定"
        result_lines = [f"与 '{keyword}' 相关的设定："]
        for r in results:
            result_lines.append(f"  - {r.get('text', '')}")
        return "\n".join(result_lines)
    except Exception as e:
        logger.warning(f"查询世界观设定失败: {e}")
        return f"查询失败: {e}"


@tool
async def get_previous_chapter_summary(chapter_number: int) -> str:
    """获取前一章的摘要，确保情节衔接。

    规划 Agent 可主动获取前文摘要，而非完全依赖传入的 previous_summary。

    Args:
        chapter_number: 前一章的章节号
    """
    try:
        from backend.models.database import async_session_factory
        from backend.models.db_models import Chapter
        from sqlalchemy import select

        async with async_session_factory() as session:
            result = await session.execute(
                select(Chapter).where(Chapter.chapter_number == chapter_number).limit(1)
            )
            chapter = result.scalar_one_or_none()
            if chapter and chapter.summary:
                return f"第{chapter.chapter_number}章 {chapter.title}: {chapter.summary}"
            return f"未找到第 {chapter_number} 章的摘要"
    except Exception as e:
        logger.warning(f"查询前章摘要失败: {e}")
        return f"查询失败: {e}"


# 规划 Agent 的完整工具集
PLANNER_TOOLS = [search_character_relations, search_world_setting, get_previous_chapter_summary]


# ============================================================
# 写作 Agent 工具
# ============================================================

@tool
async def check_character_consistency(character_name: str, action_description: str) -> str:
    """检查角色的行为是否符合其性格设定。

    写作 Agent 在创作过程中，可主动检查某角色的行为是否合理，
    而非完全依赖审查 Agent 事后发现。

    Args:
        character_name: 角色姓名
        action_description: 角色行为描述
    """
    try:
        from backend.models.database import async_session_factory
        from backend.models.db_models import Character
        from sqlalchemy import select

        async with async_session_factory() as session:
            result = await session.execute(
                select(Character).where(Character.name == character_name).limit(1)
            )
            character = result.scalar_one_or_none()

        if not character:
            return f"未找到角色 '{character_name}' 的信息，无法检查一致性"

        character_info = f"姓名：{character.name}\n性格：{character.personality}\n背景：{character.background}\n外貌：{character.appearance}\n能力：{character.abilities}\n描述：{character.description}"

        result = await llm_service.chat(
            messages=[
                {"role": "system", "content": "你是一个角色一致性检查器。判断角色的行为是否符合其性格设定。"},
                {"role": "user", "content": f"""角色设定：
{character_info}

角色行为：{action_description}

请判断该行为是否符合角色设定，简要说明理由。如果不符合，给出修改建议。"""},
            ],
            temperature=0.2,
            max_tokens=512,
        )
        return result
    except Exception as e:
        logger.warning(f"角色一致性检查失败: {e}")
        return f"检查失败: {e}"


@tool
async def lookup_style_guide(style_name: str, project_id: str) -> str:
    """查询写作风格指南，获取风格要求和示例。

    写作 Agent 可主动查询风格指南，确保文风一致。

    Args:
        style_name: 风格名称
        project_id: 项目ID
    """
    try:
        guide = await asyncio.to_thread(qdrant_service.search_style_guide_by_keyword, project_id, style_name, 2)
        if not guide:
            return f"未找到风格 '{style_name}' 的指南"
        result_lines = [f"风格 '{style_name}' 指南："]
        for g in guide:
            result_lines.append(f"  - {g.get('text', '')}")
        return "\n".join(result_lines)
    except Exception as e:
        logger.warning(f"查询风格指南失败: {e}")
        return f"查询失败: {e}"


WRITER_TOOLS = [check_character_consistency, lookup_style_guide]


# ============================================================
# 审查 Agent 工具（专业化分工）
# ============================================================

@tool
async def verify_plot_logic(chapter_content: str, outline: str) -> str:
    """专门验证情节逻辑，检查是否有剧情漏洞、前后矛盾。

    审查 Agent 可调用此工具进行深度情节分析。

    Args:
        chapter_content: 章节内容
        outline: 章节大纲
    """
    result = await llm_service.chat(
        messages=[
            {"role": "system", "content": "你是情节逻辑审查专家。只关注情节逻辑问题，不评价文笔。"},
            {"role": "user", "content": f"""大纲要求：
{outline}

章节内容：
{chapter_content}

请检查：
1. 情节是否有逻辑漏洞
2. 因果关系是否合理
3. 是否有前后矛盾
4. 伏笔是否合理

如果没有问题，回复"情节逻辑无问题"。否则列出具体问题。"""},
        ],
        temperature=0.2,
        max_tokens=1024,
    )
    return result


@tool
async def verify_character_behavior(chapter_content: str, character_context: str) -> str:
    """专门验证人物行为一致性，检查角色言行是否符合设定。

    Args:
        chapter_content: 章节内容
        character_context: 人物设定
    """
    result = await llm_service.chat(
        messages=[
            {"role": "system", "content": "你是人物行为一致性审查专家。只关注人物行为是否符合设定，不评价情节和文笔。"},
            {"role": "user", "content": f"""人物设定：
{character_context}

章节内容：
{chapter_content}

请检查每个出场角色的言行是否符合其性格设定。
如果没有问题，回复"人物行为无问题"。否则列出具体问题。"""},
        ],
        temperature=0.2,
        max_tokens=1024,
    )
    return result


@tool
async def verify_setting_consistency(chapter_content: str, setting_context: str) -> str:
    """专门验证世界观设定一致性，检查是否有设定冲突。

    Args:
        chapter_content: 章节内容
        setting_context: 世界观设定
    """
    result = await llm_service.chat(
        messages=[
            {"role": "system", "content": "你是世界观设定一致性审查专家。只关注设定是否冲突，不评价情节和文笔。"},
            {"role": "user", "content": f"""世界观设定：
{setting_context}

章节内容：
{chapter_content}

请检查章节内容是否与世界观设定冲突。
如果没有问题，回复"设定一致性无问题"。否则列出具体冲突。"""},
        ],
        temperature=0.2,
        max_tokens=1024,
    )
    return result


REVIEWER_TOOLS = [verify_plot_logic, verify_character_behavior, verify_setting_consistency]


# ============================================================
# 修改 Agent 工具
# ============================================================

@tool
async def targeted_revise(chapter_content: str, issue_description: str, issue_location: str) -> str:
    """针对特定问题进行局部修改，而非重写整个章节。

    修改 Agent 可选择局部修改（而非全文重写），更精准、更高效。

    Args:
        chapter_content: 章节内容
        issue_description: 问题描述
        issue_location: 问题位置
    """
    result = await llm_service.chat(
        messages=[
            {"role": "system", "content": "你是精准修改编辑。只修改指定位置的问题，保持其他内容不变。"},
            {"role": "user", "content": f"""请针对以下问题进行局部修改：

问题位置：{issue_location}
问题描述：{issue_description}

原文：
{chapter_content}

请输出修改后的完整章节。注意：只修改有问题的部分，其余内容保持原样。"""},
        ],
        temperature=0.3,
        max_tokens=8192,
    )
    return result


REVISER_TOOLS = [targeted_revise]
