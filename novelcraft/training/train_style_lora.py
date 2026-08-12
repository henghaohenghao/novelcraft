"""
使用 ms-swift 训练风格迁移 LoRA 适配器

支持训练多个作家风格的 LoRA 模型
适配 ms-swift v3+ 新版 API
"""
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class StyleLoRATrainingArgs:
    """风格 LoRA 训练参数"""

    # 基础模型
    model: str = "Qwen/Qwen3-8B"  # 模型 ID 或本地路径

    # 风格配置
    style_name: str = "gaoxiao"  # 风格名称：gaoxiao, gufeng, yanqing
    dataset_path: str = "dataset/gaoxiao_train.jsonl"

    # LoRA 参数
    lora_rank: int = 8
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    lora_target_modules: str = "ALL"  # 或指定具体模块如 "q_proj,v_proj"

    # 训练参数
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 4
    gradient_accumulation_steps: int = 4
    learning_rate: float = 1e-4
    warmup_ratio: float = 0.05
    max_length: int = 2048

    # 输出配置
    output_dir: str = "output"
    logging_steps: int = 10
    save_strategy: str = "epoch"
    save_total_limit: int = 3

    # 硬件配置
    torch_dtype: str = "bfloat16"
    gradient_checkpointing: bool = True

    # 多卡训练配置
    deepspeed: Optional[str] = None  # DeepSpeed 配置文件路径


def train_style_lora(args: StyleLoRATrainingArgs):
    """训练风格 LoRA（使用 swift sft CLI 命令）"""

    output_path = os.path.join(args.output_dir, f"{args.style_name}-style-lora")

    # 构建 swift sft 命令
    cmd = [
        sys.executable, "-m", "swift", "sft",
        "--model", args.model,
        "--train_type", "lora",
        "--dataset", args.dataset_path,
        "--lora_rank", str(args.lora_rank),
        "--lora_alpha", str(args.lora_alpha),
        "--lora_dropout_p", str(args.lora_dropout),
        "--lora_target_modules", args.lora_target_modules,
        "--num_train_epochs", str(args.num_train_epochs),
        "--per_device_train_batch_size", str(args.per_device_train_batch_size),
        "--gradient_accumulation_steps", str(args.gradient_accumulation_steps),
        "--learning_rate", str(args.learning_rate),
        "--warmup_ratio", str(args.warmup_ratio),
        "--max_length", str(args.max_length),
        "--output_dir", output_path,
        "--logging_steps", str(args.logging_steps),
        "--save_strategy", args.save_strategy,
        "--save_total_limit", str(args.save_total_limit),
        "--torch_dtype", args.torch_dtype,
        "--gradient_checkpointing", str(args.gradient_checkpointing).lower(),
    ]

    if args.deepspeed:
        cmd.extend(["--deepspeed", args.deepspeed])

    print(f"\n{'='*60}")
    print(f"开始训练风格 LoRA: {args.style_name}")
    print(f"模型: {args.model}")
    print(f"数据集: {args.dataset_path}")
    print(f"输出目录: {output_path}")
    print(f"LoRA 参数: rank={args.lora_rank}, alpha={args.lora_alpha}")
    print(f"命令: {' '.join(cmd)}")
    print(f"{'='*60}\n")

    # 执行训练
    result = subprocess.run(cmd, cwd=os.getcwd())

    if result.returncode != 0:
        raise RuntimeError(f"训练失败，退出码: {result.returncode}")

    print(f"\n{'='*60}")
    print(f"训练完成！模型保存在: {output_path}")
    print(f"{'='*60}\n")

    return {"output_dir": output_path, "returncode": result.returncode}


def train_all_styles(base_dataset_dir: str = "dataset", output_dir: str = "output",
                     model: str = "Qwen/Qwen3-8B"):
    """批量训练所有风格的 LoRA"""

    styles = [
        "gaoxiao",   # 搞笑
        "gufeng",    # 古风
        "yanqing",   # 言情
    ]

    results = {}

    for style in styles:
        dataset_path = os.path.join(base_dataset_dir, f"{style}_train.jsonl")

        if not os.path.exists(dataset_path):
            print(f"⚠️  跳过 {style}: 数据集文件不存在 ({dataset_path})")
            continue

        args = StyleLoRATrainingArgs(
            model=model,
            style_name=style,
            dataset_path=dataset_path,
            output_dir=output_dir,
        )

        try:
            result = train_style_lora(args)
            results[style] = result
        except Exception as e:
            print(f"❌ {style} 训练失败: {e}")
            results[style] = {"error": str(e)}

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="训练风格迁移 LoRA")
    parser.add_argument("--model", type=str, default="Qwen/Qwen3-8B",
                        help="模型 ID 或本地路径")
    parser.add_argument("--style", type=str, default="gaoxiao",
                        help="风格名称 (gaoxiao/gufeng/yanqing)")
    parser.add_argument("--dataset", type=str, default="dataset/gaoxiao_train.jsonl",
                        help="训练数据集路径")
    parser.add_argument("--output-dir", type=str, default="output",
                        help="输出目录")
    parser.add_argument("--lora-rank", type=int, default=8,
                        help="LoRA rank")
    parser.add_argument("--lora-alpha", type=int, default=32,
                        help="LoRA alpha")
    parser.add_argument("--epochs", type=int, default=3,
                        help="训练轮数")
    parser.add_argument("--batch-size", type=int, default=4,
                        help="每卡批次大小")
    parser.add_argument("--learning-rate", type=float, default=1e-4,
                        help="学习率")
    parser.add_argument("--deepspeed", type=str, default=None,
                        help="DeepSpeed 配置文件路径")
    parser.add_argument("--all", action="store_true",
                        help="训练所有风格")

    args = parser.parse_args()

    if args.all:
        # 批量训练所有风格
        print("批量训练模式：将训练所有风格的 LoRA\n")
        results = train_all_styles(output_dir=args.output_dir, model=args.model)

        print("\n" + "="*60)
        print("所有训练任务完成！")
        print("="*60)
        for style, result in results.items():
            if "error" in result:
                print(f"  ❌ {style}: {result['error']}")
            else:
                print(f"  ✓ {style}: 成功")
    else:
        # 单个风格训练
        training_args = StyleLoRATrainingArgs(
            model=args.model,
            style_name=args.style,
            dataset_path=args.dataset,
            output_dir=args.output_dir,
            lora_rank=args.lora_rank,
            lora_alpha=args.lora_alpha,
            num_train_epochs=args.epochs,
            per_device_train_batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            deepspeed=args.deepspeed,
        )

        train_style_lora(training_args)
