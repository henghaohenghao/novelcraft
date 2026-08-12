"""
数据集准备工具

从 data 目录中的小说 jsonl 文件提取内容，使用 DeepSeek-V4 Pro 生成风格迁移训练数据
"""
import json
import os
import re
import random
from datetime import datetime
from typing import List, Dict, Tuple
from pathlib import Path
from bs4 import BeautifulSoup
from openai import OpenAI


# 风格配置
STYLE_CONFIGS = {
    "gaoxiao": {
        "name": "搞笑",
        "description": """搞笑风格的特点：
1. 使用夸张的表达和比喻，制造喜剧效果
2. 善用反转和意外，打破读者预期
3. 加入诙谐的吐槽和自嘲
4. 使用网络流行语和现代梗
5. 人物对话幽默风趣，充满戏剧性
6. 叙事轻松活泼，节奏明快""",
        "instruction": "将以下通用风格的文本改写为幽默搞笑的风格，要保持剧情内容不变，但增加幽默感和喜剧效果。"
    },
    "gufeng": {
        "name": "古风",
        "description": """古风风格的特点：
1. 使用文言文或半文半白的语言
2. 注重意境和诗意的表达
3. 善用古典诗词和典故
4. 环境描写细腻，注重氛围营造
5. 人物对话典雅含蓄
6. 叙事舒缓，富有韵律感""",
        "instruction": "将以下通用风格的文本改写为古风风格，要保持剧情内容不变，但使用古典优雅的语言和意境。"
    },
    "yanqing": {
        "name": "言情",
        "description": """言情风格的特点：
1. 注重情感细腻描写，突出内心活动
2. 善用环境烘托情绪氛围
3. 人物对话含蓄深情，富有情感张力
4. 描写细节丰富，注重感官体验
5. 叙事温婉细腻，节奏舒缓
6. 情节推进以情感发展为主线""",
        "instruction": "将以下通用风格的文本改写为言情风格，要保持剧情内容不变，但增加情感描写和浪漫氛围。"
    }
}


def extract_text_from_html(html_content: str) -> str:
    """从 HTML 中提取纯文本内容"""
    soup = BeautifulSoup(html_content, 'html.parser')

    # 提取所有 blk 标签中的文本
    blk_tags = soup.find_all('blk')
    text_parts = [blk.get_text() for blk in blk_tags]

    # 合并文本，保留段落结构
    text = '\n'.join(text_parts)

    # 清理多余的空白
    text = re.sub(r'\n\s*\n', '\n', text)
    text = text.strip()

    return text


def split_text_into_chunks(text: str, min_length: int = 100, max_length: int = 500) -> List[str]:
    """将文本切分成适合训练的段落

    Args:
        text: 输入文本
        min_length: 最小段落长度
        max_length: 最大段落长度
    """
    # 先按换行符分割
    paragraphs = text.split('\n')

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # 如果当前段落已经超过 max_length，先保存
        if len(current_chunk) + len(para) > max_length and len(current_chunk) >= min_length:
            chunks.append(current_chunk)
            current_chunk = para
        else:
            if current_chunk:
                current_chunk += "\n" + para
            else:
                current_chunk = para

    # 保存最后一个 chunk
    if len(current_chunk) >= min_length:
        chunks.append(current_chunk)

    return chunks


def generate_neutral_style_text(styled_text: str, client: OpenAI) -> str:
    """使用 LLM 将目标风格文本改写为通用风格

    Args:
        styled_text: 目标风格文本（原始小说内容）
        client: OpenAI 客户端
    """
    prompt = f"""请将以下文本改写为通用、平实的叙事风格，去除任何特殊的风格特征（如幽默、古风、言情等），只保留核心的情节内容和人物动作。要求：
1. 使用现代白话文，语言简洁明了
2. 去除夸张、诗意、情感渲染等风格化表达
3. 保持情节完整性和逻辑连贯性
4. 只输出改写后的文本，不要添加任何解释

原文：
{styled_text}

通用风格改写："""

    try:
        response = client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        neutral_text = response.choices[0].message.content.strip()
        return neutral_text
    except Exception as e:
        print(f"✗ 生成通用风格失败: {e}")
        return None


