"""
LLM 大语言模型服务

封装 OpenAI 兼容 API 调用，提供小说创作各环节的 LLM 方法：
大纲生成、章节规划、内容写作、审查反馈、修改润色等。
"""
import json
import logging
from openai import AsyncOpenAI
from langchain_openai import ChatOpenAI
from backend.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def _extract_json(raw: str) -> dict | list | None:
    """从 LLM 回复中容错提取 JSON（支持 ```json 代码块或纯文本）"""
    if not raw:
        return None
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        # 兜底：截取首个 { 到末个 } 再试
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                return None
        return None


class LLMService:
    """LLM 服务：封装多智能体所需的所有语言模型调用"""

    def __init__(self):
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        """延迟初始化 OpenAI 异步客户端"""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                timeout=120.0,
                max_retries=3,
            )
        return self._client

    def _get_chat_model(self, model: str = None) -> ChatOpenAI:
        """获取 LangChain ChatOpenAI 实例，供 ReAct Agent 使用"""
        return ChatOpenAI(
            model=model or settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            request_timeout=120,
            max_retries=3,
        )

    async def chat(self, messages: list[dict], model: str = None, temperature: float = 0.7, max_tokens: int = 4096) -> str:
        """通用对话接口：发送消息并返回完整回复"""
        try:
            response = await self.client.chat.completions.create(
                model=model or settings.llm_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"[LLM] chat 调用失败: {type(e).__name__}: {e}")
            raise

    async def chat_stream(self, messages: list[dict], model: str = None, temperature: float = 0.7, max_tokens: int = 4096):
        """流式对话接口：逐步返回生成的文本块"""
        try:
            stream = await self.client.chat.completions.create(
                model=model or settings.llm_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"[LLM] chat_stream 调用失败: {type(e).__name__}: {e}")
            raise

    async def generate_outline(
        self,
        synopsis: str,
        chapter_count: int = 10,
        existing_outlines: str = "",
        start_chapter: int = 1,
    ) -> str:
        """根据小说梗概生成章节大纲（JSON 格式）

        当 existing_outlines 非空时，接着已有大纲的最后一章继续生成后续章节，
        避免每次都从第一章重新开始。
        """
        if existing_outlines:
            messages = [
                {"role": "system", "content": "你是一位专业的小说大纲规划师。请根据已有大纲继续生成后续章节，保持剧情连贯。"},
                {"role": "user", "content": f"""请根据以下小说梗概和已有大纲，继续生成{chapter_count}章的后续大纲。

梗概：
{synopsis}

已有大纲：
{existing_outlines}

要求：
1. 接着已有大纲的最后一章继续，不要重复已有章节的内容
2. 新生成的章节从第{start_chapter}章开始编号
3. 每章包含标题和200字左右的内容概要
4. 确保剧情延续已有走向，保持人物和伏笔的连贯性
5. 输出格式为JSON数组，每个元素包含 title 和 content 字段

请直接输出JSON数组，不要包含其他内容。"""},
            ]
        else:
            messages = [
                {"role": "system", "content": "你是一位专业的小说大纲规划师。请根据梗概生成详细的章节大纲。"},
                {"role": "user", "content": f"""请根据以下小说梗概，生成一个包含{chapter_count}章的详细大纲。

梗概：
{synopsis}

要求：
1. 每章包含标题和200字左右的内容概要
2. 确保故事有完整的起承转合
3. 标注关键剧情节点（如：开端、发展、转折、高潮、结局）
4. 输出格式为JSON数组，每个元素包含 title 和 content 字段

请直接输出JSON数组，不要包含其他内容。"""},
            ]
        return await self.chat(messages, model=settings.llm_planner_model, temperature=0.8, max_tokens=8192)

    async def plan_chapter(self, outline: str, previous_summary: str, character_context: str, setting_context: str) -> str:
        """为当前章节制定写作计划（规划智能体调用）"""
        messages = [
            {"role": "system", "content": "你是一位专业的小说写作规划师。请根据大纲和上下文，为当前章节制定详细的写作计划。"},
            {"role": "user", "content": f"""请为以下章节制定写作计划。

章节大纲：
{outline}

前情摘要：
{previous_summary if previous_summary else "（这是第一章，无前情）"}

相关人物信息：
{character_context}

相关设定信息：
{setting_context}

请制定详细的写作计划，包括：
1. 本章核心事件
2. 出场人物及其状态
3. 情感基调与节奏
4. 需要呼应的伏笔
5. 具体场景划分（3-5个场景）

请直接输出写作计划。"""},
        ]
        return await self.chat(messages, model=settings.llm_planner_model, temperature=0.7, max_tokens=4096)

    async def write_chapter(self, plan: str, outline: str, previous_summary: str, character_context: str, setting_context: str, style: str = "") -> str:
        """根据写作计划创作章节正文（写作智能体调用）"""
        style_instruction = f"\n写作风格要求：{style}" if style else ""
        messages = [
            {"role": "system", "content": f"你是一位才华横溢的小说作家。请根据写作计划创作章节内容。{style_instruction}"},
            {"role": "user", "content": f"""请根据以下信息创作本章内容。

写作计划：
{plan}

章节大纲：
{outline}

前情摘要：
{previous_summary if previous_summary else "（这是第一章）"}

人物信息：
{character_context}

设定信息：
{setting_context}

要求：
1. 字数在3000-5000字之间
2. 语言流畅，描写生动
3. 人物性格和行为保持一致
4. 注意场景转换的自然过渡
5. 适当埋设伏笔

请直接输出章节正文。"""},
        ]
        return await self.chat(messages, model=settings.llm_writer_model, temperature=0.9, max_tokens=8192)

    async def review_chapter(self, chapter_content: str, outline: str, character_context: str, setting_context: str) -> str:
        """审查章节内容的一致性和质量（审查智能体调用）"""
        messages = [
            {"role": "system", "content": "你是一位严格的小说审稿编辑。请审查章节内容，检查一致性和质量问题。"},
            {"role": "user", "content": f"""请审查以下章节内容。

章节大纲要求：
{outline}

人物设定：
{character_context}

世界观设定：
{setting_context}

章节正文：
{chapter_content}

请从以下维度审查：
1. 人物行为是否与设定一致
2. 情节是否与大纲吻合
3. 世界观设定是否有冲突
4. 文笔质量和节奏
5. 对话是否自然
6. 是否有逻辑漏洞

请给出审查意见。如果发现问题，请明确指出问题位置和修改建议。
如果内容合格，请回复"审查通过：内容合格，无需修改。"

请直接输出审查意见。"""},
        ]
        return await self.chat(messages, model=settings.llm_reviewer_model, temperature=0.5, max_tokens=4096)

    async def revise_chapter(self, chapter_content: str, review_feedback: str, plan: str, character_context: str, setting_context: str) -> str:
        """根据审查意见修改章节（修改智能体调用）"""
        messages = [
            {"role": "system", "content": "你是一位专业的小说修改编辑。请根据审查意见修改章节内容。"},
            {"role": "user", "content": f"""请根据审查意见修改以下章节。

审查意见：
{review_feedback}

写作计划：
{plan}

人物信息：
{character_context}

设定信息：
{setting_context}

原文：
{chapter_content}

请根据审查意见逐条修改，确保修改后的内容：
1. 解决所有指出的问题
2. 保持原有文风和叙事节奏
3. 人物行为与设定一致
4. 情节逻辑通顺

请直接输出修改后的完整章节正文。"""},
        ]
        return await self.chat(messages, model=settings.llm_writer_model, temperature=0.8, max_tokens=8192)

    async def generate_summary(self, chapter_content: str) -> str:
        """生成章节摘要：包含主要情节、人物变化和新伏笔"""
        messages = [
            {"role": "system", "content": "你是一位专业的摘要撰写者。请为章节内容撰写简洁的摘要。"},
            {"role": "user", "content": f"""请为以下章节内容撰写摘要，包含：
1. 主要情节（2-3句话）
2. 关键人物变化
3. 新埋设的伏笔

章节内容：
{chapter_content}

请直接输出摘要。"""},
        ]
        return await self.chat(messages, model=settings.llm_model, temperature=0.5, max_tokens=1024)

    async def generate_characters_from_synopsis(self, synopsis: str) -> str:
        """根据梗概自动设计小说人物（JSON 格式）"""
        messages = [
            {"role": "system", "content": "你是一位专业的小说人物设计师。请根据梗概设计人物。"},
            {"role": "user", "content": f"""请根据以下小说梗概，设计主要人物。

梗概：
{synopsis}

请为每个主要人物提供：
1. 姓名
2. 性格特点
3. 背景故事
4. 外貌描述
5. 能力特长
6. 在故事中的角色定位

输出格式为JSON数组，每个元素包含 name, personality, background, appearance, abilities, role 字段。

请直接输出JSON数组。"""},
        ]
        return await self.chat(messages, model=settings.llm_planner_model, temperature=0.8, max_tokens=4096)

    async def extract_characters_and_relations(self, chapter_content: str) -> str:
        """从章节内容中提取人物和人物关系（JSON 格式）"""
        messages = [
            {"role": "system", "content": "你是一位专业的小说分析师。请从章节内容中提取人物信息和人物关系。"},
            {"role": "user", "content": f"""请从以下章节内容中提取人物信息和人物关系。

章节内容：
{chapter_content}

请提取：
1. 出现的所有人物及其基本信息（姓名、性格、外貌、能力等）
2. 人物之间的关系（如：朋友、敌人、师徒、亲属等）

输出格式为JSON对象，包含两个字段：
- characters: 人物数组，每个元素包含 name, personality, background, appearance, abilities, description 字段
- relationships: 关系数组，每个元素包含 source_name, target_name, relation_type, description 字段

relation_type 必须是以下之一：FRIEND, ENEMY, RELATIVE, MENTOR, LOVER, COLLEAGUE, RIVAL, SUBORDINATE, MASTER, ALLY

请直接输出JSON对象。"""},
        ]
        return await self.chat(messages, model=settings.llm_planner_model, temperature=0.7, max_tokens=4096)


    async def generate_structured_summary(
        self, chapter_content: str, chapter_number: int
    ) -> dict:
        """生成结构化章节摘要（Level 1）：情节/关键事件/人物变化/伏笔

        替代旧的 generate_summary 字符串输出，产出可直接入库的结构化结果。
        同时识别本章回收的历史伏笔 ID，供 memory_service 回写 resolved 标记。
        """
        logger.info(f"[LLM] generate_structured_summary 开始 ch{chapter_number} 内容长度={len(chapter_content)}字")
        messages = [
            {"role": "system", "content": "你是小说章节分析师。请输出严格 JSON。"},
            {"role": "user", "content": f"""请为以下章节内容生成结构化摘要。

章节内容：
{chapter_content}

输出 JSON，字段如下：
{{
  "summary": "情节+人物变化摘要（200字以内）",
  "key_events": [{{"event": "事件描述", "importance": 0.8}}],
  "character_changes": [{{"name": "角色名", "change": "状态变化描述"}}],
  "foreshadows": [
    {{"id": "fs_{chapter_number}_1", "desc": "伏笔描述", "type": "object|plot|character|secret", "resolved": false}}
  ],
  "resolved_foreshadow_ids": ["fs_3_2"]
}}

要求：
1. key_events 按重要性从高到低排序，importance 取 0-1
2. foreshadows 的 id 必须以 fs_{{本章号}}_{{序号}} 格式命名
3. resolved_foreshadow_ids 填写本章呼应/回收的历史伏笔 id（若无可填空数组）

请直接输出 JSON。"""},
        ]
        raw = await self.chat(messages, model=settings.llm_model, temperature=0.3, max_tokens=2048)
        logger.info(f"[LLM] generate_structured_summary LLM返回 ch{chapter_number} 长度={len(raw)}字")
        data = _extract_json(raw)
        if not data or not isinstance(data, dict):
            logger.warning(f"[LLM] 结构化摘要解析失败，回退到纯文本摘要 ch{chapter_number}。raw={raw[:200]}")
            fallback = await self.generate_summary(chapter_content)
            return {
                "summary": fallback,
                "key_events": [],
                "character_changes": [],
                "foreshadows": [],
                "resolved_foreshadow_ids": [],
            }
        # 字段兜底
        data.setdefault("summary", "")
        data.setdefault("key_events", [])
        data.setdefault("character_changes", [])
        data.setdefault("foreshadows", [])
        data.setdefault("resolved_foreshadow_ids", [])
        logger.info(
            f"[LLM] generate_structured_summary 完成 ch{chapter_number} | "
            f"events={len(data.get('key_events', []))} "
            f"foreshadows={len(data.get('foreshadows', []))} "
            f"resolved={len(data.get('resolved_foreshadow_ids', []))}"
        )
        return data

    async def compress_to_volume(self, chapter_summaries: list[dict], volume_number: int) -> dict:
        """Level 1 → Level 2：把多章摘要合并为一条卷摘要

        保留主线进展与未回收伏笔，丢弃日常描写与已回收伏笔细节。
        """
        logger.info(f"[LLM] compress_to_volume 开始 v{volume_number} 输入{len(chapter_summaries)}章")
        chapters_text = "\n\n".join([
            f"第{s['chapter_number']}章：{s.get('level1_detail') or s.get('summary', '')}\n"
            f"关键事件：{json.dumps(s.get('key_events', []), ensure_ascii=False)}\n"
            f"伏笔：{json.dumps(s.get('foreshadows', []), ensure_ascii=False)}"
            for s in chapter_summaries
        ])

        messages = [
            {"role": "system", "content": "你是小说情节压缩器。把多章摘要合并为卷摘要，保留主线进展和未回收伏笔。"},
            {"role": "user", "content": f"""请把以下 {len(chapter_summaries)} 章的摘要合并为第 {volume_number} 卷的摘要。

要求：
1. summary：主线进展（3-5 句话，只保留影响后续的关键转折），人物状态净变化
2. unresolved_foreshadows：列出所有尚未呼应的伏笔，标注埋设章节
3. 丢弃：日常描写、重复铺垫、已回收伏笔的细节

章节摘要：
{chapters_text}

输出 JSON：{{"summary": "...", "unresolved_foreshadows": [{{"id": "...", "desc": "...", "from_chapter": N}}]}}

请直接输出 JSON。"""},
        ]
        raw = await self.chat(messages, model=settings.llm_model, temperature=0.3, max_tokens=2048)
        logger.info(f"[LLM] compress_to_volume LLM返回 v{volume_number} 长度={len(raw)}字")
        data = _extract_json(raw)
        if not data or not isinstance(data, dict):
            logger.warning(f"[LLM] 卷摘要解析失败，回退为拼接 v{volume_number}。raw={raw[:200]}")
            joined = " ".join([s.get("level1_detail") or s.get("summary", "") for s in chapter_summaries])
            return {"summary": joined[:800], "unresolved_foreshadows": []}
        data.setdefault("summary", "")
        data.setdefault("unresolved_foreshadows", [])
        logger.info(
            f"[LLM] compress_to_volume 完成 v{volume_number} | "
            f"摘要长度={len(data.get('summary', ''))}字 "
            f"未回收伏笔={len(data.get('unresolved_foreshadows', []))}个"
        )
        return data

    async def compress_to_arc(self, volume_summaries: list[dict]) -> str:
        """Level 2 → Level 3：把多卷摘要提炼为全书纲要片段（500 字以内）"""
        logger.info(f"[LLM] compress_to_arc 开始 输入{len(volume_summaries)}卷")
        volumes_text = "\n".join([
            f"第{v['volume_number']}卷（{v['start_chapter']}-{v['end_chapter']}章）：{v['summary']}"
            for v in volume_summaries
        ])
        messages = [
            {"role": "system", "content": "你是小说主线提炼器。从卷摘要中提取全书主线进展。"},
            {"role": "user", "content": f"""请把以下 {len(volume_summaries)} 卷的摘要提炼为全书纲要更新。

要求：
1. 主线推进到什么阶段（起/承/转/合）
2. 核心矛盾当前状态
3. 主要人物的成长弧线当前位置
4. 全局未回收的关键伏笔（只保留影响结局的）

卷摘要：
{volumes_text}

直接输出纲要文本，控制在 500 字以内。"""},
        ]
        arc_text = await self.chat(messages, model=settings.llm_planner_model, temperature=0.3, max_tokens=1024)
        logger.info(f"[LLM] compress_to_arc 完成 长度={len(arc_text)}字")
        return arc_text

    async def score_importance(self, structured_summary: dict) -> float:
        """评估章节重要性（0-1），影响后续是否被压缩归档"""
        events = structured_summary.get("key_events", [])
        foreshadows = structured_summary.get("foreshadows", [])
        char_changes = structured_summary.get("character_changes", [])

        has_turning_point = any(e.get("importance", 0) >= 0.7 for e in events)
        has_foreshadow = len(foreshadows) > 0
        has_char_change = len(char_changes) > 0

        # 规则评分（无需额外 LLM 调用，节省成本）
        score = 0.2  # 基础分
        if has_turning_point:
            score += 0.35
        if has_foreshadow:
            score += 0.25
        if has_char_change:
            score += 0.15
        # 关键事件平均重要性
        if events:
            avg_imp = sum(e.get("importance", 0.5) for e in events) / len(events)
            score += avg_imp * 0.15

        score = max(0.0, min(1.0, round(score, 2)))
        logger.info(
            f"[LLM] score_importance 规则评分: {score} | "
            f"转折点={has_turning_point} 伏笔={has_foreshadow} "
            f"人物变化={has_char_change} 事件均值={avg_imp if events else 0}"
        )
        return score


llm_service = LLMService()