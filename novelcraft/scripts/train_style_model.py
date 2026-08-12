#!/usr/bin/env python3
"""
风格迁移模型训练脚本

使用 LLaMA Factory 训练 Qwen3-8B 的风格 LoRA 适配器
"""
import os
import json
import argparse
from pathlib import Path


def create_training_config(style_name, style_id, dataset_path, output_dir):
    """创建训练配置文件"""
    config = {
        "model_name_or_path": "Qwen/Qwen3-8B-Instruct",
        "quantization_bit": 4,
        "lora_rank": 16,
        "lora_alpha": 32,
        "lora_dropout": 0.05,
        "lora_target": "all",
        "stage": "sft",
        "do_train": True,
        "finetuning_type": "lora",
        "dataset": f"{style_id}_style",
        "template": "qwen",
        "cutoff_len": 2048,
        "output_dir": output_dir,
        "overwrite_output_dir": True,
        "per_device_train_batch_size": 4,
        "gradient_accumulation_steps": 4,
        "learning_rate": 5e-5,
        "num_train_epochs": 3,
        "lr_scheduler_type": "cosine",
        "warmup_ratio": 0.1,
        "logging_steps": 10,
        "save_steps": 500,
        "save_total_limit": 3,
        "optim": "adamw_torch",
        "weight_decay": 0.01,
        "max_grad_norm": 1.0,
        "fp16": True,
        "report_to": "tensorboard",
    }

    return config


def create_dataset_info(style_id, dataset_file):
    """创建数据集信息配置"""
    return {
        f"{style_id}_style": {
            "file_name": dataset_file,
            "formatting": "alpaca",
            "columns": {
                "prompt": "instruction",
                "query": "input",
                "response": "output"
            }
        }
    }


def generate_sample_data(style_name, style_id, num_samples=100):
    """生成示例训练数据"""
    samples = []

    # 根据不同风格生成示例数据
    if style_id == "gulong":
        # 古龙风格：短句、留白、节奏感
        examples = [
            {
                "input": "夜色降临，一个黑衣人走进了客栈。他坐在角落里，默默地喝着酒。",
                "output": "夜。\n黑衣人来了。\n他坐在角落。\n一个人。\n一壶酒。\n沉默如铁。"
            },
            {
                "input": "他拔出了剑，剑光闪烁，非常锋利。敌人看到后感到害怕。",
                "output": "剑出鞘。\n寒光一闪。\n快如闪电。\n敌人的脸色变了。"
            },
            {
                "input": "月光照在湖面上，波光粼粼，景色很美。",
                "output": "月光如水。\n湖面如镜。\n美得让人心碎。"
            },
        ]
    elif style_id == "caowenxuan":
        # 曹文轩风格：诗意、细腻、温暖
        examples = [
            {
                "input": "太阳升起来了，照在田野上。",
                "output": "太阳像一个金色的圆盘，缓缓地从地平线上升起，温柔地抚摸着沉睡的田野。金色的光芒洒在每一片叶子上，像是给大地披上了一层薄薄的纱衣。"
            },
            {
                "input": "小男孩在河边玩耍。",
                "output": "小男孩赤着脚，在河边的青石板上跳来跳去。清澈的河水倒映着他快乐的身影，水面上泛起一圈圈涟漪，像是时光的年轮。"
            },
        ]
    elif style_id == "jinyong":
        # 金庸风格：武侠、历史、人物
        examples = [
            {
                "input": "他使出了一招剑法。",
                "output": "只见他长剑一抖，使出了华山派的「有凤来仪」，剑光如凤凰展翅，姿态优美而凌厉，直取对方胸口要害。"
            },
            {
                "input": "两人在山顶相遇了。",
                "output": "华山之巅，云雾缭绕。两人相对而立，一个白衣飘飘，一个青衫如故。多年恩怨，今日终要了结。"
            },
        ]
    else:
        # 通用示例
        examples = [
            {
                "input": "这是一个示例文本。",
                "output": f"这是转换为{style_name}风格的示例文本。"
            }
        ]

    # 生成训练样本
    for i in range(num_samples):
        example = examples[i % len(examples)]
        sample = {
            "instruction": f"将以下文本转换为{style_name}的写作风格",
            "input": example["input"],
            "output": example["output"]
        }
        samples.append(sample)

    return samples


def main():
    parser = argparse.ArgumentParser(description="训练风格迁移 LoRA 模型")
    parser.add_argument("--style-name", required=True, help="风格名称（如：古龙）")
    parser.add_argument("--style-id", required=True, help="风格标识（如：gulong）")
    parser.add_argument("--dataset", help="训练数据集路径（JSON 格式）")
    parser.add_argument("--output-dir", default="outputs", help="输出目录")
    parser.add_argument("--generate-sample", action="store_true", help="生成示例数据")
    parser.add_argument("--num-samples", type=int, default=100, help="生成的示例数量")

    args = parser.parse_args()

    # 创建输出目录
    output_dir = Path(args.output_dir) / f"{args.style_id}-style-lora"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 数据集路径
    if args.dataset:
        dataset_path = Path(args.dataset)
    else:
        dataset_path = Path("data/style_transfer") / f"{args.style_id}_train.json"

    # 生成示例数据
    if args.generate_sample or not dataset_path.exists():
        print(f"生成 {args.num_samples} 个示例训练数据...")
        samples = generate_sample_data(args.style_name, args.style_id, args.num_samples)

        dataset_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dataset_path, "w", encoding="utf-8") as f:
            json.dump(samples, f, ensure_ascii=False, indent=2)

        print(f"示例数据已保存到: {dataset_path}")

    # 创建训练配置
    print(f"\n创建训练配置...")
    config = create_training_config(
        args.style_name,
        args.style_id,
        str(dataset_path),
        str(output_dir)
    )

    config_path = output_dir / "train_config.yaml"

    # 保存为 YAML 格式
    import yaml
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

    print(f"训练配置已保存到: {config_path}")

    # 创建数据集信息
    dataset_info = create_dataset_info(args.style_id, dataset_path.name)
    dataset_info_path = Path("data/dataset_info.json")

    # 读取现有配置（如果存在）
    if dataset_info_path.exists():
        with open(dataset_info_path, "r", encoding="utf-8") as f:
            existing_info = json.load(f)
        existing_info.update(dataset_info)
        dataset_info = existing_info

    dataset_info_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dataset_info_path, "w", encoding="utf-8") as f:
        json.dump(dataset_info, f, ensure_ascii=False, indent=2)

    print(f"数据集信息已保存到: {dataset_info_path}")

    # 打印训练命令
    print("\n" + "="*60)
    print("训练准备完成！")
    print("="*60)
    print("\n使用以下命令开始训练：")
    print(f"\nllamafactory-cli train {config_path}")
    print("\n或使用原生脚本：")
    print(f"\npython scripts/train_style_lora.py --config {config_path}")
    print("\n监控训练进度：")
    print(f"\ntensorboard --logdir {output_dir}")
    print("\n" + "="*60)


if __name__ == "__main__":
    main()
