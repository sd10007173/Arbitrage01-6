#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
環境檢查腳本
驗證超參數調優系統的運行環境
"""

import sys
import os
import importlib
from typing import List, Tuple


def check_python_version() -> Tuple[bool, str]:
    """檢查Python版本"""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 7:
        return True, f"✅ Python {version.major}.{version.minor}.{version.micro}"
    else:
        return False, f"❌ Python版本過低: {version.major}.{version.minor}.{version.micro} (需要3.7+)"


def check_required_packages() -> List[Tuple[str, bool, str]]:
    """檢查必需的套件"""
    required_packages = [
        'yaml',
        'pandas', 
        'numpy',
        'matplotlib',
        'seaborn'
    ]
    
    results = []
    for package in required_packages:
        try:
            importlib.import_module(package)
            results.append((package, True, "✅ 已安裝"))
        except ImportError:
            results.append((package, False, "❌ 未安裝"))
    
    return results


def check_file_structure() -> List[Tuple[str, bool, str]]:
    """檢查文件結構"""
    required_files = [
        'config.yaml',
        'param_generator.py',
        'batch_runner.py', 
        'result_analyzer.py',
        'main.py',
        'README.md'
    ]
    
    results = []
    for file in required_files:
        if os.path.exists(file):
            results.append((file, True, "✅ 存在"))
        else:
            results.append((file, False, "❌ 缺失"))
    
    return results


def check_config_file() -> Tuple[bool, str]:
    """檢查配置文件"""
    try:
        import yaml
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 檢查必要的配置項
        required_sections = ['parameters', 'execution', 'backtest', 'output', 'analysis']
        missing_sections = [section for section in required_sections if section not in config]
        
        if missing_sections:
            return False, f"❌ 配置文件缺少必要節: {', '.join(missing_sections)}"
        else:
            return True, "✅ 配置文件完整"
            
    except Exception as e:
        return False, f"❌ 配置文件錯誤: {str(e)}"


def estimate_parameter_space() -> Tuple[int, str]:
    """估算參數空間大小"""
    try:
        from param_generator import ParameterGenerator
        import yaml
        
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        generator = ParameterGenerator(config)
        space_info = generator.get_space_info()
        
        total = space_info['total_combinations']
        
        if total < 1000:
            level = "🟢 小規模"
        elif total < 10000:
            level = "🟡 中等規模"
        elif total < 100000:
            level = "🟠 大規模"
        else:
            level = "🔴 超大規模"
        
        return total, f"{level} ({total:,} 個組合)"
        
    except Exception as e:
        return 0, f"❌ 無法計算: {str(e)}"


def main():
    """主檢查函數"""
    print("🔍 超參數調優系統環境檢查")
    print("=" * 50)
    
    # 檢查Python版本
    py_ok, py_msg = check_python_version()
    print(f"\n📐 Python版本: {py_msg}")
    
    # 檢查套件
    print(f"\n📦 Python套件檢查:")
    package_results = check_required_packages()
    all_packages_ok = True
    for package, ok, msg in package_results:
        print(f"  - {package}: {msg}")
        if not ok:
            all_packages_ok = False
    
    # 檢查文件結構
    print(f"\n📁 文件結構檢查:")
    file_results = check_file_structure()
    all_files_ok = True
    for file, ok, msg in file_results:
        print(f"  - {file}: {msg}")
        if not ok:
            all_files_ok = False
    
    # 檢查配置文件
    print(f"\n⚙️  配置文件檢查:")
    config_ok, config_msg = check_config_file()
    print(f"  - config.yaml: {config_msg}")
    
    # 估算參數空間
    print(f"\n📊 參數空間估算:")
    total, space_msg = estimate_parameter_space()
    print(f"  - 總組合數: {space_msg}")
    
    # 總結
    print(f"\n" + "=" * 50)
    all_ok = py_ok and all_packages_ok and all_files_ok and config_ok
    
    if all_ok:
        print("🎉 環境檢查通過！系統準備就緒。")
        print("\n🚀 建議執行順序:")
        print("  1. python main.py --test --test-strategies 5")
        print("  2. python main.py --test --test-strategies 50") 
        print("  3. 修改config.yaml調整參數範圍")
        print("  4. python main.py")
    else:
        print("⚠️  環境檢查發現問題，請先解決後再使用系統。")
        
        if not all_packages_ok:
            missing_packages = [pkg for pkg, ok, _ in package_results if not ok]
            print(f"\n💡 安裝缺失套件: pip install {' '.join(missing_packages)}")


if __name__ == "__main__":
    main() 