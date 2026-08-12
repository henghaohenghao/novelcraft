"""
初始化风格模型信息

预置三种风格：搞笑、古风、言情
与 training/prepare_dataset.py 的 STYLE_CONFIGS 保持一致
"""
import asyncio
from sqlalchemy import select
from backend.models.database import get_async_session
from backend.models.style_models import StyleModelInfo


async def init_style_models():
    """初始化风格模型数据"""
    print("初始化风格模型信息...")

    # 预置风格（与 training/prepare_dataset.py 的 STYLE_CONFIGS 一致）
    styles = [
        {
            "style_id": "gaoxiao",
            "style_name": "搞笑",
            "description": """搞笑风格的特点：
1. 使用夸张的表达和比喻，制造喜剧效果
2. 善用反转和意外，打破读者预期
3. 加入诙谐的吐槽和自嘲
4. 使用网络流行语和现代梗
5. 人物对话幽默风趣，充满戏剧性
6. 叙事轻松活泼，节奏明快""",
            "author_example": "网络搞笑小说、段子式叙事",
            "lora_adapter_name": "gaoxiao-style-lora",
        },
        {
            "style_id": "gufeng",
            "style_name": "古风",
            "description": """古风风格的特点：
1. 使用文言文或半文半白的语言
2. 注重意境和诗意的表达
3. 善用古典诗词和典故
4. 环境描写细腻，注重氛围营造
5. 人物对话典雅含蓄
6. 叙事舒缓，富有韵律感""",
            "author_example": "古典言情、仙侠、架空历史小说",
            "lora_adapter_name": "gufeng-style-lora",
        },
        {
            "style_id": "yanqing",
            "style_name": "言情",
            "description": """言情风格的特点：
1. 注重情感细腻描写，突出内心活动
2. 善用环境烘托情绪氛围
3. 人物对话含蓄深情，富有情感张力
4. 描写细节丰富，注重感官体验
5. 叙事温婉细腻，节奏舒缓
6. 情节推进以情感发展为主线""",
            "author_example": "现代言情、都市情感小说",
            "lora_adapter_name": "yanqing-style-lora",
        },
    ]

    async for db in get_async_session():
        for style_data in styles:
            # 检查是否已存在
            stmt = select(StyleModelInfo).where(
                StyleModelInfo.style_id == style_data["style_id"]
            )
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if not existing:
                style = StyleModelInfo(**style_data)
                db.add(style)
                print(f"  添加风格: {style_data['style_name']} ({style_data['style_id']})")
            else:
                print(f"  风格已存在: {style_data['style_name']}")

        await db.commit()
        print("\n风格模型初始化完成！")
        break


if __name__ == "__main__":
    asyncio.run(init_style_models())
