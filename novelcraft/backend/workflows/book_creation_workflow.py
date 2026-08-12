"""
Temporal 工作流定义

编排整书创作流程：
1. 创建项目
2. 生成大纲
3. 人工确认
4. 按序调度章节生成
5. 完成通知
"""
import logging
from datetime import timedelta
from temporalio import workflow, activity
from temporalio.common import RetryPolicy
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BookCreationInput:
    """整书创作输入"""
    project_id: str
    title: str
    synopsis: str
    genre: str
    style: str
    chapter_count: int
    user_id: str


@dataclass
class ChapterGenerationInput:
    """章节生成输入"""
    project_id: str
    chapter_id: str
    chapter_number: int
    outline_id: Optional[str] = None


@dataclass
class BookCreationResult:
    """整书创作结果"""
    project_id: str
    status: str
    chapters_completed: int
    total_chapters: int
    error_message: Optional[str] = None


@workflow.defn
class BookCreationWorkflow:
    """整书创作工作流"""

    @workflow.run
    async def run(self, input: BookCreationInput) -> BookCreationResult:
        """
        执行整书创作流程

        流程：
        1. 生成大纲
        2. 等待人工确认（可选）
        3. 按序生成章节
        4. 发送完成通知
        """
        workflow.logger.info(
            "开始整书创作工作流 (project_id=%s, title=%s)",
            input.project_id, input.title
        )

        chapters_completed = 0
        error_message = None

        try:
            # 步骤 1: 生成大纲
            workflow.logger.info("生成大纲...")
            outline_result = await workflow.execute_activity(
                generate_outline,
                args=[input.project_id, input.synopsis, input.genre],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=10),
                    maximum_interval=timedelta(minutes=1),
                ),
            )

            if not outline_result["success"]:
                raise Exception(f"大纲生成失败: {outline_result.get('error')}")

            outline_nodes = outline_result["outline_nodes"]
            workflow.logger.info("大纲生成完成，共 %d 个章节", len(outline_nodes))

            # 步骤 2: 等待人工确认（可选）
            # 这里可以使用 workflow.wait_condition 等待外部信号
            # await workflow.wait_condition(lambda: self.outline_approved)

            # 步骤 3: 按序生成章节
            workflow.logger.info("开始生成章节...")
            for i, outline_node in enumerate(outline_nodes[:input.chapter_count]):
                chapter_input = ChapterGenerationInput(
                    project_id=input.project_id,
                    chapter_id=outline_node["chapter_id"],
                    chapter_number=i + 1,
                    outline_id=outline_node["outline_id"],
                )

                workflow.logger.info("生成第 %d 章...", chapter_input.chapter_number)

                # 调用章节生成活动
                chapter_result = await workflow.execute_activity(
                    generate_chapter,
                    args=[chapter_input],
                    start_to_close_timeout=timedelta(minutes=30),
                    retry_policy=RetryPolicy(
                        maximum_attempts=2,
                        initial_interval=timedelta(seconds=30),
                        maximum_interval=timedelta(minutes=2),
                    ),
                )

                if chapter_result["success"]:
                    chapters_completed += 1
                    workflow.logger.info(
                        "第 %d 章生成完成 (chapter_id=%s)",
                        chapter_input.chapter_number,
                        chapter_input.chapter_id
                    )
                else:
                    workflow.logger.error(
                        "第 %d 章生成失败: %s",
                        chapter_input.chapter_number,
                        chapter_result.get("error")
                    )
                    # 继续生成下一章，不中断整个流程

            # 步骤 4: 发送完成通知
            await workflow.execute_activity(
                send_completion_notification,
                args=[input.project_id, input.user_id, chapters_completed, input.chapter_count],
                start_to_close_timeout=timedelta(minutes=1),
            )

            workflow.logger.info(
                "整书创作工作流完成 (project_id=%s, completed=%d/%d)",
                input.project_id, chapters_completed, input.chapter_count
            )

            return BookCreationResult(
                project_id=input.project_id,
                status="completed",
                chapters_completed=chapters_completed,
                total_chapters=input.chapter_count,
            )

        except Exception as e:
            workflow.logger.error("整书创作工作流失败: %s", e)
            error_message = str(e)

            return BookCreationResult(
                project_id=input.project_id,
                status="failed",
                chapters_completed=chapters_completed,
                total_chapters=input.chapter_count,
                error_message=error_message,
            )


