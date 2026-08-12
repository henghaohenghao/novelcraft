"""
Temporal 工作流 API 路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from backend.services.temporal_service import temporal_service

router = APIRouter(prefix="/api/workflows", tags=["工作流"])


class BookCreationRequest(BaseModel):
    """整书创作请求"""
    project_id: str = Field(..., description="项目ID")
    title: str = Field(..., description="书名")
    synopsis: str = Field(..., description="梗概")
    genre: str = Field(..., description="类型")
    style: str = Field(..., description="风格")
    chapter_count: int = Field(..., description="章节数量", ge=1, le=1000)
    user_id: str = Field(..., description="用户ID")


class ChapterRevisionRequest(BaseModel):
    """章节修订请求"""
    chapter_id: str = Field(..., description="章节ID")
    revision_instructions: str = Field(..., description="修订指令")


class WorkflowResponse(BaseModel):
    """工作流响应"""
    workflow_id: str
    status: str
    message: str | None = None


@router.post("/book-creation", response_model=WorkflowResponse)
async def start_book_creation(request: BookCreationRequest):
    """
    启动整书创作工作流

    编排整本书的创作流程：
    1. 生成大纲
    2. 按序生成章节
    3. 发送完成通知
    """
    try:
        workflow_id = await temporal_service.start_book_creation(
            project_id=request.project_id,
            title=request.title,
            synopsis=request.synopsis,
            genre=request.genre,
            style=request.style,
            chapter_count=request.chapter_count,
            user_id=request.user_id,
        )

        return WorkflowResponse(
            workflow_id=workflow_id,
            status="started",
            message=f"整书创作工作流已启动，预计生成 {request.chapter_count} 章",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动工作流失败: {str(e)}")


@router.post("/chapter-revision", response_model=WorkflowResponse)
async def start_chapter_revision(request: ChapterRevisionRequest):
    """
    启动章节修订工作流

    根据修订指令重新生成章节内容
    """
    try:
        workflow_id = await temporal_service.start_chapter_revision(
            chapter_id=request.chapter_id,
            revision_instructions=request.revision_instructions,
        )

        return WorkflowResponse(
            workflow_id=workflow_id,
            status="started",
            message="章节修订工作流已启动",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动工作流失败: {str(e)}")


@router.get("/status/{workflow_id}")
async def get_workflow_status(workflow_id: str):
    """查询工作流状态"""
    status = await temporal_service.get_workflow_status(workflow_id)
    return status


@router.post("/cancel/{workflow_id}")
async def cancel_workflow(workflow_id: str):
    """取消工作流"""
    success = await temporal_service.cancel_workflow(workflow_id)
    if success:
        return {"workflow_id": workflow_id, "status": "cancelled"}
    else:
        raise HTTPException(status_code=500, detail="取消工作流失败")


@router.get("/result/{workflow_id}")
async def get_workflow_result(workflow_id: str, timeout: int = 60):
    """
    获取工作流执行结果

    Args:
        workflow_id: 工作流ID
        timeout: 超时时间（秒）
    """
    try:
        result = await temporal_service.get_workflow_result(workflow_id, timeout)
        return {"workflow_id": workflow_id, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取工作流结果失败: {str(e)}")
