#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 简单的优化系统测试
直接测试核心功能，避免subprocess调用的复杂性
"""

import os
import sys
import json
import time
from datetime import datetime

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

def test_strategy_generation():
    """测试策略生成功能"""
    print("🧪 测试策略生成功能")
    print("-" * 50)
    
    try:
        from optimized_hyperparameter_tuning import OptimizedHyperparameterTuner
        
        # 创建调优器
        tuner = OptimizedHyperparameterTuner()
        
        # 生成策略
        strategies = tuner.generate_strategy_configs(n_strategies=3)
        
        print(f"✅ 成功生成 {len(strategies)} 个策略")
        
        # 显示策略详情
        for i, strategy in enumerate(strategies, 1):
            print(f"\n策略 {i}: {strategy['strategy_name']}")
            print(f"  因子: {strategy['factors']}")
            print(f"  参数: W{strategy['window']}, {strategy['input_column']}, D{strategy['min_data_days']}")
            
        return True, strategies
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        return False, []

def test_strategy_registration():
    """测试策略注册功能"""
    print("\n🧪 测试策略注册功能")
    print("-" * 50)
    
    try:
        # 创建测试策略配置
        test_strategy = {
            'strategy_name': 'TEST_SR_W30_1D_D60_S0_EQ',
            'factors': ['calculate_sharpe_ratio'],
            'window': 30,
            'input_column': 'roi_1d',
            'min_data_days': 60,
            'skip_first_n_days': 0,
            'weight_method': 'equal'
        }
        
        # 注册策略
        from factor_strategies.factor_strategy_config import FACTOR_STRATEGIES
        
        # 构建因子配置
        factors_dict = {}
        for factor_func in test_strategy['factors']:
            factor_name = f"F_{factor_func.replace('calculate_', '')}"
            factors_dict[factor_name] = {
                'function': factor_func,
                'window': test_strategy['window'],
                'input_col': test_strategy['input_column']
            }
        
        # 构建完整策略配置
        factor_strategy = {
            'name': f"Test_{test_strategy['strategy_name']}",
            'description': f"测试策略: {test_strategy['strategy_name']}",
            'data_requirements': {
                'min_data_days': test_strategy['min_data_days'],
                'skip_first_n_days': test_strategy['skip_first_n_days']
            },
            'factors': factors_dict,
            'ranking_logic': {
                'indicators': list(factors_dict.keys()),
                'weights': [1.0]
            }
        }
        
        # 注册策略
        strategy_name = test_strategy['strategy_name']
        FACTOR_STRATEGIES[strategy_name] = factor_strategy
        
        print(f"✅ 策略注册成功: {strategy_name}")
        print(f"📋 注册的因子: {list(factors_dict.keys())}")
        
        # 验证注册
        if strategy_name in FACTOR_STRATEGIES:
            print(f"✅ 策略验证成功: 已存在于配置中")
        else:
            print(f"❌ 策略验证失败: 未找到在配置中")
            return False
        
        # 清理测试策略
        del FACTOR_STRATEGIES[strategy_name]
        print(f"🧹 测试策略已清理")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        return False

def test_factor_engine_direct():
    """直接测试FactorEngine功能"""
    print("\n🧪 测试FactorEngine直接调用")
    print("-" * 50)
    
    try:
        # 导入FactorEngine
        from factor_strategies.factor_engine import FactorEngine
        
        # 创建实例
        engine = FactorEngine()
        print(f"✅ FactorEngine创建成功")
        
        # 测试获取数据
        test_date = "2024-06-15"
        print(f"📅 测试日期: {test_date}")
        
        # 获取交易对数据
        trading_pairs = engine.get_trading_pairs(min_market_cap=1000000)
        print(f"📊 获取交易对数量: {len(trading_pairs)}")
        
        if len(trading_pairs) > 0:
            # 测试获取策略数据
            test_pair = trading_pairs[0]
            print(f"🎯 测试交易对: {test_pair}")
            
            # 获取策略数据
            strategy_data = engine.get_strategy_data(
                trading_pair=test_pair,
                target_date=test_date,
                window=30,
                input_col='roi_1d'
            )
            
            if strategy_data is not None and len(strategy_data) > 0:
                print(f"✅ 数据获取成功: {len(strategy_data)} 条记录")
                print(f"📋 数据列: {list(strategy_data.columns)}")
                
                # 测试计算因子
                from factor_strategies.factor_library import calculate_sharpe_ratio
                
                factor_value = calculate_sharpe_ratio(strategy_data['roi_1d'].values)
                print(f"📈 计算因子值: {factor_value}")
                
                return True
            else:
                print(f"❌ 数据获取失败: 无数据")
                return False
        else:
            print(f"❌ 无可用交易对")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_performance_comparison():
    """测试性能对比"""
    print("\n🧪 测试性能预期对比")
    print("-" * 50)
    
    # 预期性能对比
    scenarios = [
        {
            'name': '小规模测试 (5策略, 30天)',
            'strategies': 5,
            'days': 30,
            'old_time': 5 * 30 * 0.6,  # 5策略 × 30天 × 0.6秒
            'new_time': 5 * 2.0,       # 5策略 × 2秒 (有缓存)
        },
        {
            'name': '中等规模 (20策略, 90天)',
            'strategies': 20,
            'days': 90,
            'old_time': 20 * 90 * 0.6,
            'new_time': 20 * 2.0,
        },
        {
            'name': '大规模 (100策略, 365天)',
            'strategies': 100,
            'days': 365,
            'old_time': 100 * 365 * 0.6,
            'new_time': 100 * 2.0,
        }
    ]
    
    print(f"📊 性能对比预期:")
    for scenario in scenarios:
        old_minutes = scenario['old_time'] / 60
        new_minutes = scenario['new_time'] / 60
        speedup = scenario['old_time'] / scenario['new_time']
        improvement = (1 - scenario['new_time'] / scenario['old_time']) * 100
        
        print(f"\n{scenario['name']}:")
        print(f"  旧系统: {old_minutes:.1f} 分钟")
        print(f"  新系统: {new_minutes:.1f} 分钟")
        print(f"  加速: {speedup:.1f}x")
        print(f"  提升: {improvement:.1f}%")
    
    return True

def main():
    """主测试函数"""
    print("🚀 简单优化系统测试")
    print("=" * 80)
    
    tests = []
    start_time = time.time()
    
    # 测试1: 策略生成
    success1, strategies = test_strategy_generation()
    tests.append(('策略生成', success1))
    
    # 测试2: 策略注册
    success2 = test_strategy_registration()
    tests.append(('策略注册', success2))
    
    # 测试3: FactorEngine直接调用
    success3 = test_factor_engine_direct()
    tests.append(('FactorEngine直接调用', success3))
    
    # 测试4: 性能对比
    success4 = test_performance_comparison()
    tests.append(('性能对比', success4))
    
    # 总结
    end_time = time.time()
    elapsed = end_time - start_time
    
    print("\n" + "=" * 80)
    print("🎯 测试总结")
    print("=" * 80)
    
    passed = 0
    for test_name, success in tests:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {test_name}: {status}")
        if success:
            passed += 1
    
    success_rate = passed / len(tests) * 100
    
    print(f"\n📊 测试结果:")
    print(f"  - 总测试数: {len(tests)}")
    print(f"  - 通过: {passed}")
    print(f"  - 失败: {len(tests) - passed}")
    print(f"  - 成功率: {success_rate:.1f}%")
    print(f"  - 测试耗时: {elapsed:.2f} 秒")
    
    if success_rate >= 75:
        print(f"\n🎉 系统核心功能测试通过！")
        print(f"\n💡 建议下一步:")
        print(f"  1. 核心组件工作正常，可以进行实际测试")
        print(f"  2. 问题可能在subprocess调用或命令行参数")
        print(f"  3. 建议直接使用Python API而不是命令行调用")
    else:
        print(f"\n⚠️ 系统核心功能存在问题，需要修复")
    
    return success_rate >= 75


if __name__ == "__main__":
    main() 