def generate_style_transfer_pair(
    styled_text: str,
    client: OpenAI,
) -> Dict[str, str]:
    """生成风格迁移数据对

    Args:
        styled_text: 目标风格文本（原始小说内容）
        client: OpenAI 客户端

    Returns:
        {"neutral": "通用风格文本", "styled": "目标风格文本（原文）"}
    """
    # 生成通用风格文本
    print(f"  生成通用风格...")
    neutral_text = generate_neutral_style_text(styled_text, client)
    if not neutral_text:
        return None

    return {
        "neutral": neutral_text,
        "styled": styled_text  # 原文就是目标风格
    }


def create_style_training_sample(
    neutral_text: str,
    styled_text: str,
    style_name: str,
    style_description: str,
) -> Dict:
    """创建单个训练样本"""
    system_prompt = f"""你是一位专业的文学风格转换专家，擅长将文本转换为{style_name}的写作风格。

{style_name}的风格特点：
{style_description}

转换要求：
1. 保持原文的核心内容和情节不变
2. 充分体现{style_name}的语言特色和叙事风格
3. 注意句式、用词、节奏的风格化处理
4. 保持文本的流畅性和可读性
5. 只输出转换后的文本，不要添加任何解释或说明"""

    user_prompt = f"请将以下文本转换为{style_name}的写作风格：\n\n{neutral_text}"

    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": styled_text}
        ]
    }


def split_train_test(samples: List[Dict], test_ratio: float = 0.1, seed: int = 42) -> Tuple[List[Dict], List[Dict]]:
    """将样本按比例分割为训练集和测试集"""
    random.seed(seed)
    indices = list(range(len(samples)))
    random.shuffle(indices)
    test_count = max(1, int(len(samples) * test_ratio))
    test_indices = set(indices[:test_count])
    train = [s for i, s in enumerate(samples) if i not in test_indices]
    test = [s for i, s in enumerate(samples) if i in test_indices]
    return train, test


