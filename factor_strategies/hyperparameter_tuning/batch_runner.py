#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量執行器
負責批量運行策略回測並收集結果
"""

import os
import sys
import json
import time
import subprocess
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# 暫時註釋掉外部模組導入，使用模擬功能
# sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# from factor_strategies.run_factor_strategies import main as run_factor_strategy
# from backtest_v5 import FundingRateBacktest


class BatchRunner:
    """批量執行器"""
    
    def __init__(self, config: Dict[str, Any], output_dir: str):
        """
        初始化批量執行器
        :param config: 配置字典
        :param output_dir: 輸出目錄
        """
        self.config = config
        self.output_dir = output_dir
        self.backtest_config = config['backtest']
        self.execution_config = config['execution']
        
        # 設置日誌
        self._setup_logging()
        
        # 結果存儲
        self.results = []
        self.failed_strategies = []
        
    def _setup_logging(self):
        """設置日誌"""
        log_dir = os.path.join(self.output_dir, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'batch_execution_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
    
    def run_batch_backtest(self, strategy_configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        批量運行回測
        :param strategy_configs: 策略配置列表
        :return: 執行結果統計
        """
        total_strategies = len(strategy_configs)
        self.logger.info(f"🚀 開始批量回測，共 {total_strategies} 個策略")
        
        start_time = time.time()
        
        # 並行執行
        max_workers = self.execution_config.get('max_parallel_jobs', 4)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任務
            future_to_strategy = {
                executor.submit(self._run_single_strategy, strategy_config): strategy_config
                for strategy_config in strategy_configs
            }
            
            # 收集結果
            completed = 0
            for future in as_completed(future_to_strategy):
                strategy_config = future_to_strategy[future]
                completed += 1
                
                try:
                    result = future.result()
                    if result:
                        self.results.append(result)
                        self.logger.info(f"✅ ({completed}/{total_strategies}) 策略 {strategy_config['strategy_id']} 完成")
                    else:
                        self.failed_strategies.append(strategy_config['strategy_id'])
                        self.logger.error(f"❌ ({completed}/{total_strategies}) 策略 {strategy_config['strategy_id']} 失敗")
                        
                except Exception as e:
                    self.failed_strategies.append(strategy_config['strategy_id'])
                    self.logger.error(f"❌ ({completed}/{total_strategies}) 策略 {strategy_config['strategy_id']} 異常: {str(e)}")
                
                # 顯示進度
                if completed % 10 == 0:
                    progress = (completed / total_strategies) * 100
                    elapsed_time = time.time() - start_time
                    avg_time_per_strategy = elapsed_time / completed
                    estimated_remaining = avg_time_per_strategy * (total_strategies - completed)
                    
                    self.logger.info(f"📊 進度: {completed}/{total_strategies} ({progress:.1f}%) - "
                                   f"平均耗時: {avg_time_per_strategy:.1f}s - "
                                   f"預估剩餘: {estimated_remaining/60:.1f}分鐘")
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # 統計結果
        execution_stats = {
            'total_strategies': total_strategies,
            'successful': len(self.results),
            'failed': len(self.failed_strategies),
            'success_rate': len(self.results) / total_strategies * 100,
            'execution_time_seconds': execution_time,
            'execution_time_minutes': execution_time / 60,
            'average_time_per_strategy': execution_time / total_strategies,
            'failed_strategy_ids': self.failed_strategies
        }
        
        self.logger.info(f"🎯 批量回測完成！")
        self.logger.info(f"   - 總策略數: {total_strategies}")
        self.logger.info(f"   - 成功: {len(self.results)}")
        self.logger.info(f"   - 失敗: {len(self.failed_strategies)}")
        self.logger.info(f"   - 成功率: {execution_stats['success_rate']:.1f}%")
        self.logger.info(f"   - 總耗時: {execution_time/60:.1f} 分鐘")
        
        return execution_stats
    
    def _run_single_strategy(self, strategy_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        運行單個策略
        :param strategy_config: 策略配置
        :return: 策略結果
        """
        strategy_id = strategy_config['strategy_id']
        
        try:
            # 第1步：運行因子策略生成排行榜
            ranking_result = self._run_factor_strategy(strategy_config)
            if not ranking_result:
                self.logger.error(f"因子策略運行失敗: {strategy_id}")
                return None
            
            # 第2步：運行回測
            backtest_result = self._run_backtest(strategy_id, ranking_result)
            if not backtest_result:
                self.logger.error(f"回測運行失敗: {strategy_id}")
                return None
            
            # 第3步：合併結果
            combined_result = {
                'strategy_id': strategy_id,
                'strategy_config': strategy_config,
                'ranking_result': ranking_result,
                'backtest_result': backtest_result,
                'execution_time': datetime.now().isoformat()
            }
            
            # 第4步：保存中間結果（可選）
            if self.execution_config.get('save_intermediate_results', False):
                self._save_intermediate_result(combined_result)
            
            return combined_result
            
        except Exception as e:
            self.logger.error(f"策略 {strategy_id} 執行異常: {str(e)}")
            return None
    
    def _run_factor_strategy(self, strategy_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        運行因子策略
        :param strategy_config: 策略配置
        :return: 因子策略結果
        """
        try:
            # 創建臨時的因子策略配置文件
            temp_config_path = self._create_temp_factor_config(strategy_config)
            
            # 運行因子策略 - 調用現有的 run_factor_strategies
            # 這裡需要修改 run_factor_strategies 的調用方式
            # 暫時返回模擬結果
            
            ranking_result = {
                'strategy_name': strategy_config['strategy_name'],
                'generated_days': 100,  # 模擬數據
                'avg_daily_pairs': 50,
                'config_file': temp_config_path
            }
            
            return ranking_result
            
        except Exception as e:
            self.logger.error(f"因子策略運行失敗: {str(e)}")
            return None
    
    def _run_backtest(self, strategy_id: str, ranking_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        運行回測 (模擬版本)
        :param strategy_id: 策略ID
        :param ranking_result: 因子策略結果
        :return: 回測結果
        """
        try:
            # 模擬回測結果
            import random
            
            # 生成隨機但合理的回測結果
            annual_return = random.uniform(-0.1, 0.3)  # -10% 到 30%
            sharpe_ratio = random.uniform(0.5, 3.0)    # 0.5 到 3.0
            max_drawdown = random.uniform(0.05, 0.3)   # 5% 到 30%
            win_rate = random.uniform(0.4, 0.8)        # 40% 到 80%
            total_trades = random.randint(20, 100)     # 20 到 100 次交易
            
            backtest_summary = {
                'strategy_id': strategy_id,
                'roi': annual_return,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': -max_drawdown,  # 負數表示回撤
                'win_rate': win_rate,
                'total_return': annual_return * 1.5,  # 模擬總回報
                'total_trades': total_trades,
                'final_balance': self.backtest_config['initial_capital'] * (1 + annual_return * 1.5),
                'status': 'completed'
            }
            
            return backtest_summary
            
        except Exception as e:
            self.logger.error(f"回測運行失敗: {str(e)}")
            return None
    
    def _create_temp_factor_config(self, strategy_config: Dict[str, Any]) -> str:
        """
        創建臨時的因子策略配置文件
        :param strategy_config: 策略配置
        :return: 配置文件路徑
        """
        # 轉換格式以符合現有的 factor_strategy_config.py 格式
        factor_config = {
            'strategy_name': strategy_config['strategy_name'],
            'data_requirements': strategy_config['data_requirements'],
            'factors': []
        }
        
        # 轉換因子配置
        for factor_cfg in strategy_config['factors']:
            factor_config['factors'].append({
                'function': factor_cfg['function'],
                'params': {
                    'window': factor_cfg['window'],
                    'input_column': factor_cfg['input_column']
                }
            })
        
        factor_config['scoring'] = strategy_config['scoring']
        
        # 保存臨時配置文件
        temp_dir = os.path.join(self.output_dir, 'temp_configs')
        os.makedirs(temp_dir, exist_ok=True)
        
        temp_config_path = os.path.join(temp_dir, f"{strategy_config['strategy_id']}_config.json")
        
        with open(temp_config_path, 'w', encoding='utf-8') as f:
            json.dump(factor_config, f, indent=2, ensure_ascii=False)
        
        return temp_config_path
    
    def _save_intermediate_result(self, result: Dict[str, Any]):
        """保存中間結果"""
        results_dir = os.path.join(self.output_dir, 'intermediate_results')
        os.makedirs(results_dir, exist_ok=True)
        
        filename = f"{result['strategy_id']}_result.json"
        filepath = os.path.join(results_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    
    def save_final_results(self) -> str:
        """
        保存最終結果
        :return: 結果文件路徑
        """
        results_dir = os.path.join(self.output_dir, 'final_results')
        os.makedirs(results_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_file = os.path.join(results_dir, f'batch_results_{timestamp}.json')
        
        final_results = {
            'execution_summary': {
                'total_strategies': len(self.results) + len(self.failed_strategies),
                'successful_strategies': len(self.results),
                'failed_strategies': len(self.failed_strategies),
                'success_rate': len(self.results) / (len(self.results) + len(self.failed_strategies)) * 100 if (len(self.results) + len(self.failed_strategies)) > 0 else 0,
                'execution_timestamp': datetime.now().isoformat()
            },
            'results': self.results,
            'failed_strategy_ids': self.failed_strategies
        }
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(final_results, f, indent=2, ensure_ascii=False, default=str)
        
        self.logger.info(f"💾 最終結果已保存到: {results_file}")
        return results_file
    
    def get_results(self) -> List[Dict[str, Any]]:
        """獲取所有結果"""
        return self.results
    
    def get_failed_strategies(self) -> List[str]:
        """獲取失敗的策略ID列表"""
        return self.failed_strategies


def main():
    """測試函數"""
    import yaml
    from param_generator import ParameterGenerator
    
    # 載入配置
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 生成少量策略用於測試
    config['execution']['mode'] = 'sampling'
    config['execution']['n_strategies'] = 5  # 測試用少量策略
    
    generator = ParameterGenerator(config)
    strategies = generator.generate_sample_combinations(5)
    
    print(f"🧪 測試模式：運行 {len(strategies)} 個策略")
    
    # 創建批量執行器
    output_dir = 'results'
    runner = BatchRunner(config, output_dir)
    
    # 運行批量回測
    stats = runner.run_batch_backtest(strategies)
    
    print("\n📊 執行統計:")
    for key, value in stats.items():
        if key != 'failed_strategy_ids':
            print(f"  - {key}: {value}")
    
    # 保存結果
    results_file = runner.save_final_results()
    print(f"\n💾 結果已保存到: {results_file}")


if __name__ == "__main__":
    main() 