"""
风格迁移 API 路由（简化版，无缓存）
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.database import get_async_session
from backend.services.style_transfer_service import style_transfer_service

router = APIRouter(prefix="/api/style-transfer", tags=["风格迁移"])


class StyleTransferRequest(BaseModel):
    """风格迁移请求"""
    original_text: str = Field(..., description="原始文本", min_length=1, max_length=50000)
    style_id: str = Field(..., description="目标风格标识", examples=["gulong", "caowenxuan", "jinyong"])
    project_id: str = Field(..., description="项目ID")


class StyleTransferResponse(BaseModel):
    """风格迁移响应"""
    task_id: str
    status: str
    original_text: str | None = None
    transformed_text: str | None = None
    style_id: str | None = None
    style_name: str | None = None
    inference_time_ms: int | None = None
    error: str | None = None


@router.post("/transfer", response_model=StyleTransferResponse)
async def transfer_style(
    request: StyleTransferRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """
    执行风格迁移

    将输入文本转换为指定作家风格。
    直接调用 Qwen3-8B 模型进行推理，不使用缓存。
    """
    result = await style_transfer_service.transfer_style(
        original_text=request.original_text,
        style_id=request.style_id,
        project_id=request.project_id,
        db=db,
    )
    return result


@router.get("/task/{task_id}", response_model=StyleTransferResponse)
async def get_task_status(
    task_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    """查询风格迁移任务状态"""
    result = await style_transfer_service.get_task_status(task_id, db)
    if not result:
        raise HTTPException(status_code=404, detail="任务不存在")
    return result


@router.get("/styles")
async def list_styles(db: AsyncSession = Depends(get_async_session)):
    """列出所有可用的风格"""
    styles = await style_transfer_service.list_available_styles(db)
    return {"styles": styles}
