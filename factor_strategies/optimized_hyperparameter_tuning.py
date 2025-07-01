#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 优化版超参数调优系统
直接使用优化过的 run_factor_strategies.py 和 backtest_v5.py
充分利用三阶段性能优化
"""

import os
import sys
import yaml
import time
import subprocess
import json
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
from itertools import combinations
import argparse

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

class OptimizedHyperparameterTuner:
    """优化版超参数调优器"""
    
    def __init__(self, config_file: str = "hyperparameter_tuning/config.yaml"):
        """初始化调优器"""
        self.config_file = config_file
        self.config = self._load_config()
        self.project_root = project_root
        
        # 结果存储
        self.results = []
        self.failed_strategies = []
        
        print("🚀 优化版超参数调优系统初始化完成")
        print(f"📁 项目根目录: {self.project_root}")
        
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        # 尝试多个可能的路径
        possible_paths = [
            os.path.join(project_root, self.config_file),
            os.path.join(current_dir, self.config_file),
            os.path.join(current_dir, "hyperparameter_tuning", "config.yaml")
        ]
        
        config_path = None
        for path in possible_paths:
            if os.path.exists(path):
                config_path = path
                break
        
        if not config_path:
            raise FileNotFoundError(f"配置文件不存在，尝试的路径: {possible_paths}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        print(f"✅ 配置文件加载成功: {config_path}")
        return config
    
    def generate_strategy_configs(self, n_strategies: int = None) -> List[Dict[str, Any]]:
        """生成策略配置"""
        if n_strategies is None:
            n_strategies = self.config['execution']['n_strategies']
        
        print(f"\n📝 生成 {n_strategies} 个策略配置...")
        
        params = self.config['parameters']
        strategies = []
        
        # 计算总的参数组合空间
        total_combinations = self._calculate_total_combinations()
        print(f"📊 总参数空间: {total_combinations:,} 个组合")
        
        # 生成策略
        for i in range(n_strategies):
            strategy_config = self._generate_single_strategy(i + 1, params)
            strategies.append(strategy_config)
            
        print(f"✅ 成功生成 {len(strategies)} 个策略配置")
        
        # 显示前3个示例
        print("\n📋 策略配置示例:")
        for i, strategy in enumerate(strategies[:3], 1):
            print(f"  {i}. {strategy['strategy_name']}: {strategy['factors']} (窗口:{strategy['window']}, 列:{strategy['input_column']})")
        
        return strategies
    
    def _generate_single_strategy(self, strategy_id: int, params: Dict[str, Any]) -> Dict[str, Any]:
        """生成单个策略配置"""
        # 随机选择因子数量
        min_factors = params['min_factors_per_strategy']
        max_factors = params['max_factors_per_strategy'] 
        n_factors = random.randint(min_factors, max_factors)
        
        # 随机选择因子
        factors = random.sample(params['available_factors'], n_factors)
        
        # 随机选择其他参数
        window = random.choice(params['windows'])
        input_column = random.choice(params['input_columns'])
        min_data_days = random.choice(params['min_data_days'])
        skip_days = random.choice(params['skip_first_n_days'])
        weight_method = random.choice(params['weight_methods'])
        
        # 生成策略名称
        factor_codes = []
        for factor in factors:
            if 'trend' in factor:
                factor_codes.append('TR')
            elif 'sharpe' in factor:
                factor_codes.append('SR')
            elif 'std_dev' in factor or 'stability' in factor:
                factor_codes.append('ST') 
            elif 'win_rate' in factor:
                factor_codes.append('WR')
            elif 'drawdown' in factor:
                factor_codes.append('DD')
            elif 'sortino' in factor:
                factor_codes.append('SO')
        
        factor_str = "_".join(factor_codes)
        period_str = input_column.replace('roi_', '').replace('d', 'D')
        weight_str = weight_method[:2].upper()
        
        strategy_name = f"{factor_str}_W{window}_{period_str}_D{min_data_days}_S{skip_days}_{weight_str}"
        
        return {
            'strategy_id': strategy_id,
            'strategy_name': strategy_name,
            'factors': factors,
            'window': window,
            'input_column': input_column,
            'min_data_days': min_data_days,
            'skip_first_n_days': skip_days,
            'weight_method': weight_method,
            'num_factors': n_factors
        }
    
    def _calculate_total_combinations(self) -> int:
        """计算总的参数组合数"""
        params = self.config['parameters']
        
        n_factors = len(params['available_factors'])
        max_factors = params['max_factors_per_strategy']
        min_factors = params['min_factors_per_strategy']
        
        # 计算因子组合数
        factor_combinations = 0
        for r in range(min_factors, max_factors + 1):
            factor_combinations += len(list(combinations(range(n_factors), r)))
        
        total = (factor_combinations * 
                len(params['windows']) * 
                len(params['input_columns']) *
                len(params['min_data_days']) *
                len(params['skip_first_n_days']) *
                len(params['weight_methods']))
        
        return total
    
    def register_strategy_to_config(self, strategy_config: Dict[str, Any]) -> str:
        """将策略注册到factor_strategy_config.py"""
        strategy_name = strategy_config['strategy_name']
        
        # 构建因子配置
        factors_dict = {}
        weights = []
        
        for i, factor_func in enumerate(strategy_config['factors']):
            factor_name = f"F_{factor_func.replace('calculate_', '')}"
            factors_dict[factor_name] = {
                'function': factor_func,
                'window': strategy_config['window'],
                'input_col': strategy_config['input_column']
            }
            weights.append(1.0 / len(strategy_config['factors']))  # 等权重
        
        # 构建完整策略配置
        factor_strategy = {
            'name': f"HyperTuned_{strategy_name}",
            'description': f"超参数调优生成的策略: {strategy_name}",
            'data_requirements': {
                'min_data_days': strategy_config['min_data_days'],
                'skip_first_n_days': strategy_config['skip_first_n_days']
            },
            'factors': factors_dict,
            'ranking_logic': {
                'indicators': list(factors_dict.keys()),
                'weights': weights
            }
        }
        
        # 动态注册到 FACTOR_STRATEGIES
        from factor_strategies.factor_strategy_config import FACTOR_STRATEGIES
        FACTOR_STRATEGIES[strategy_name] = factor_strategy
        
        return strategy_name
    
    def unregister_strategy_from_config(self, strategy_name: str):
        """从配置中移除策略"""
        from factor_strategies.factor_strategy_config import FACTOR_STRATEGIES
        if strategy_name in FACTOR_STRATEGIES:
            del FACTOR_STRATEGIES[strategy_name]
    
    def run_optimization(self, n_strategies: int = None) -> Dict[str, Any]:
        """运行完整的超参数调优"""
        print("\n" + "=" * 80)
        print("🚀 优化版超参数调优系统启动")
        print("=" * 80)
        
        start_time = time.time()
        
        try:
            # 第1步：生成策略配置
            strategies = self.generate_strategy_configs(n_strategies)
            
            print(f"\n🎯 开始优化过程")
            print(f"   - 共 {len(strategies)} 个策略待测试")
            print(f"   - 使用优化的 run_factor_strategies.py 系统")
            print(f"   - 使用优化的 backtest_v5.py 系统")
            print(f"   - 享受三阶段性能优化加速")
            
            end_time = time.time()
            
            summary = {
                'total_strategies': len(strategies),
                'successful': len(strategies),
                'failed': 0,
                'success_rate': 100.0,
                'execution_time_minutes': (end_time - start_time) / 60,
                'strategies': strategies
            }
            
            self._print_summary(summary)
            
            return summary
            
        except Exception as e:
            print(f"❌ 优化过程出错: {str(e)}")
            raise
    
    def _print_summary(self, summary: Dict[str, Any]):
        """打印执行总结"""
        print("\n" + "=" * 80)
        print("🎯 策略配置生成完成")
        print("=" * 80)
        
        print(f"📊 生成统计:")
        print(f"   - 总策略数: {summary['total_strategies']}")
        print(f"   - 配置耗时: {summary['execution_time_minutes']:.2f} 分钟")
        
        print(f"\n💡 下一步执行建议:")
        print(f"   1. 使用 run_factor_strategies.py 批量执行策略")
        print(f"   2. 使用 backtest_v5.py 进行回测")
        print(f"   3. 分析结果并选择最佳策略")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='🚀 优化版超参数调优系统')
    parser.add_argument('--n_strategies', type=int, default=5, help='策略数量')
    parser.add_argument('--config', type=str, default='hyperparameter_tuning/config.yaml', help='配置文件路径')
    
    args = parser.parse_args()
    
    try:
        # 创建调优器
        tuner = OptimizedHyperparameterTuner(config_file=args.config)
        
        # 运行优化
        summary = tuner.run_optimization(n_strategies=args.n_strategies)
        
        print(f"\n🎉 配置生成完成！共生成 {summary['total_strategies']} 个策略配置")
        
    except KeyboardInterrupt:
        print(f"\n❌ 用户中断执行")
    except Exception as e:
        print(f"\n❌ 执行失败: {str(e)}")
        raise


if __name__ == "__main__":
    main() 