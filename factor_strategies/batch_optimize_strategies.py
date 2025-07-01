#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 批量策略执行器
使用优化的系统执行大量策略配置
"""

import os
import sys
import json
import subprocess
import time
from datetime import datetime
from typing import Dict, Any, List
import argparse

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

class BatchStrategyExecutor:
    """批量策略执行器"""
    
    def __init__(self):
        self.project_root = project_root
        self.results = []
        self.failed_strategies = []
        
    def create_temp_strategy_config(self, strategy_config: Dict[str, Any], temp_dir: str) -> str:
        """创建临时策略配置文件"""
        os.makedirs(temp_dir, exist_ok=True)
        
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
            strategy_name: {
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
        }
        
        # 创建临时配置文件
        temp_config_file = os.path.join(temp_dir, f"{strategy_name}_config.json")
        with open(temp_config_file, 'w', encoding='utf-8') as f:
            json.dump(factor_strategy, f, indent=2, ensure_ascii=False)
        
        return temp_config_file
    
    def run_factor_strategy(self, strategy_config: Dict[str, Any], start_date: str, end_date: str, temp_dir: str) -> bool:
        """运行因子策略"""
        strategy_name = strategy_config['strategy_name']
        
        try:
            print(f"\n🚀 执行因子策略: {strategy_name}")
            print(f"📅 日期范围: {start_date} - {end_date}")
            
            # 注册策略到主配置
            registered_name = self._register_strategy_to_main_config(strategy_config)
            
            # 构建命令 - 使用优化的run_factor_strategies.py
            cmd = [
                sys.executable,
                os.path.join(self.project_root, 'factor_strategies', 'run_factor_strategies.py'),
                '--start_date', start_date,
                '--end_date', end_date,
                '--strategy', registered_name,
                '--auto',
                '--sequential'  # 使用串行模式确保缓存效果最佳
            ]
            
            # 执行命令
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                cwd=self.project_root,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                print(f"✅ 因子策略执行成功: {strategy_name}")
                
                # 提取性能统计
                output = result.stdout
                if '缓存' in output and '命中率' in output:
                    print(f"💾 缓存系统正常工作")
                    
                return True
            else:
                print(f"❌ 因子策略执行失败: {strategy_name}")
                print(f"错误信息: {result.stderr[:200]}...")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"⏰ 因子策略执行超时: {strategy_name}")
            return False
        except Exception as e:
            print(f"❌ 因子策略执行异常: {strategy_name} - {str(e)}")
            return False
        finally:
            # 清理注册的策略
            self._unregister_strategy_from_main_config(strategy_name)
    
    def _register_strategy_to_main_config(self, strategy_config: Dict[str, Any]) -> str:
        """将策略注册到主配置文件"""
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
        try:
            sys.path.append(os.path.join(self.project_root, 'factor_strategies'))
            from factor_strategy_config import FACTOR_STRATEGIES
            FACTOR_STRATEGIES[strategy_name] = factor_strategy
            print(f"📝 策略已注册: {strategy_name}")
            return strategy_name
        except Exception as e:
            print(f"⚠️ 策略注册失败: {str(e)}")
            return strategy_name
    
    def _unregister_strategy_from_main_config(self, strategy_name: str):
        """从主配置中移除策略"""
        try:
            from factor_strategy_config import FACTOR_STRATEGIES
            if strategy_name in FACTOR_STRATEGIES:
                del FACTOR_STRATEGIES[strategy_name]
                print(f"🧹 策略已清理: {strategy_name}")
        except Exception as e:
            print(f"⚠️ 策略清理失败: {str(e)}")
    
    def run_backtest(self, strategy_name: str, start_date: str, end_date: str, 
                    initial_capital: int = 10000, position_size: float = 0.25,
                    fee_rate: float = 0.001, max_positions: int = 4,
                    entry_top_n: int = 4, exit_threshold: int = 10) -> Dict[str, Any]:
        """运行回测"""
        try:
            print(f"📊 执行回测: {strategy_name}")
            
            # 构建命令
            cmd = [
                sys.executable,
                os.path.join(self.project_root, 'backtest_v5.py'),
                strategy_name,
                start_date,
                end_date,
                str(initial_capital),
                str(position_size),
                str(fee_rate),
                str(max_positions),
                str(entry_top_n),
                str(exit_threshold)
            ]
            
            # 执行回测
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=120  # 2分钟超时
            )
            
            if result.returncode == 0:
                print(f"✅ 回测执行成功: {strategy_name}")
                
                # 解析回测结果
                output = result.stdout
                backtest_result = self._parse_backtest_output(output, strategy_name)
                return backtest_result
            else:
                print(f"❌ 回测执行失败: {strategy_name}")
                print(f"错误信息: {result.stderr[:200]}...")
                return None
                
        except subprocess.TimeoutExpired:
            print(f"⏰ 回测执行超时: {strategy_name}")
            return None
        except Exception as e:
            print(f"❌ 回测执行异常: {strategy_name} - {str(e)}")
            return None
    
    def _parse_backtest_output(self, output: str, strategy_name: str) -> Dict[str, Any]:
        """解析回测输出结果"""
        lines = output.split('\n')
        
        result = {
            'strategy_name': strategy_name,
            'status': 'completed',
            'raw_output': output,
            'timestamp': datetime.now().isoformat()
        }
        
        # 尝试提取关键指标
        for line in lines:
            if '总收益率' in line or 'Total Return' in line:
                try:
                    import re
                    numbers = re.findall(r'-?\d+\.?\d*', line)
                    if numbers:
                        result['total_return'] = float(numbers[-1])
                except:
                    pass
            elif '最大回撤' in line or 'Max Drawdown' in line:
                try:
                    import re
                    numbers = re.findall(r'-?\d+\.?\d*', line)
                    if numbers:
                        result['max_drawdown'] = float(numbers[-1])
                except:
                    pass
            elif '夏普比率' in line or 'Sharpe Ratio' in line:
                try:
                    import re
                    numbers = re.findall(r'-?\d+\.?\d*', line)
                    if numbers:
                        result['sharpe_ratio'] = float(numbers[-1])
                except:
                    pass
        
        return result
    
    def batch_execute(self, strategies: List[Dict[str, Any]], 
                     start_date: str, end_date: str,
                     temp_dir: str = "temp_strategies",
                     **backtest_params) -> Dict[str, Any]:
        """批量执行策略"""
        print("\n" + "=" * 80)
        print("🚀 批量策略执行启动")
        print("=" * 80)
        
        start_time = time.time()
        
        successful_count = 0
        failed_count = 0
        
        # 创建临时目录
        temp_path = os.path.join(self.project_root, temp_dir)
        os.makedirs(temp_path, exist_ok=True)
        
        try:
            for i, strategy_config in enumerate(strategies, 1):
                strategy_name = strategy_config['strategy_name']
                
                print(f"\n📈 ({i}/{len(strategies)}) 处理策略: {strategy_name}")
                
                # 执行因子策略
                factor_success = self.run_factor_strategy(strategy_config, start_date, end_date, temp_path)
                
                if factor_success:
                    # 执行回测
                    backtest_result = self.run_backtest(strategy_name, start_date, end_date, **backtest_params)
                    
                    if backtest_result:
                        # 合并结果
                        combined_result = {
                            'strategy_config': strategy_config,
                            'backtest_result': backtest_result,
                            'execution_time': datetime.now().isoformat()
                        }
                        
                        self.results.append(combined_result)
                        successful_count += 1
                        print(f"✅ 策略完成: {strategy_name}")
                    else:
                        self.failed_strategies.append(strategy_name)
                        failed_count += 1
                        print(f"❌ 回测失败: {strategy_name}")
                else:
                    self.failed_strategies.append(strategy_name)
                    failed_count += 1
                    print(f"❌ 因子策略失败: {strategy_name}")
                
                # 显示进度
                if i % 5 == 0:
                    elapsed = time.time() - start_time
                    avg_time = elapsed / i
                    remaining_time = avg_time * (len(strategies) - i)
                    
                    print(f"📊 进度: {i}/{len(strategies)} ({i/len(strategies)*100:.1f}%) - "
                          f"成功:{successful_count}, 失败:{failed_count} - "
                          f"预估剩余: {remaining_time/60:.1f}分钟")
            
            # 生成总结
            end_time = time.time()
            execution_time = end_time - start_time
            
            summary = {
                'total_strategies': len(strategies),
                'successful': successful_count,
                'failed': failed_count,
                'success_rate': successful_count / len(strategies) * 100 if len(strategies) > 0 else 0,
                'execution_time_minutes': execution_time / 60,
                'results': self.results,
                'failed_strategies': self.failed_strategies
            }
            
            self._print_summary(summary)
            
            return summary
            
        finally:
            # 清理临时文件
            self._cleanup_temp_files(temp_path)
    
    def _cleanup_temp_files(self, temp_path: str):
        """清理临时文件"""
        try:
            import shutil
            if os.path.exists(temp_path):
                shutil.rmtree(temp_path)
                print(f"🧹 清理临时文件: {temp_path}")
        except Exception as e:
            print(f"⚠️ 清理临时文件时出错: {str(e)}")
    
    def _print_summary(self, summary: Dict[str, Any]):
        """打印执行总结"""
        print("\n" + "=" * 80)
        print("🎯 批量执行完成")
        print("=" * 80)
        
        print(f"📊 执行统计:")
        print(f"   - 总策略数: {summary['total_strategies']}")
        print(f"   - 成功: {summary['successful']}")
        print(f"   - 失败: {summary['failed']}")
        print(f"   - 成功率: {summary['success_rate']:.1f}%")
        print(f"   - 总耗时: {summary['execution_time_minutes']:.1f} 分钟")
        
        if summary['successful'] > 0:
            print(f"\n🏆 前5个成功的策略:")
            for i, result in enumerate(summary['results'][:5], 1):
                strategy_name = result['strategy_config']['strategy_name']
                backtest = result['backtest_result']
                total_return = backtest.get('total_return', 'N/A')
                print(f"   {i}. {strategy_name}: 收益率 {total_return}")
        
        if summary['failed'] > 0:
            print(f"\n❌ 失败的策略 (前5个):")
            for i, strategy_name in enumerate(summary['failed_strategies'][:5], 1):
                print(f"   {i}. {strategy_name}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='🚀 批量策略执行器')
    parser.add_argument('--strategies_file', type=str, required=True, help='策略配置文件 (JSON)')
    parser.add_argument('--start_date', type=str, default='2024-01-01', help='开始日期')
    parser.add_argument('--end_date', type=str, default='2025-06-20', help='结束日期')
    parser.add_argument('--initial_capital', type=int, default=10000, help='初始资金')
    parser.add_argument('--position_size', type=float, default=0.25, help='仓位大小')
    parser.add_argument('--fee_rate', type=float, default=0.001, help='手续费率')
    parser.add_argument('--max_positions', type=int, default=4, help='最大持仓数')
    parser.add_argument('--entry_top_n', type=int, default=4, help='入场前N名')
    parser.add_argument('--exit_threshold', type=int, default=10, help='出场阈值')
    
    args = parser.parse_args()
    
    try:
        # 加载策略配置
        if not os.path.exists(args.strategies_file):
            raise FileNotFoundError(f"策略配置文件不存在: {args.strategies_file}")
        
        with open(args.strategies_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        strategies = data.get('strategies', [])
        if not strategies:
            raise ValueError("策略配置文件中没有找到策略")
        
        print(f"📄 加载了 {len(strategies)} 个策略配置")
        
        # 创建执行器
        executor = BatchStrategyExecutor()
        
        # 回测参数
        backtest_params = {
            'initial_capital': args.initial_capital,
            'position_size': args.position_size,
            'fee_rate': args.fee_rate,
            'max_positions': args.max_positions,
            'entry_top_n': args.entry_top_n,
            'exit_threshold': args.exit_threshold
        }
        
        # 批量执行
        summary = executor.batch_execute(
            strategies, 
            args.start_date, 
            args.end_date,
            **backtest_params
        )
        
        # 保存结果
        results_file = f"batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 结果已保存到: {results_file}")
        print(f"🎉 批量执行完成！成功率: {summary['success_rate']:.1f}%")
        
    except KeyboardInterrupt:
        print(f"\n❌ 用户中断执行")
    except Exception as e:
        print(f"\n❌ 执行失败: {str(e)}")
        raise


if __name__ == "__main__":
    main() 