"""
Temporal Worker 启动脚本

启动 Temporal Worker 来执行工作流和活动
"""
import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker
from backend.workflows.book_creation_workflow import (
    BookCreationWorkflow,
    ChapterRevisionWorkflow,
    generate_outline,
    generate_chapter,
    send_completion_notification,
    read_chapter,
    revise_chapter,
    save_chapter_version,
)
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def run_worker():
    """运行 Temporal Worker"""
    # 连接到 Temporal Server
    temporal_host = getattr(settings, "temporal_host", "localhost:7233")
    client = await Client.connect(temporal_host)

    logger.info("Temporal Worker 已连接到 %s", temporal_host)

    # 创建 Worker
    worker = Worker(
        client,
        task_queue="novelcraft-task-queue",
        workflows=[
            BookCreationWorkflow,
            ChapterRevisionWorkflow,
        ],
        activities=[
            generate_outline,
            generate_chapter,
            send_completion_notification,
            read_chapter,
            revise_chapter,
            save_chapter_version,
        ],
    )

    logger.info("Temporal Worker 已启动，监听任务队列: novelcraft-task-queue")

    # 运行 Worker
    await worker.run()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    asyncio.run(run_worker())
