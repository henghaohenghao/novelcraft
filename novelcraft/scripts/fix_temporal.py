#!/usr/bin/env python3
"""
修复 Temporal 依赖问题

自动检查并安装 temporalio 包
"""
import subprocess
import sys


def check_temporal():
    """检查 Temporal 是否已安装"""
    try:
        import temporalio
        print(f"✓ temporalio 已安装 (版本: {temporalio.__version__})")
        return True
    except ImportError:
        print("✗ temporalio 未安装")
        return False


def install_temporal():
    """安装 Temporal 依赖"""
    print("\n正在安装 temporalio...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "temporalio==1.7.1"
        ])
        print("✓ temporalio 安装成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ temporalio 安装失败: {e}")
        return False


def main():
    print("="*60)
    print("Temporal 依赖检查与修复")
    print("="*60)

    # 检查是否已安装
    if check_temporal():
        print("\n所有依赖已就绪！")
        return 0

    # 询问是否安装
    print("\nTemporal 工作流功能需要 temporalio 包。")
    response = input("是否现在安装？(y/n): ").lower().strip()

    if response == 'y':
        if install_temporal():
            print("\n验证安装...")
            if check_temporal():
                print("\n✓ 安装成功！现在可以使用工作流功能。")
                return 0
            else:
                print("\n✗ 安装验证失败，请手动安装：")
                print("  pip install temporalio==1.7.1")
                return 1
        else:
            print("\n✗ 安装失败，请手动安装：")
            print("  pip install temporalio==1.7.1")
            return 1
    else:
        print("\n跳过安装。")
        print("注意：工作流功能将不可用。")
        print("\n如需使用工作流功能，请运行：")
        print("  pip install temporalio==1.7.1")
        return 0


if __name__ == "__main__":
    sys.exit(main())
