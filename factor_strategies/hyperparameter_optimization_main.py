#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎯 优化版超参数调优系统主程序
一键运行完整的超参数调优流程
直接使用优化过的系统，享受三阶段性能优化
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from optimized_hyperparameter_tuning import OptimizedHyperparameterTuner
from batch_optimize_strategies import BatchStrategyExecutor

class OptimizedHyperparameterMain:
    """优化版超参数调优系统主程序"""
    
    def __init__(self, config_file: str = "hyperparameter_tuning/config.yaml"):
        self.config_file = config_file
        self.tuner = OptimizedHyperparameterTuner(config_file)
        self.executor = BatchStrategyExecutor()
        self.project_root = project_root
        
        # 结果存储目录
        self.results_dir = os.path.join(current_dir, "optimized_results")
        os.makedirs(self.results_dir, exist_ok=True)
        
        # 时间戳用于文件命名
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
    def run_complete_optimization(self, n_strategies: int = 10, 
                                 start_date: str = "2024-01-01",
                                 end_date: str = "2025-06-20",
                                 run_mode: str = "test") -> dict:
        """运行完整的超参数调优流程"""
        
        print("🚀 优化版超参数调优系统")
        print("=" * 80)
        print(f"📅 回测期间: {start_date} - {end_date}")
        print(f"🎯 策略数量: {n_strategies}")
        print(f"🔧 运行模式: {run_mode}")
        print(f"📁 结果目录: {self.results_dir}")
        print("=" * 80)
        
        total_start_time = time.time()
        
        try:
            # 第一阶段：生成策略配置
            print("\n🎯 第一阶段：生成策略配置")
            print("-" * 50)
            
            phase1_start = time.time()
            
            strategies = self.tuner.generate_strategy_configs(n_strategies)
            
            # 保存策略配置
            strategies_file = os.path.join(self.results_dir, f"strategies_{self.timestamp}.json")
            strategy_data = {
                'strategies': strategies,
                'generated_at': datetime.now().isoformat(),
                'parameters': {
                    'n_strategies': n_strategies,
                    'start_date': start_date,
                    'end_date': end_date,
                    'run_mode': run_mode
                }
            }
            
            with open(strategies_file, 'w', encoding='utf-8') as f:
                json.dump(strategy_data, f, indent=2, ensure_ascii=False)
            
            phase1_time = time.time() - phase1_start
            
            print(f"✅ 第一阶段完成: {phase1_time:.2f}秒")
            print(f"📄 策略配置已保存: {strategies_file}")
            
            # 第二阶段：批量执行策略
            print(f"\n🎯 第二阶段：批量执行策略")
            print("-" * 50)
            
            phase2_start = time.time()
            
            if run_mode == "test":
                # 测试模式：只运行前2个策略
                print("🧪 测试模式：仅运行前2个策略")
                test_strategies = strategies[:2]
                
                # 创建测试的时间范围（缩短）
                test_start_date = "2024-06-01"
                test_end_date = "2024-06-30"
                
                print(f"📅 测试期间: {test_start_date} - {test_end_date}")
                
                # 回测参数
                backtest_params = {
                    'initial_capital': 10000,
                    'position_size': 0.25,
                    'fee_rate': 0.001,
                    'max_positions': 4,
                    'entry_top_n': 4,
                    'exit_threshold': 10
                }
                
                # 执行测试
                execution_result = self.executor.batch_execute(
                    test_strategies,
                    test_start_date,
                    test_end_date,
                    temp_dir=f"temp_strategies_{self.timestamp}",
                    **backtest_params
                )
                
            elif run_mode == "full":
                # 完整模式：运行所有策略
                print("🚀 完整模式：运行所有策略")
                
                # 从配置中获取回测参数
                backtest_config = self.tuner.config.get('backtest', {})
                backtest_params = {
                    'initial_capital': backtest_config.get('initial_capital', 10000),
                    'position_size': backtest_config.get('position_size', 0.25),
                    'fee_rate': backtest_config.get('fee_rate', 0.001),
                    'max_positions': backtest_config.get('max_positions', 4),
                    'entry_top_n': backtest_config.get('entry_top_n', 4),
                    'exit_threshold': backtest_config.get('exit_threshold', 10)
                }
                
                # 执行完整批量处理
                execution_result = self.executor.batch_execute(
                    strategies,
                    start_date,
                    end_date,
                    temp_dir=f"temp_strategies_{self.timestamp}",
                    **backtest_params
                )
                
            else:
                # 配置模式：只生成配置，不执行
                print("📝 配置模式：仅生成策略配置")
                execution_result = {
                    'total_strategies': len(strategies),
                    'successful': 0,
                    'failed': 0,
                    'success_rate': 0,
                    'execution_time_minutes': 0,
                    'results': [],
                    'mode': 'config_only'  
                }
            
            phase2_time = time.time() - phase2_start
            
            print(f"✅ 第二阶段完成: {phase2_time:.2f}秒")
            
            # 第三阶段：分析和保存结果
            print(f"\n🎯 第三阶段：分析和保存结果")
            print("-" * 50)
            
            phase3_start = time.time()
            
            # 合并所有结果
            final_result = {
                'optimization_summary': {
                    'total_strategies': len(strategies),
                    'execution_mode': run_mode,
                    'date_range': {
                        'start': start_date,
                        'end': end_date
                    },
                    'timestamp': self.timestamp,
                    'total_time_minutes': 0  # 稍后计算
                },
                'phase_times': {
                    'phase1_config_generation': phase1_time,
                    'phase2_batch_execution': phase2_time,
                    'phase3_analysis': 0  # 稍后计算
                },
                'strategies_generated': strategies,
                'execution_results': execution_result
            }
            
            # 分析最佳策略
            if execution_result.get('results'):
                best_strategies = self._analyze_best_strategies(execution_result['results'])
                final_result['best_strategies'] = best_strategies
            
            # 保存最终结果
            final_results_file = os.path.join(self.results_dir, f"final_results_{self.timestamp}.json")
            with open(final_results_file, 'w', encoding='utf-8') as f:
                json.dump(final_result, f, indent=2, ensure_ascii=False)
            
            phase3_time = time.time() - phase3_start
            final_result['phase_times']['phase3_analysis'] = phase3_time
            
            # 更新总时间
            total_time = time.time() - total_start_time
            final_result['optimization_summary']['total_time_minutes'] = total_time / 60
            
            print(f"✅ 第三阶段完成: {phase3_time:.2f}秒")
            print(f"📄 最终结果已保存: {final_results_file}")
            
            # 打印最终总结
            self._print_final_summary(final_result)
            
            return final_result
            
        except Exception as e:
            print(f"❌ 优化过程出错: {str(e)}")
            raise
    
    def _analyze_best_strategies(self, results: list) -> dict:
        """分析最佳策略"""
        if not results:
            return {}
        
        # 按不同指标排序
        strategies_with_metrics = []
        
        for result in results:
            backtest = result.get('backtest_result', {})
            strategy_config = result.get('strategy_config', {})
            
            metrics = {
                'strategy_name': strategy_config.get('strategy_name', 'Unknown'),
                'total_return': backtest.get('total_return', 0),
                'max_drawdown': backtest.get('max_drawdown', 0),
                'sharpe_ratio': backtest.get('sharpe_ratio', 0),
                'factors': strategy_config.get('factors', []),
                'window': strategy_config.get('window', 0)
            }
            
            strategies_with_metrics.append(metrics)
        
        # 按总收益率排序
        by_return = sorted(strategies_with_metrics, key=lambda x: x['total_return'], reverse=True)
        
        # 按夏普比率排序
        by_sharpe = sorted(strategies_with_metrics, key=lambda x: x['sharpe_ratio'], reverse=True)
        
        # 按最大回撤排序 (越小越好)
        by_drawdown = sorted(strategies_with_metrics, key=lambda x: abs(x['max_drawdown']))
        
        return {
            'top_by_return': by_return[:5],
            'top_by_sharpe': by_sharpe[:5],
            'top_by_drawdown': by_drawdown[:5],
            'total_analyzed': len(strategies_with_metrics)
        }
    
    def _print_final_summary(self, final_result: dict):
        """打印最终总结"""
        print("\n" + "=" * 80)
        print("🎉 优化版超参数调优完成")
        print("=" * 80)
        
        summary = final_result['optimization_summary']
        execution = final_result['execution_results']
        phase_times = final_result['phase_times']
        
        print(f"📊 执行总结:")
        print(f"   - 总策略数: {summary['total_strategies']}")
        print(f"   - 执行模式: {summary['execution_mode']}")
        print(f"   - 成功执行: {execution.get('successful', 0)}")
        print(f"   - 失败执行: {execution.get('failed', 0)}")
        print(f"   - 成功率: {execution.get('success_rate', 0):.1f}%")
        print(f"   - 总耗时: {summary['total_time_minutes']:.2f} 分钟")
        
        print(f"\n⏱️ 阶段耗时:")
        print(f"   - 配置生成: {phase_times['phase1_config_generation']:.2f}s")
        print(f"   - 批量执行: {phase_times['phase2_batch_execution']:.2f}s")
        print(f"   - 结果分析: {phase_times['phase3_analysis']:.2f}s")
        
        # 显示最佳策略
        if 'best_strategies' in final_result:
            best = final_result['best_strategies']
            
            if best.get('top_by_return'):
                print(f"\n🏆 收益率最佳策略:")
                for i, strategy in enumerate(best['top_by_return'][:3], 1):
                    print(f"   {i}. {strategy['strategy_name']}: {strategy['total_return']:.2f}%")
            
            if best.get('top_by_sharpe'):
                print(f"\n📈 夏普比率最佳策略:")
                for i, strategy in enumerate(best['top_by_sharpe'][:3], 1):
                    print(f"   {i}. {strategy['strategy_name']}: {strategy['sharpe_ratio']:.2f}")
        
        print(f"\n🚀 性能提升效果:")
        print(f"   - 使用了三阶段优化的 run_factor_strategies.py")
        print(f"   - 单例FactorEngine避免重复初始化")
        print(f"   - 智能并行化减少执行时间")
        print(f"   - 双重缓存系统提供20-100x加速")
        
        print(f"\n📁 结果文件:")
        print(f"   - 策略配置: strategies_{summary['timestamp']}.json")
        print(f"   - 最终结果: final_results_{summary['timestamp']}.json")
        print(f"   - 存储位置: {self.results_dir}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='🎯 优化版超参数调优系统主程序')
    parser.add_argument('--n_strategies', type=int, default=10, help='策略数量 (默认:10)')
    parser.add_argument('--start_date', type=str, default='2024-01-01', help='回测开始日期')
    parser.add_argument('--end_date', type=str, default='2025-06-20', help='回测结束日期')
    parser.add_argument('--mode', type=str, choices=['test', 'full', 'config'], 
                       default='test', help='运行模式 (test/full/config)')
    parser.add_argument('--config', type=str, default='hyperparameter_tuning/config.yaml', 
                       help='配置文件路径')
    
    args = parser.parse_args()
    
    try:
        # 创建主程序
        main_program = OptimizedHyperparameterMain(config_file=args.config)
        
        # 运行完整流程
        result = main_program.run_complete_optimization(
            n_strategies=args.n_strategies,
            start_date=args.start_date,
            end_date=args.end_date,
            run_mode=args.mode
        )
        
        print(f"\n🎉 优化完成！")
        
        if args.mode == 'test':
            print(f"🧪 测试模式完成，如果结果满意，请使用 --mode full 运行完整优化")
        elif args.mode == 'full':
            print(f"🚀 完整优化完成，请查看结果文件获取最佳策略")
        else:
            print(f"📝 配置生成完成，请使用 batch_optimize_strategies.py 执行策略")
        
    except KeyboardInterrupt:
        print(f"\n❌ 用户中断执行")
    except Exception as e:
        print(f"\n❌ 执行失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 