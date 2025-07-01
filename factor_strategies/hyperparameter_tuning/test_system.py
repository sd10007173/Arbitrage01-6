#!/usr/bin/env python3
"""
大規模超參數調優系統測試腳本
Test Script for Mass Hyperparameter Tuning System
"""

import sys
import logging
from pathlib import Path

# 添加項目根目錄到路徑
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from factor_strategies.hyperparameter_tuning.mass_tuning_system import MassTuningSystem

def test_basic_functionality():
    """測試基本功能"""
    print("🧪 測試大規模超參數調優系統基本功能")
    print("=" * 60)
    
    try:
        # 初始化系統
        print("1. 初始化系統...")
        config_path = Path(__file__).parent / "mass_tuning_config.yaml"
        system = MassTuningSystem(str(config_path))
        print("✅ 系統初始化成功")
        
        # 驗證環境
        print("\n2. 驗證執行環境...")
        env_check = system.execution_engine.validate_environment()
        if env_check['valid']:
            print("✅ 環境驗證通過")
        else:
            print("⚠️  環境驗證問題:")
            for issue in env_check['issues']:
                print(f"   - {issue}")
        
        # 生成小規模測試策略
        print("\n3. 生成測試策略參數組合...")
        session_id = system.generate_strategies(mode="sampling", size=5)
        print(f"✅ 生成策略成功，會話ID: {session_id}")
        
        # 查看生成的策略
        print("\n4. 查看生成的策略...")
        status = system.get_status(session_id, detailed=True)
        print(f"✅ 會話狀態: {status.get('status')}")
        print(f"   總策略數: {status.get('total_strategies')}")
        print(f"   進度: {status.get('progress_percent', 0):.1f}%")
        
        # 測試參數空間信息
        print("\n5. 獲取參數空間信息...")
        param_info = system.param_generator.get_parameter_space_info()
        print(f"✅ 參數數量: {param_info['parameter_count']}")
        print(f"   總組合數: {param_info['total_combinations']:,}")
        
        # 顯示參數詳情
        print("\n   參數詳情:")
        for param_name, param_info in param_info['parameters'].items():
            print(f"   - {param_name}: {param_info['type']}, {param_info['value_count']} 個值")
            if param_info['sample_values']:
                print(f"     樣本值: {param_info['sample_values']}")
        
        print(f"\n✅ 基本功能測試完成")
        return True
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_parameter_generation():
    """測試參數生成功能"""
    print("\n🧪 測試參數生成功能")
    print("=" * 40)
    
    try:
        config_path = Path(__file__).parent / "mass_tuning_config.yaml"
        system = MassTuningSystem(str(config_path))
        
        # 測試不同生成模式
        test_cases = [
            ("sampling", "random", 3),
            ("sampling", "grid", 5),
            ("exhaustive", None, 10),  # 限制前10個
        ]
        
        for mode, method, size in test_cases:
            print(f"\n測試 {mode} 模式, 方法: {method}, 大小: {size}")
            try:
                if mode == "sampling":
                    strategies = system.param_generator.generate_strategies(
                        mode=mode, size=size, method=method
                    )
                else:
                    strategies = system.param_generator.generate_strategies(
                        mode=mode, size=size
                    )
                    
                print(f"✅ 生成策略數量: {len(strategies)}")
                
                # 顯示第一個策略示例
                if strategies:
                    first_strategy = strategies[0]
                    print(f"   示例策略: {first_strategy['strategy_id']}")
                    print(f"   因子: {first_strategy['factors']}")
                    print(f"   窗口: {first_strategy['window_size']}")
                    print(f"   重平衡: {first_strategy['rebalance_frequency']}")
                    
            except Exception as e:
                print(f"❌ {mode} 模式測試失敗: {e}")
                
        return True
        
    except Exception as e:
        print(f"❌ 參數生成測試失敗: {e}")
        return False

def test_database_operations():
    """測試數據庫操作"""
    print("\n🧪 測試數據庫操作")
    print("=" * 40)
    
    try:
        config_path = Path(__file__).parent / "mass_tuning_config.yaml"
        system = MassTuningSystem(str(config_path))
        
        # 測試創建會話
        print("1. 測試創建會話...")
        session_id = system.progress_manager.create_session(
            mode="test",
            total_strategies=10,
            notes="測試會話"
        )
        print(f"✅ 創建會話: {session_id}")
        
        # 測試添加策略到隊列
        print("\n2. 測試添加策略到隊列...")
        test_strategies = [
            {
                'strategy_id': f'test_strategy_{i:03d}',
                'factors': ['SR'],
                'window_size': 30,
                'rebalance_frequency': 7,
                'data_period': 60,
                'selection_count': 5,
                'weight_method': 'EQ'
            }
            for i in range(5)
        ]
        
        system.progress_manager.add_strategies_to_queue(session_id, test_strategies)
        print(f"✅ 添加 {len(test_strategies)} 個策略到隊列")
        
        # 測試獲取待執行策略
        print("\n3. 測試獲取待執行策略...")
        pending = system.progress_manager.get_pending_strategies(session_id, limit=3)
        print(f"✅ 獲取待執行策略: {len(pending)} 個")
        
        # 測試狀態查詢
        print("\n4. 測試狀態查詢...")
        status = system.get_status(session_id)
        print(f"✅ 會話狀態: {status}")
        
        # 清理測試數據
        print("\n5. 清理測試數據...")
        system.clean_data(session_id)
        print("✅ 測試數據清理完成")
        
        return True
        
    except Exception as e:
        print(f"❌ 數據庫操作測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主測試函數"""
    print("🚀 大規模超參數調優系統測試")
    print("=" * 80)
    
    # 設置日誌級別
    logging.basicConfig(level=logging.INFO)
    
    # 執行測試
    tests = [
        ("基本功能測試", test_basic_functionality),
        ("參數生成測試", test_parameter_generation),
        ("數據庫操作測試", test_database_operations),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"\n✅ {test_name} 通過")
            else:
                print(f"\n❌ {test_name} 失敗")
        except Exception as e:
            print(f"\n❌ {test_name} 異常: {e}")
    
    print(f"\n📊 測試結果: {passed}/{total} 通過")
    
    if passed == total:
        print("🎉 所有測試通過！系統準備就緒。")
        print("\n📖 使用指南:")
        print("   # 生成策略參數組合")
        print("   python mass_tuning_system.py generate --mode sampling --size 100")
        print("")
        print("   # 查看執行狀態")
        print("   python mass_tuning_system.py status --detailed")
        print("")
        print("   # 執行批量回測（注意：需要真實回測環境）")
        print("   python mass_tuning_system.py execute --parallel 2")
    else:
        print("⚠️  部分測試失敗，請檢查系統配置。")
        return 1
        
    return 0

if __name__ == "__main__":
    exit(main()) 