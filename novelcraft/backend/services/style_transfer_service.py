"""
风格迁移服务

直接调用 vLLM 部署的 Qwen3-8B 模型进行风格转换
不使用缓存机制，每次请求都调用模型推理
"""
import logging
import re
import time
from datetime import datetime
import httpx
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.style_models import StyleTransferTask, StyleModelInfo
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class StyleTransferService:
    """风格迁移服务 - 直接调用模型推理"""

    def __init__(self):
        self.vllm_base_url = getattr(settings, "vllm_base_url", "https://u861108-we7h-6e651fa3.bjb3.seetacloud.com:8443")
        self.timeout = 300.0  # 推理超时时间（秒），Qwen3-8B 在 CPU/弱 GPU 上较慢
        self._cached_model_id = None  # 缓存已发现的模型ID
        logger.info(
            "StyleTransferService 初始化完成 (vLLM URL: %s)",
            self.vllm_base_url
        )

    async def _discover_model(self) -> str:
        """从部署服务中获取可用模型ID（缓存首次结果）"""
        if self._cached_model_id:
            return self._cached_model_id

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(f"{self.vllm_base_url}/v1/models")
                resp.raise_for_status()
                model_list = resp.json().get("data", [])
            except Exception as e:
                logger.error("无法连接到部署服务获取模型列表: %s", e)
                raise Exception(f"无法连接到部署服务: {e}")

        if not model_list:
            raise Exception("部署服务中没有可用模型")

        self._cached_model_id = model_list[0]["id"]
        logger.info("自动发现模型: %s", self._cached_model_id)
        return self._cached_model_id

    async def transfer_style(
        self,
        original_text: str,
        style_id: str,
        project_id: str,
        db: AsyncSession,
    ) -> dict:
        """
        执行风格迁移

        Args:
            original_text: 原始文本
            style_id: 目标风格标识（如 "gulong", "caowenxuan"）
            project_id: 项目ID
            db: 数据库会话

        Returns:
            包含转换结果的字典
        """
        start_time = time.time()

        # 查询风格信息
        style_info = await self._get_style_info(style_id, db)
        if not style_info:
            return {
                "status": "failed",
                "error": f"风格 {style_id} 不存在",
            }

        # 创建任务记录
        task = StyleTransferTask(
            project_id=project_id,
            style_id=style_id,
            original_text=original_text,
            status="processing",
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

        try:
            # 调用模型进行风格迁移
            transformed_text = await self._call_model_inference(
                original_text=original_text,
                style_name=style_info.style_name,
                style_description=style_info.description,
            )

            # 计算耗时
            inference_time_ms = int((time.time() - start_time) * 1000)

            # 更新任务状态
            task.status = "completed"
            task.transformed_text = transformed_text
            task.inference_time_ms = inference_time_ms
            task.completed_at = datetime.utcnow()
            await db.commit()

            logger.info(
                "风格迁移完成 (task_id=%s, style=%s, time=%dms)",
                task.id, style_id, inference_time_ms
            )

            return {
                "task_id": task.id,
                "status": "completed",
                "original_text": original_text,
                "transformed_text": transformed_text,
                "style_id": style_id,
                "style_name": style_info.style_name,
                "inference_time_ms": inference_time_ms,
            }

        except Exception as e:
            logger.error("风格迁移失败 (task_id=%s): %s", task.id, e)
            task.status = "failed"
            task.error_message = str(e)
            await db.commit()

            return {
                "task_id": task.id,
                "status": "failed",
                "error": str(e),
            }

    async def _call_model_inference(
        self,
        original_text: str,
        style_name: str,
        style_description: str,
    ) -> str:
        """
        调用 vLLM 模型进行推理

        Args:
            original_text: 原始文本
            style_name: 风格名称（如"古龙"）
            style_description: 风格描述

        Returns:
            转换后的文本
        """
        # 自动发现可用模型
        model_id = await self._discover_model()

        # 构建 Prompt
        system_prompt = self._build_system_prompt(style_name, style_description)
        user_prompt = f"请将以下文本转换为{style_name}的写作风格：\n\n{original_text}"

        # 构建请求
        # max_tokens 需预留 Qwen3 思考过程的 token 开销，否则思考把额度用完会导致实际转换内容为空
        # 按"原文长度 × 3 + 思考预留 1024"估算
        max_tokens = len(original_text) * 3 + 1024
        request_data = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": max_tokens,
        }

        # 调用 vLLM API
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.vllm_base_url}/v1/chat/completions",
                    json=request_data,
                )
                response.raise_for_status()
                result = response.json()

                # 提取生成的文本
                transformed_text = result["choices"][0]["message"]["content"]
                # 剥离 Qwen3 思考模式的 <think>...</think> 标签，只保留实际转换内容
                transformed_text = re.sub(
                    r"<think>.*?</think>\s*",
                    "",
                    transformed_text,
                    flags=re.DOTALL,
                ).strip()
                return transformed_text

            except httpx.TimeoutException:
                raise Exception(f"模型推理超时（超过 {self.timeout} 秒）")
            except httpx.HTTPStatusError as e:
                raise Exception(f"模型推理失败: HTTP {e.response.status_code}")
            except Exception as e:
                raise Exception(f"模型推理错误: {str(e)}")

    def _build_system_prompt(self, style_name: str, style_description: str) -> str:
        """构建系统提示词"""
        return f"""你是一位专业的文学风格转换专家，擅长将文本转换为{style_name}的写作风格。

{style_name}的风格特点：
{style_description}

转换要求：
1. 保持原文的核心内容和情节不变
2. 充分体现{style_name}的语言特色和叙事风格
3. 注意句式、用词、节奏的风格化处理
4. 保持文本的流畅性和可读性
5. 只输出转换后的文本，不要添加任何解释或说明"""

    async def _get_style_info(
        self,
        style_id: str,
        db: AsyncSession,
    ) -> Optional[object]:
        """获取风格信息"""
        stmt = select(StyleModelInfo).where(StyleModelInfo.style_id == style_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_task_status(
        self,
        task_id: str,
        db: AsyncSession,
    ) -> Optional[dict]:
        """查询任务状态"""
        stmt = select(StyleTransferTask).where(StyleTransferTask.id == task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()

        if not task:
            return None

        return {
            "task_id": task.id,
            "status": task.status,
            "style_id": task.style_id,
            "original_text": task.original_text,
            "transformed_text": task.transformed_text,
            "inference_time_ms": task.inference_time_ms,
            "error_message": task.error_message,
            "created_at": task.created_at.isoformat(),
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        }

    async def list_available_styles(self, db: AsyncSession) -> list:
        """列出所有可用的风格"""
        stmt = select(StyleModelInfo).order_by(StyleModelInfo.style_name)
        result = await db.execute(stmt)
        styles = result.scalars().all()

        return [
            {
                "style_id": style.style_id,
                "style_name": style.style_name,
                "description": style.description,
                "author_example": style.author_example,
                "lora_adapter_name": style.lora_adapter_name,
            }
            for style in styles
        ]


# 全局单例
style_transfer_service = StyleTransferService()