@activity.defn
async def generate_outline(project_id: str, synopsis: str, genre: str) -> dict:
    """
    生成大纲活动

    调用规划 Agent 生成章节大纲
    """
    activity.logger.info("执行大纲生成活动 (project_id=%s)", project_id)

    try:
        # TODO: 实际实现应调用规划 Agent
        # from backend.agents.planner import planner_agent
        # outline = await planner_agent.generate_outline(synopsis, genre)

        # 模拟生成大纲
        outline_nodes = [
            {
                "outline_id": f"outline_{i}",
                "chapter_id": f"chapter_{i}",
                "title": f"第{i}章",
                "content": f"章节{i}大纲内容",
            }
            for i in range(1, 11)  # 生成10章大纲
        ]

        return {
            "success": True,
            "outline_nodes": outline_nodes,
        }

    except Exception as e:
        activity.logger.error("大纲生成失败: %s", e)
        return {
            "success": False,
            "error": str(e),
        }


@activity.defn
async def generate_chapter(input: ChapterGenerationInput) -> dict:
    """
    生成章节活动

    调用多智能体写作流水线生成章节内容
    """
    activity.logger.info(
        "执行章节生成活动 (chapter_id=%s, number=%d)",
        input.chapter_id, input.chapter_number
    )

    try:
        # TODO: 实际实现应调用 LangGraph 写作流水线
        # from backend.agents.graph import writing_graph
        # result = await writing_graph.run(chapter_id=input.chapter_id)

        # 模拟章节生成
        import asyncio
        await asyncio.sleep(2)  # 模拟生成耗时

        return {
            "success": True,
            "chapter_id": input.chapter_id,
            "content": f"第{input.chapter_number}章的内容...",
        }

    except Exception as e:
        activity.logger.error("章节生成失败: %s", e)
        return {
            "success": False,
            "error": str(e),
        }


@activity.defn
async def send_completion_notification(
    project_id: str,
    user_id: str,
    chapters_completed: int,
    total_chapters: int,
) -> dict:
    """
    发送完成通知活动

    通知用户整书创作已完成
    """
    activity.logger.info(
        "发送完成通知 (project_id=%s, user_id=%s, completed=%d/%d)",
        project_id, user_id, chapters_completed, total_chapters
    )

    try:
        # TODO: 实际实现应发送邮件、推送通知等
        # await notification_service.send(user_id, message)

        return {
            "success": True,
            "message": f"项目 {project_id} 创作完成，共完成 {chapters_completed}/{total_chapters} 章",
        }

    except Exception as e:
        activity.logger.error("发送通知失败: %s", e)
        return {
            "success": False,
            "error": str(e),
        }


@workflow.defn
class ChapterRevisionWorkflow:
    """章节修订工作流"""

    @workflow.run
    async def run(self, chapter_id: str, revision_instructions: str) -> dict:
        """
        执行章节修订流程

        流程：
        1. 读取当前章节内容
        2. 调用修改 Agent
        3. 审查修改结果
        4. 保存新版本
        """
        workflow.logger.info("开始章节修订工作流 (chapter_id=%s)", chapter_id)

        try:
            # 步骤 1: 读取章节
            chapter_data = await workflow.execute_activity(
                read_chapter,
                args=[chapter_id],
                start_to_close_timeout=timedelta(minutes=1),
            )

            # 步骤 2: 执行修订
            revision_result = await workflow.execute_activity(
                revise_chapter,
                args=[chapter_id, chapter_data["content"], revision_instructions],
                start_to_close_timeout=timedelta(minutes=15),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )

            # 步骤 3: 保存新版本
            if revision_result["success"]:
                await workflow.execute_activity(
                    save_chapter_version,
                    args=[chapter_id, revision_result["revised_content"]],
                    start_to_close_timeout=timedelta(minutes=1),
                )

            workflow.logger.info("章节修订工作流完成 (chapter_id=%s)", chapter_id)
            return revision_result

        except Exception as e:
            workflow.logger.error("章节修订工作流失败: %s", e)
            return {
                "success": False,
                "error": str(e),
            }


@activity.defn
async def read_chapter(chapter_id: str) -> dict:
    """读取章节内容"""
    # TODO: 从数据库读取
    return {
        "chapter_id": chapter_id,
        "content": "章节内容...",
    }


@activity.defn
async def revise_chapter(chapter_id: str, content: str, instructions: str) -> dict:
    """修订章节内容"""
    # TODO: 调用修改 Agent
    return {
        "success": True,
        "revised_content": f"修订后的内容: {content}",
    }


@activity.defn
async def save_chapter_version(chapter_id: str, content: str) -> dict:
    """保存章节版本"""
    # TODO: 保存到数据库
    return {"success": True}
