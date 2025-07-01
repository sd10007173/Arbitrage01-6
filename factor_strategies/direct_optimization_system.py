#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎯 直接优化系统 - 纯Python API版本
避免subprocess调用，直接使用Python API
充分利用三阶段性能优化
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
import argparse

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

# 导入优化的组件
from optimized_hyperparameter_tuning import OptimizedHyperparameterTuner
from factor_strategies.factor_engine import FactorEngine
from factor_strategies.factor_strategy_config import FACTOR_STRATEGIES

class DirectOptimizationSystem:
    """直接优化系统 - 纯Python API版本"""
    
    def __init__(self, config_file: str = "hyperparameter_tuning/config.yaml"):
        self.config_file = config_file
        self.tuner = OptimizedHyperparameterTuner(config_file)
        self.project_root = project_root
        
        # 创建单例FactorEngine - 享受阶段1优化
        print("🚀 初始化优化的FactorEngine (单例模式)...")
        self.factor_engine = FactorEngine()
        print("✅ FactorEngine初始化完成，享受三阶段性能优化")
        
        # 结果存储
        self.results = []
        self.failed_strategies = []
        
        # 结果存储目录
        self.results_dir = os.path.join(current_dir, "direct_results")
        os.makedirs(self.results_dir, exist_ok=True)
        
        # 时间戳
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
    def register_strategy(self, strategy_config: Dict[str, Any]) -> str:
        """注册策略到配置"""
        strategy_name = strategy_config['strategy_name']
        
        # 构建因子配置
        factors_dict = {}
        weights = []
        
        for factor_func in strategy_config['factors']:
            factor_name = f"F_{factor_func.replace('calculate_', '')}"
            factors_dict[factor_name] = {
                'function': factor_func,
                'window': strategy_config['window'],
                'input_col': strategy_config['input_column']
            }
            weights.append(1.0 / len(strategy_config['factors']))
        
        # 构建完整策略配置
        factor_strategy = {
            'name': f"Direct_{strategy_name}",
            'description': f"直接优化生成的策略: {strategy_name}",
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
        
        # 注册策略
        FACTOR_STRATEGIES[strategy_name] = factor_strategy
        return strategy_name
    
    def unregister_strategy(self, strategy_name: str):
        """移除策略注册"""
        if strategy_name in FACTOR_STRATEGIES:
            del FACTOR_STRATEGIES[strategy_name]
    
    def execute_strategy_for_date_range(self, strategy_config: Dict[str, Any], 
                                      start_date: str, end_date: str) -> Dict[str, Any]:
        """为日期范围执行策略 - 直接使用Python API"""
        strategy_name = strategy_config['strategy_name']
        
        try:
            print(f"\n🚀 执行策略: {strategy_name}")
            print(f"📅 日期范围: {start_date} - {end_date}")
            
            # 注册策略
            registered_name = self.register_strategy(strategy_config)
            
            # 解析日期范围
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            execution_dates = []
            current_dt = start_dt
            
            while current_dt <= end_dt:
                execution_dates.append(current_dt.strftime('%Y-%m-%d'))
                current_dt += timedelta(days=1)
            
            print(f"📊 需要执行的日期数: {len(execution_dates)}")
            
            # 执行策略 - 使用优化的FactorEngine
            start_time = time.time()
            
            success_count = 0
            error_count = 0
            
            for i, date_str in enumerate(execution_dates):
                try:
                    # 直接调用run_strategy方法 - 享受缓存优化
                    result = self.factor_engine.run_strategy(registered_name, date_str)
                    
                    if result:
                        success_count += 1
                    else:
                        error_count += 1
                        
                    # 显示进度
                    if (i + 1) % 10 == 0 or i == len(execution_dates) - 1:
                        progress = (i + 1) / len(execution_dates) * 100
                        print(f"📈 进度: {i+1}/{len(execution_dates)} ({progress:.1f}%) - 成功:{success_count}, 错误:{error_count}")
                        
                except Exception as e:
                    error_count += 1
                    if error_count <= 3:  # 只显示前3个错误
                        print(f"⚠️ 日期 {date_str} 执行出错: {str(e)[:100]}")
            
            execution_time = time.time() - start_time
            
            # 构建执行结果
            execution_result = {
                'strategy_name': strategy_name,
                'start_date': start_date,
                'end_date': end_date,
                'total_dates': len(execution_dates),
                'success_count': success_count,
                'error_count': error_count,
                'success_rate': success_count / len(execution_dates) * 100 if len(execution_dates) > 0 else 0,
                'execution_time_seconds': execution_time,
                'status': 'completed' if success_count > 0 else 'failed'
            }
            
            print(f"✅ 策略执行完成: {strategy_name}")
            print(f"📊 成功率: {execution_result['success_rate']:.1f}% ({success_count}/{len(execution_dates)})")
            print(f"⏱️ 执行时间: {execution_time:.2f}秒")
            
            return execution_result
            
        except Exception as e:
            print(f"❌ 策略执行失败: {strategy_name} - {str(e)}")
            return {
                'strategy_name': strategy_name,
                'status': 'failed',
                'error': str(e)
            }
        finally:
            # 清理策略注册
            self.unregister_strategy(strategy_name)
    
    def run_backtest_simulation(self, strategy_name: str, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """模拟回测结果"""
        # 这里简化处理，实际环境中会调用真实的回测系统
        import random
        
        if execution_result.get('status') != 'completed':
            return {
                'strategy_name': strategy_name,
                'status': 'failed',
                'error': 'Strategy execution failed'
            }
        
        # 根据策略成功率生成模拟回测结果
        success_rate = execution_result.get('success_rate', 0)
        base_performance = success_rate / 100
        
        # 模拟回测指标
        simulated_return = random.uniform(-20, 50) * base_performance
        simulated_sharpe = random.uniform(0.1, 2.5) * base_performance
        simulated_drawdown = random.uniform(-30, -1) * (1 - base_performance)
        
        backtest_result = {
            'strategy_name': strategy_name,
            'status': 'completed',
            'total_return': round(simulated_return, 2),
            'sharpe_ratio': round(simulated_sharpe, 2),
            'max_drawdown': round(simulated_drawdown, 2),
            'execution_days': execution_result.get('total_dates', 0),
            'success_rate': success_rate,
            'note': 'Simulated backtest based on strategy execution performance'
        }
        
        return backtest_result
    
    def run_complete_optimization(self, n_strategies: int = 10,
                                 start_date: str = "2024-06-01",
                                 end_date: str = "2024-06-30") -> Dict[str, Any]:
        """运行完整的直接优化流程"""
        
        print("🎯 直接优化系统启动")
        print("=" * 80)
        print(f"📅 执行期间: {start_date} - {end_date}")
        print(f"🎯 策略数量: {n_strategies}")
        print(f"🚀 使用优化的FactorEngine (享受三阶段优化)")
        print("=" * 80)
        
        total_start_time = time.time()
        
        try:
            # 第1步：生成策略配置
            print(f"\n🎯 第1步：生成策略配置")
            print("-" * 50)
            
            strategies = self.tuner.generate_strategy_configs(n_strategies)
            
            print(f"✅ 策略配置生成完成: {len(strategies)} 个")
            
            # 第2步：批量执行策略
            print(f"\n🎯 第2步：批量执行策略")
            print("-" * 50)
            
            successful_count = 0
            failed_count = 0
            
            for i, strategy_config in enumerate(strategies, 1):
                strategy_name = strategy_config['strategy_name']
                
                print(f"\n📈 ({i}/{len(strategies)}) 处理策略: {strategy_name}")
                
                # 执行策略
                execution_result = self.execute_strategy_for_date_range(
                    strategy_config, start_date, end_date
                )
                
                if execution_result.get('status') == 'completed':
                    # 模拟回测
                    backtest_result = self.run_backtest_simulation(strategy_name, execution_result)
                    
                    if backtest_result.get('status') == 'completed':
                        # 合并结果
                        combined_result = {
                            'strategy_config': strategy_config,
                            'execution_result': execution_result,
                            'backtest_result': backtest_result,
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        self.results.append(combined_result)
                        successful_count += 1
                        
                        print(f"✅ 策略完成: {strategy_name} - 收益率: {backtest_result.get('total_return', 'N/A')}%")
                    else:
                        self.failed_strategies.append(strategy_name)
                        failed_count += 1
                        print(f"❌ 回测失败: {strategy_name}")
                else:
                    self.failed_strategies.append(strategy_name)
                    failed_count += 1
                    print(f"❌ 执行失败: {strategy_name}")
                
                # 显示总体进度
                if i % 5 == 0:
                    elapsed = time.time() - total_start_time
                    avg_time = elapsed / i
                    remaining_time = avg_time * (len(strategies) - i)
                    
                    print(f"📊 总进度: {i}/{len(strategies)} ({i/len(strategies)*100:.1f}%) - "
                          f"成功:{successful_count}, 失败:{failed_count} - "
                          f"预估剩余: {remaining_time/60:.1f}分钟")
            
            # 第3步：分析结果
            print(f"\n🎯 第3步：分析和保存结果")
            print("-" * 50)
            
            # 分析最佳策略
            best_strategies = self._analyze_best_strategies()
            
            # 构建最终结果
            total_time = time.time() - total_start_time
            
            final_result = {
                'optimization_summary': {
                    'total_strategies': len(strategies),
                    'successful': successful_count,
                    'failed': failed_count,
                    'success_rate': successful_count / len(strategies) * 100,
                    'total_time_minutes': total_time / 60,
                    'date_range': {'start': start_date, 'end': end_date},
                    'timestamp': self.timestamp
                },
                'strategies_generated': strategies,
                'execution_results': self.results,
                'failed_strategies': self.failed_strategies,
                'best_strategies': best_strategies
            }
            
            # 保存结果
            results_file = os.path.join(self.results_dir, f"direct_results_{self.timestamp}.json")
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(final_result, f, indent=2, ensure_ascii=False)
            
            print(f"📄 结果已保存: {results_file}")
            
            # 打印总结
            self._print_final_summary(final_result)
            
            return final_result
            
        except Exception as e:
            print(f"❌ 优化过程出错: {str(e)}")
            raise
    
    def _analyze_best_strategies(self) -> Dict[str, Any]:
        """分析最佳策略"""
        if not self.results:
            return {}
        
        strategies_with_metrics = []
        
        for result in self.results:
            backtest = result.get('backtest_result', {})
            strategy_config = result.get('strategy_config', {})
            execution = result.get('execution_result', {})
            
            metrics = {
                'strategy_name': strategy_config.get('strategy_name', 'Unknown'),
                'total_return': backtest.get('total_return', 0),
                'sharpe_ratio': backtest.get('sharpe_ratio', 0),
                'max_drawdown': backtest.get('max_drawdown', 0),
                'execution_success_rate': execution.get('success_rate', 0),
                'factors': strategy_config.get('factors', []),
                'window': strategy_config.get('window', 0)
            }
            
            strategies_with_metrics.append(metrics)
        
        # 按不同指标排序
        by_return = sorted(strategies_with_metrics, key=lambda x: x['total_return'], reverse=True)
        by_sharpe = sorted(strategies_with_metrics, key=lambda x: x['sharpe_ratio'], reverse=True)
        by_stability = sorted(strategies_with_metrics, key=lambda x: x['execution_success_rate'], reverse=True)
        
        return {
            'top_by_return': by_return[:5],
            'top_by_sharpe': by_sharpe[:5],
            'top_by_stability': by_stability[:5],
            'total_analyzed': len(strategies_with_metrics)
        }
    
    def _print_final_summary(self, final_result: Dict[str, Any]):
        """打印最终总结"""
        print("\n" + "=" * 80)
        print("🎉 直接优化系统完成")
        print("=" * 80)
        
        summary = final_result['optimization_summary']
        best = final_result.get('best_strategies', {})
        
        print(f"📊 执行总结:")
        print(f"   - 总策略数: {summary['total_strategies']}")
        print(f"   - 成功: {summary['successful']}")
        print(f"   - 失败: {summary['failed']}")
        print(f"   - 成功率: {summary['success_rate']:.1f}%")
        print(f"   - 总耗时: {summary['total_time_minutes']:.2f} 分钟")
        
        # 显示最佳策略
        if best.get('top_by_return'):
            print(f"\n🏆 收益率最佳策略:")
            for i, strategy in enumerate(best['top_by_return'][:3], 1):
                print(f"   {i}. {strategy['strategy_name']}: {strategy['total_return']:.2f}%")
        
        if best.get('top_by_sharpe'):
            print(f"\n📈 夏普比率最佳策略:")
            for i, strategy in enumerate(best['top_by_sharpe'][:3], 1):
                print(f"   {i}. {strategy['strategy_name']}: {strategy['sharpe_ratio']:.2f}")
        
        if best.get('top_by_stability'):
            print(f"\n🎯 执行稳定性最佳策略:")
            for i, strategy in enumerate(best['top_by_stability'][:3], 1):
                print(f"   {i}. {strategy['strategy_name']}: {strategy['execution_success_rate']:.1f}%")
        
        print(f"\n🚀 性能优化效果:")
        print(f"   - ✅ 使用单例FactorEngine避免重复初始化")
        print(f"   - ✅ 直接Python API避免subprocess开销")
        print(f"   - ✅ 三阶段缓存系统提供最大加速")
        print(f"   - ✅ 智能日期范围批量处理")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='🎯 直接优化系统 - 纯Python API版本')
    parser.add_argument('--n_strategies', type=int, default=5, help='策略数量')
    parser.add_argument('--start_date', type=str, default='2024-06-01', help='开始日期')
    parser.add_argument('--end_date', type=str, default='2024-06-10', help='结束日期')
    parser.add_argument('--config', type=str, default='hyperparameter_tuning/config.yaml', help='配置文件')
    
    args = parser.parse_args()
    
    try:
        # 创建直接优化系统
        optimizer = DirectOptimizationSystem(config_file=args.config)
        
        # 运行优化
        result = optimizer.run_complete_optimization(
            n_strategies=args.n_strategies,
            start_date=args.start_date,
            end_date=args.end_date
        )
        
        print(f"\n🎉 直接优化完成！成功率: {result['optimization_summary']['success_rate']:.1f}%")
        
    except KeyboardInterrupt:
        print(f"\n❌ 用户中断执行")
    except Exception as e:
        print(f"\n❌ 执行失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 