def save_dataset(samples: List[Dict], output_path: str):
    """保存数据集为 jsonl 格式"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')

    print(f"✓ 数据集已保存: {output_path} ({len(samples)} 条样本)")


def process_novel_file(
    input_file: str,
    style_key: str,
    client: OpenAI,
    max_samples: int = None,
) -> List[Dict]:
    """处理单个小说文件，生成训练数据

    Args:
        input_file: 输入的 jsonl 文件路径
        style_key: 风格键
        client: OpenAI 客户端
        max_samples: 最大样本数（None 表示不限制）
    """
    style_config = STYLE_CONFIGS[style_key]
    print(f"\n处理文件: {input_file}")
    print(f"目标风格: {style_config['name']}")

    samples = []

    # 读取原始数据
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    print(f"共 {len(lines)} 个章节")

    for idx, line in enumerate(lines):
        if max_samples and len(samples) >= max_samples:
            print(f"已达到最大样本数 {max_samples}，停止处理")
            break

        try:
            data = json.loads(line)
            title = data.get('title', '')
            html_content = data.get('content', '')

            print(f"\n[{idx+1}/{len(lines)}] 处理章节: {title}")

            # 提取文本（这就是目标风格文本）
            styled_text = extract_text_from_html(html_content)
            if not styled_text:
                print("  ✗ 无法提取文本，跳过")
                continue

            # 切分段落
            chunks = split_text_into_chunks(styled_text, min_length=100, max_length=500)
            print(f"  切分为 {len(chunks)} 个段落")

            # 对每个段落生成训练样本（限制数量避免过多）
            chunk_limit = min(3, len(chunks))  # 每章最多取 3 个段落
            for chunk_idx, chunk in enumerate(chunks[:chunk_limit]):
                print(f"  段落 {chunk_idx+1}/{chunk_limit} (长度: {len(chunk)})")

                # 生成风格迁移对（原文是目标风格，生成通用风格）
                pair = generate_style_transfer_pair(chunk, client)
                if not pair:
                    continue

                # 创建训练样本：输入通用风格 → 输出目标风格
                sample = create_style_training_sample(
                    neutral_text=pair["neutral"],
                    styled_text=pair["styled"],
                    style_name=style_config["name"],
                    style_description=style_config["description"],
                )
                samples.append(sample)
                print(f"  ✓ 生成样本 {len(samples)}")

        except Exception as e:
            print(f"  ✗ 处理失败: {e}")
            continue

    return samples


def main():
    import argparse

    parser = argparse.ArgumentParser(description="从小说数据生成风格迁移训练数据集")
    parser.add_argument(
        "--style",
        type=str,
        choices=["gaoxiao", "gufeng", "yanqing", "all"],
        default="all",
        help="要处理的风格类型"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="DeepSeek API Key（也可以通过环境变量 DEEPSEEK_API_KEY 设置）"
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="每个风格最多生成的样本数（用于测试）"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="测试模式：每个风格只生成少量样本"
    )
    parser.add_argument(
        "--input-file",
        type=str,
        default=None,
        help="指定单个输入文件路径（跳过目录扫描）"
    )

    args = parser.parse_args()

    # 获取 API Key
    api_key = "sk-984e6c654c0a4fa8bdcd44a9347776da"
    if not api_key:
        print("❌ 错误：未提供 DeepSeek API Key")
        print("请通过 --api-key 参数或环境变量 DEEPSEEK_API_KEY 设置")
        return

    # 创建 OpenAI 客户端
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )

    # 测试模式
    if args.test:
        args.max_samples = 10
        print("⚠️  测试模式：每个风格只生成 10 个样本")

    # 确定要处理的风格
    styles_to_process = list(STYLE_CONFIGS.keys()) if args.style == "all" else [args.style]

    output_dir = Path("dataset")
    output_dir.mkdir(exist_ok=True)

    # 单文件模式
    if args.input_file:
        input_path = Path(args.input_file)
        if not input_path.exists():
            print(f"❌ 错误：文件不存在 {args.input_file}")
            return

        style_key = args.style if args.style != "all" else "gaoxiao"
        print(f"\n{'='*60}")
        print(f"单文件模式")
        print(f"输入文件: {input_path}")
        print(f"目标风格: {STYLE_CONFIGS[style_key]['name']}")
        print(f"{'='*60}")

        samples = process_novel_file(
            input_file=str(input_path),
            style_key=style_key,
            client=client,
            max_samples=args.max_samples,
        )

        if samples:
            train, test = split_train_test(samples)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_dataset(train, str(output_dir / f"{style_key}_train_{timestamp}.jsonl"))
            save_dataset(test, str(output_dir / f"{style_key}_test_{timestamp}.jsonl"))
            print(f"\n✅ 数据集生成完成！训练集 {len(train)} 条，测试集 {len(test)} 条")
        else:
            print(f"\n❌ 未生成任何样本")

        print(f"\n{'='*60}")
        print("数据集生成完成！")
        print(f"输出目录: {output_dir.absolute()}")
        print(f"{'='*60}")
        return

    # 目录扫描模式
    data_dir = Path("data")

    for style_key in styles_to_process:
        style_dir = data_dir / style_key

        if not style_dir.exists():
            print(f"\n⚠️  跳过 {style_key}：目录不存在 {style_dir}")
            continue

        # 查找该风格目录下的所有 jsonl 文件
        jsonl_files = list(style_dir.glob("*.jsonl"))

        if not jsonl_files:
            print(f"\n⚠️  跳过 {style_key}：没有找到 jsonl 文件")
            continue

        print(f"\n{'='*60}")
        print(f"处理风格: {STYLE_CONFIGS[style_key]['name']}")
        print(f"找到 {len(jsonl_files)} 个文件")
        print(f"{'='*60}")

        all_samples = []

        for jsonl_file in jsonl_files:
            samples = process_novel_file(
                input_file=str(jsonl_file),
                style_key=style_key,
                client=client,
                max_samples=args.max_samples - len(all_samples) if args.max_samples else None,
            )
            all_samples.extend(samples)

            if args.max_samples and len(all_samples) >= args.max_samples:
                break

        # 保存数据集
        if all_samples:
            train, test = split_train_test(all_samples)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_dataset(train, str(output_dir / f"{style_key}_train_{timestamp}.jsonl"))
            save_dataset(test, str(output_dir / f"{style_key}_test_{timestamp}.jsonl"))
            print(f"\n✅ {STYLE_CONFIGS[style_key]['name']} 风格数据集生成完成！训练集 {len(train)} 条，测试集 {len(test)} 条")
        else:
            print(f"\n❌ {STYLE_CONFIGS[style_key]['name']} 风格未生成任何样本")

    print(f"\n{'='*60}")
    print("所有数据集生成完成！")
    print(f"输出目录: {output_dir.absolute()}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
