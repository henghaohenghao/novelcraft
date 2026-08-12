"""
Temporal 工作流服务

提供工作流启动、查询、控制等功能
"""
import logging
from typing import Optional
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TemporalWorkflowService:
    """Temporal 工作流服务"""

    def __init__(self):
        self.client = None
        self.temporal_host = getattr(settings, "temporal_host", "localhost:7233")
        self.task_queue = "novelcraft-task-queue"

    async def init_client(self):
        """初始化 Temporal 客户端"""
        if not self.client:
            from temporalio.client import Client
            self.client = await Client.connect(self.temporal_host)
            logger.info("Temporal 客户端已连接到 %s", self.temporal_host)

    async def close(self):
        """关闭客户端"""
        if self.client:
            await self.client.close()
            logger.info("Temporal 客户端已关闭")

    async def start_book_creation(
        self,
        project_id: str,
        title: str,
        synopsis: str,
        genre: str,
        style: str,
        chapter_count: int,
        user_id: str,
    ) -> str:
        """
        启动整书创作工作流

        Returns:
            工作流 ID
        """
        await self.init_client()

        from backend.workflows.book_creation_workflow import (
            BookCreationWorkflow,
            BookCreationInput,
        )

        workflow_id = f"book-creation-{project_id}"
        input_data = BookCreationInput(
            project_id=project_id,
            title=title,
            synopsis=synopsis,
            genre=genre,
            style=style,
            chapter_count=chapter_count,
            user_id=user_id,
        )

        handle = await self.client.start_workflow(
            BookCreationWorkflow.run,
            input_data,
            id=workflow_id,
            task_queue=self.task_queue,
        )

        logger.info(
            "启动整书创作工作流 (workflow_id=%s, project_id=%s)",
            workflow_id, project_id
        )

        return workflow_id

    async def start_chapter_revision(
        self,
        chapter_id: str,
        revision_instructions: str,
    ) -> str:
        """
        启动章节修订工作流

        Returns:
            工作流 ID
        """
        await self.init_client()

        from backend.workflows.book_creation_workflow import ChapterRevisionWorkflow

        workflow_id = f"chapter-revision-{chapter_id}"

        handle = await self.client.start_workflow(
            ChapterRevisionWorkflow.run,
            args=[chapter_id, revision_instructions],
            id=workflow_id,
            task_queue=self.task_queue,
        )

        logger.info(
            "启动章节修订工作流 (workflow_id=%s, chapter_id=%s)",
            workflow_id, chapter_id
        )

        return workflow_id

    async def get_workflow_status(self, workflow_id: str) -> dict:
        """
        查询工作流状态

        Returns:
            工作流状态信息
        """
        await self.init_client()

        try:
            handle = self.client.get_workflow_handle(workflow_id)
            description = await handle.describe()

            return {
                "workflow_id": workflow_id,
                "status": description.status.name,
                "start_time": description.start_time.isoformat() if description.start_time else None,
                "close_time": description.close_time.isoformat() if description.close_time else None,
                "execution_time": description.execution_time.isoformat() if description.execution_time else None,
            }

        except Exception as e:
            logger.error("查询工作流状态失败 (workflow_id=%s): %s", workflow_id, e)
            return {
                "workflow_id": workflow_id,
                "status": "unknown",
                "error": str(e),
            }

    async def cancel_workflow(self, workflow_id: str) -> bool:
        """
        取消工作流

        Returns:
            是否成功取消
        """
        await self.init_client()

        try:
            handle = self.client.get_workflow_handle(workflow_id)
            await handle.cancel()
            logger.info("取消工作流 (workflow_id=%s)", workflow_id)
            return True

        except Exception as e:
            logger.error("取消工作流失败 (workflow_id=%s): %s", workflow_id, e)
            return False

    async def get_workflow_result(self, workflow_id: str, timeout_seconds: int = 60):
        """
        等待并获取工作流结果

        Args:
            workflow_id: 工作流 ID
            timeout_seconds: 超时时间（秒）

        Returns:
            工作流执行结果
        """
        await self.init_client()

        try:
            handle = self.client.get_workflow_handle(workflow_id)
            result = await handle.result(timeout=timeout_seconds)
            return result

        except Exception as e:
            logger.error("获取工作流结果失败 (workflow_id=%s): %s", workflow_id, e)
            raise


# 全局单例
temporal_service = TemporalWorkflowService()
