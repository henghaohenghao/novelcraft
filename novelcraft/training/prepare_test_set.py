"""
测试集准备脚本

从训练数据集中分离出测试集，确保：
1. 测试集和训练集不重复
2. 覆盖多种场景类型
3. 每个风格都有对应的测试样本
"""
import json
import random
from pathlib import Path
from typing import List, Dict


def load_training_data(train_file: str) -> List[Dict]:
    """加载训练数据"""
    samples = []
    with open(train_file, 'r', encoding='utf-8') as f:
        for line in f:
            samples.append(json.loads(line))
    return samples


def extract_test_samples(
    train_samples: List[Dict],
    test_ratio: float = 0.1,
    min_test_samples: int = 10,
    max_test_samples: int = 50,
) -> tuple[List[Dict], List[Dict]]:
    """从训练数据中分离测试集

    Args:
        train_samples: 训练样本列表
        test_ratio: 测试集比例
        min_test_samples: 最小测试样本数
        max_test_samples: 最大测试样本数

    Returns:
        (train_samples, test_samples)
    """
    # 打乱顺序
    samples = train_samples.copy()
    random.shuffle(samples)

    # 计算测试集大小
    test_size = max(
        min_test_samples,
        min(max_test_samples, int(len(samples) * test_ratio))
    )

    test_samples = samples[:test_size]
    train_samples = samples[test_size:]

    return train_samples, test_samples


def create_benchmark_test_set(
    test_samples: List[Dict],
    num_samples: int = 5,
) -> List[Dict]:
    """创建用于 benchmark 的测试集

    从测试集中选择有代表性的样本用于对比实验
    """
    # 随机选择 num_samples 个样本
    selected = random.sample(test_samples, min(num_samples, len(test_samples)))

    # 提取原始文本（用于 benchmark）
    benchmark_cases = []
    for sample in selected:
        # 从 messages 中提取用户输入的原文
        messages = sample["messages"]
        user_message = next((m for m in messages if m["role"] == "user"), None)

        if user_message:
            # 提取 "请将以下文本转换为...风格：\n\n{原文}" 中的原文
            content = user_message["content"]
            # 找到最后一个 \n\n 之后的内容
            if "\n\n" in content:
                original_text = content.split("\n\n")[-1].strip()
            else:
                original_text = content

            # 提取参考答案（目标风格文本）
            assistant_message = next((m for m in messages if m["role"] == "assistant"), None)
            reference_text = assistant_message["content"] if assistant_message else None

            benchmark_cases.append({
                "text": original_text,
                "reference": reference_text,
            })

    return benchmark_cases


def save_jsonl(data: List[Dict], output_file: str):
    """保存为 jsonl 格式"""
    with open(output_file, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    print(f"✓ 已保存: {output_file} ({len(data)} 条)")


def save_json(data: List[Dict], output_file: str):
    """保存为 json 格式"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✓ 已保存: {output_file} ({len(data)} 条)")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="准备测试集")
    parser.add_argument("--dataset-dir", type=str, default="dataset",
                        help="数据集目录")
    parser.add_argument("--test-ratio", type=float, default=0.1,
                        help="测试集比例")
    parser.add_argument("--benchmark-samples", type=int, default=5,
                        help="用于 benchmark 的样本数")
    parser.add_argument("--seed", type=int, default=42,
                        help="随机种子")

    args = parser.parse_args()

    random.seed(args.seed)

    dataset_dir = Path(args.dataset_dir)

    # 查找所有训练集文件
    train_files = list(dataset_dir.glob("*_train.jsonl"))

    if not train_files:
        print("❌ 未找到训练集文件")
        print(f"请确保 {dataset_dir} 目录下有 *_train.jsonl 文件")
        return

    print(f"找到 {len(train_files)} 个训练集文件\n")

    # 创建输出目录
    test_dir = dataset_dir / "test"
    test_dir.mkdir(exist_ok=True)

    benchmark_dir = dataset_dir / "benchmark"
    benchmark_dir.mkdir(exist_ok=True)

    all_benchmark_cases = {}

    for train_file in train_files:
        style_name = train_file.stem.replace("_train", "")
        print(f"处理: {style_name}")

        # 加载训练数据
        train_samples = load_training_data(str(train_file))
        print(f"  原始样本数: {len(train_samples)}")

        # 分离测试集
        new_train_samples, test_samples = extract_test_samples(
            train_samples,
            test_ratio=args.test_ratio,
        )
        print(f"  训练集: {len(new_train_samples)}")
        print(f"  测试集: {len(test_samples)}")

        # 保存新的训练集（减去测试集）
        new_train_file = dataset_dir / f"{style_name}_train_split.jsonl"
        save_jsonl(new_train_samples, str(new_train_file))

        # 保存测试集
        test_file = test_dir / f"{style_name}_test.jsonl"
        save_jsonl(test_samples, str(test_file))

        # 创建 benchmark 测试集
        benchmark_cases = create_benchmark_test_set(
            test_samples,
            num_samples=args.benchmark_samples,
        )
        all_benchmark_cases[style_name] = benchmark_cases

        print()

    # 保存所有 benchmark 测试集
    benchmark_file = benchmark_dir / "test_cases.json"
    save_json(all_benchmark_cases, str(benchmark_file))

    print("="*60)
    print("测试集准备完成！")
    print("="*60)
    print(f"\n目录结构:")
    print(f"  {dataset_dir}/")
    print(f"    ├── *_train_split.jsonl  (新训练集，已移除测试样本)")
    print(f"    ├── test/")
    print(f"    │   └── *_test.jsonl     (完整测试集)")
    print(f"    └── benchmark/")
    print(f"        └── test_cases.json  (用于对比实验的精选样本)")
    print()
    print(f"使用方法:")
    print(f"  1. 使用 *_train_split.jsonl 进行训练")
    print(f"  2. 使用 test/*_test.jsonl 进行完整评估")
    print(f"  3. 使用 benchmark/test_cases.json 进行对比实验")


if __name__ == "__main__":
    main()
